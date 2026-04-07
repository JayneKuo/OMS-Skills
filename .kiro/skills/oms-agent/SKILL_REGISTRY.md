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
- order_query
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

## 2. order_query（🔲 规划中）

### Purpose
查询订单基础信息、订单状态、订单明细、履约状态和关键业务节点。

### Use When
当用户请求以下任务时优先使用：

- 查询订单
- 查看订单状态
- 查看订单明细
- 订单当前在哪个阶段
- 某个订单是否已分仓 / 已发货 / 已取消

### Inputs
- order_no
- customer_order_no
- external_order_no

### Outputs
- order_header
- order_lines
- order_status
- fulfillment_status
- allocated_warehouse
- shipment_status
- exception_summary

### Constraints
- 仅返回系统中可查到的真实订单数据
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

## 3. order_analysis（🔲 规划中）

### Purpose
针对订单异常、失败、卡单、规则命中等场景，分析根因并给出处理建议。

### Use When
当用户请求以下任务时优先使用：

- 这个订单为什么失败
- 为什么没有分仓
- 为什么没有生成标签
- 为什么没有算出运费
- 为什么没有推送成功

### Inputs
- order_no
- order_context
- status_history
- error_logs
- rule_hit_logs
- dependency_status

### Outputs
- issue_type
- root_cause
- impacted_step
- recommendation
- retryable_flag
- manual_action_needed

### Constraints
- 分析结论必须基于日志、状态和规则
- 不得编造失败原因
- 若证据不足，必须明确说明无法确定唯一根因

### Upstream Dependencies
- order_query
- exception_log_query
- rule_log_query

### Downstream Consumers
- oms_main_agent
- order_exception_diagnosis_workflow

---

## 4. warehouse_allocation（🔲 规划中）

### Purpose
根据订单目的地、库存、仓库能力、业务规则等因素，输出仓库分配建议。

### Use When
当用户请求以下任务时优先使用：

- 这单该分哪个仓
- 推荐发货仓
- 为什么分到这个仓
- 哪个仓最优

### Inputs
- destination
- sku_list
- qty_list
- inventory_snapshot
- warehouse_capability
- allocation_rules

### Outputs
- recommended_warehouse
- candidate_warehouses
- allocation_reason
- rejected_warehouses

### Constraints
- 不负责计算完整发货成本
- 不负责最终物流推荐
- 如果缺少库存或仓能力数据，只能输出初步建议

### Upstream Dependencies
- order_query
- inventory_query
- warehouse_capability_query

### Downstream Consumers
- warehouse_allocation_recommendation_workflow
- shipping_plan_recommendation_workflow

---

## 5. shipping_rate（🔲 规划中）

### Purpose
根据发货地、收货地、包裹信息、承运商和服务，计算运费结果。

### Use When
当用户请求以下任务时优先使用：

- 运费是多少
- 不同承运商哪个更便宜
- 装箱后怎么计算运费
- 哪个服务价格更优

### Inputs
- origin
- destination
- package_list
- carrier
- service
- billing_context

### Outputs
- rate_amount
- surcharge_breakdown
- billable_weight
- pricing_notes

### Constraints
- 必须基于真实包裹数据或明确的估算包裹数据
- 不直接做最终推荐结论

### Upstream Dependencies
- cartonization
- order_query

### Downstream Consumers
- shipping_plan_recommendation_workflow
- warehouse_allocation_recommendation_workflow

---

## 6. eta（🔲 规划中）

### Purpose
根据发货地、收货地、承运商、服务和业务规则，计算预计时效。

### Use When
当用户请求以下任务时优先使用：

- 大概几天能到
- 哪个服务更快
- 这个方案时效如何
- 哪个仓发货更快

### Inputs
- origin
- destination
- carrier
- service
- shipping_calendar
- warehouse_cutoff_time

### Outputs
- estimated_delivery_days
- estimated_delivery_date
- cutoff_impact
- eta_notes

### Constraints
- 不得编造时效结果
- 若缺少服务级别或路由条件，只能输出估算时效

### Upstream Dependencies
- order_query
- shipping_rate
- warehouse_allocation

### Downstream Consumers
- shipping_plan_recommendation_workflow
- warehouse_allocation_recommendation_workflow

---

## 7. cost（🔲 规划中）

### Purpose
根据仓配成本、物流成本、包装成本等，输出综合成本结果。

### Use When
当用户请求以下任务时优先使用：

- 这单成本是多少
- 哪个方案成本更低
- 比较不同仓库或承运商的总成本

### Inputs
- warehouse_cost
- packaging_cost
- shipping_cost
- operational_cost
- scenario_options

### Outputs
- total_cost
- cost_breakdown
- scenario_comparison
- cost_notes

### Constraints
- 必须基于真实或明确的估算成本输入
- 不单独做业务最终推荐

### Upstream Dependencies
- cartonization
- shipping_rate
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
| order_query | 🔲 规划中 | 查询型 | — |
| order_analysis | 🔲 规划中 | 分析型 | — |
| warehouse_allocation | 🔲 规划中 | 推荐型 | — |
| shipping_rate | 🔲 规划中 | 计算型 | — |
| eta | 🔲 规划中 | 计算型 | — |
| cost | 🔲 规划中 | 计算型 | — |

当 Agent 遇到需要调用规划中 skill 的请求时，必须：
1. 明确告知用户该能力暂未上线
2. 说明当前可提供的替代建议（如基于规则的经验建议）
3. 不得伪装成已有该能力