---
name: batch-reallocation
description: Use when users need to analyze and safely execute OMS batch reallocation for imported, exception, deallocated, or on-hold orders with explicit confirmation.
---

# batch-reallocation

## Purpose
批量重新分仓能力。先分析订单是否适合重新分仓，再通过聊天窗口确认表单视图收集用户选择，最后在显式确认后执行真实 OMS recover 接口。面向最终用户默认只输出业务摘要、资格判断和确认信息，不暴露内部结构化 payload 或实现细节。

## Use When
当用户请求以下任务时优先使用：

- 批量执行重新分仓
- import / exception 订单长时间未分仓，需要批量恢复分仓
- deallocated 订单需要重新分仓
- on hold 订单需要释放后重新分仓
- 想先分析哪些订单可重分，再由用户决定执行哪些订单 / SKU

## Trigger Boundary
仅处理以下场景：

- `Imported`
- `Exception`
- `Deallocated`
- `On Hold`

不处理：

- 已完全履约、`unfulfilled_qty = 0` 的 SKU
- 未经确认的危险执行
- 其他非 recover / reallocation 类型动作

## Required Flow
1. query / resolve 订单
2. analyze 订单状态、recover 能力、SKU 未履约数量
3. 在内部生成结构化执行上下文，并向用户返回聊天窗口确认表单视图
4. 收集用户批量选择
5. 显式确认
6. execute 并返回业务执行结果与执行后复核结论

## Inputs
- `identifiers_json`：订单号或可解析订单标识列表
- `merchant_no`：可选；未传时沿用运行时环境
- 执行阶段 `request_json`：
  - `decisions[].order_no`
  - `decisions[].action_mode`
  - `decisions[].selected_skus[]`
  - `decisions[].release_hold`

## Outputs
### User-facing analysis output
- 中文业务摘要
- 逐单资格判断
- 确认表单视图（由 `user_view_builder.py` 生成用户视图模型后组织输出）
- `requires_confirmation = true`
- `next_action = collect_user_decision`

### Internal execution context
- `form_type = batch-reallocation-analysis`
- `groups[]`：按 `imported / exception / deallocated / on_hold / ineligible` 分组
- `selection_mode = order | sku`
- `warnings[]`
- 用于执行的结构化 payload

### User-facing execution output
- `submitted_orders`
- `succeeded_orders`
- `partial_succeeded_orders`
- `failed_orders`
- `skipped_orders`
- `warnings`
- 执行后业务复核结论

## Scenario Rules
- `Imported` / `Exception`：默认整单候选，允许批量勾选订单执行
- `Deallocated`：需要基于 SKU 未履约情况判断，混合履约场景优先走 SKU 级选择
- `On Hold`：先释放 hold，再 recover；必要时走 SKU 级选择
- 所有场景都只能处理 `unfulfilled_qty != 0` 的 SKU

## Constraints
- 绝不允许超发
- 执行前必须再次读取订单状态，避免 stale state
- 缺少 `USER` 时可分析，不可执行
- 缺少基础运行时环境（URL / tenant / token）时不可分析
- 面向用户只暴露业务动作，不暴露内部模块实现
- 默认不向最终用户展示 JSON、内部 payload、endpoint、原始 API response、MCP 参数或内部字段映射
- 只有用户明确要求调试信息时，才可额外提供技术细节，并需明确标注为调试输出

## Runtime Env
兼容 OMS 现有 skill 的运行时变量：

- `OMS_BASE_URL` / `baseUrl` / `BASE_URL`
- `OMS_TENANT_ID` / `TENANT_ID` / `tenantId` / `x-tenant-id`
- `CRM_MERCHANT_CODE` / `OMS_MERCHANT_NO` / `merchantNo`
- `OMS_ACCESS_TOKEN` / `OMS_SESSION_TOKEN` / `ACCESS_TOKEN`
- `USER` / `username` / `user`

## MCP Tools
- `batch_reallocation_analyze`
- `batch_reallocation_execute`

## References
- `references/form-protocol.md`
- `references/api-mapping.md`
