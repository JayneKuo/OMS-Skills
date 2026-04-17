# 需求文档：寻仓推荐引擎（warehouse_allocation）

## 1. 概述

寻仓推荐引擎根据订单目的地、SKU 库存、仓库能力和业务规则，输出最优发货仓推荐。
MVP 版本实现 P0 硬约束过滤（5 条）+ P2 多维评分排序（3 维）+ 单仓直发/多仓拆发方案。

### 1.1 行业对标

| 能力 | Shopify SOR | Manhattan DOM | ShipBob | 我们 MVP | 我们后续 |
|------|-------------|---------------|---------|----------|----------|
| 库存可用性过滤 | ✅ | ✅ | ✅ | ✅ | — |
| 最小拆单优先 | ✅（默认第一规则） | ✅ | ✅ | ✅ | — |
| 距离/区域就近 | ✅（直线距离） | ✅（承运商路由） | ✅（zone-based） | ✅（州级距离） | zipcode 级 |
| 成本优化 | ❌（无运费维度） | ✅（全成本） | ✅（zone 运费） | ✅（距离估算） | 真实运费 API |
| 仓容量均衡 | ❌ | ✅ | ✅ | ✅ | — |
| 仓优先级/分组 | ✅（ranked locations） | ✅ | ❌ | ❌ | ✅ |
| 自定义 metafield 规则 | ✅ | ✅ | ❌ | ❌ | ✅ |
| 温区匹配 | ❌ | ✅ | ❌ | ✅ | — |
| 多仓拆发 | ✅（自动） | ✅ | ✅ | ✅ | — |
| 调拨合发 | ❌ | ✅ | ❌ | ❌ | ✅ |
| 白盒解释 | ❌ | 部分 | ❌ | ✅ | — |
| 备选方案输出 | ❌ | ✅ | ❌ | ✅ | — |
| 稳定性/粘性规则 | ❌ | ✅ | ❌ | ❌ | ✅ |
| 库存老化/周转率优先 | ❌ | ✅ | ❌ | ❌ | ✅ |
| 在途库存/预期到货 | ❌ | ✅ | ✅ | ❌ | ✅ |
| 退货回流预判 | ❌ | ✅ | ❌ | ❌ | ✅ |
| 批量全局最优（蓄水池） | ❌ | ✅ | ❌ | ❌ | ✅ |
| Markdown 规避寻仓 | ❌ | ✅ | ❌ | ❌ | ✅ |
| 动态权重自适应 | ❌ | ✅ | ❌ | ❌ | ✅ |

## 2. MVP 功能需求

### 2.1 输入

- AC-1: 支持按订单号推荐（自动从 oms_query 获取订单详情、商品行、收货地址）
- AC-2: 支持直接传入 SKU 列表 + 数量 + 收货地址
- AC-3: 支持传入自定义评分权重（可选，有默认值）
- AC-4: 支持 allow_split 开关（默认 true）和 max_split_warehouses（默认 3）

### 2.2 P0 硬约束过滤（5 条）

| 编号 | 硬约束 | AC | 说明 |
|------|--------|-----|------|
| P0-1 | 仓状态可用 | AC-5 | is_active=true AND fulfillment_enabled=true |
| P0-2 | SKU 有库存 | AC-6 | 该仓的 onHandQty >= order_qty（MVP 用 onHandQty 近似 available_qty，因为 API 不返回 availableQty） |
| P0-3 | 配送国家匹配 | AC-7 | 仓库所在国家与收货地址国家一致（MVP 简化，后续加州级/区域级） |
| P0-4 | 温区匹配 | AC-8 | 如果订单商品有温区要求，仓库必须支持该温区（MVP：如果 API 无温区数据则跳过此检查） |
| P0-5 | 淘汰原因记录 | AC-9 | 每个被淘汰的仓必须记录淘汰原因（哪条硬约束不满足、缺哪个 SKU） |

库存口径说明：
- 理想口径：available_qty = physical_qty - reserved_qty - locked_qty - safety_stock
- MVP 口径：onHandQty（实物库存），因为 inventory/list API 只返回 onHandQty
- 降级标记：使用 onHandQty 时标记 `inventory_degraded=true`，置信度降为 medium

### 2.3 P2 多维评分排序（3 维）

- AC-10: 成本维度评分 — 基于仓到目的地的州级距离估算运费，距离越近成本越低，得分越高
- AC-11: 时效维度评分 — 基于同一距离模型，距离越近时效越快，得分越高
- AC-12: 容量维度评分 — 基于仓剩余容量占比（如果有 daily_capacity 和 current_load），容量越充裕得分越高；无容量数据时该维度得分为 1.0（不产生区分度）
- AC-13: 归一化方式为 min-max，映射到 [0,1]；当 max=min 时返回 1.0
- AC-14: 加权求和公式：Score = w_cost × S_cost + w_eta × S_eta + w_cap × S_cap
- AC-15: 默认权重：w_cost=0.40, w_eta=0.35, w_capacity=0.25（从 PRD 四维砍掉稳定性后重新分配，成本和时效占主导）

距离估算算法（MVP）：
- 使用美国州级中心点坐标查表，计算仓库州到目的地州的直线距离（km）
- 距离 → 成本映射：每 100km 约 $2 运费（粗略估算，仅用于排序）
- 距离 → 时效映射：每 500km 约 1 天（粗略估算）
- 同州：距离=0，成本=基础运费，时效=1 天

### 2.4 方案生成

- AC-16: 最小拆单优先 — 优先选择能单仓满足所有 SKU 的方案（对标 Shopify 第一规则）
- AC-17: 单仓直发 — 从 can_fulfill_all=true 的仓中选评分最高的
- AC-18: 多仓拆发 — 当无单仓可满足且 allow_split=true 时，枚举 2 仓、3 仓组合
- AC-19: 拆单惩罚 — 多仓方案的组合评分 = Σ(仓评分 × SKU 占比) - split_penalty × (仓数-1)，split_penalty 默认 0.10（评分空间内的惩罚）
- AC-20: SKU 分配策略 — 贪心：优先把 SKU 分到评分最高且有库存的仓
- AC-21: allow_split=false 时 — 如果没有单仓可满足，直接返回失败，不尝试拆发
- AC-22: 全部不可行时 — 返回失败，附带原因（所有仓的淘汰原因汇总）和建议（补货/调整规则）

### 2.5 输出

- AC-23: 推荐方案 — 仓库、SKU 分配、评分、评分明细（各维度得分）、推荐理由
- AC-24: 备选方案 — 输出 Top2/Top3 备选方案（如果有），标注与推荐方案的差异
- AC-25: 候选仓列表 — 通过 P0 的所有仓，含评分和排名
- AC-26: 淘汰仓列表 — 未通过 P0 的仓，含淘汰原因
- AC-27: 置信度 — high（数据完整）/ medium（库存用 onHandQty 近似或缺少容量数据）/ low（关键数据缺失）
- AC-28: 白盒解释 — 用业务语言说明：为什么选这个仓、为什么不选其他仓、拆单原因

### 2.6 数据来源

- AC-29: 仓库列表从 facility/v2/page 获取，映射为 Warehouse 模型
- AC-30: 库存从 inventory/list 获取，按 SKU+仓库聚合
- AC-31: 订单详情从 sale-order/{orderNo} 获取（order_no 模式）
- AC-32: 复用 oms_query_engine 的 API client，不重复认证

### 2.7 数据降级策略

| 缺失数据 | 降级策略 | 置信度影响 |
|----------|----------|-----------|
| availableQty 不可用 | 用 onHandQty 近似 | → medium |
| 仓库无容量数据 | 容量维度得分=1.0（不区分） | → medium |
| 仓库无坐标/州信息 | 距离=最大值，成本/时效得分=0 | → medium |
| 库存数据为空 | 该仓排除 | 不影响 |
| 订单无收货地址 | 阻断，返回错误 | — |
| 订单无商品行 | 阻断，返回错误 | — |

### 2.8 外部数据不可用的降级策略

以下数据在 PRD 中被引用，但当前 OMS/WMS 系统不提供对应 API，MVP 需要明确降级处理：

| 缺失数据 | PRD 用途 | MVP 降级策略 | 输出标记 |
|----------|----------|-------------|----------|
| 仓库排单/波次信息 | P1 截单时间判断、仓内处理时间估算 | 不检查截单时间，仓内处理时间用固定默认值（24h） | `cutoff_not_checked=true` |
| 仓库当日已接单量 / 日处理产能 | P1 仓容量检查、P2 容量评分 | 如果 API 返回了 daily_capacity/current_load 就用，否则容量维度得分=1.0 | `capacity_estimated=true` |
| 天气状况 | ETA 风险修正（f_weather） | 不叠加天气风险因子，ETA 使用基础估算值 | `weather_not_factored=true` |
| 物流拥堵指数 | ETA 风险修正（f_congestion） | 不叠加拥堵因子 | `congestion_not_factored=true` |
| 承运商准点率 | P2 稳定性评分、ETA 风险修正 | MVP 不含稳定性维度，不修正 ETA | — |
| 承运商揽收班次 | ETA 中的 T_handover 计算 | 交接时间用固定默认值（4h） | `handover_estimated=true` |
| 承运商余额 | 承运商可用性检查 | 不检查余额，假设充足 | `balance_not_checked=true` |
| 承运商实时运费 API | P2 成本评分 | 用距离线性估算替代 | `cost_estimated=true` |
| 承运商实时 ETA API | P2 时效评分 | 用距离线性估算替代 | `eta_estimated=true` |
| SKU 温区属性 | P0 温区匹配 | 如果 SKU 无温区标记，默认常温，跳过温区检查 | `temp_zone_defaulted=true` |
| SKU 危险品/超大件标记 | P0 合规/物理可发检查 | 跳过这两项检查 | — |
| 调拨通道信息 | 调拨合发方案 | MVP 不做调拨 | — |

这些降级标记会汇总到输出的 `data_degradation` 字段中，并影响最终置信度：
- 0 个降级标记 → confidence=high
- 1~3 个降级标记 → confidence=medium
- 4 个以上降级标记 → confidence=low

白盒解释中必须提及关键降级项，例如：
> "推荐从 Valley View 发货（置信度 medium）。注意：库存使用实物库存近似，未扣除预占和锁定；时效为距离估算，未考虑天气和物流拥堵因素。"

### 2.9 订单/SKU/仓库级数据缺失的降级策略

以下字段在 PRD 数据契约中定义为必填，但 OMS API 可能不返回或 MVP 不使用：

| 缺失数据 | PRD 用途 | MVP 降级策略 |
|----------|----------|-------------|
| customer_level | VIP/SVIP 权重偏好 | 默认普通客户，不调整权重 |
| promised_sla | P1 SLA 时效检查 | MVP 不检查 SLA，跳过 P1 |
| cogs（商品成本） | 毛利率计算 | MVP 不计算毛利率 |
| is_bundle / bundle_components | 组合商品必须同仓 | MVP 不检查组合商品约束，所有 SKU 独立处理 |
| is_gift | 赠品必须同包 | MVP 不检查赠品约束 |
| warehouse_type | 仓库类型优先级 | MVP 不区分仓库类型 |
| max_package_weight / dimension | 单包物理限制 | MVP 不检查（装箱引擎负责） |
| ops_cost / packaging_cost | 仓操费 + 包材费 | MVP 成本评分只用距离估算，不含仓操费 |
| inventory_snapshot_time | 库存新鲜度判断 | MVP 不检查库存新鲜度，假设数据实时 |
| 承运商 daily_capacity / current_load | 承运商产能检查 | MVP 不检查承运商产能 |

### 2.8 MCP 集成

- AC-33: 在 MCP server 中注册 warehouse_allocate tool
- AC-34: 参数：order_no（可选）、merchant_no、sku_list（可选 JSON）、country、state、allow_split、weights
- AC-35: 返回 AllocationResult 的 JSON

## 3. 非功能需求

- NF-1: 单次推荐响应时间 < 5s（含 API 调用）
- NF-2: 数据缺失时按降级策略处理，不阻断（除 AC-32 的阻断场景）
- NF-3: 所有推荐结论可追溯（白盒），每个决策点有理由
- NF-4: 输出格式符合 OUTPUT_POLICY 的推荐型模板（Level 2/3）

## 4. 后续迭代（不在 MVP 范围）

### 4.1 原 PRD 规划的后续能力
- P1 业务条件过滤（截单时间、SLA 时效、仓容量上限）
- P3 稳定性规则（同 SKU 粘性、切仓冷却期、最大切仓频率、容量均衡保护）
- 调拨合发方案（主仓覆盖率 + 调拨成本 + 调拨时效）
- 部分发货方案（有货先发 + 缺货登记）
- 仓优先级/分组（对标 Shopify ranked locations）
- 真实运费 API 接入（替代距离估算）
- 真实时效 API 接入
- zipcode 级距离计算（替代州级）
- 承运商可达性检查（P0-5）
- 合规限制检查（P0-7）

### 4.2 行业前沿能力（PRD 未覆盖，基于 2025-2026 行业调研补充）

| 能力 | 说明 | 行业参考 | 价值 |
|------|------|----------|------|
| 库存老化/周转率优先发货 | 优先从滞销仓发货，减少 markdown 损失。评分公式加入 SKU 在该仓的销售速度维度 | Manhattan DOM、Agentic AI sourcing | 减少库存积压和打折损失 |
| 在途库存/预期到货 | 纳入在途补货和预期到货量，扩大候选仓范围。如仓 A 明天到货 100 件，今天的订单可以等 | Manhattan、ShipBob | 减少因临时缺货导致的远仓发货 |
| 退货回流预判 | 分析 RMA 数据，预判即将退回的库存纳入可用库存计算 | Agentic AI sourcing | 提高库存利用率 |
| 批量订单全局最优 | 一批订单一起求解（蓄水池模式），避免所有订单涌向同一仓。PRD 的 PoolingWindowSeconds 就是这个概念 | Manhattan、学术界 | 仓网负载均衡，全局成本最优 |
| 历史分仓成功率 | 某仓对某 SKU 的历史分仓成功率（是否经常因库存不足被退回），作为稳定性评分维度 | 内部运营经验 | 减少分仓失败率 |
| 多目标帕累托最优 | 不用加权求和（单一评分），而是输出帕累托前沿（多个不可比的最优解），让用户在成本和时效之间自主选择 | 学术界、Manhattan | 避免权重设置的主观性 |
| Markdown 规避寻仓 | 分仓时考虑 SKU 在各仓的 sell-through velocity，优先从卖得慢的仓发货，避免该仓库存最终被打折清仓 | RTInsights Agentic AI 2026 | 直接提升毛利率 |
| 动态权重自适应 | 根据订单特征（品类、客户等级、大促期间）自动调整评分权重，而非固定默认值 | Manhattan、Shopify Plus | 不同场景自动优化 |
