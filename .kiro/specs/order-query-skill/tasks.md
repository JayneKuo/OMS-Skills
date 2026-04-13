# 实施计划：订单全景查询引擎（order_query_engine）

## 概述

按依赖顺序实现订单全景查询引擎的 10 个核心模块 + CLI 重构。先建立数据模型和配置基础，再逐步实现各业务组件（错误定义 → API 客户端 → 缓存 → 标识解析 → 状态归一化 → 查询编排 → 结果组装），最后通过顶层引擎入口将所有模块串联，并重构现有 CLI 脚本。每个模块实现后紧跟单元测试和属性测试，确保增量验证。

## 任务列表

- [x] 1. 项目结构初始化与数据模型实现
  - [x] 1.1 创建项目目录结构和依赖配置
    - 创建 `order_query_engine/` 包目录和 `__init__.py`
    - 创建 `tests/order_query/` 目录和 `conftest.py`
    - 在 `pyproject.toml` 中添加依赖：pydantic>=2.0, requests, pytest, hypothesis
    - _需求: 12.1, 12.2_

  - [x] 1.2 实现请求与标识解析数据模型
    - 在 `order_query_engine/models.py` 中实现：`QueryRequest`（identifier, query_intent, force_refresh）、`BatchQueryRequest`（query_type, status_filter, page_no, page_size）
    - 实现 `QueryInput`（input_value, identified_type, resolved_order_no）、`ResolveResult`（success, query_input, candidates, error）
    - _需求: 7.1, 11.1, 12.3_

  - [x] 1.3 实现状态映射与归一化数据模型
    - 在 `order_query_engine/models.py` 中实现：`StatusMapping`（main_status, category, is_exception, is_hold）、`NormalizedStatus`（status_code, main_status, category, is_exception, is_hold）
    - _需求: 4.1~4.15, 7.1, 12.3_

  - [x] 1.4 实现查询中间结果数据模型
    - 在 `order_query_engine/models.py` 中实现：`CoreQueryResult`（search_result, order_detail, order_logs, success, errors）、`ExtendedQueryResult`（tracking_detail, fulfillment_orders, tracking_status, warehouse_list, deallocate_info, routing_rules, custom_rules, sku_warehouse_rules, inventory, hold_rules, timeline, failed_apis, called_apis）
    - _需求: 3.1, 7.1, 12.3_

  - [x] 1.5 实现输出数据模型（OrderQueryResult 及子模型）
    - 在 `order_query_engine/models.py` 中实现所有输出子模型：`OrderIdentity`, `OrderContext`, `CurrentStatus`, `OrderItem`, `ShippingAddress`, `ShipmentInfo`, `InventoryInfo`, `WarehouseInfo`, `AllocationInfo`, `RuleInfo`, `EventInfo`, `QueryExplanation`, `DataCompleteness`
    - 实现顶层 `OrderQueryResult` 模型和 `BatchQueryResult` 模型
    - 所有扩展字段使用 `Optional` 类型，默认 `None`
    - _需求: 5.4, 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 12.3_

  - [x]* 1.6 编写属性测试：OrderQueryResult 序列化往返一致性
    - 使用 hypothesis 生成随机 `OrderQueryResult` 对象，验证 `model_dump_json()` 再 `model_validate_json()` 后与原始对象等价
    - **验证: 需求 11.3**

- [x] 2. 配置模块与错误定义实现
  - [x] 2.1 实现环境配置模块
    - 在 `order_query_engine/config.py` 中实现 `EngineConfig`（base_url, username, password, tenant_id, merchant_no, request_timeout=15, token_refresh_buffer=30）
    - 支持从环境变量覆盖默认值
    - _需求: 1.1, 1.2, 12.4_

  - [x] 2.2 实现结构化错误类型
    - 在 `order_query_engine/errors.py` 中实现：`QueryError`（error_type, message, context）、`AuthenticationError`（status_code, response_summary）、`OrderNotFoundError`（order_no）、`APICallError`（path, status_code, response_summary）、`NetworkTimeoutError`（url）、`IdentifierResolveError`（input_value, tried_types）
    - 每个错误类型的 `error_type` 字段对应：auth_failed / not_found / api_error / network_error / resolve_failed
    - _需求: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 3. 检查点 - 确保数据模型和基础模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. API 客户端实现
  - [x] 4.1 实现 OMSAPIClient 认证与 token 管理
    - 在 `order_query_engine/api_client.py` 中实现 `OMSAPIClient` 类
    - 实现 `authenticate()` 方法：使用 password grant 调用 POST /api/linker-oms/opc/iam/token 获取 access_token
    - 实现 `_ensure_token()` 方法：检查 token 有效性，剩余有效期 < 30s 时自动刷新
    - 存储 `_token` 和 `_token_expires_at`（Unix timestamp）
    - _需求: 1.1, 1.3_

  - [x] 4.2 实现 OMSAPIClient HTTP 请求方法
    - 实现 `get(path, params)` 和 `post(path, data)` 方法
    - 实现 `_headers()` 方法：构建 Authorization + x-tenant-id + Content-Type 请求头
    - 每次请求前调用 `_ensure_token()`
    - 请求超时设置为 config.request_timeout（默认 15 秒）
    - _需求: 1.2, 1.6_

  - [x] 4.3 实现 OMSAPIClient 错误处理
    - 认证接口返回非 200 → 抛出 `AuthenticationError`（含 HTTP 状态码和响应体摘要）
    - 业务接口返回非 200 → 抛出 `APICallError`（含接口路径、HTTP 状态码和响应体摘要）
    - 网络连接超时 → 抛出 `NetworkTimeoutError`（含目标 URL）
    - _需求: 1.4, 1.5, 1.6_

  - [x]* 4.4 编写 OMSAPIClient 单元测试
    - 使用 unittest.mock 模拟 requests 响应
    - 测试场景：成功认证、token 自动刷新、认证失败、业务接口 404、网络超时
    - _需求: 1.1, 1.3, 1.4, 1.5, 1.6_

- [x] 5. 查询缓存实现
  - [x] 5.1 实现 QueryCache
    - 在 `order_query_engine/cache.py` 中实现 `QueryCache` 类
    - 实现 `get(key)` 方法：返回缓存值，过期返回 None
    - 实现 `set(key, value, ttl)` 方法：设置缓存值和 TTL（秒）
    - 实现 `invalidate_all()` 方法：清除所有缓存
    - 内部使用 `dict[str, tuple[float, Any]]` 存储 key → (expires_at, value)
    - TTL 策略：订单详情/日志 60s，仓库/规则/Hold 规则 300s，token = expires_in - 30s
    - 错误结果不缓存
    - _需求: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 5.2 编写 QueryCache 单元测试
    - 测试场景：缓存命中、缓存过期、缓存清除、不同 TTL 策略
    - _需求: 8.1, 8.2, 8.3, 8.4_

- [x] 6. 标识解析器实现
  - [x] 6.1 实现 IdentifierResolver 模式匹配
    - 在 `order_query_engine/identifier_resolver.py` 中实现 `IdentifierResolver` 类
    - 实现正则模式匹配：SO/PO/WO 开头 → orderNo，SH 开头 → shipmentNo，evt_ 前缀或纯数字 → eventId
    - _需求: 2.1, 2.2, 2.3_

  - [x] 6.2 实现 IdentifierResolver API 反查兜底
    - 不匹配任何模式时，按 orderNo → eventId → shipmentNo → trackingNo 优先级依次调用 POST search-order-no 接口
    - 多候选 orderNo 时返回候选列表（candidates），不自动选取
    - 全部失败时返回 `IdentifierResolveError`（含原始输入值和已尝试类型列表）
    - 在 `QueryInput` 中记录原始输入值、识别类型和解析后的 orderNo
    - _需求: 2.4, 2.5, 2.6, 2.7_

  - [x]* 6.3 编写 IdentifierResolver 单元测试
    - 测试场景：SO 开头识别为 orderNo、SH 开头识别为 shipmentNo、evt_ 识别为 eventId、纯数字识别为 eventId、未知格式 API 反查、多候选返回、全部失败
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 7. 状态归一化器实现
  - [x] 7.1 实现 StatusNormalizer
    - 在 `order_query_engine/status_normalizer.py` 中实现 `StatusNormalizer` 类
    - 实现完整 25 个状态码映射表（STATUS_MAP）：
      - 0→已导入/初始, 1→已分仓/正常, 2→仓库处理中/正常, 3→已发货/正常, 4→已关闭/终态
      - 5→退货中/逆向, 6→已退货/逆向, 7→已退款/逆向, 8→已取消/终态, 9→待处理/初始
      - 10→异常/异常(is_exception=True), 11→重新打开/特殊, 12→取消中/过渡, 13→已接受/正常, 14→已拒绝/终态
      - 15→强制关闭/终态, 16→暂停履约/Hold(is_hold=True), 18→仓库已收货/正常, 20→已提交/正常, 21→已拣货/正常
      - 22→已打包/正常, 23→已装车/正常, 24→部分发货/正常, 25→已解除分配/特殊
    - 未知 status_code → 主状态"未知状态({code})"、分类"未知"
    - 确保 is_exception 和 is_hold 不同时为 true
    - _需求: 4.1~4.15_

  - [x]* 7.2 编写属性测试：状态归一化完整性与互斥性
    - 使用 hypothesis 生成随机 status_code（0~30 范围），验证：
      - 已知状态码返回正确的中文名称和分类
      - 未知状态码返回"未知状态({code})"
      - is_exception 和 is_hold 不同时为 true
    - **验证: 需求 4.11, 4.12, 4.14, 4.15**

  - [x]* 7.3 编写 StatusNormalizer 单元测试
    - 逐一验证 25 个状态码的映射结果
    - 验证 status_code=10 的 is_exception=True, is_hold=False
    - 验证 status_code=16 的 is_exception=False, is_hold=True
    - 验证未知 status_code（如 99）的降级处理
    - _需求: 4.1~4.15_

- [x] 8. 检查点 - 确保标识解析和状态归一化测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 9. 查询编排器实现
  - [x] 9.1 实现 QueryOrchestrator 意图检测
    - 在 `order_query_engine/query_orchestrator.py` 中实现 `QueryOrchestrator` 类
    - 实现 `detect_intents(query_intent)` 方法：从用户查询意图字符串中检测关键词
      - shipment/追踪/发运 → shipment
      - 仓库/分仓 → warehouse
      - 规则/策略 → rule
      - 库存 → inventory
      - Hold/暂停 → hold
      - 时间线/事件 → timeline
      - 全景 → panorama（触发全部扩展查询）
      - 仅"状态" → 不触发扩展查询
    - _需求: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [x] 9.2 实现 QueryOrchestrator 核心查询
    - 实现 `execute_core(order_no)` 方法：依次调用 POST search-order-no、GET sale-order/{orderNo}、GET orderLog/list
    - 认证失败时立即抛出 `AuthenticationError`
    - sale-order 返回 404 时抛出 `OrderNotFoundError`
    - 使用 QueryCache 缓存结果
    - _需求: 3.1, 3.10, 9.1, 9.2_

  - [x] 9.3 实现 QueryOrchestrator 扩展查询
    - 实现 `execute_extended(order_no, intents, core_result)` 方法
    - 根据意图列表选择对应 API 子集调用
    - 扩展查询失败时不阻断，将失败 API 记录到 `failed_apis`
    - 缓存命中时跳过 API 调用
    - _需求: 3.3~3.9, 3.10, 9.3_

  - [x]* 9.4 编写 QueryOrchestrator 单元测试
    - 使用 mock 模拟 API 客户端
    - 测试场景：仅核心查询（status 意图）、shipment 扩展、warehouse 扩展、panorama 全部扩展、缓存命中跳过、扩展查询部分失败降级
    - _需求: 3.1~3.10_

- [x] 10. 结果组装器实现
  - [x] 10.1 实现 ResultAssembler 核心组装逻辑
    - 在 `order_query_engine/result_assembler.py` 中实现 `ResultAssembler` 类
    - 实现 `assemble(core, extended, query_input)` 方法：
      - 从 core_result 提取 order_identity、order_context、current_status、order_items、shipping_address、event_info
      - 从 extended_result 提取 shipment_info、inventory_info、warehouse_info、allocation_info、rule_info、timeline
      - 未调用的 API → 对应字段设为 None
      - 调用失败的 API → 对应字段设为 None + 记录到 missing_fields
    - _需求: 7.1, 7.2, 7.3_

  - [x] 10.2 实现 ResultAssembler 查询级解释生成
    - 实现 `_build_explanation(status, core, extended)` 方法：
      - Hold 状态 → why_hold（规则名称 + 触发条件）
      - Exception 状态 → why_exception（异常事件类型 + 时间）
      - 已分仓 → why_this_warehouse（分仓策略 + 命中规则）
      - current_step（基于主状态描述当前业务步骤）
    - 仅描述现象，不做根因推断或决策建议
    - _需求: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 10.3 实现 ResultAssembler 数据完整度评估
    - 实现 `_assess_completeness(core_success, extended_failures)` 方法：
      - 核心查询全部成功 + 扩展查询全部成功 → "full"
      - 核心查询成功 + 部分扩展失败 → "partial"
      - 核心查询失败 → "minimal"
    - 记录实际调用的所有 API 路径到 data_sources
    - _需求: 7.4, 7.5_

  - [x] 10.4 实现异常与暂停履约区分逻辑
    - status_code=10 → is_exception=True, is_hold=False，从日志提取 exception_reason
    - status_code=16 → is_exception=False, is_hold=True，从 Hold 规则提取 hold_reason
    - 其他状态 → is_exception=False, is_hold=False
    - exception_reason 和 hold_reason 作为独立字段
    - _需求: 5.1, 5.2, 5.3, 5.4_

  - [x]* 10.5 编写 ResultAssembler 单元测试
    - 测试场景：核心查询成功组装、扩展查询部分失败降级、Hold 状态解释生成、Exception 状态解释生成、已分仓解释生成、数据完整度评估（full/partial/minimal）
    - _需求: 5.1~5.4, 6.1~6.5, 7.1~7.5_

- [x] 11. 检查点 - 确保查询编排和结果组装测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 12. 顶层引擎入口实现
  - [x] 12.1 实现 OrderQueryEngine 单订单查询
    - 在 `order_query_engine/engine.py` 中实现 `OrderQueryEngine` 类
    - 实现 `__init__(config)` 方法：初始化 config、client、cache、resolver、orchestrator、normalizer、assembler
    - 实现 `query(request: QueryRequest) -> OrderQueryResult` 方法，按流水线编排：
      - force_refresh=True 时清除缓存
      - 标识解析 → 查询编排（核心 + 扩展）→ 状态归一化 → 结果组装 → 输出
      - 标识解析失败 → 返回含 error 的 OrderQueryResult
      - 认证失败 → 返回含 error 的 OrderQueryResult
      - 订单不存在 → 返回含 error 的 OrderQueryResult
    - _需求: 1.1~1.6, 2.1~2.7, 3.1~3.10, 4.1~4.15, 5.1~5.4, 6.1~6.5, 7.1~7.5, 8.1~8.5, 9.1~9.5, 12.1, 12.2_

  - [x] 12.2 实现 OrderQueryEngine 批量查询
    - 实现 `query_batch(request: BatchQueryRequest) -> BatchQueryResult` 方法：
      - query_type="status_count" → 调用 GET sale-order/status/num
      - query_type="order_list" → 调用 GET sale-order/page（传入 status_filter 和分页参数）
      - 返回 BatchQueryResult（含 total, page_no, page_size）
    - _需求: 10.1, 10.2, 10.3_

  - [x]* 12.3 编写 OrderQueryEngine 集成单元测试
    - 使用 mock 模拟 API 客户端
    - 测试场景：
      - 正常订单查询（SO 开头 → 核心查询 → 输出）
      - 全景查询（panorama 意图 → 核心 + 全部扩展）
      - 标识解析失败（无效标识 → 错误输出）
      - 认证失败（→ 错误输出，不继续业务查询）
      - 订单不存在（404 → 错误输出）
      - 扩展查询部分失败（→ partial 完整度）
      - 批量查询（状态统计 + 订单列表）
      - force_refresh 跳过缓存
    - _需求: 9.1~9.5, 11.1, 11.2, 11.3_

- [x] 13. CLI 脚本重构
  - [x] 13.1 重构 query_oms.py 使用 order_query_engine
    - 修改 `.kiro/skills/order-query/scripts/query_oms.py`，将直接 API 调用替换为 `OrderQueryEngine` 调用
    - 保留现有 CLI 参数接口（--order-no, --event-id, --search, --inventory, --warehouses, --hold-rules, --routing-rules, --raw）
    - 使用 `QueryRequest` 和 `BatchQueryRequest` 构建请求
    - 输出 `OrderQueryResult` 的 JSON 序列化结果
    - _需求: 11.1, 11.2, 12.1, 12.2_

- [x] 14. 检查点 - 确保引擎集成和 CLI 测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 15. 端到端单元测试
  - [ ]* 15.1 编写端到端集成测试
    - 在 `tests/order_query/test_engine_e2e.py` 中编写以下场景的集成测试（使用 mock API）：
      - 按 orderNo 查询全景（核心 + 全部扩展 → full 完整度）
      - 按 shipmentNo 反查（SH 开头 → search-order-no → 核心查询）
      - 按 trackingNo 反查（未知格式 → API 反查 → 核心查询）
      - Hold 订单查询（status_code=16 → is_hold=True + hold_reason）
      - Exception 订单查询（status_code=10 → is_exception=True + exception_reason）
      - 扩展查询部分失败降级（→ partial 完整度 + missing_fields）
      - 批量状态统计
      - 缓存命中验证（同一订单二次查询不重复调用 API）
    - _需求: 1.1~1.6, 2.1~2.7, 3.1~3.10, 4.1~4.15, 5.1~5.4, 7.1~7.5, 8.1~8.5, 9.1~9.5_

  - [ ]* 15.2 编写错误处理单元测试
    - 在 `tests/order_query/test_errors.py` 中编写：
      - 认证失败 → AuthenticationError（含状态码和响应摘要）
      - 订单不存在 → OrderNotFoundError（含 orderNo）
      - 网络超时 → NetworkTimeoutError（含 URL）
      - 标识解析失败 → IdentifierResolveError（含输入值和已尝试类型）
      - 错误结构化输出验证（error_type + message + context）
    - _需求: 9.1~9.5_

- [x] 16. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保需求可追溯
- 检查点任务确保增量验证，及时发现问题
- 属性测试验证通用正确性属性（序列化往返、状态互斥性），单元测试验证具体场景和边界条件
- 实现顺序遵循依赖关系：models → config/errors → api_client → cache → identifier_resolver → status_normalizer → query_orchestrator → result_assembler → engine → CLI
