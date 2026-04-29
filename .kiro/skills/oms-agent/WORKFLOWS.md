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
2. 调用 `warehouse_allocation` 生成候选仓和推荐仓
3. 输出：
   - 推荐仓
   - 候选仓
   - 推荐理由
   - 风险与约束
4. 如果用户要求完整发货建议，则切换到 `fulfillment_planner_workflow`

### Outputs
- recommended_warehouse
- candidate_warehouses
- allocation_reason
- risks_and_constraints

---

## 4. fulfillment_planner_workflow（✅ 当前主编排层）

### Trigger
当用户请求：

- 这单怎么发最合适
- 给我一个完整发货方案
- 这单该分哪个仓、怎么装箱、走哪个承运商
- 比较几个履约方案的成本、时效、风险

### Steps
1. 调用 `oms_query` 获取订单、商品、地址、当前履约上下文
2. 调用 `warehouse_allocation` 生成单仓 / 多仓候选方案
3. 对每个候选方案调用 `cartonization` 生成装箱结果
4. 调用 `shipping_rate` 计算包裹级与订单级运费
5. 调用 `eta` 计算 ETA、准时率、时效风险
6. 调用 `cost` 做综合评分、排序和推荐
7. 输出推荐方案、备选方案、风险与假设

### Outputs
- recommended_plan
- alternative_plans
- warehouse_summary
- package_summary
- freight_summary
- eta_summary
- cost_summary
- risks_and_constraints
- degraded / confidence

---

## 5. workflow 使用原则

1. 能单 skill 解决的问题，不要强行走 workflow  
2. 涉及多个业务维度的推荐问题，优先走 `fulfillment_planner_workflow`  
3. workflow 中每一步都要基于前一步结果，不得跳步  
4. 如果某个关键步骤失败，必须明确说明失败位置和影响  
5. 如果数据不完整，可以输出估算型 workflow 结果，但必须标记为估算或 degraded  
6. 最终输出必须包含：
   - 结果
   - 原因
   - 风险/限制
