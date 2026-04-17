# Implementation Plan: Shipping Rate Engine（运费计算引擎）

## Overview

基于现有 shipping_rate_engine 映射规则引擎，新增运费计算能力。实现 6 个核心组件（RateEngine、ZoneResolver、RateCalculator、SurchargeCalculator、RateAggregator、RateProvider），支持 4 种计费模式、8 种附加费、促销减免，并注册 MCP tool。

代码目录：`.kiro/skills/shipping-rate/scripts/shipping_rate_engine/`
测试目录：`tests/`

## Tasks

- [x] 1. 定义运费计算数据模型
  - [x] 1.1 在 `shipping_rate_engine/rate_models.py` 中定义所有输入/输出 Pydantic 模型
    - 枚举：BillingMode、SurchargeType、SurchargeChargeMode
    - 输入模型：Address、PackageInput、ZoneMapping、WeightTier、ZoneRate、PriceTable、SurchargeRule、SurchargeRuleSet、PromotionRule、RateRequest
    - 输出模型：SurchargeDetail、SurchargeBreakdown、PackageRate、PromotionApplied、RateResult、ProviderRateResult、OrderRateSummary
    - 使用 Decimal 类型处理金额，避免浮点误差
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 19.1, 19.2, 19.3_

  - [ ]* 1.2 Write property test for data model round-trip serialization
    - **Property 15: Data model round-trip serialization**
    - **Validates: Requirements 18.5, 18.6, 19.4**

- [x] 2. 实现 ZoneResolver（计费区域解析器）
  - [x] 2.1 在 `shipping_rate_engine/zone_resolver.py` 中实现 ZoneResolver
    - 实现 `resolve(origin, destination, zone_mappings)` 静态方法
    - 支持省/市/区三级地址匹配，优先匹配最精确的区级
    - 同城判定逻辑：发货仓和收货地址在同一城市时返回同城区域编号
    - 无匹配时返回 ZONE_NOT_FOUND 错误
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 2.2 Write property test for zone resolution
    - **Property 3: Zone resolution with hierarchical priority**
    - **Validates: Requirements 2.1, 2.2, 2.4**

- [x] 3. 实现 RateCalculator（基础运费计算器）
  - [x] 3.1 在 `shipping_rate_engine/rate_calculator.py` 中实现 RateCalculator
    - 实现 `calculate(billing_weight, volume_cm3, zone_rate)` 分派方法
    - 实现 `calc_first_weight_step`：首重+续重公式，计费重量向上取整到 0.1kg
    - 实现 `calc_weight_tier`：阶梯重量分段计费，超出最高区间用最高单价
    - 实现 `calc_volume`：体积计费，cm³ → m³ 转换
    - 实现 `calc_fixed`：固定费用模式
    - 所有金额 round(2) 保留 2 位小数
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 6.1, 6.2_

  - [ ]* 3.2 Write property test for first weight + step formula
    - **Property 4: First weight + step formula correctness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

  - [ ]* 3.3 Write property test for tiered weight formula
    - **Property 5: Tiered weight formula correctness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [ ]* 3.4 Write property test for volume formula
    - **Property 6: Volume formula correctness**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 3.5 Write property test for monetary precision
    - **Property 7: All monetary amounts have exactly 2 decimal places**
    - **Validates: Requirements 3.5, 4.4, 5.3, 6.2, 10.3, 16.3**

- [x] 4. 实现 SurchargeCalculator（附加费计算器）
  - [x] 4.1 在 `shipping_rate_engine/surcharge_calculator.py` 中实现 SurchargeCalculator
    - 实现 `calculate_all` 按 5 步顺序叠加所有附加费
    - 实现 8 种附加费独立计算方法：calc_fuel、calc_remote、calc_overweight、calc_oversize、calc_cold_chain、calc_insurance、calc_stair、calc_holiday
    - 节假日附加费基于（基础运费 + 燃油附加费）计算
    - 步骤 3 和步骤 4 中各附加费独立计算后累加
    - _Requirements: 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 11.1, 11.2, 11.3, 12.1, 12.2, 12.3, 13.1, 13.2, 13.3, 14.1, 14.2, 14.3, 15.1, 15.2, 15.3_

  - [ ]* 4.2 Write property test for conditional surcharge triggers
    - **Property 8: Conditional surcharge trigger correctness**
    - **Validates: Requirements 7.1, 7.3, 8.1, 8.2, 9.1, 9.2**

  - [ ]* 4.3 Write property test for fuel surcharge formula
    - **Property 9: Fuel surcharge formula**
    - **Validates: Requirements 10.1, 10.2, 10.3**

  - [ ]* 4.4 Write property test for service surcharge triggers
    - **Property 10: Service surcharge trigger correctness**
    - **Validates: Requirements 12.1, 12.2, 13.1, 13.2, 14.1, 14.2**

  - [ ]* 4.5 Write property test for holiday surcharge base
    - **Property 11: Holiday surcharge uses correct base**
    - **Validates: Requirements 11.2, 15.2**

  - [ ]* 4.6 Write property test for surcharge pipeline ordering
    - **Property 12: Surcharge pipeline ordering**
    - **Validates: Requirements 15.1, 15.3**

- [x] 5. Checkpoint — 核心计算组件验证
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 实现 RateAggregator（运费汇总器）
  - [x] 6.1 在 `shipping_rate_engine/rate_aggregator.py` 中实现 RateAggregator
    - 实现 `aggregate(package_rates, promotion_rules, order_total_amount)` 方法
    - 汇总公式：Freight_order = Σ(freight_base + surcharge_total)
    - 促销减免：支持 full_free / fixed_discount / percentage_discount
    - 确保减免后运费 >= 0
    - 结果包含每个包裹运费明细和促销减免信息
    - _Requirements: 16.1, 16.2, 16.3, 17.1, 17.2, 17.3, 17.4_

  - [ ]* 6.2 Write property test for order aggregation sum
    - **Property 13: Order aggregation sum**
    - **Validates: Requirements 16.1, 16.2, 16.3**

  - [ ]* 6.3 Write property test for promotion discount floor
    - **Property 14: Promotion discount with non-negative floor**
    - **Validates: Requirements 17.1, 17.2**

- [x] 7. 实现 RateProvider 抽象层
  - [x] 7.1 在 `shipping_rate_engine/rate_provider.py` 中实现 RateProvider 抽象接口和 LocalRateProvider
    - 定义 RateProvider ABC，包含 `get_rate()` 和 `priority` 属性
    - 实现 LocalRateProvider：组合 ZoneResolver + RateCalculator + SurchargeCalculator
    - 预留 ExternalRateProvider 扩展点（空实现）
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [ ]* 7.2 Write property test for provider chain fallback
    - **Property 17: Provider chain with priority fallback**
    - **Validates: Requirements 21.3, 21.4**

- [x] 8. 实现 RateEngine 顶层编排（扩展现有 ShippingRateEngine）
  - [x] 8.1 在 `shipping_rate_engine/rate_engine.py` 中实现运费计算编排逻辑
    - 实现 `calculate_rate(request: RateRequest) -> RateResult` 主入口
    - 实现输入验证：9 项必填/可选字段校验，返回对应错误码
    - 实现降级策略：可选字段缺失时标记 degraded
    - 实现计算流水线：验证 → 区域解析 → 基础运费 → 附加费叠加 → 汇总 → 促销减免
    - 实现 `calculate_rate_multi(request, recommendations)` 多承运商计算
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 20.1, 20.2, 20.3_

  - [ ]* 8.2 Write property test for input validation
    - **Property 1: Input validation correctness**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

  - [ ]* 8.3 Write property test for graceful degradation
    - **Property 2: Graceful degradation on missing optional rules**
    - **Validates: Requirements 1.5**

  - [ ]* 8.4 Write property test for multi-recommendation calculation
    - **Property 16: Multi-recommendation rate calculation**
    - **Validates: Requirements 20.2, 20.3**

- [x] 9. Checkpoint — 引擎级集成验证
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. 整合与 MCP Tool 注册
  - [x] 10.1 在现有 `engine.py` 中整合 RateEngine，添加 `calculate_rate` 方法代理
    - ShippingRateEngine 新增 `calculate_rate()` 和 `calculate_rate_multi()` 方法
    - 接受映射引擎的 RecommendResult 作为承运商输入
    - 保留承运商推荐来源信息
    - _Requirements: 20.1, 20.2, 20.3_

  - [x] 10.2 在 `mcp_server/oms_agent_server.py` 中注册 `shipping_rate_calculate` MCP tool
    - 接受订单号或包裹列表 + 地址 + 承运商参数
    - 返回运费明细、计算过程说明和置信度
    - _Requirements: 22.1, 22.2, 22.3_

  - [ ]* 10.3 Write example-based tests for PRD cases
    - 测试不同承运商和计费模式的基础运费案例
    - 测试多包裹订单运费计算
    - 测试固定费用模式
    - _Requirements: 3.1, 4.1, 5.1, 6.1, 16.1_

- [x] 11. Final checkpoint — 全量测试验证
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (17 properties)
- 所有代码在 `.kiro/skills/shipping-rate/scripts/shipping_rate_engine/` 目录下
- 测试文件在 `tests/` 目录下
- 使用 Decimal 类型避免浮点误差，所有金额保留 2 位小数
