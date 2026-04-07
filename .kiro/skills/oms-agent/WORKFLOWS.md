# OMS Agent Workflows

本文档定义 OMS Agent 在复杂业务场景下的标准编排流程。
当用户的问题不能由单个 skill 直接完成时，Agent 应参考本文件进行多 skill 编排。

---

## 1. order_query_workflow

### Trigger
当用户请求：

- 查询订单
- 订单当前状态是什么
- 订单明细是什么
- 这个订单进行到哪一步了

### Steps
1. 识别订单号或相关订单标识
2. 调用 `order_query`
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
- 为什么没有算出运费

### Steps
1. 调用 `order_query` 获取订单状态和上下文
2. 调用 `order_analysis` 获取失败节点和根因
3. 如与仓分配有关，可调用 `warehouse_allocation` 检查规则和候选仓
4. 如与物流有关，可调用 `cartonization` / `shipping_rate` / `eta` 检查依赖环节
5. 汇总输出：
   - 问题类型
   - 根因
   - 影响步骤
   - 是否可重试
   - 修复建议

### Outputs
- issue_type
- root_cause
- impacted_step
- recommendation
- retryable_flag
- manual_action_needed

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
1. 调用 `order_query` 获取订单、商品、目的地
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

## 4. shipping_plan_recommendation_workflow

### Trigger
当用户请求：

- 这单怎么发最合适
- 走哪个承运商
- 用什么服务
- 这票货怎么装箱并发货
- 给我一个完整发货方案

### Steps
1. 调用 `order_query` 获取订单、商品、目的地
2. 获取 SKU 主数据与物理属性
3. 调用 `cartonization` 生成装箱方案
4. 调用 `shipping_rate` 获取不同承运商/服务报价
5. 调用 `eta` 获取不同承运商/服务时效
6. 调用 `cost` 计算综合成本
7. 输出推荐方案：
   - 装箱方案
   - 推荐承运商
   - 推荐服务
   - 预计运费
   - 预计时效
   - 推荐理由
   - 备选方案

### Outputs
- package_plan
- recommended_carrier
- recommended_service
- estimated_shipping_cost
- estimated_eta
- total_cost
- recommendation_reason
- alternative_options

---

## 5. warehouse_plus_shipping_recommendation_workflow

### Trigger
当用户请求：

- 这单该分哪个仓、走哪个承运商、用什么服务
- 给我完整推荐方案
- 从仓库到物流服务一起推荐

### Steps
1. 调用 `order_query`
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