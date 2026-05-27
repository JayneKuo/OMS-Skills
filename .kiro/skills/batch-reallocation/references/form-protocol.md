# batch-reallocation form protocol

## Purpose
该文档定义 batch-reallocation 的双层协议：一层是 agent 内部使用的结构化执行上下文，另一层是面向最终用户的业务输出约束。重点不是只返回接口成功，而是按真实用户使用路径输出：查询结果、资格判断、确认表单、执行结果、执行后复查与最终结论。

## Internal analysis payload
以下结构仅供 agent / MCP 内部编排使用，不属于默认用户可见输出：
- `form_type`: always `batch-reallocation-analysis`
- `groups[]`: scenario groups for imported / exception / deallocated / on_hold / ineligible
- `groups[].selection_mode`: `order` or `sku`
- `groups[].orders[].skus[]`: includes quantity and eligibility fields
- `warnings[]`: non-blocking safety notes
- `requires_confirmation`: always true before execution
- `next_action`: `collect_user_decision`

## Internal execution request payload
以下结构仅供执行阶段内部使用：
- `confirmed`: must be `true` before execution
- `decisions[]`
- `decisions[].order_no`
- `decisions[].action_mode`
- `decisions[].selected_skus[]`
- `decisions[].release_hold`

## User-facing output requirements
每次真实使用都必须按以下 5 段输出，不能跳步，不能只贴原始 JSON。

说明：
- `form_builder.py` 和 `result_formatter.py` 继续服务于内部协议与 MCP 返回。
- `user_view_builder.py` 负责把分析结果和执行结果转换为默认用户可见的业务视图模型。
- 最终用户默认不直接看到内部 JSON，agent 应优先消费用户视图模型组织业务输出。

### 1. 查询结果
必须明确：
- `orderNo`
- 当前状态
- 异常 / 风险摘要
- SKU 的 `ordered / fulfilled / unfulfilled`
- 是否允许进入执行阶段

### 2. 资格判断
必须明确：
- 当前场景是否支持
- 整单还是 SKU 级执行
- 哪些订单 / SKU 可执行
- 哪些订单 / SKU 不可执行
- 风险提示

### 3. 确认表单
必须输出面向用户的确认表单视图，而不是结构化 JSON，并明确：
- 场景分组
- action mode
- 哪些订单 / SKU 可选
- 用户当前可以修改或选择的内容
- 只读事实
- `requires_confirmation = true`

### 4. 执行结果
必须用业务语言明确：
- 是否已执行
- 执行了什么动作
- 哪些订单 / SKU 被提交处理
- 是否需要人工继续处理

### 5. 执行后复查与最终结论
执行后不能只看接口 `code = 0`。
必须重新检查：
- 订单状态是否推进
- 未履约数量是否变化
- recover / dispatch 结果是否变化
- 日志中是否出现新的成功或失败证据

最终结论只允许使用以下判断标准：
- **执行成功**：复查证明业务状态真实推进
- **提交成功但业务未生效**：接口成功，但订单状态 / SKU / recover 结果未变化
- **执行失败**：接口直接报错，或复查出现明确失败证据

## Default visibility rule
默认情况下，不向最终用户展示 JSON、内部 payload、OMS endpoint、原始 API response、MCP 参数或内部字段映射。
只有当用户明确要求查看调试细节时，才可额外提供，并必须先说明这些内容属于技术调试信息。
