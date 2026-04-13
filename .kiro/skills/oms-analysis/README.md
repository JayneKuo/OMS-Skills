# OMS Analysis Skill — OMS 运营分析

> v1.0 (2026-04-09): 初始版本

## 定位

oms_analysis 是 OMS Agent 的运营分析 Skill，消费 oms_query 的数据做深层分析。
采用可插拔 Analyzer 架构，每个分析能力独立一个模块，方便单独调整算法。

## 架构

```
oms_analysis（统一 Skill 入口）
  │
  ├── OMSAnalysisEngine（顶层编排器）
  │     ├── IntentDetector（分析意图识别）
  │     ├── AnalyzerRegistry（Analyzer 注册与发现）
  │     └── ResultAggregator（结果聚合）
  │
  ├── 诊断类 Analyzer
  │     ├── ExceptionRootCauseAnalyzer
  │     ├── HoldAnalyzer
  │     ├── StuckOrderAnalyzer
  │     ├── AllocationFailureAnalyzer
  │     ├── ShipmentExceptionAnalyzer
  │     └── BatchPatternAnalyzer
  │
  ├── 洞察类 Analyzer
  │     ├── InventoryHealthAnalyzer
  │     ├── WarehouseEfficiencyAnalyzer
  │     ├── ChannelPerformanceAnalyzer
  │     ├── OrderTrendAnalyzer
  │     └── SkuSalesAnalyzer
  │
  └── 建议类 Analyzer
        ├── FixRecommendationGenerator
        ├── ReplenishmentAdvisor
        └── ImpactAssessor
```

## 文件结构

```
oms-analysis/
├── SKILL.md
├── README.md
├── references/
│   └── 需求规格.md
└── scripts/
    └── oms_analysis_engine/
        ├── engine.py
        ├── base.py
        ├── models/
        └── analyzers/
```

## 数据来源

所有分析基于 oms_query 的 MCP tool 返回的真实数据，不直接调用 OMS API。

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
