# OMS Agent Workflows

本文档定义 OMS Agent 在复杂业务场景下的标准编排流程。
当用户的问题不能由单个 skill 直接完成时，Agent 应参考本文件进行多 skill 编排。

---

## 1. oms_query_workflow

### Trigger
当用户请求：

- 查询订单
- 订单当前状态是什么
- 订单明细是什么
- 这个订单进行到哪一步了

### Steps
1. 识别订单号或相关订单标识
2. 调用 `oms_query`
3. 获取订单头、订单行、订单状态、履约状态、发货状态
4. 输出关键结果
5. 如有必要，补充业务解释

### Outputs
- order_header
- order_lines
- order_status
- fulfillment_status
- shipment_status
- exception_summary

---

## 2. order_exception_diagnosis_workflow

### Trigger
当用户请求：

- 这个订单为什么失败
- 为什么没有分仓
- 为什么没有发货
- 为什么没有生成标签
- 为什么订单总是异常

### Steps（单订单）
1. 调用 `oms_query`（intent=panorama）获取订单全景
2. 调用 `oms_analysis`（intent=root_cause, identifier=订单号）获取根因 + 影响 + 修复建议
3. 按 OUTPUT_POLICY Level 2 模板输出

### Steps（批量异常）
1. 调用 `oms_analysis`（query="为什么订单总是异常"）
   - IntentDetector 自动扩展为 batch_pattern + impact_assessment + fix_recommendation
   - DataFetcher 自动拉取订单列表 + 抽样事件日志
2. 按 OUTPUT_POLICY Level 2 模板输出根因 + 影响范围 + 修复建议

### Outputs
- root_cause（根因）
- affected_skus（涉及的 SKU）
- impact_scope（影响范围：订单数、仓库数）
- severity（严重程度）
- recommendations（修复建议，含前置条件和风险）

---

## 3. warehouse_allocation_recommendation_workflow

### Trigger
当用户请求：

- 这单应该分哪个仓
- 推荐发货仓
- 为什么分到这个仓
- 哪个仓最优
- 这个订单从哪个仓发最合理

### Steps
1. 调用 `oms_query` 获取订单、商品、目的地
2. 调用库存/仓能力相关能力，获取库存与仓能力
3. 调用 `warehouse_allocation` 生成候选仓和推荐仓
4. 如用户要求完整发货建议，则继续：
   - 调用 `cartonization` 获取装箱方案
   - 调用 `shipping_rate` 计算运费
   - 调用 `eta` 计算时效
   - 调用 `cost` 计算综合成本
5. 输出：
   - 推荐仓
   - 候选仓
   - 如果有完整建议，则补充推荐承运商、服务和理由

### Outputs
- recommended_warehouse
- candidate_warehouses
- allocation_reason
- recommended_carrier
- recommended_service
- recommendation_reason
- risks_and_constraints

---

## 4. shipping_plan_recommendation_workflow（✅ 已实现）

### Trigger
当用户请求：

- 这单怎么发最合适
- 走哪个承运商
- 用什么服务
- 这票货怎么装箱并发货
- 给我一个完整发货方案

### MCP Tool
`shipping_plan_recommend(order_no, merchant_no?, risk_level?)`

### 实现
`workflow_engine/shipping_plan.py` → `ShippingPlanWorkflow.run()`

### Pipeline Steps
1. **oms_query** → 调用 OMSQueryEngine 获取订单全景（SKU、数量、地址、仓库）
2. **build_packages** → 构建包裹信息（无 SKU 物理数据时用默认重量 0.9kg 估算，标注 degraded）
3. **shipping_rate** → 调用 DefaultUSRateProvider 做多承运商运费比价（UPS Ground / FedEx Ground / USPS Priority）
4. **eta** → 调用 ETAEngine 为每个承运商方案计算 ETA（支持 P50/P75/P90 口径）
5. **cost_score** → 调用 CostEngine 做综合评分排序（4 维加权：成本/时效/准时率/容量）
6. **输出** → Top-3 推荐方案 + 每步执行状态 + 白盒解释

### 降级策略
- 每一步失败不阻断后续步骤，降级继续
- 无 SKU 重量数据 → 使用默认 0.9kg/件估算
- 无仓库地址 → 默认 NJ 州
- cost_engine 失败 → 降级为仅按运费排序
- 结果中标注所有降级步骤和原因

### Outputs
- order_summary（订单摘要：SKU、数量、地址、仓库）
- package_summary（包裹摘要：包裹数、重量）
- plans[]（Top-3 方案：承运商、运费、ETA、准时率、Score、排名）
- recommended_plan（推荐方案）
- pipeline_steps[]（每步执行状态：名称、成功/失败、耗时、降级标记）
- degraded / degraded_reasons（降级标记和原因）
- explanation（白盒解释）

---

## 5. warehouse_plus_shipping_recommendation_workflow

### Trigger
当用户请求：

- 这单该分哪个仓、走哪个承运商、用什么服务
- 给我完整推荐方案
- 从仓库到物流服务一起推荐

### Steps
1. 调用 `oms_query`
2. 调用库存/仓能力相关能力
3. 调用 `warehouse_allocation`
4. 调用 `cartonization`
5. 调用 `shipping_rate`
6. 调用 `eta`
7. 调用 `cost`
8. 比较多个候选组合：
   - 仓库 + 承运商 + 服务
9. 输出最终推荐：
   - 推荐仓库
   - 推荐承运商
   - 推荐服务
   - 推荐理由
   - 成本与时效差异
   - 备选方案

### Outputs
- recommended_warehouse
- recommended_carrier
- recommended_service
- package_plan
- estimated_shipping_cost
- estimated_eta
- total_cost
- recommendation_reason
- alternative_options

---

## 6. workflow 使用原则

1. 能单 skill 解决的问题，不要强行走 workflow  
2. 涉及多个业务维度的推荐问题，必须走 workflow  
3. workflow 中每一步都要基于前一步结果，不得跳步  
4. 如果某个关键步骤失败，必须明确说明失败位置和影响  
5. 如果数据不完整，可以输出估算型 workflow 结果，但必须标记为估算  
6. 最终输出必须包含：
   - 结果
   - 原因
   - 风险/限制