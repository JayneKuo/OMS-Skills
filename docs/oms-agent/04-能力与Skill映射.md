# Skill ↔ 现有能力映射表

> 将 oms-existing-capabilities-index.md 中的能力映射到既定 skill 体系。
> 能力编号引用自 capabilities index。
>
> 迭代记录:
> - v1.1 (2026-04-08): 修正 oms_query 映射，标注 DispatchLogVO 摘要级限制
> - v1.0 (2026-04-07): 初始版本
>
> 最后更新：2026-04-08

---

## 1. cartonization

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| H1 | order_item_data | 数据桥接 | OrderItemDO 含 length/width/height/weight/fragile/stackable/containBattery，可映射到装箱引擎 SKUItem |
| E1 | one_to_one_mapping (SKU/UOM) | 部分复用 | SKU 映射、UOM 映射，装箱前需要标准化 SKU |
| H9 | sku_uom_mapping | 数据桥接 | SKU::UOM 复合键处理 |

已有独立实现：cartonization_engine/（Python），不依赖 OMS Java 代码。
OMS 代码为 cartonization 提供的是**输入数据源**，而非计算逻辑。

## 2. oms_query

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| A5 | dispatch_log_query | 直接调用 API | GET /dispatch-log/{eventId}，返回 DispatchLogVO 摘要 |
| G3 | dispatch_result_log | 需扩展 API | 完整 DispatchLogDO 含策略/日志/拆单明细，当前 API 只返回摘要 |
| D4 | dispatch_status_tracking | 直接读取 | 拆单状态（1=SUCCESS, 2=NO_WAREHOUSE, -1=EXCEPTION） |
| F3 | delivery_status_update | 需扩展 API | 出库单状态在完整 DispatchLogDO 中 |
| H1 | order_item_data | 需扩展 API | 订单商品行在 dispatch 请求中，非独立查询 |

当前限制：GET /dispatch-log/{eventId} 返回的是 DispatchLogVO 摘要级数据（orderNo/eventId/status/summary/eventTime），不含完整拆单明细。详见 `09-order-query-设计.md`。

## 3. order_analysis

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| G2 | dispatch_process_log | 直接读取 | 拆单过程日志（逐步操作记录） |
| D5 | dispatch_exception_msg | 直接读取 | 异常原因 |
| G1 | oas_log_aspect | 直接读取 | 接口调用日志 |
| D4 | dispatch_status_tracking | 直接读取 | 状态流转分析 |
| B3 | warehouse_inventory_check | 逻辑复用 | 库存不足根因分析 |
| B4 | warehouse_fulfillment_check | 逻辑复用 | 全量发货校验失败分析 |
| G3 | dispatch_result_log | 直接读取 | 含策略命中记录（filterStrategies/dispatchStrategies） |

## 4. warehouse_allocation

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| A1 | sales_order_dispatch | 直接调用接口 | /dispatch/sales-order 是核心入口 |
| B1 | warehouse_filter_by_zipcode | 策略复用 | 邮编过滤 |
| B2 | warehouse_filter_by_country | 策略复用 | 国家过滤 |
| B3 | warehouse_inventory_check | 逻辑复用 | 库存校验 |
| B4 | warehouse_fulfillment_check | 逻辑复用 | 全量发货校验 |
| B5 | warehouse_distance_data | 数据复用 | 距离数据 |
| B6 | closest_warehouse_selection | 策略复用 | 最近仓 |
| C1 | no_split_strategy | 策略复用 | 单仓不拆 |
| C2 | minimal_split_strategy | 策略复用 | 允许拆单 |
| C3 | specify_warehouse_strategy | 策略复用 | 指定仓 |
| C4 | sku_specify_warehouse | 策略复用 | SKU 指定仓 |
| C5 | custom_rule_dispatch | 策略复用 | 自定义规则 |
| C7 | default_rule_config | 配置复用 | 默认规则 |
| C8 | custom_rule_config | 配置复用 | 自定义规则配置 |
| D1 | one_warehouse_backup | 策略复用 | 兜底-最高优先级仓 |
| D2 | multi_warehouse_backup | 策略复用 | 兜底-多仓 |
| D3 | exception_backup | 策略复用 | 兜底-异常挂起 |
| F1 | one_warehouse_one_delivery | 策略复用 | 出库单生成 |
| E1 | one_to_one_mapping | 部分复用 | 分仓前的 SKU/承运商映射 |
| E2 | condition_mapping | 部分复用 | 条件映射影响仓库选择 |

## 5. shipping_rate

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| E4 | shipping_mapping_execute | 直接调用 | /mapping/shipping/execute 核心能力 |
| E3 | shipping_mapping_rule | 配置查询 | 规则 CRUD |
| E1 | one_to_one_mapping | 直接复用 | Carrier/ShipMethod/DeliveryService/FreightTerm 映射 |
| E2 | condition_mapping | 直接复用 | 多条件→承运商/服务映射 |
| E5 | carrier_data | 数据复用 | 承运商基础数据 |
| E6 | specify_carrier_delivery | 部分复用 | 指定承运商逻辑 |

## 6. eta（✅ 已实现）

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| B5 | warehouse_distance_data | 数据复用 | 仓库→目的地距离 |
| E5 | carrier_data | 数据复用 | 承运商信息 |

已有独立实现：ETAEngine（Python），基于 8 组件 ETA 公式计算预估送达时间。
- 8 组件：T_queue + T_cutoff_wait + T_process + T_handover + T_transit + T_last_mile + T_weather + T_risk_buffer
- 支持 P50/P75/P90 三个风险化口径
- 内置美国市场默认 transit time 表（州级距离分段）
- 无历史数据时降级估算，标注 confidence="estimated" 和 degraded=True
- OMS 代码为 eta 提供的是**输入数据源**（距离、承运商信息），而非计算逻辑

## 7. cost（✅ 已实现）

| 能力编号 | capability_name | 复用方式 | 说明 |
|---------|----------------|---------|------|
| B5 | warehouse_distance_data | 数据复用 | 距离影响运费 |
| E4 | shipping_mapping_execute | 逻辑复用 | 运费条件映射 |

已有独立实现：CostEngine（Python），实现综合成本计算和多方案评分排序。
- Cost_total 公式（6 项成本）：Freight_order + Cost_warehouse + Cost_transfer + Penalty_split + Penalty_capacity + Cost_risk
- Score 公式（4 维加权评分）：w_cost × Normalize(Cost_total) + w_eta × Normalize(ETA) + w_ontime × OnTimeProbability + w_cap × Normalize(RemainCapacity)
- 容量惩罚 4 梯度（0-70% 无惩罚 / 70-85% 线性 / 85-95% 加速 / 95-100% 重度）
- 拆单惩罚：(N_warehouses - 1) × split_penalty_unit
- 归一化后加权排序，输出 Top-N 推荐方案
- OMS 代码为 cost 提供的是**输入数据源**（距离、映射数据），而非计算逻辑

---

## 能力覆盖度总结

| skill | 可直接复用的能力数 | 部分复用 | 仅数据桥接 | 无现有实现 |
|-------|-----------------|---------|-----------|-----------|
| cartonization | 0 | 1 | 2 | — (已有独立 Python 实现) |
| oms_query | 5 | 0 | 0 | — |
| order_analysis | 7 | 0 | 0 | — |
| warehouse_allocation | 18 | 2 | 0 | — |
| shipping_rate | 5 | 1 | 0 | — (已有独立 Python 实现 v2.0) |
| eta | 0 | 0 | 2 | — (已有独立 Python 实现，内置美国默认 transit time 表) |
| cost | 0 | 0 | 2 | — (已有独立 Python 实现，Cost_total + Score 公式) |
