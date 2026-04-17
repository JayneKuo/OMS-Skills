# 实施计划：寻仓推荐引擎（allocation_engine）

## 概述

按依赖顺序实现寻仓推荐引擎 MVP。先建立数据模型和距离计算基础，再实现 P0 过滤、P2 评分、方案生成，
最后实现顶层 Engine 编排、白盒解释和 MCP tool 注册。

引擎代码路径：`.kiro/skills/warehouse-allocation/scripts/allocation_engine/`

## 任务列表

- [x] 1. 数据模型与基础设施
  - [x] 1.1 实现数据模型（models.py）
    - AllocationRequest, OrderItem, Address, ScoringWeights
    - Warehouse
    - AllocationResult, FulfillmentPlan, WarehouseAssignment
    - ScoredWarehouse, EliminatedWarehouse
    - _需求: AC-1~AC-4, AC-23~AC-28_

  - [x] 1.2 实现美国州级距离计算（distance.py）
    - US_STATE_COORDS 查表（50 州 + DC 中心点经纬度）
    - Haversine 公式
    - get_distance(wh_state, dest_state) → km
    - 成本估算：estimate_cost(distance_km) → $
    - 时效估算：estimate_days(distance_km) → days
    - _需求: AC-10, AC-11_

  - [x] 1.3 创建 __init__.py 和项目结构

  - [ ]* 1.4 编写属性测试：距离计算正确性
    - 同州距离=0
    - 距离 ≥ 0
    - 距离对称性：d(A,B) == d(B,A)
    - 未知州返回最大距离
    - _验证: Property P3_

- [x] 2. 数据加载层
  - [x] 2.1 实现 DataLoader（data_loader.py）
    - 从 oms_query_engine 加载仓库列表（facility/v2/page）
    - 从 oms_query_engine 加载库存（inventory/list）
    - 从 oms_query_engine 加载订单详情（sale-order/{orderNo}）
    - 将 API 数据映射为 Warehouse 模型
    - 合并库存到仓库对象（按 SKU + warehouse_id 聚合）
    - 记录降级标记（inventory_degraded 等）
    - _需求: AC-29~AC-32_

- [x] 3. 检查点 — 数据模型和加载层验证

- [x] 4. P0 硬约束过滤
  - [x] 4.1 实现 P0Filter（p0_filter.py）
    - P0-1: 仓状态检查（is_active + fulfillment_enabled）
    - P0-2: SKU 库存检查（onHandQty >= order_qty，记录缺货 SKU）
    - P0-3: 配送国家匹配（大小写不敏感）
    - P0-4: 温区匹配（可选，无数据时跳过）
    - P0-5: 淘汰原因记录（每个仓可能有多条原因）
    - 输出：通过的仓列表（含 can_fulfill_all / fulfillable_skus / missing_skus）+ 淘汰仓列表
    - _需求: AC-5~AC-9_

  - [ ]* 4.2 编写属性测试：P0 过滤正确性
    - 淘汰仓必须有至少一条原因（Property P1）
    - 通过的仓必须满足所有已检查的硬约束
    - can_fulfill_all=True 的仓对所有 SKU 都有足够库存（Property P2）
    - _验证: Property P1, P2_

- [x] 5. P2 多维评分
  - [x] 5.1 实现 P2Scorer（p2_scorer.py）
    - 对每个通过 P0 的仓计算距离、成本、时效
    - min-max 归一化（max==min 时返回 1.0）
    - 容量评分（有数据时用，无数据时 1.0）
    - 加权求和
    - 输出：ScoredWarehouse 列表（含 score_breakdown）
    - _需求: AC-10~AC-15_

  - [ ]* 5.2 编写属性测试：评分正确性
    - 所有维度得分 ∈ [0, 1]（Property P3）
    - 权重求和 == 1.0（Property P4）
    - 距离越近成本得分越高
    - _验证: Property P3, P4_

- [x] 6. 检查点 — P0 + P2 验证

- [x] 7. 方案生成
  - [x] 7.1 实现 PlanGenerator（plan_generator.py）
    - 单仓直发：从 can_fulfill_all 的仓中选 Top1（Property P5）
    - 多仓拆发：枚举 2 仓、3 仓组合 + 贪心 SKU 分配
    - 拆单惩罚：split_penalty × (仓数-1)
    - allow_split=False 处理（Property P8）
    - 无解兜底：返回失败 + 原因 + 建议
    - 备选方案：输出 Top2/Top3
    - _需求: AC-16~AC-22, AC-24_

  - [ ]* 7.2 编写属性测试：方案生成正确性
    - 单仓优先（Property P5）
    - 拆单上限（Property P6）
    - SKU 完整覆盖（Property P7）
    - allow_split 尊重（Property P8）
    - 库存不超卖（Property P2）
    - _验证: Property P2, P5, P6, P7, P8_

- [x] 8. 顶层引擎和结果构建
  - [x] 8.1 实现 WarehouseAllocationEngine（engine.py）
    - 编排：DataLoader → P0Filter → P2Scorer → PlanGenerator → ResultBuilder
    - 阻断检查：无地址/无商品行 → 返回错误
    - 异常捕获：任何步骤失败不崩溃，返回 error
    - _需求: AC-23, AC-27, AC-28_

  - [x] 8.2 实现 ResultBuilder（result_builder.py）
    - 构建 AllocationResult
    - 生成白盒解释文本（单仓/多仓/失败三种模板）
    - 汇总降级标记 → 计算置信度
    - _需求: AC-23~AC-28_

  - [ ]* 8.3 编写属性测试：降级标记与置信度一致性
    - data_degradation 非空时 confidence ≠ "high"（Property P9）
    - _验证: Property P9_

- [x] 9. MCP tool 注册
  - [x] 9.1 在 MCP server 中注册 warehouse_allocate tool
    - 参数：order_no, merchant_no, sku_list, country, state, allow_split
    - 调用 WarehouseAllocationEngine
    - 返回 AllocationResult JSON
    - _需求: AC-33~AC-35_

  - [x] 9.2 更新 mcp.json autoApprove 列表

  - [x] 9.3 更新 SKILL_REGISTRY（warehouse_allocation 标记为已上线）

- [x] 10. 最终检查点 — 端到端验证
  - 用真实 staging 数据测试完整流程
  - 验证白盒解释的可读性
  - 验证降级标记的完整性

## 备注

- 标记 `*` 的子任务为可选属性测试
- 距离计算使用硬编码的州级坐标，不依赖外部 API
- 复用 oms_query_engine 的 API client，不重复认证
- 所有降级标记汇总到 data_degradation 字段
- 9 个 Correctness Properties 覆盖核心不变量
