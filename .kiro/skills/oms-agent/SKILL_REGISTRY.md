# OMS Agent Skill Registry

本文档用于统一登记 OMS Agent 当前可用 skills 及后续扩展 skills。
Agent 在进行任务路由、能力选择和 workflow 编排时，应参考本文件中的能力定义。

---

## 1. cartonization

### Purpose
根据订单商品、SKU 物理属性、箱规、承运商限制和包装规则，输出装箱建议或装箱计算结果。

### Use When
当用户请求以下任务时优先使用：

- 这票货怎么装箱
- 应该用什么箱型
- 会拆成几个包裹
- 装箱后计费重是多少
- 为什么这样装箱
- 装箱是否违反规则

### Inputs
- order_items
- sku_dimensions
- sku_weights
- item_attributes
- carton_rules
- box_catalog
- carrier_constraints
- packaging_preferences

### Outputs
- package_count
- package_list
- selected_box
- actual_weight
- volumetric_weight
- billable_weight
- fill_rate
- special_flags
- selection_reason
- rule_validation
- physical_validation

### Constraints
- 不负责订单查询
- 不负责承运商最终推荐
- 不直接做跨仓分仓决策
- 若缺少关键主数据，只能输出估算结果

### Upstream Dependencies
- oms_query
- sku_master_data

### Downstream Consumers
- shipping_rate
- eta
- cost
- shipping_plan_recommendation
- warehouse_allocation_recommendation

---

---

> 以下 skills 为规划中，尚未实现。Agent 在遇到相关请求时，应明确告知用户该能力暂未上线，并说明当前可提供的替代建议。

---

## 2. oms_query（✅ 已上线）

### Purpose
OMS 全域强查询。以订单为主入口，联动查询订单、商品、库存、仓库、分仓、规则、履约、发运、同步、日志、事件、集成中心配置等 OMS 核心对象。通过调用 OMS API 获取真实数据。
同时支持 OMS 本体知识图谱检索，查询业务概念、流程、规则、状态、API 等知识。

### Use When
当用户请求以下任务时优先使用：

- 查询订单状态 / 详情 / 全景
- 查看 shipment / tracking / 发运进度
- 查看库存 / 仓库 / 分仓结果
- 查看规则命中 / Hold 原因 / 异常原因
- 查看集成中心连接器 / 渠道配置 / 认证状态
- 查看发运同步状态
- 批量订单统计
- **查询业务概念**（如"什么是分仓"、"订单有哪些状态"、"履约流程是什么"）
- **查询业务流程**（如"OMS 有哪些业务流程"、"分仓流程怎么走"）
- **查询业务规则**（如"订单关联了哪些规则"、"Hold 规则有哪些"）
- **查询 API 接口**（如"哪个 API 负责拆单"、"sale-order 相关接口"）
- **查询状态机**（如"订单有哪些状态"、"状态之间怎么流转"）
- **查询系统架构**（如"OMS 有哪些模块"、"订单处理中心包含什么"）

### Inputs
- order_no / shipment_no / tracking_no / event_id / sku / connector_key
- query_intent（status / shipment / warehouse / rule / inventory / hold / timeline / integration / panorama）
- force_refresh
- **知识查询参数**：query（搜索关键词）、node_type（节点类型过滤）、search_mode（name/type/api_path/related/stats）、relation_type（关系类型过滤）

### Outputs
- OMSQueryResult（订单身份、来源、状态、商品、地址、库存、仓库、分仓、规则、履约、发运、追踪、同步、事件、集成、查询级解释、数据完整度）
- **知识查询结果**：匹配的业务节点（名称、描述、内容、别名）、关联关系、知识库统计

### Constraints
- 仅返回系统中可查到的真实数据
- 不负责解释复杂异常根因
- 不做推荐决策

### Upstream Dependencies
- OMS order service

### Downstream Consumers
- order_analysis
- warehouse_allocation
- cartonization
- shipping_rate
- eta
- cost

---

## 3. oms_analysis（✅ 已上线）

### Purpose
OMS 运营分析。基于 oms_query 的真实数据，执行异常诊断、根因分析、模式识别、运营洞察和修复建议生成。采用可插拔 Analyzer 架构，15 个 Analyzer 覆盖诊断/洞察/建议三大类。

### Use When
当用户请求以下任务时优先使用：

- 为什么订单总是异常 / exception
- 这个订单为什么失败
- Hold 原因是什么，怎么解除
- 订单卡在哪个环节
- 库存健康状况 / 哪些 SKU 缺货
- 仓库效率对比
- 渠道表现对比
- 订单趋势 / 近 7 天 / 近 30 天
- SKU 销量分析
- 补货建议
- 影响评估

### Key Features (v2)
- 意图扩展联动：异常类问题自动追加影响评估 + 修复建议
- 时间范围提取：从自然语言中解析"近7天"、"本月"等，默认近 30 天
- 事件日志抽样：批量异常分析自动抽样订单事件日志归纳根因
- 金额维度：GMV、客单价、取消率、渠道 GMV 占比

### Inputs
- identifier（单订单分析时使用）
- merchant_no
- intent（root_cause / hold_analysis / stuck_order / allocation_failure / shipment_exception / batch_pattern / inventory_health / warehouse_efficiency / channel_performance / order_trend / sku_sales / fix_recommendation / replenishment / impact_assessment / cross_dimension）
- query（自然语言查询）

### Outputs
- AnalysisResponse（results[], overall_severity, overall_confidence, all_recommendations[], sampling_info）
- 每个 AnalysisResult 包含：summary, reason, evidences[], confidence, severity, recommendations[], metrics, details

### Constraints
- 所有结论必须基于真实数据，不编造根因
- 证据不足时标注置信度为 low
- 分析 ≠ 查询（查询是 oms_query 的事）
- 分析 ≠ 推荐仓库/承运商（那是其他 skill 的事）

### Upstream Dependencies
- oms_query（数据来源）

### Downstream Consumers
- oms_main_agent
- order_exception_diagnosis_workflow

---

## 4. warehouse_allocation（✅ 已上线）

### Purpose
寻仓推荐。根据订单目的地、SKU 库存、仓库能力和业务规则，输出最优发货仓推荐。支持 P0 硬约束过滤、P2 多维评分排序、单仓直发和多仓拆发方案。

### Use When
当用户请求以下任务时优先使用：

- 这单该分哪个仓
- 推荐发货仓
- 为什么分到这个仓
- 哪个仓最优
- 这个订单从哪个仓发最合理

### Inputs
- order_no（按订单号推荐）
- sku_list + country + state（直接传入模式）
- allow_split, merchant_no

### Outputs
- AllocationResult（推荐方案、备选方案、候选仓、淘汰仓、置信度、白盒解释、降级标记）

### Constraints
- 库存使用 onHandQty 近似（降级标记）
- 成本/时效使用州级距离估算（降级标记）
- 不含 P1 业务条件、P3 稳定性规则、调拨合发

### Upstream Dependencies
- oms_query（仓库/库存/订单数据）

### Downstream Consumers
- warehouse_allocation_recommendation_workflow
- shipping_plan_recommendation_workflow

---

## 5. shipping_rate（✅ 已上线 v2.0）

### Purpose
运费映射与承运商推荐 + 运费计算引擎。
Part 1: 基于 OMS 三层映射规则体系推荐承运商和服务方式。
Part 2: 基于承运商价格表计算包裹级和订单级运费，支持 4 种计费模式、8 种附加费、促销减免。

### Use When
当用户请求以下任务时优先使用：

- 这单走哪个承运商 / 推荐运输方式
- 运费是多少 / 运费估算
- 不同承运商运费对比
- 查看映射规则配置
- 执行条件映射匹配

### Inputs
- merchant_no, channel_no（映射推荐）
- packages（包裹列表，含计费重量/尺寸）、origin/destination（地址）、carrier、price_table（价格表）、surcharge_rules（附加费规则）、promotion_rules（促销规则）（运费计算）

### Outputs
- MappingQueryResult / MappingExecuteResult / RecommendResult（映射推荐）
- RateResult（运费计算：订单运费、包裹运费明细、附加费明细、促销减免、degraded 标记）

### Constraints
- 推荐基于映射规则数据，不编造
- 运费计算基于价格表配置，无价格表时返回错误
- 金额保留 2 位小数，使用 Decimal 避免浮点误差
- 不负责时效计算（→ eta）

### Upstream Dependencies
- oms_query（订单/渠道数据）
- cartonization（包裹列表/计费重量）

### Downstream Consumers
- shipping_plan_recommendation_workflow
- warehouse_allocation_recommendation_workflow
- cost

---

## 6. eta（✅ 已上线）

### Purpose
时效计算引擎。基于 8 组件 ETA 公式，计算订单从发货仓到收货地的预估送达时间。
支持 P50/P75/P90 三个风险化口径，内置美国市场默认 transit time 表。

### Use When
当用户请求以下任务时优先使用：

- 大概几天能到
- 哪个服务更快
- 这个方案时效如何
- 哪个仓发货更快
- ETA 是多少
- 准时率多少

### Inputs
- origin_state, dest_state（发货/收货州）
- carrier, service_level（承运商/服务级别）
- risk_level（P50/P75/P90）
- sla_hours（SLA 时限）
- warehouse context（积压量、截单时间、处理速度）
- carrier context（揽收时间、准点率、API transit time）
- risk_factors（天气、拥堵、承运商风险）

### Outputs
- ETAResult（总 ETA、各组件明细、三口径 ETA、OnTimeProbability、风险修正、degraded 标记）

### Constraints
- 无历史数据时降级估算，标注 confidence="estimated" 和 degraded=True
- 内置美国市场默认 transit time（州级距离分段）
- 不负责运费计算（→ shipping_rate）
- 不负责综合成本（→ cost）

### Upstream Dependencies
- oms_query
- shipping_rate
- warehouse_allocation

### Downstream Consumers
- cost
- shipping_plan_recommendation_workflow
- warehouse_allocation_recommendation_workflow

---

## 7. cost（✅ 已上线）

### Purpose
综合成本计算引擎。实现 Cost_total 公式（6 项成本）和 Score 公式（4 维加权评分），
支持容量惩罚（4 梯度）、拆单惩罚、归一化、多方案排序。

### Use When
当用户请求以下任务时优先使用：

- 这单成本是多少
- 哪个方案成本更低
- 比较不同仓库或承运商的总成本
- 综合评分是多少
- 方案排序

### Inputs
- plans（方案列表，每个方案含运费、仓操费、调拨费、仓数、容量利用率、风险成本、ETA、准时率）
- weights（评分权重：w_cost/w_eta/w_ontime/w_cap）
- split_penalty_unit（拆单惩罚单价）

### Outputs
- CostResult（各方案 Cost_total、Score、排名、推荐方案、成本明细、评分明细）

### Constraints
- 所有金额使用 Decimal，保留 2 位小数
- 不同量纲通过归一化后加权
- 不负责运费计算（→ shipping_rate）
- 不负责时效计算（→ eta）

### Upstream Dependencies
- cartonization
- shipping_rate
- eta
- warehouse_allocation

### Downstream Consumers
- shipping_plan_recommendation_workflow
- warehouse_allocation_recommendation_workflow

---

## 技能使用总原则

1. 查询型问题优先调用查询型 skill  
2. 分析型问题优先调用查询 + 分析 skill  
3. 推荐型问题优先调用多个计算/分析 skill 后再汇总  
4. 编排型问题必须按 workflow 执行  
5. 缺少关键输入时，不得伪造精确结果

## 当前可用状态总结

| Skill | 状态 | 类型 | 可执行脚本 |
|-------|------|------|-----------|
| cartonization | ✅ 已上线 | 工具型 | `scripts/cartonize.py` `scripts/validate_result.py` |
| oms_query | ✅ 已上线 | 查询型 | `scripts/query_oms.py` |
| oms_analysis | ✅ 已上线 | 分析型 | MCP tool `oms_analysis` |
| warehouse_allocation | ✅ 已上线 | 推荐型 | MCP tool `warehouse_allocate` |
| shipping_rate | ✅ 已上线 v2.0 | 推荐+计算型 | MCP tools `shipping_rate_query` `shipping_rate_execute` `shipping_rate_recommend` `shipping_rate_calculate` |
| eta | ✅ 已上线 | 计算型 | MCP tool `eta_calculate` |
| cost | ✅ 已上线 | 计算型 | MCP tool `cost_calculate` |

当 Agent 遇到需要调用规划中 skill 的请求时，必须：
1. 明确告知用户该能力暂未上线
2. 说明当前可提供的替代建议（如基于规则的经验建议）
3. 不得伪装成已有该能力