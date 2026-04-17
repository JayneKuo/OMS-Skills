# Warehouse Allocation Skill — 寻仓推荐引擎

> v1.0 (2026-04-14): MVP 版本，规则解析 + P0 硬约束 + P2 评分 + 单仓/多仓/Backup 方案

## 定位

warehouse_allocation 是 OMS Agent 的寻仓推荐 Skill，消费 oms_query 的库存和仓库数据，
结合商户路由规则配置，执行寻源漏斗过滤和多维评分，输出最优发货仓推荐。

## 架构

```
WarehouseAllocationEngine（顶层编排器）
  ├── DataLoader            # 加载仓库/库存/订单/规则数据
  ├── RuleResolver          # 解析商户路由规则 → 引擎行为参数
  ├── P0Filter              # 硬约束过滤（受规则影响）
  │     ├── 仓状态检查
  │     ├── 库存匹配（可按规则跳过）
  │     ├── 国家匹配（US/USA 标准化）
  │     └── 温区匹配（可选）
  ├── P2Scorer              # 多维评分（权重可被规则覆盖）
  │     ├── DistanceCalculator（Haversine 州级距离）
  │     ├── CostEstimator
  │     ├── ETAEstimator
  │     └── CapacityScorer
  ├── PlanGenerator         # 方案生成
  │     ├── 单仓直发
  │     ├── 多仓拆发
  │     └── Backup 模式（库存不足走最高优先级仓）
  └── ResultBuilder         # 白盒解释 + 降级标记 + 置信度
```

## 支持的商户规则

| 规则 | 引擎行为 |
|------|----------|
| ONE_WAREHOUSE_BACKUP | 跳过库存硬约束，无库存时走最高优先级仓 |
| NO_SPLIT | 禁止拆单 |
| MINIMAL_SPLIT | 允许拆单 |
| CLOSEST_WAREHOUSE | 调整权重，时效优先（eta=0.60） |
| SPECIFY_WAREHOUSE | 指定仓（标记，MVP 不完全实现） |
| SKU_SPECIFY_WAREHOUSE | SKU 指定仓映射 |

## 数据来源

通过 oms_query_engine 的 API client 获取：
- 仓库列表：facility/v2/page
- 库存：inventory/list
- 订单详情：sale-order/{orderNo}
- 路由规则：routing/v2/rules

## MCP Tool

`warehouse_allocate(order_no, merchant_no, sku_list, country, state, allow_split)`

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
数据契约见 [references/数据契约.md](references/数据契约.md)。
