# 需求文档：订单全景查询引擎（order_query_engine）

## 简介

order_query_engine 是 OMS Agent 的核心查询引擎，以 Python 模块形式实现（类似 cartonization_engine/），负责围绕订单及其关联对象进行多源 API 查询、状态归一化、查询编排和结构化输出。该引擎接收用户提供的任意订单标识（orderNo/shipmentNo/trackingNo/eventId），通过分层查询编排策略调用 OMS staging API，将 25+ 种原始订单状态归一化为统一业务语言，明确区分异常（Exception）与暂停履约（Hold），输出标准化的 OrderQueryResult 结构供下游 skill（order_analysis、warehouse_allocation、shipping_rate）复用。

## 术语表

- **Order_Query_Engine（查询引擎）**：执行订单全景查询的核心 Python 模块，接收标识输入，输出 OrderQueryResult
- **OMS_API_Client（API 客户端）**：封装 OMS staging 环境 HTTP 调用的底层模块，负责认证、请求、错误处理
- **Identifier_Resolver（标识解析器）**：识别输入标识类型并解析为 orderNo 的模块
- **Query_Orchestrator（查询编排器）**：根据用户意图决定调用哪些 API 的调度模块
- **Status_Normalizer（状态归一化器）**：将 OMS 原始 status_code 映射为统一业务状态的模块
- **Result_Assembler（结果组装器）**：将多个 API 返回合并为 OrderQueryResult 的模块
- **Query_Cache（查询缓存）**：在同一 workflow 内缓存 API 结果避免重复调用的模块
- **OrderQueryResult（查询结果）**：标准化输出数据结构，包含订单身份、状态、商品行、地址、shipment、库存、仓库、规则、事件、查询级解释等字段
- **Core_Query（核心查询）**：每次查询必须执行的 3 个 API 调用（search-order-no + sale-order + orderLog）
- **Extended_Query（扩展查询）**：根据用户问题按需触发的额外 API 调用
- **Exception（异常）**：订单流程出错或失败，status_code=10，需排查根因
- **Hold（暂停履约）**：订单被规则拦截或人工控制暂停，status_code=16，不一定是错误
- **Query_Explanation（查询级解释）**：基于查询结果解释当前现象，不做深层根因分析

## 需求

### 需求 1：API 客户端与认证

**用户故事：** 作为查询引擎，我需要一个可靠的 API 客户端来管理 OMS staging 环境的认证和 HTTP 调用，以便所有查询操作都能安全、稳定地访问后端服务。

#### 验收标准

1. WHEN OMS_API_Client 初始化，THE OMS_API_Client SHALL 使用 password grant 方式调用 POST /api/linker-oms/opc/iam/token 获取 access_token
2. WHEN OMS_API_Client 发送任何业务请求，THE OMS_API_Client SHALL 在请求头中携带 Authorization: Bearer {access_token}、x-tenant-id: LT 和 Content-Type: application/json
3. WHEN access_token 的剩余有效期低于 30 秒，THE OMS_API_Client SHALL 自动重新获取 access_token 后再发送业务请求
4. IF OMS_API_Client 调用认证接口返回非 200 状态码，THEN THE OMS_API_Client SHALL 返回认证失败错误，包含 HTTP 状态码和响应体摘要
5. IF OMS_API_Client 调用业务接口返回非 200 状态码，THEN THE OMS_API_Client SHALL 返回 API 调用失败错误，包含接口路径、HTTP 状态码和响应体摘要
6. IF OMS_API_Client 调用任何接口时网络连接超时超过 15 秒，THEN THE OMS_API_Client SHALL 返回连接超时错误，包含目标 URL

### 需求 2：多标识类型识别与解析

**用户故事：** 作为查询引擎，我需要识别用户提供的任意订单标识类型并将其解析为 orderNo，以便后续查询操作统一基于 orderNo 执行。

#### 验收标准

1. WHEN Identifier_Resolver 接收到以 SO、PO 或 WO 开头的标识，THE Identifier_Resolver SHALL 将该标识识别为 orderNo 类型
2. WHEN Identifier_Resolver 接收到以 SH 开头的标识，THE Identifier_Resolver SHALL 将该标识识别为 shipmentNo 类型
3. WHEN Identifier_Resolver 接收到以 evt_ 开头或纯数字格式的标识，THE Identifier_Resolver SHALL 将该标识识别为 eventId 类型
4. WHEN Identifier_Resolver 接收到不匹配上述任何模式的标识，THE Identifier_Resolver SHALL 按 orderNo → eventId → shipmentNo → trackingNo 的优先级依次尝试调用 POST search-order-no 接口解析
5. WHEN Identifier_Resolver 成功将标识解析为 orderNo，THE Identifier_Resolver SHALL 在 OrderQueryResult.query_input 中记录原始输入值、识别的类型和解析后的 orderNo
6. IF Identifier_Resolver 尝试所有类型后均无法解析为有效的 orderNo，THEN THE Identifier_Resolver SHALL 返回标识解析失败错误，包含原始输入值和已尝试的类型列表
7. WHEN POST search-order-no 接口返回多个候选 orderNo，THE Identifier_Resolver SHALL 返回候选列表供上层选择，不自动选取

### 需求 3：查询编排策略

**用户故事：** 作为查询引擎，我需要根据用户的查询意图智能决定调用哪些 API，以便在满足信息需求的同时避免不必要的 API 调用。

#### 验收标准

1. WHEN Query_Orchestrator 接收到任何查询请求，THE Query_Orchestrator SHALL 先执行核心查询：依次调用 POST search-order-no、GET sale-order/{orderNo}、GET orderLog/list
2. WHEN 用户查询意图为"订单状态"，THE Query_Orchestrator SHALL 仅执行核心查询，不触发扩展查询
3. WHEN 用户查询意图包含"shipment"或"追踪"或"发运"，THE Query_Orchestrator SHALL 在核心查询之后额外调用 GET tracking-assistant/{orderNo}、GET fulfillment-orders/{orderNo}、GET tracking-status/{orderNo}
4. WHEN 用户查询意图包含"仓库"或"分仓"，THE Query_Orchestrator SHALL 在核心查询之后额外调用 POST facility/v2/page 和 GET dispatch/recover/query/{orderNo}
5. WHEN 用户查询意图包含"规则"或"策略"，THE Query_Orchestrator SHALL 在核心查询之后额外调用 GET routing/v2/rules、GET routing/v2/custom-rule、GET sku-warehouse/page
6. WHEN 用户查询意图包含"库存"，THE Query_Orchestrator SHALL 在核心查询之后额外调用 POST inventory/list
7. WHEN 用户查询意图包含"Hold"或"暂停"，THE Query_Orchestrator SHALL 在核心查询之后额外调用 GET hold-rule-data/page
8. WHEN 用户查询意图包含"时间线"或"事件"，THE Query_Orchestrator SHALL 在核心查询之后额外调用 GET payment/time-line/{orderNo}
9. WHEN 用户查询意图为"全景"，THE Query_Orchestrator SHALL 执行核心查询加全部扩展查询
10. WHEN Query_Cache 中已存在某个 API 的有效缓存结果，THE Query_Orchestrator SHALL 直接使用缓存结果，不重复调用该 API

### 需求 4：订单状态归一化

**用户故事：** 作为查询引擎，我需要将 OMS 返回的 25+ 种原始 status_code 映射为统一的业务状态，以便输出结果使用一致的中文业务术语。

#### 验收标准

1. THE Status_Normalizer SHALL 将 status_code=0 映射为主状态"已导入"、分类"初始"
2. THE Status_Normalizer SHALL 将 status_code=1 映射为主状态"已分仓"、分类"正常"
3. THE Status_Normalizer SHALL 将 status_code=2 映射为主状态"仓库处理中"、分类"正常"
4. THE Status_Normalizer SHALL 将 status_code=3 映射为主状态"已发货"、分类"正常"
5. THE Status_Normalizer SHALL 将 status_code=4 映射为主状态"已关闭"、分类"终态"
6. THE Status_Normalizer SHALL 将 status_code=5 映射为主状态"退货中"、分类"逆向"
7. THE Status_Normalizer SHALL 将 status_code=6 映射为主状态"已退货"、分类"逆向"
8. THE Status_Normalizer SHALL 将 status_code=7 映射为主状态"已退款"、分类"逆向"
9. THE Status_Normalizer SHALL 将 status_code=8 映射为主状态"已取消"、分类"终态"
10. THE Status_Normalizer SHALL 将 status_code=9 映射为主状态"待处理"、分类"初始"
11. THE Status_Normalizer SHALL 将 status_code=10 映射为主状态"异常"、分类"异常"，并设置 is_exception=true、is_hold=false
12. THE Status_Normalizer SHALL 将 status_code=16 映射为主状态"暂停履约"、分类"Hold"，并设置 is_exception=false、is_hold=true
13. THE Status_Normalizer SHALL 将 status_code 为 11、12、13、14、15、18、20、21、22、23、24、25 的状态分别映射为对应的中文业务名称
14. WHEN Status_Normalizer 接收到未在映射表中定义的 status_code，THE Status_Normalizer SHALL 将主状态设置为"未知状态({status_code})"、分类设置为"未知"
15. FOR ALL 已定义的 status_code 值，THE Status_Normalizer SHALL 确保 is_exception 和 is_hold 不同时为 true（异常与暂停互斥性）

### 需求 5：异常与暂停履约区分查询

**用户故事：** 作为查询引擎，我需要明确区分订单的异常（Exception）和暂停履约（Hold）状态，以便用户准确理解订单当前的阻塞原因。

#### 验收标准

1. WHEN 订单 status_code 为 10，THE Order_Query_Engine SHALL 在输出中设置 is_exception=true、is_hold=false，并从订单日志中提取最近的异常事件作为 exception_reason
2. WHEN 订单 status_code 为 16，THE Order_Query_Engine SHALL 在输出中设置 is_exception=false、is_hold=true，并从 Hold 规则查询结果中提取命中的规则作为 hold_reason
3. WHEN 订单 status_code 既不是 10 也不是 16，THE Order_Query_Engine SHALL 在输出中设置 is_exception=false、is_hold=false
4. THE Order_Query_Engine SHALL 在输出结构中将 exception_reason 和 hold_reason 作为独立字段呈现，不合并为单一字段

### 需求 6：查询级解释生成

**用户故事：** 作为查询引擎，我需要基于多个 API 的查询结果组合生成查询级解释，以便用户理解订单当前所处的步骤和现象。

#### 验收标准

1. WHEN 订单处于 Hold 状态，THE Result_Assembler SHALL 在 query_explanation.why_hold 字段中说明命中的 Hold 规则名称和触发条件
2. WHEN 订单处于 Exception 状态，THE Result_Assembler SHALL 在 query_explanation.why_exception 字段中说明最近的异常事件类型和时间
3. WHEN 订单已分仓，THE Result_Assembler SHALL 在 query_explanation.why_this_warehouse 字段中说明分仓策略和命中的规则
4. THE Result_Assembler SHALL 在 query_explanation.current_step 字段中基于订单主状态描述订单当前所处的业务步骤
5. THE Result_Assembler SHALL 确保查询级解释仅描述当前现象，不包含根因推断或决策建议

### 需求 7：结构化输出（OrderQueryResult）

**用户故事：** 作为查询引擎，我需要将所有查询结果组装为标准化的 OrderQueryResult 数据结构，以便下游 skill 和 Agent 直接复用查询结果。

#### 验收标准

1. THE Result_Assembler SHALL 输出 OrderQueryResult 结构，包含以下顶层字段：query_input、order_identity、order_context、current_status、order_items、shipping_address、shipment_info、inventory_info、warehouse_info、allocation_info、rule_info、event_info、query_explanation、data_completeness
2. WHEN 某个 API 未被调用（因查询编排策略判定不需要），THE Result_Assembler SHALL 将对应字段设置为 null，不填充虚假数据
3. WHEN 某个 API 调用失败，THE Result_Assembler SHALL 将对应字段设置为 null，并在 data_completeness.missing_fields 中记录该字段名称
4. THE Result_Assembler SHALL 在 data_completeness.completeness_level 中标注数据完整度：核心查询全部成功为"full"，部分扩展查询失败为"partial"，核心查询失败为"minimal"
5. THE Result_Assembler SHALL 在 data_completeness.data_sources 中记录实际调用的所有 API 路径列表

### 需求 8：查询缓存

**用户故事：** 作为查询引擎，我需要在同一 workflow 内缓存 API 查询结果，以便避免对同一订单的重复 API 调用。

#### 验收标准

1. WHEN Query_Cache 缓存订单详情或日志列表结果，THE Query_Cache SHALL 设置 60 秒的缓存有效期
2. WHEN Query_Cache 缓存仓库列表、路由规则或 Hold 规则结果，THE Query_Cache SHALL 设置 300 秒的缓存有效期
3. WHEN Query_Cache 缓存 access_token，THE Query_Cache SHALL 设置有效期为 token 的 expires_in 减去 30 秒
4. WHEN 用户明确要求"刷新"查询结果，THE Query_Cache SHALL 跳过所有缓存，重新调用 API
5. IF 某个 API 调用返回错误，THEN THE Query_Cache SHALL 不缓存该错误结果

### 需求 9：错误处理与降级

**用户故事：** 作为查询引擎，我需要对各类查询错误进行分类处理和优雅降级，以便在部分 API 不可用时仍能返回尽可能多的有效信息。

#### 验收标准

1. IF 认证接口调用失败，THEN THE Order_Query_Engine SHALL 返回认证失败错误，不继续执行任何业务查询
2. IF 核心查询中的 sale-order/{orderNo} 接口返回 404，THEN THE Order_Query_Engine SHALL 返回订单不存在错误，包含输入的 orderNo
3. IF 扩展查询中的某个 API 调用失败，THEN THE Order_Query_Engine SHALL 将对应字段设置为 null，继续执行其余查询，并在 data_completeness 中记录失败信息
4. IF 网络连接失败，THEN THE Order_Query_Engine SHALL 返回网络连接错误，包含目标 URL 和超时时间
5. THE Order_Query_Engine SHALL 对每个错误返回结构化的错误信息，包含错误类型（auth_failed/not_found/api_error/network_error）、错误消息和相关上下文

### 需求 10：批量查询支持

**用户故事：** 作为查询引擎，我需要支持按状态过滤的批量订单查询和状态统计，以便用户了解整体订单分布情况。

#### 验收标准

1. WHEN 用户请求订单状态统计，THE Order_Query_Engine SHALL 调用 GET sale-order/status/num 接口返回各状态的订单数量
2. WHEN 用户请求按状态过滤的订单列表，THE Order_Query_Engine SHALL 调用 GET sale-order/page 接口，传入 status 过滤条件和分页参数
3. THE Order_Query_Engine SHALL 在批量查询结果中包含总数、当前页码和每页数量

### 需求 11：输入输出序列化

**用户故事：** 作为查询引擎，我需要支持 JSON 格式的输入输出序列化与反序列化，以便与 Agent 框架和下游 skill 进行数据交换。

#### 验收标准

1. THE Order_Query_Engine SHALL 支持将查询请求（标识值、查询意图、刷新标志）从 JSON 格式反序列化为内部数据结构
2. THE Order_Query_Engine SHALL 支持将 OrderQueryResult 序列化为 JSON 格式
3. FOR ALL 有效的 OrderQueryResult 对象，将 OrderQueryResult 序列化为 JSON 再反序列化回对象 SHALL 产生与原始对象等价的结果（往返一致性）

### 需求 12：模块架构

**用户故事：** 作为开发者，我需要查询引擎按照职责分离原则组织为独立模块，以便各模块可独立测试和维护。

#### 验收标准

1. THE Order_Query_Engine SHALL 将 API 客户端（认证与 HTTP 调用）、标识解析、查询编排、状态归一化、结果组装、缓存分别实现为独立的 Python 模块
2. THE Order_Query_Engine SHALL 提供一个顶层 engine 模块作为统一入口，协调各子模块完成完整查询流程
3. THE Order_Query_Engine SHALL 将所有数据模型（OrderQueryResult、QueryInput、StatusMapping 等）定义在独立的 models 模块中
4. THE Order_Query_Engine SHALL 将环境配置（Base URL、账号、租户、商户）集中在配置模块中，不硬编码在业务逻辑中
