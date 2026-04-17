# Requirements Document — Shipping Rate Engine（运费计算引擎）

## Introduction

为 shipping_rate skill 增加运费计算能力。当前 skill 仅实现了 OMS 三层映射规则匹配（承运商/服务推荐），
缺少真正的运费计算。本需求基于 PRD 7.6 节规格，实现一个通用运费计算引擎，支持 4 种计费模式、8 种附加费、
计费取整规则和附加费叠加顺序。引擎不绑定具体承运商 API，通过价格表配置驱动计算，预留第三方 API 扩展点。

运费计算是 warehouse_allocation 综合评分（Score 公式）的核心输入之一：
- 装箱引擎（cartonization_engine）输出包裹列表和计费重量
- 映射规则引擎确定承运商和服务方式
- 运费计算引擎基于包裹信息 + 承运商价格表 → 输出订单级运费

## Glossary

- **Rate_Engine**: 运费计算引擎，负责基于包裹信息、价格表和附加费规则计算运费
- **Rate_Calculator**: 基础运费计算器，实现 4 种计费模式的运费计算
- **Surcharge_Calculator**: 附加费计算器，实现 8 种附加费的触发判定和费用计算
- **Rate_Aggregator**: 运费汇总器，将包裹级运费汇总为订单级运费并应用促销减免
- **Zone_Resolver**: 计费区域解析器，根据发货仓和收货地址确定计费区域
- **Price_Table**: 承运商价格表，包含计费区域、首重/续重费率、阶梯价格等配置
- **Surcharge_Rule**: 附加费规则，定义附加费的触发条件和费率
- **Promotion_Rule**: 促销运费规则，定义运费减免的触发条件和减免方式
- **Billing_Weight**: 计费重量，由装箱引擎输出，取实际重量和体积重量的较大值
- **Charge_Zone**: 计费区域，由发货仓地址和收货地址映射得到的承运商分区编号
- **Package**: 包裹，装箱引擎输出的单个包裹，包含 SKU 列表、箱型、计费重量等
- **Freight_Base**: 基础运费，按计费模式计算的单包裹运费（不含附加费）
- **Freight_Surcharge**: 附加费总额，单包裹所有附加费之和
- **Freight_Order**: 订单级运费，所有包裹运费之和
- **Rate_Provider**: 运费数据提供者接口，抽象价格表和附加费规则的数据来源，预留第三方 API 扩展

## Requirements

### Requirement 1: 运费计算输入验证

**User Story:** As a 寻仓引擎调用方, I want 运费计算引擎验证所有必要输入, so that 计算结果可靠且错误可追溯。

#### Acceptance Criteria

1. WHEN 运费计算请求被提交, THE Rate_Engine SHALL 验证以下 9 项输入是否存在：包裹列表、计费重量、发货仓地址、收货地址、承运商、承运商价格表、商家运费协议、附加费规则、促销运费规则
2. IF 包裹列表为空或计费重量缺失, THEN THE Rate_Engine SHALL 返回错误码 MISSING_PACKAGE_INFO 和描述信息
3. IF 承运商价格表未找到, THEN THE Rate_Engine SHALL 返回错误码 PRICE_TABLE_NOT_FOUND 和描述信息
4. IF 发货仓地址或收货地址缺失, THEN THE Rate_Engine SHALL 返回错误码 MISSING_ADDRESS 和描述信息
5. WHEN 商家运费协议、附加费规则或促销运费规则缺失, THE Rate_Engine SHALL 使用空规则集继续计算并在结果中标注 degraded 字段

### Requirement 2: 计费区域解析

**User Story:** As a 运费计算引擎, I want 根据发货仓和收货地址确定计费区域, so that 后续运费计算使用正确的价格档位。

#### Acceptance Criteria

1. WHEN 发货仓地址和收货地址被提供, THE Zone_Resolver SHALL 根据承运商价格表中的区域映射规则确定 Charge_Zone
2. IF 发货仓地址和收货地址在同一城市, THEN THE Zone_Resolver SHALL 返回同城区域编号
3. IF 收货地址无法匹配任何计费区域, THEN THE Zone_Resolver SHALL 返回错误码 ZONE_NOT_FOUND 和描述信息
4. THE Zone_Resolver SHALL 支持省/市/区三级地址匹配，优先匹配最精确的区级，逐级回退到市级和省级

### Requirement 3: 基础运费计算 — 首重+续重模式

**User Story:** As a 运费计算引擎, I want 按首重+续重模式计算基础运费, so that 快递类承运商的运费计算准确。

#### Acceptance Criteria

1. WHEN 计费模式为首重+续重, THE Rate_Calculator SHALL 按公式 `Freight_base = FirstWeight_fee + ceil((ChargeWeight - FirstWeight) / StepWeight) × StepWeight_fee` 计算基础运费
2. WHEN 计费重量小于或等于首重, THE Rate_Calculator SHALL 返回首重费用作为基础运费
3. THE Rate_Calculator SHALL 将计费重量向上取整到 0.1kg：`ceil(weight × 10) / 10`
4. THE Rate_Calculator SHALL 将续重段数向上取整：`ceil((ChargeWeight - FirstWeight) / StepWeight)`
5. THE Rate_Calculator SHALL 将运费金额保留 2 位小数，四舍五入：`round(fee, 2)`
6. FOR ALL 有效的计费重量和价格表参数, 计算后再解析回输入参数 SHALL 产生等价的运费金额（round-trip 一致性）

### Requirement 4: 基础运费计算 — 阶梯重量模式

**User Story:** As a 运费计算引擎, I want 按阶梯重量模式计算基础运费, so that 零担物流的分段计费准确。

#### Acceptance Criteria

1. WHEN 计费模式为阶梯重量, THE Rate_Calculator SHALL 按重量区间分段计费，每个区间使用对应的单价
2. WHEN 计费重量跨越多个区间, THE Rate_Calculator SHALL 对每个区间内的重量分别计费后累加
3. IF 计费重量超过价格表定义的最大区间, THEN THE Rate_Calculator SHALL 使用最高区间的单价计算超出部分
4. THE Rate_Calculator SHALL 将运费金额保留 2 位小数，四舍五入

### Requirement 5: 基础运费计算 — 体积计费模式

**User Story:** As a 运费计算引擎, I want 按体积计费模式计算基础运费, so that 泡货和轻抛货的运费计算准确。

#### Acceptance Criteria

1. WHEN 计费模式为体积计费, THE Rate_Calculator SHALL 按公式 `Freight_base = volume_m3 × unit_price_per_m3` 计算基础运费
2. THE Rate_Calculator SHALL 将包裹体积从立方厘米转换为立方米：`volume_m3 = length_cm × width_cm × height_cm / 1_000_000`
3. THE Rate_Calculator SHALL 将运费金额保留 2 位小数，四舍五入

### Requirement 6: 基础运费计算 — 固定费用模式

**User Story:** As a 运费计算引擎, I want 按固定费用模式计算基础运费, so that 同城配送和特殊线路的运费计算准确。

#### Acceptance Criteria

1. WHEN 计费模式为固定费用, THE Rate_Calculator SHALL 返回价格表中定义的固定费用作为基础运费
2. THE Rate_Calculator SHALL 将运费金额保留 2 位小数，四舍五入

### Requirement 7: 附加费计算 — 偏远地区附加费

**User Story:** As a 运费计算引擎, I want 计算偏远地区附加费, so that 偏远地区的额外配送成本被正确计入。

#### Acceptance Criteria

1. WHEN 收货地址在偏远地区列表中, THE Surcharge_Calculator SHALL 按附加费规则计算偏远地区附加费
2. THE Surcharge_Calculator SHALL 支持两种计费方式：固定金额加收和基础运费百分比加收
3. WHEN 收货地址不在偏远地区列表中, THE Surcharge_Calculator SHALL 返回偏远地区附加费为 0

### Requirement 8: 附加费计算 — 超重附加费

**User Story:** As a 运费计算引擎, I want 计算超重附加费, so that 超重包裹的额外处理成本被正确计入。

#### Acceptance Criteria

1. WHEN 单包裹计费重量超过超重阈值, THE Surcharge_Calculator SHALL 按超出部分的更高单价计算超重附加费
2. WHEN 单包裹计费重量未超过超重阈值, THE Surcharge_Calculator SHALL 返回超重附加费为 0
3. THE Surcharge_Calculator SHALL 从附加费规则中读取超重阈值和超重单价

### Requirement 9: 附加费计算 — 超尺寸附加费

**User Story:** As a 运费计算引擎, I want 计算超尺寸附加费, so that 超尺寸包裹的额外处理成本被正确计入。

#### Acceptance Criteria

1. WHEN 单包裹最长边超过超尺寸阈值, THE Surcharge_Calculator SHALL 按固定金额加收超尺寸附加费
2. WHEN 单包裹最长边未超过超尺寸阈值, THE Surcharge_Calculator SHALL 返回超尺寸附加费为 0
3. THE Surcharge_Calculator SHALL 从附加费规则中读取超尺寸阈值和固定金额

### Requirement 10: 附加费计算 — 燃油附加费

**User Story:** As a 运费计算引擎, I want 计算燃油附加费, so that 随油价调整的运输成本被正确计入。

#### Acceptance Criteria

1. THE Surcharge_Calculator SHALL 始终计算燃油附加费：`fuel_surcharge = Freight_base × fuel_surcharge_rate`
2. THE Surcharge_Calculator SHALL 从附加费规则中读取当前生效的燃油附加费率
3. THE Surcharge_Calculator SHALL 将燃油附加费金额保留 2 位小数，四舍五入

### Requirement 11: 附加费计算 — 节假日附加费

**User Story:** As a 运费计算引擎, I want 计算节假日附加费, so that 节假日期间的额外配送成本被正确计入。

#### Acceptance Criteria

1. WHEN 发货日或预计送达日在节假日期间, THE Surcharge_Calculator SHALL 计算节假日附加费
2. THE Surcharge_Calculator SHALL 支持两种计费方式：固定金额加收和（基础运费 + 燃油附加费）百分比加收
3. WHEN 发货日和预计送达日均不在节假日期间, THE Surcharge_Calculator SHALL 返回节假日附加费为 0

### Requirement 12: 附加费计算 — 保价费

**User Story:** As a 运费计算引擎, I want 计算保价费, so that 高价值商品的保险成本被正确计入。

#### Acceptance Criteria

1. WHEN 商品声明价值超过保价阈值, THE Surcharge_Calculator SHALL 按公式 `insurance_fee = declared_value × insurance_rate` 计算保价费
2. WHEN 商品声明价值未超过保价阈值, THE Surcharge_Calculator SHALL 返回保价费为 0
3. THE Surcharge_Calculator SHALL 从附加费规则中读取保价阈值和保价费率

### Requirement 13: 附加费计算 — 冷链附加费

**User Story:** As a 运费计算引擎, I want 计算冷链附加费, so that 冷藏和冷冻商品的额外配送成本被正确计入。

#### Acceptance Criteria

1. WHEN 包裹包含冷藏或冷冻商品, THE Surcharge_Calculator SHALL 按固定金额加收冷链附加费（含冷媒成本）
2. WHEN 包裹不包含冷藏或冷冻商品, THE Surcharge_Calculator SHALL 返回冷链附加费为 0
3. THE Surcharge_Calculator SHALL 从附加费规则中读取冷链附加费固定金额

### Requirement 14: 附加费计算 — 上楼费

**User Story:** As a 运费计算引擎, I want 计算上楼费, so that 大件商品无电梯配送的额外成本被正确计入。

#### Acceptance Criteria

1. WHEN 大件商品且收货地址无电梯, THE Surcharge_Calculator SHALL 按公式 `stair_fee = floor_number × per_floor_price` 计算上楼费
2. WHEN 商品非大件或收货地址有电梯, THE Surcharge_Calculator SHALL 返回上楼费为 0
3. THE Surcharge_Calculator SHALL 从附加费规则中读取楼层单价

### Requirement 15: 附加费叠加顺序

**User Story:** As a 运费计算引擎, I want 按规定顺序叠加附加费, so that 附加费之间的依赖关系被正确处理。

#### Acceptance Criteria

1. THE Surcharge_Calculator SHALL 按以下 5 步顺序叠加附加费：(1) 计算基础运费 → (2) 叠加燃油附加费 → (3) 叠加偏远/超重/超尺寸附加费 → (4) 叠加冷链/保价/上楼等服务附加费 → (5) 叠加节假日附加费
2. WHEN 计算节假日附加费百分比时, THE Surcharge_Calculator SHALL 基于（基础运费 + 燃油附加费）计算，而非仅基于基础运费
3. THE Surcharge_Calculator SHALL 在步骤 3 和步骤 4 中独立计算各附加费后累加，附加费之间互不影响

### Requirement 16: 订单级运费汇总

**User Story:** As a 寻仓引擎调用方, I want 将所有包裹运费汇总为订单级运费, so that 综合成本函数可以使用统一的订单运费。

#### Acceptance Criteria

1. THE Rate_Aggregator SHALL 按公式 `Freight_order = Σ(Freight_base(i) + Freight_surcharge(i)) for i in packages` 汇总订单级运费
2. THE Rate_Aggregator SHALL 在结果中包含每个包裹的运费明细（基础运费、各项附加费、包裹总运费）
3. THE Rate_Aggregator SHALL 将订单级运费金额保留 2 位小数，四舍五入

### Requirement 17: 促销运费减免

**User Story:** As a 运费计算引擎, I want 应用促销运费规则减免运费, so that 满减免运费等促销活动被正确处理。

#### Acceptance Criteria

1. WHEN 促销运费规则生效且订单满足触发条件, THE Rate_Aggregator SHALL 从订单级运费中扣减促销减免金额
2. THE Rate_Aggregator SHALL 确保减免后的运费不低于 0
3. THE Rate_Aggregator SHALL 在结果中标注促销减免金额和命中的促销规则名称
4. WHEN 无生效的促销运费规则, THE Rate_Aggregator SHALL 不做任何减免

### Requirement 18: 运费计算数据模型

**User Story:** As a 开发者, I want 运费计算引擎使用清晰的 Pydantic 数据模型, so that 输入输出契约明确且可序列化。

#### Acceptance Criteria

1. THE Rate_Engine SHALL 使用 Pydantic BaseModel 定义所有输入和输出数据模型
2. THE Rate_Engine SHALL 定义 RateRequest 模型包含：包裹列表、发货仓地址、收货地址、承运商、价格表、附加费规则、促销规则
3. THE Rate_Engine SHALL 定义 RateResult 模型包含：订单级运费、包裹运费明细列表、促销减免信息、degraded 标记、错误列表
4. THE Rate_Engine SHALL 定义 PackageRate 模型包含：包裹 ID、基础运费、各项附加费明细、包裹总运费
5. FOR ALL 有效的 RateRequest 对象, 序列化为 JSON 再反序列化 SHALL 产生等价的 RateRequest 对象（round-trip 属性）
6. FOR ALL 有效的 RateResult 对象, 序列化为 JSON 再反序列化 SHALL 产生等价的 RateResult 对象（round-trip 属性）

### Requirement 19: 价格表数据模型

**User Story:** As a 开发者, I want 价格表使用结构化数据模型, so that 4 种计费模式的价格配置可以统一表达。

#### Acceptance Criteria

1. THE Rate_Engine SHALL 定义 PriceTable 模型支持 4 种计费模式：first_weight_step（首重+续重）、weight_tier（阶梯重量）、volume（体积计费）、fixed（固定费用）
2. THE Rate_Engine SHALL 定义 ZoneRate 模型包含：计费区域、计费模式、首重/续重参数、阶梯区间列表、体积单价、固定费用
3. THE Rate_Engine SHALL 定义 ZoneMapping 模型包含：发货地区域、收货地区域、计费区域编号
4. FOR ALL 有效的 PriceTable 对象, 序列化为 JSON 再反序列化 SHALL 产生等价的 PriceTable 对象（round-trip 属性）

### Requirement 20: 与现有映射规则引擎整合

**User Story:** As a 寻仓引擎调用方, I want 运费计算引擎与现有映射规则引擎整合, so that 映射确定承运商后可以直接计算运费。

#### Acceptance Criteria

1. THE Rate_Engine SHALL 接受映射规则引擎的 RecommendResult 作为承运商输入
2. WHEN 映射规则引擎返回多个承运商推荐, THE Rate_Engine SHALL 为每个推荐分别计算运费
3. THE Rate_Engine SHALL 在运费结果中保留承运商推荐的来源信息（one_to_one / condition_mapping / shipping_mapping）

### Requirement 21: 第三方承运商 API 扩展点

**User Story:** As a 开发者, I want 运费计算引擎预留第三方承运商 API 扩展点, so that 未来可以对接 UPS/FedEx/USPS 等实时报价 API。

#### Acceptance Criteria

1. THE Rate_Engine SHALL 定义 Rate_Provider 抽象接口，包含 `get_rate(package, origin, destination, carrier)` 方法
2. THE Rate_Engine SHALL 提供 LocalRateProvider 实现，基于本地价格表计算运费
3. THE Rate_Engine SHALL 支持注册多个 Rate_Provider 实例，按优先级依次尝试
4. IF 高优先级 Rate_Provider 返回错误, THEN THE Rate_Engine SHALL 回退到下一个 Rate_Provider

### Requirement 22: MCP Tool 注册

**User Story:** As a OMS Agent 用户, I want 通过 MCP tool 调用运费计算, so that 可以在对话中直接获取运费估算。

#### Acceptance Criteria

1. THE Rate_Engine SHALL 在 oms_agent_server.py 中注册 `shipping_rate_calculate` MCP tool
2. WHEN `shipping_rate_calculate` 被调用, THE Rate_Engine SHALL 接受订单号或包裹列表 + 地址 + 承运商参数，返回运费计算结果
3. THE Rate_Engine SHALL 在 MCP tool 返回中包含运费明细、计算过程说明和置信度

