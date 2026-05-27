# batch-reallocation user-view-builder 设计文档

## 1. 概述

本设计文档定义 `batch-reallocation` 的“用户视图构建层”最小落地方案。

目标不是重写现有分析或执行协议，而是在保留内部 JSON 协议的前提下，新增一层稳定的用户可见视图模型，避免把内部 payload、endpoint、原始 API response、MCP 参数或字段映射直接暴露给最终用户。

核心原则：
- 内部协议继续存在
- 用户视图单独建模
- agent 只消费脱敏后的用户视图模型
- prompt 约束输出格式，代码约束输出边界
- 不破坏现有 MCP JSON 协议和已有测试基线

本设计只覆盖 `batch-reallocation` 当前工作流，不扩展到其他 oms-agent skill。

---

## 2. 当前问题

当前 `batch-reallocation` 已经具备两类内部能力：

1. 分析结果结构化：`form_builder.py`
2. 执行结果结构化：`result_formatter.py`

同时，MCP 工具当前直接返回 JSON：
- `batch_reallocation_analyze(...)` 返回分析 payload JSON
- `batch_reallocation_execute(...)` 返回执行结果 JSON

这套设计对工具调用、测试和前端协议是有效的，但它天然偏“内部协议视角”，存在以下问题：

- agent 很容易直接把 JSON 转发给用户
- prompt 虽然已经禁止直接展示内部 JSON，但代码层没有显式的“用户视图边界”
- 文档层已经区分“内部 payload”和“确认表单视图”，代码层尚未显式落地
- 未来如果接聊天 UI、卡片 UI 或其他前端呈现，缺少统一的用户视图模型

因此需要补上一层明确的 `user_view_builder`。

---

## 3. 设计目标

### 3.1 需要达成的目标

- 为 `batch-reallocation` 新增用户侧 view model 生成能力
- 保留现有 `form_builder.py` / `result_formatter.py` / MCP JSON 返回协议
- agent 后续应优先基于用户视图模型组织 5 段业务输出
- 用户默认看不到以下内容：
  - 内部 payload
  - endpoint
  - 原始 API response
  - MCP 参数
  - 内部字段映射
  - 实现编排过程

### 3.2 明确不做的事

- 不修改现有 recover / release hold / eligibility 的业务判断逻辑
- 不重写 MCP server 工具协议
- 不把脚本层直接写死为最终 markdown 输出器
- 不扩展成通用 OMS 输出框架

---

## 4. 分层设计

### 4.1 保留的内部协议层

现有内部协议继续保留：

- `batch_reallocation/form_builder.py`
- `batch_reallocation/result_formatter.py`
- `mcp_server.py` 中 `batch_reallocation_analyze` / `batch_reallocation_execute` 的 JSON 返回

职责：
- 为 MCP 调用、脚本集成、自动化测试、前端协议保留完整结构化数据
- 表达完整分析字段与执行字段
- 不承担最终用户展示职责

### 4.2 新增的用户视图层

新增文件：
- `batch_reallocation/user_view_builder.py`

职责：
- 接收分析结果或执行结果对象
- 输出脱敏后的用户视图模型
- 仅保留用户展示所需业务信息
- 明确过滤技术字段和内部协议字段

### 4.3 agent 表达层

agent 继续负责最终输出组织，但后续应优先消费 `user_view_builder.py` 的产物。

职责：
- 将用户视图模型组织成固定 5 段输出
- 补充极少量上下文串联语句
- 不再直接把内部 JSON 当作用户输出来源

边界定义：
- 脚本层决定“哪些信息可以给用户看”
- agent 层决定“这些信息如何按业务语言讲出来”

---

## 5. 用户视图模型设计

`user_view_builder.py` 不直接输出最终 markdown，而是输出可复用的 view model。

这样可以同时支持：
- 聊天窗口 markdown
- 前端卡片渲染
- 后续结构化 UI 适配

### 5.1 Analysis view

建议提供：
- `orders[]`
  - `order_no`
  - `current_status`
  - `scenario_group`
  - `exception_or_hold_summary`
  - `sku_facts[]`
    - `sku`
    - `ordered_qty`
    - `fulfilled_qty`
    - `unfulfilled_qty`
  - `eligibility`
    - `supported`
    - `action_mode`
    - `executable_scope_summary`
    - `ineligible_scope_summary`
    - `reasons[]`
    - `risks[]`
- `global_warnings[]`
- `requires_confirmation`

约束：
- 不直接暴露 `form_type`
- 不直接暴露 `next_action`
- 不直接暴露内部 `eligible` 判定字段树
- 只保留业务可理解摘要

### 5.2 Confirmation view

建议提供：
- `order_nos[]`
- `scenario_groups[]`
- `action_mode_summary`
- `selected_skus_by_order[]`
- `includes_release_hold`
- `editable_choices[]`
- `readonly_facts[]`
- `risks[]`
- `status = waiting_for_confirmation`

职责：
- 明确告诉用户当前需要确认什么
- 明确哪些内容可改、哪些只是只读事实
- 不暴露底层 request payload

### 5.3 Execution view

建议提供：
- `executed`
- `submitted_orders[]`
- `succeeded_orders[]`
- `partial_succeeded_orders[]`
- `failed_orders[]`
- `skipped_orders[]`
- `follow_up_actions[]`
- `warnings[]`

职责：
- 面向用户解释“这次到底做了什么”
- 不暴露 endpoint、payload、原始 response

### 5.4 Final conclusion view

如果当前执行结果对象已经包含足够复核信息，建议补充：
- `conclusion`
  - `执行成功`
  - `提交成功但业务未生效`
  - `执行失败`
- `evidence[]`
- `business_changes[]`

如果当前模型暂时不够承载，可先把这一层并入 execution view，不强制一开始单独拆出函数。

---

## 6. 函数设计

建议最小提供以下函数：

- `build_analysis_view(result: AnalyzeResponse) -> dict`
- `build_confirmation_view(result: AnalyzeResponse, decisions: dict | None = None) -> dict`
- `build_execution_view(result: ExecuteResponse) -> dict`

可选：
- `build_final_conclusion_view(result: ExecuteResponse) -> dict`

### 6.1 命名原则

- 使用 `build_*_view` 命名，而不是 `format_*_markdown`
- 强调这是“用户视图模型构建”，不是最终渲染
- 避免命名上和 `form_builder.py` / `result_formatter.py` 混淆

### 6.2 输出原则

所有 `build_*_view` 输出必须满足：
- 业务字段优先
- 技术字段默认过滤
- 稳定、可测试
- 允许 agent 在不重新理解底层结构的情况下直接消费

---

## 7. 接入策略

### 7.1 第一阶段

第一阶段不改动 MCP 协议：
- `batch_reallocation_analyze(...)` 继续返回 JSON payload
- `batch_reallocation_execute(...)` 继续返回 JSON summary

原因：
- 不破坏现有脚本调用方
- 不破坏现有测试
- 不影响潜在前端协议依赖

### 7.2 第二阶段

在 agent 输出链路中，优先引入 `user_view_builder.py`：

1. agent 获取分析或执行结果
2. 先转换成 user-facing view model
3. 再输出固定 5 段业务内容：
   1. 查询结果
   2. 资格判断
   3. 确认表单
   4. 执行结果
   5. 执行后校验与最终结论

### 7.3 长期方向

如果后续前端聊天表单需要直接消费“用户视图模型”，可以在不移除内部协议的前提下，额外暴露专门的 view-model 接口或中间层。

当前版本不提前扩展这一能力。

---

## 8. 测试策略

### 8.1 保留现有测试

以下测试继续保留，用于验证内部协议：
- `test_batch_reallocation_form_builder.py`
- `test_batch_reallocation_mcp.py`
- 其他 analyzer / executor 相关测试

### 8.2 新增测试

新增针对 `user_view_builder.py` 的测试，重点覆盖：

#### A. 有业务字段
验证能输出：
- 订单号
- 当前状态
- SKU 数量事实
- action mode 摘要
- 风险提示

#### B. 无技术泄露
验证输出中不包含：
- `form_type`
- `next_action`
- `endpoint`
- `payload`
- `raw_response`
- `MCP`
- 内部字段映射名

#### C. 场景覆盖
至少覆盖：
- Imported / Exception
- Deallocated 的 SKU 级选择
- On Hold + release hold

### 8.3 测试原则

新测试验证的是“用户可见边界”，不是重复验证分析器逻辑。

因此测试应尽量：
- 使用清晰、最小的输入对象
- 断言 view model 结构和字段可见性
- 不把测试写成 analyzer 的重复集成测试

---

## 9. 风险与权衡

### 9.1 为什么不直接让脚本层输出 markdown

不推荐脚本层直接产出最终 markdown，原因：
- 文案会过早写死
- agent 失去最后一层上下文表达能力
- 不利于未来前端卡片、结构化 UI 复用

因此本设计选择 view model，而不是最终渲染文本。

### 9.2 为什么不只靠 agent prompt

只靠 prompt 的问题是：
- 规则存在，但边界不在代码中显式体现
- 后续更容易再次把内部 JSON 直接发给用户
- 测试无法直接验证“哪些字段不得展示”

因此需要把“用户视图边界”显式落到脚本层。

### 9.3 为什么不改现有 MCP 返回

当前不改 MCP JSON 返回的原因是：
- 现有协议已经被测试覆盖
- 可能已有前端或其他调用方依赖
- 当前目标是补用户视图层，不是重做协议层

---

## 10. 实施顺序

推荐实施顺序：

1. 新增 `user_view_builder.py`
2. 先为 `build_analysis_view` / `build_execution_view` 编写失败测试
3. 以最小实现让测试通过
4. 视需要补 `build_confirmation_view`
5. agent 输出链路改为优先消费 view model
6. 补充文档说明“内部 payload”与“用户视图”的职责分离

---

## 11. 结论

本设计采用“双层都保留”的最小落地策略：

- 内部 JSON 协议继续存在
- 新增 `user_view_builder.py` 作为用户视图边界层
- agent 继续负责最终 5 段业务表达
- 测试新增“技术字段不得泄露”的用户视图断言

这样可以在不破坏现有内部协议的前提下，把“用户只能看到业务视图”从 prompt 规则推进到代码结构与测试约束中。