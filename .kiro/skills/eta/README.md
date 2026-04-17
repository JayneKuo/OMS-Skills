# ETA Skill — 时效计算引擎

> v1.0: MVP 版本，8 组件 ETA + 三口径 + 风险修正 + 美国默认 transit time

## 定位

eta 是 OMS Agent 的时效计算 Skill，基于 8 组件 ETA 公式计算订单预估送达时间，
支持 P50/P75/P90 三个风险化口径，内置美国市场默认数据。

## 架构

```
ETAEngine（顶层编排器）
  ├── DefaultUSTransitProvider  # 美国市场默认 transit time 表
  │     ├── 州级距离分段         # 同州/邻州/跨区/远距
  │     └── 承运商服务级别       # Ground/Express/Priority
  ├── ComponentCalculator       # 8 组件计算
  │     ├── T_queue             # 排队等待
  │     ├── T_cutoff_wait       # 截单等待
  │     ├── T_process           # 仓内处理
  │     ├── T_handover          # 交接
  │     ├── T_transit           # 干线运输
  │     ├── T_last_mile         # 末端配送
  │     ├── T_weather           # 天气影响
  │     └── T_risk_buffer       # 风险缓冲
  ├── RiskAdjuster              # 风险修正
  │     ├── 天气风险
  │     ├── 拥堵风险
  │     └── 承运商风险
  ├── OnTimeProbCalculator      # 准时率计算
  └── ResultBuilder             # 结果构建 + 白盒解释
```

## ETA 公式

```
ETA_total = T_queue + T_cutoff_wait + T_process + T_handover + T_transit + T_last_mile + T_weather + T_risk_buffer
```

## 风险化口径

| 口径 | 百分位 | 用途 |
|------|--------|------|
| 乐观 | P50 | 前端展示"最快送达" |
| 标准 | P75 | 分仓决策默认口径 |
| 保守 | P90 | SLA 承诺和客诉判定 |

## MCP Tools

- `eta_calculate(origin_state, dest_state, carrier, service_level, ...)` — 计算 ETA

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
