# 实施计划：OMS 运营分析引擎（oms_analysis_engine）

## 概述

按依赖顺序实现 OMS 运营分析引擎。先建立数据模型和枚举定义，再实现基础设施层（BaseAnalyzer、AnalyzerRegistry、DataFetcher、IntentDetector、ResultAggregator），然后逐个实现 15 个 Analyzer，最后实现顶层 Engine 编排器并注册 MCP tool。每个 Analyzer 独立一个任务，实现后紧跟属性测试，确保增量验证。

引擎代码路径：`.kiro/skills/oms-analysis/scripts/oms_analysis_engine/`

## 任务列表

- [x] 1. 项目结构初始化与数据模型实现
  - [x] 1.1 创建项目目录结构
    - 创建 `oms_analysis_engine/` 包目录和 `__init__.py`
    - 创建 `oms_analysis_engine/models/` 子包和 `__init__.py`
    - 创建 `oms_analysis_engine/analyzers/` 子包和 `__init__.py`
    - 创建 `tests/oms_analysis/` 测试目录和 `conftest.py`
    - 所有代码放在 `.kiro/skills/oms-analysis/scripts/oms_analysis_engine/` 下
    - _需求: AC-1, 2.5_

  - [x] 1.2 实现枚举定义（models/enums.py）
    - 实现 `Confidence`（HIGH/MEDIUM/LOW）
    - 实现 `DataCompleteness`（COMPLETE/PARTIAL/INSUFFICIENT）
    - 实现 `Severity`（CRITICAL/MAJOR/MINOR）
    - 实现 `Urgency`（URGENT/SUGGESTED/OPTIONAL）
    - 实现 `ExceptionCategory`（INVENTORY/RULE/WAREHOUSE/SHIPMENT/SYNC/SYSTEM）
    - 实现 `HoldSource`（RULE/MANUAL/SYSTEM）
    - 实现 `InventoryHealthLevel`（OUT_OF_STOCK/LOW/NORMAL/OVERSTOCK）
    - _需求: 2.4.1, 4.6, 5.4, 10.2.4, 16.3_

  - [x] 1.3 实现请求模型（models/request.py）
    - 实现 `TimeRange`（start, end）
    - 实现 `AnalysisIntent`（intent_type, confidence, parameters）
    - 实现 `AnalysisRequest`（identifier, merchant_no, intent, query, time_range, filters）
    - _需求: 2.2, 3_

  - [x] 1.4 实现上下文模型（models/context.py）
    - 实现 `SamplingInfo`（total_count, sample_count, sample_ratio, method）
    - 实现 `AnalysisContext`（request, order_data, inventory_data, warehouse_data, rule_data, event_data, shipment_data, batch_orders, sampling_info）
    - 实现 `has_data(field)` 方法
    - _需求: 2.3, 2.4_

  - [x] 1.5 实现结果模型（models/result.py）
    - 实现 `Evidence`（source, description, data）
    - 实现 `Recommendation`（action, precondition, risk, priority, expected_effect）
    - 实现 `AnalysisResult`（analyzer_name, analyzer_version, success, summary, reason, evidences, confidence, data_completeness, severity, recommendations, metrics, details, errors）
    - 实现 `AnalysisResult.error_result()` 类方法
    - 实现 `AnalysisResponse`（results, overall_severity, overall_confidence, overall_data_completeness, all_recommendations, sampling_info）
    - _需求: 2.4, AC-2, AC-16_

  - [ ]* 1.6 编写属性测试：AnalysisResult 结构完整性（Property 1）
    - **Property 1: AnalysisResult 结构完整性**
    - 验证任意 Analyzer 返回的 AnalysisResult 中 analyzer_name 和 analyzer_version 非空
    - 验证 success=True 时 evidences 非空
    - **验证: 需求 AC-2, AC-16**

- [x] 2. 基础设施层实现
  - [x] 2.1 实现 BaseAnalyzer 接口（base.py）
    - 实现抽象基类 `BaseAnalyzer`，声明 name/version/intent/required_data
    - 实现抽象方法 `analyze(context) → AnalysisResult`
    - 实现 `_build_evidence()` 辅助方法
    - 实现 `_assess_confidence(evidences)` 置信度评估
    - 实现 `_assess_data_completeness(context, required_fields)` 数据完整度评估
    - _需求: AC-1, 2.5.1, 2.5.2_

  - [ ]* 2.2 编写属性测试：置信度与数据完整度降级一致性（Property 2）
    - **Property 2: 置信度与数据完整度降级一致性**
    - 验证 `_assess_confidence` 的三级降级逻辑
    - 验证 `_assess_data_completeness` 的三级降级逻辑
    - **验证: 需求 AC-15, AC-17**

  - [x] 2.3 实现 AnalyzerRegistry（analyzer_registry.py）
    - 实现 `register(analyzer)` 手动注册
    - 实现 `unregister(intent)` 注销
    - 实现 `auto_discover()` 自动发现 analyzers/ 目录下的 BaseAnalyzer 子类
    - 实现 `resolve(intents)` 根据意图查找 Analyzer
    - 实现 `list_analyzers()` 列出所有已注册 Analyzer
    - _需求: AC-1, 2.5.1_

  - [x] 2.4 实现 IntentDetector（intent_detector.py）
    - 实现关键词映射表（15 个意图对应的中英文关键词）
    - 实现 `detect(request)` 意图识别逻辑
    - 支持明确指定 intent 和自然语言关键词匹配两种模式
    - _需求: 3_

  - [x] 2.5 实现 DataFetcher（data_fetcher.py）
    - 实现 `fetch(request, analyzers)` 批量获取数据
    - 实现 `_fetch_order_data`、`_fetch_inventory_data`、`_fetch_warehouse_data`、`_fetch_batch_data` 等方法
    - 实现 `_apply_sampling(data, threshold=1000)` 大数据量采样降级
    - 数据通过 oms_query MCP tool / oms_query_engine 获取
    - _需求: 2.3.4, AC-18_

  - [ ]* 2.6 编写属性测试：大数据量采样降级（Property 14）
    - **Property 14: 大数据量采样降级**
    - 验证 len(data) ≤ 1000 时返回原始数据且 SamplingInfo 为 None
    - 验证 len(data) > 1000 时返回采样数据且 SamplingInfo 正确
    - **验证: 需求 AC-18**

  - [x] 2.7 实现 ResultAggregator（result_aggregator.py）
    - 实现 `aggregate(results, context)` 聚合逻辑
    - 按 Analyzer 类型分组、合并证据链、取最高严重程度、合并建议列表
    - _需求: 2.4_

- [x] 3. 检查点 — 基础设施验证
  - 确保所有基础设施层测试通过，ask the user if questions arise.

- [x] 4. 诊断类 Analyzer 实现（第一批）
  - [x] 4.1 实现 ExceptionRootCauseAnalyzer（analyzers/exception_root_cause.py）
    - 实现异常环节识别逻辑
    - 实现异常分类体系映射（6 大类 13 个子类错误码）
    - 实现技术错误到业务语言的翻译
    - 实现多证据合并判断和候选根因列表
    - _需求: 4.1~4.10, AC-3_

  - [ ]* 4.2 编写属性测试：异常分类映射完备性（Property 3）
    - **Property 3: 异常分类映射完备性**
    - 验证所有已知错误码都能映射到正确的 ExceptionCategory 大类
    - **验证: 需求 AC-3**

  - [x] 4.3 实现 HoldAnalyzer（analyzers/hold_analyzer.py）
    - 实现 Hold 来源三分类（RULE/MANUAL/SYSTEM）
    - 实现规则条件关联与逐条解释
    - 实现解除前置条件和风险提示输出
    - _需求: 5.1~5.8, AC-4_

  - [ ]* 4.4 编写属性测试：Hold 来源三分类（Property 4）
    - **Property 4: Hold 来源三分类**
    - 验证任意 Hold 订单数据的分类结果为 RULE/MANUAL/SYSTEM 之一
    - 验证分类逻辑与数据标记的一致性
    - **验证: 需求 AC-4**

  - [x] 4.5 实现 StuckOrderAnalyzer（analyzers/stuck_order.py）
    - 实现环节识别和停留时长计算
    - 实现默认环节阈值配置（待分仓 2h、待履约 24h、仓库处理 48h、待发运 24h、待同步 4h）
    - 实现超时判定和超时倍数计算
    - _需求: 6.1~6.9, AC-5_

  - [ ]* 4.6 编写属性测试：停留时长计算与超时判定（Property 5）
    - **Property 5: 停留时长计算与超时判定**
    - 验证 duration = now - start_time
    - 验证 is_stuck 与 overtime_ratio 的一致性
    - **验证: 需求 AC-5**

  - [x] 4.7 实现 AllocationFailureAnalyzer（analyzers/allocation_failure.py）
    - 实现候选仓逐层排除逻辑（库存 → 仓可用性 → 规则 → 地址/时效）
    - 实现库存问题与规则问题的区分
    - _需求: 7.1~7.6, AC-6_

  - [ ]* 4.8 编写属性测试：分仓失败原因区分（Property 6）
    - **Property 6: 分仓失败原因区分**
    - 验证全部候选仓库存满足率为 0% 时归类为库存问题
    - 验证存在满足仓但被规则排除时归类为规则问题
    - **验证: 需求 AC-6**

  - [x] 4.9 实现 ShipmentExceptionAnalyzer（analyzers/shipment_exception.py）
    - 实现发运异常子类型识别
    - 实现可重试性标注（临时性 vs 永久性错误）
    - _需求: 8.1~8.6, AC-7_

  - [ ]* 4.10 编写属性测试：发运异常可重试性标注（Property 7）
    - **Property 7: 发运异常可重试性标注**
    - 验证临时性错误标注 retryable=True
    - 验证永久性错误标注 retryable=False
    - **验证: 需求 AC-7**

  - [x] 4.11 实现 BatchPatternAnalyzer（analyzers/batch_pattern.py）
    - 实现按异常类型分组和共性维度识别
    - 实现批量异常模式阈值判定（去重订单数 > 3）
    - _需求: 9.1~9.6, AC-8_

  - [ ]* 4.12 编写属性测试：批量模式阈值不变量（Property 8）
    - **Property 8: 批量模式阈值不变量**
    - 验证去重订单数 ≤ 3 时不标记为批量异常模式
    - 验证去重订单数 > 3 时可标记为批量异常模式
    - **验证: 需求 AC-8**

- [x] 5. 检查点 — 诊断类 Analyzer 验证
  - 确保所有诊断类 Analyzer 测试通过，ask the user if questions arise.

- [x] 6. 洞察类 Analyzer 实现（第二批）
  - [x] 6.1 实现 InventoryHealthAnalyzer（analyzers/inventory_health.py）
    - 实现可售天数计算（含除零特殊处理）
    - 实现库存健康等级判定（OUT_OF_STOCK/LOW/NORMAL/OVERSTOCK）
    - 实现仓间库存分布占比计算
    - _需求: 10.1~10.4, AC-9_

  - [ ]* 6.2 编写属性测试：可售天数计算正确性（Property 9）
    - **Property 9: 可售天数计算正确性**
    - 验证 stock=0 时可售天数=0
    - 验证 daily_consumption=0 且 stock>0 时标记为"无法计算"
    - 验证正常情况下 可售天数 = stock / daily_consumption
    - **验证: 需求 AC-9**

  - [x] 6.3 实现 WarehouseEfficiencyAnalyzer（analyzers/warehouse_efficiency.py）
    - 实现平均处理时长和中位处理时长双指标计算
    - 实现效率异常判定（某仓 > 全仓平均 × 2）
    - _需求: 11.1~11.4, AC-10_

  - [ ]* 6.4 编写属性测试：仓库效率统计双指标（Property 10）
    - **Property 10: 仓库效率统计双指标**
    - 验证非空时长列表同时输出 mean_duration 和 median_duration
    - 验证两个值均为非负数
    - **验证: 需求 AC-10**

  - [x] 6.5 实现 ChannelPerformanceAnalyzer（analyzers/channel_performance.py）
    - 实现渠道订单量、异常率、履约时长对比
    - 实现低样本渠道降级（低于最小样本阈值时置信度不为 HIGH）
    - _需求: 12.1~12.4, AC-11_

  - [ ]* 6.6 编写属性测试：低样本渠道降级（Property 11）
    - **Property 11: 低样本渠道降级**
    - 验证低于最小样本阈值的渠道置信度不为 HIGH
    - **验证: 需求 AC-11**

  - [x] 6.7 实现 OrderTrendAnalyzer（analyzers/order_trend.py）
    - 实现日订单量、日异常率趋势计算
    - 实现环比变化率计算
    - 实现连续 3 天上升预警判定
    - _需求: 13.1~13.4, AC-12_

  - [ ]* 6.8 编写属性测试：连续恶化预警判定（Property 12）
    - **Property 12: 连续恶化预警判定**
    - 验证连续 3 天 d_i < d_{i+1} < d_{i+2} 时触发预警
    - 验证不存在连续 3 天递增时不触发预警
    - **验证: 需求 AC-12**

  - [x] 6.9 实现 SkuSalesAnalyzer（analyzers/sku_sales.py）
    - 实现销量排名和热销/滞销标签（Top 20% / Bottom 20%）
    - 实现仓间销量分布
    - _需求: 14.1~14.4_

- [x] 7. 检查点 — 洞察类 Analyzer 验证
  - 确保所有洞察类 Analyzer 测试通过，ask the user if questions arise.

- [x] 8. 建议类与增强 Analyzer 实现（第三批）
  - [x] 8.1 实现 FixRecommendationAnalyzer（analyzers/fix_recommendation.py）
    - 实现问题类型归类和建议模板匹配
    - 实现动作、前置条件、风险、优先级输出
    - 低置信度时建议补充核实信息
    - _需求: 15.1~15.5, AC-13_

  - [x] 8.2 实现 ReplenishmentAdvisor（analyzers/replenishment_advisor.py）
    - 实现建议补货量计算：`max(0, target_days × consumption - stock)`
    - 实现紧急程度判定（URGENT/SUGGESTED/OPTIONAL）
    - _需求: 16.1~16.5, AC-14_

  - [ ]* 8.3 编写属性测试：补货量计算与紧急程度（Property 13）
    - **Property 13: 补货量计算与紧急程度**
    - 验证 suggested_qty = max(0, target_days × consumption - stock)
    - 验证紧急程度与可售天数阈值的一致性
    - **验证: 需求 AC-14**

  - [x] 8.4 实现 ImpactAssessor（analyzers/impact_assessor.py）
    - 实现受影响订单/SKU/仓库数统计
    - 实现严重程度分级（CRITICAL/MAJOR/MINOR）
    - 数据不足时明确标注
    - _需求: 17.1~17.5, AC-15_

  - [x] 8.5 实现 CrossDimensionAnalyzer（analyzers/cross_dimension.py）
    - 实现维度间交叉异常率计算
    - 实现维度共振识别
    - 输出关联维度对和可能的因果方向
    - _需求: 18.1~18.4_

- [x] 9. 检查点 — 建议类 Analyzer 验证
  - 确保所有建议类和增强 Analyzer 测试通过，ask the user if questions arise.

- [x] 10. 顶层 Engine 编排与 MCP tool 注册
  - [x] 10.1 实现 OMSAnalysisEngine（engine.py）
    - 实现主分析入口 `analyze(request) → AnalysisResponse`
    - 实现流水线编排：IntentDetector → AnalyzerRegistry → DataFetcher → Analyzer(s) → ResultAggregator
    - 实现单个 Analyzer 异常捕获和 error_result 降级
    - 自动调用 `registry.auto_discover()` 注册所有内置 Analyzer
    - _需求: 2.5, AC-1, AC-2_

  - [ ]* 10.2 编写集成测试：Engine 端到端流水线
    - 测试完整流水线：请求 → 意图识别 → Analyzer 调度 → 数据获取 → 分析 → 聚合
    - 测试单个 Analyzer 异常不阻断其他 Analyzer
    - 测试意图无匹配时返回空 AnalysisResponse
    - _需求: AC-1, AC-2, AC-16, AC-17_

  - [x] 10.3 在 MCP Server 中注册 oms_analysis tool
    - 在 `mcp_server/oms_agent_server.py` 中添加 `oms_analysis` tool 函数
    - 接收分析请求参数（identifier, merchant_no, intent, query, time_range）
    - 调用 OMSAnalysisEngine.analyze() 并返回 JSON 结果
    - _需求: 3_

  - [x] 10.4 更新 MCP 配置和 Skill 文档
    - 更新 `.kiro/settings/mcp.json` 注册新 tool（如需要）
    - 更新 `.kiro/skills/oms-analysis/SKILL.md` 中的能力描述
    - 更新 `.kiro/skills/oms-analysis/README.md`
    - _需求: 3_

- [x] 11. 最终检查点 — 全量验证
  - 确保所有测试通过，ask the user if questions arise.

## 备注

- 标记 `*` 的子任务为可选，可跳过以加速 MVP
- 每个任务引用了对应的需求编号，确保可追溯
- 检查点确保增量验证，及时发现问题
- 属性测试覆盖设计文档中的 14 个 Correctness Properties
- 单元测试覆盖各 Analyzer 的典型业务场景和边界条件
