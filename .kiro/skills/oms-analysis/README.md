# OMS Analysis Skill — OMS 运营分析

> v2.0 (2026-04-13): 多 Analyzer 联动、时间范围过滤、金额维度、事件日志抽样

## 定位

oms_analysis 是 OMS Agent 的运营分析 Skill，消费 oms_query 的数据做深层分析。
采用可插拔 Analyzer 架构，15 个 Analyzer 覆盖诊断/洞察/建议三大类。

## v2.0 核心改进

- 意图扩展联动：异常类问题自动追加影响评估 + 修复建议，一次调用给出完整分析
- 时间范围提取：从自然语言解析"近7天"、"本月"等，无时间默认近 30 天
- 事件日志抽样：BatchPatternAnalyzer 自动抽样异常订单事件日志归纳根因
- 金额维度：OrderTrendAnalyzer / ChannelPerformanceAnalyzer / SkuSalesAnalyzer 加入 GMV、客单价、取消率
- 数据源修正：批量分析从订单 API（sale-order/page）获取数据，而非 Shipping Request

## 架构

```
OMSAnalysisEngine（顶层编排器）
  ├── IntentDetector（意图识别 + 扩展联动 + 时间提取）
  ├── AnalyzerRegistry（自动发现 + 意图路由）
  ├── DataFetcher（数据获取 + 时间过滤 + 商品行补充 + 事件日志抽样）
  └── ResultAggregator（多结果聚合）

诊断类 Analyzer
  ├── ExceptionRootCauseAnalyzer v1
  ├── HoldAnalyzer v1
  ├── StuckOrderAnalyzer v1
  ├── AllocationFailureAnalyzer v1
  ├── ShipmentExceptionAnalyzer v1
  └── BatchPatternAnalyzer v2（事件日志抽样 + 根因归纳）

洞察类 Analyzer
  ├── InventoryHealthAnalyzer v1
  ├── WarehouseEfficiencyAnalyzer v1.1
  ├── ChannelPerformanceAnalyzer v2（GMV/客单价/取消率）
  ├── OrderTrendAnalyzer v2（GMV/客单价/取消率/件单比）
  └── SkuSalesAnalyzer v2（销售额）

建议类 Analyzer
  ├── FixRecommendationAnalyzer v2（支持批量场景）
  ├── ReplenishmentAdvisor v1
  ├── ImpactAssessor v1
  └── CrossDimensionAnalyzer v1
```

## 数据来源

通过 DataFetcher 调用 oms_query_engine 的 API client 获取真实数据：
- 订单列表：sale-order/page（按状态分别采样）
- 事件日志：orderLog/list（为异常订单抽样获取）
- 库存：inventory/list
- 仓库：facility/v2/page
- 规则：routing/v2/rules
- 状态统计：sale-order/status/num
- 商品行明细：sale-order/{orderNo}（逐单补充）

## MCP Tool

`oms_analysis(identifier, merchant_no, intent, query)` — 在 oms-agent MCP server 中注册。

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
