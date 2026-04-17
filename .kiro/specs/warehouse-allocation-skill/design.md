# 设计文档：寻仓推荐引擎（allocation_engine）

## 1. 架构

```
WarehouseAllocationEngine（顶层编排器）
  ├── DataLoader            # 从 oms_query_engine 加载仓库/库存/订单数据
  ├── P0Filter              # 硬约束过滤（5 条）
  ├── P2Scorer              # 多维评分排序（3 维）
  │     ├── DistanceCalculator  # 州级距离计算（Haversine）
  │     ├── CostEstimator       # 距离→成本映射
  │     ├── ETAEstimator        # 距离→时效映射
  │     └── CapacityScorer      # 容量评分
  ├── PlanGenerator         # 方案生成（单仓/多仓）
  └── ResultBuilder         # 结果构建 + 白盒解释 + 降级标记
```

## 2. 数据模型

### 2.1 输入模型

```python
class AllocationRequest(BaseModel):
    order_no: str | None = None
    merchant_no: str = "LAN0000002"
    items: list[OrderItem] | None = None
    shipping_address: Address | None = None
    allow_split: bool = True
    max_split_warehouses: int = 3
    weights: ScoringWeights | None = None

class OrderItem(BaseModel):
    sku: str
    quantity: int
    weight: float | None = None  # kg

class Address(BaseModel):
    country: str
    state: str | None = None
    city: str | None = None
    zipcode: str | None = None

class ScoringWeights(BaseModel):
    cost: float = 0.40
    eta: float = 0.35
    capacity: float = 0.25
```

### 2.2 仓库模型（从 API 映射）

```python
class Warehouse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    country: str
    state: str | None = None
    city: str | None = None
    zipcode: str | None = None
    is_active: bool
    fulfillment_enabled: bool
    inventory_enabled: bool
    inventory: dict[str, int] = {}  # sku → onHandQty
    daily_capacity: int | None = None
    current_load: int | None = None
```

### 2.3 输出模型

```python
class AllocationResult(BaseModel):
    success: bool
    recommended_plan: FulfillmentPlan | None = None
    alternative_plans: list[FulfillmentPlan] = []  # Top2/Top3 备选
    candidate_warehouses: list[ScoredWarehouse] = []
    eliminated_warehouses: list[EliminatedWarehouse] = []
    confidence: str = "low"  # high/medium/low
    explanation: str = ""
    data_degradation: list[str] = []  # 降级标记列表
    error: str | None = None

class FulfillmentPlan(BaseModel):
    plan_type: str  # single_warehouse / multi_warehouse
    assignments: list[WarehouseAssignment]
    total_score: float
    split_penalty: float = 0.0
    recommendation_reason: str = ""

class WarehouseAssignment(BaseModel):
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    items: list[OrderItem]
    score: float
    score_breakdown: dict[str, float] = {}  # cost/eta/capacity 各维度得分
    estimated_cost: float | None = None
    estimated_days: float | None = None
    distance_km: float | None = None

class ScoredWarehouse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    score: float
    score_breakdown: dict[str, float] = {}
    can_fulfill_all: bool
    fulfillable_skus: list[str] = []
    missing_skus: list[str] = []

class EliminatedWarehouse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    reasons: list[str]  # 可能有多条淘汰原因
```

## 3. DataLoader 逻辑

```
1. 如果有 order_no:
   → 调用 sale-order/{orderNo} 获取订单详情
   → 提取 items（SKU + qty）和 shipping_address
   → 如果 request.items 也传了，以 request.items 为准

2. 调用 facility/v2/page 获取仓库列表
   → 映射为 Warehouse 模型
   → 提取 state/country/is_active/fulfillment_enabled

3. 调用 inventory/list 获取库存
   → 按 SKU + warehouse_id 聚合
   → 合并到 Warehouse.inventory
   → 标记 inventory_degraded=true（因为用 onHandQty）

4. 验证必要数据:
   → items 为空 → 阻断
   → shipping_address 为空 → 阻断
   → 仓库列表为空 → 返回失败
```

## 4. P0 硬约束过滤逻辑

```
对每个仓库 w，依次检查 5 条硬约束:

P0-1: 仓状态
  w.is_active == True AND w.fulfillment_enabled == True
  → 否则淘汰，原因: "仓库未启用" 或 "未开启履约功能"

P0-2: SKU 库存
  对订单中每个 SKU s:
    w.inventory.get(s.sku, 0) >= s.quantity
  → 记录每个缺货 SKU 和缺口数量
  → 如果全部满足 → can_fulfill_all=True
  → 如果部分满足 → fulfillable_skus=[...], missing_skus=[...]
  → 如果全部不满足 → 淘汰，原因: "所有 SKU 均无库存"

P0-3: 配送国家
  w.country == shipping_address.country（大小写不敏感）
  → 否则淘汰，原因: "不在配送范围（国家不匹配）"

P0-4: 温区匹配（可选）
  如果订单 items 有温区标记 AND 仓库有温区数据:
    检查仓库支持的温区是否覆盖订单所有温区
  → 否则淘汰，原因: "温区不匹配"
  → 如果无温区数据 → 跳过，标记 temp_zone_defaulted=true

P0-5: 淘汰原因记录
  每个被淘汰的仓记录所有不满足的硬约束
  → EliminatedWarehouse(reasons=["仓库未启用", "SKU CCC 缺货 5 件"])
```

## 5. P2 评分逻辑

### 5.1 距离计算

```python
# 美国 50 州 + DC 中心点坐标（硬编码）
US_STATE_COORDS = {
    "CA": (36.78, -119.42),
    "TX": (31.97, -99.90),
    "NY": (42.17, -74.95),
    "FL": (27.66, -81.52),
    # ... 全部 51 个
}

def haversine(lat1, lon1, lat2, lon2) -> float:
    """返回两点间大圆距离（km）"""

def get_distance(wh_state: str, dest_state: str) -> float:
    if wh_state == dest_state:
        return 0.0
    coord1 = US_STATE_COORDS.get(wh_state.upper())
    coord2 = US_STATE_COORDS.get(dest_state.upper())
    if not coord1 or not coord2:
        return 5000.0  # 最大距离
    return haversine(*coord1, *coord2)
```

### 5.2 成本和时效估算

```python
BASE_COST = 5.0        # 基础运费 $5
COST_PER_KM = 0.02     # 每 km $0.02
ETA_KM_PER_DAY = 500   # 每天 500km

def estimate_cost(distance_km: float) -> float:
    return BASE_COST + distance_km * COST_PER_KM

def estimate_days(distance_km: float) -> float:
    return max(1.0, distance_km / ETA_KM_PER_DAY)
```

### 5.3 归一化和评分

```python
def normalize(values: list[float], reverse: bool = False) -> list[float]:
    """min-max 归一化到 [0,1]。reverse=True 时越小越好。"""
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return [1.0] * len(values)
    normalized = [(v - min_v) / (max_v - min_v) for v in values]
    if reverse:
        normalized = [1.0 - n for n in normalized]
    return normalized

def score_warehouse(w, all_candidates, weights) -> float:
    S_cost = normalize(costs, reverse=True)[i]
    S_eta  = normalize(etas, reverse=True)[i]
    S_cap  = normalize(capacities, reverse=False)[i]  # 或 1.0 如果无数据
    return weights.cost * S_cost + weights.eta * S_eta + weights.capacity * S_cap
```

## 6. 方案生成逻辑

```
Step 1: 单仓直发
  candidates = [w for w in scored if w.can_fulfill_all]
  if candidates:
    ranked = sorted(candidates, key=score, reverse=True)
    recommended = ranked[0]  # Top1
    alternatives = ranked[1:3]  # Top2, Top3

Step 2: 多仓拆发（仅当 Step 1 无解且 allow_split=True）
  from itertools import combinations
  for n in [2, 3]:  # 最多 max_split_warehouses
    for combo in combinations(scored_warehouses, n):
      # 检查组合是否覆盖所有 SKU
      all_skus_covered = union(w.fulfillable_skus for w in combo) >= required_skus
      if all_skus_covered:
        # 贪心分配 SKU：优先分到评分最高的仓
        assignments = greedy_assign(combo, items)
        combo_score = sum(a.score * a.item_ratio for a in assignments) - SPLIT_PENALTY * (n-1)
        plans.append(plan)
  if plans:
    recommended = max(plans, key=score)
    alternatives = sorted(plans, key=score, reverse=True)[1:3]

Step 3: 无解
  if allow_split == False and no single warehouse:
    return failure("不允许拆单，且无单仓可满足所有 SKU")
  else:
    return failure("所有仓库组合均无法满足订单", suggestions=["补充库存", "调整拆单规则"])
```

### 6.1 贪心 SKU 分配

```
def greedy_assign(warehouses, items):
    # 按仓评分降序排列
    sorted_wh = sorted(warehouses, key=score, reverse=True)
    assignments = {wh.id: [] for wh in sorted_wh}
    remaining = list(items)

    for item in remaining:
        for wh in sorted_wh:
            if wh.inventory.get(item.sku, 0) >= item.quantity:
                assignments[wh.id].append(item)
                wh.inventory[item.sku] -= item.quantity
                break
    return assignments
```

## 7. 置信度计算

```
degradation_count = len(data_degradation)
if degradation_count == 0:
    confidence = "high"
elif degradation_count <= 3:
    confidence = "medium"
else:
    confidence = "low"
```

## 8. 白盒解释生成

```
模板（单仓直发）:
"推荐从 {仓库名}（{编码}）发货。
 库存满足：{SKU1} × {qty1}、{SKU2} × {qty2} 均有货。
 距离：距收货地 {目的州} 约 {距离}km，预估运费 ${成本}，预估 {天数} 天送达。
 综合评分 {分数}（成本 {成本分} + 时效 {时效分} + 容量 {容量分}）。
 {降级说明}"

模板（多仓拆发）:
"建议拆为 {N} 仓发货：
 仓 A（{编码}）发 {SKU1} × {qty1}，评分 {分数}
 仓 B（{编码}）发 {SKU2} × {qty2}，评分 {分数}
 拆单惩罚 -{惩罚分}
 综合评分 {总分}"

模板（失败）:
"无法推荐发货仓。
 {N} 个仓库被淘汰：
 - {仓A}：{原因}
 - {仓B}：{原因}
 建议：{补货/调整规则}"
```

## 9. 引擎代码路径

`.kiro/skills/warehouse-allocation/scripts/allocation_engine/`

## 10. Correctness Properties

| # | Property | 验证内容 |
|---|----------|----------|
| P1 | P0 过滤完整性 | 淘汰仓必须至少有一条淘汰原因 |
| P2 | 库存不超卖 | 推荐方案中每个仓分配的 SKU 数量 ≤ 该仓库存 |
| P3 | 评分归一化 | 所有维度得分 ∈ [0, 1] |
| P4 | 权重求和 | weights.cost + weights.eta + weights.capacity == 1.0 |
| P5 | 单仓优先 | 如果存在 can_fulfill_all 的仓，推荐方案必须是单仓 |
| P6 | 拆单上限 | 多仓方案的仓数 ≤ max_split_warehouses |
| P7 | SKU 完整覆盖 | 推荐方案覆盖订单中所有 SKU |
| P8 | allow_split 尊重 | allow_split=False 时不输出多仓方案 |
| P9 | 降级标记一致 | data_degradation 非空时 confidence ≠ "high" |
