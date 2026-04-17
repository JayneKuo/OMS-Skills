# Cost Skill — 综合成本计算引擎

> v1.0: MVP 版本，Cost_total + Score + 容量惩罚 + 拆单惩罚 + 多方案排序

## 定位

cost 是 OMS Agent 的综合成本计算 Skill，将运费、仓操费、惩罚等成本项与时效指标
统一为可排序的综合评分，支持多方案对比。

## 架构

```
CostEngine（顶层编排器）
  ├── CostCalculator           # 综合成本计算
  │     ├── Freight_order      # 订单运费
  │     ├── Cost_warehouse     # 仓操费
  │     ├── Cost_transfer      # 调拨费
  │     ├── Penalty_split      # 拆单惩罚
  │     ├── Penalty_capacity   # 容量惩罚（4 梯度）
  │     └── Cost_risk          # 风险成本
  ├── ScoreCalculator          # 综合评分
  │     ├── Normalizer         # Min-Max 归一化
  │     └── WeightedScorer     # 加权评分
  └── PlanRanker               # 多方案排序
```

## 公式

### Cost_total
```
Cost_total = Freight_order + Cost_warehouse + Cost_transfer + Penalty_split + Penalty_capacity + Cost_risk
```

### Score
```
Score = w_cost × Normalize(Cost_total) + w_eta × Normalize(ETA) + w_ontime × OnTimeProbability + w_cap × Normalize(RemainCapacity)
```

默认权重：w_cost=0.40, w_eta=0.30, w_ontime=0.15, w_cap=0.15

## MCP Tools

- `cost_calculate(plans_json)` — 计算综合成本和评分

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
