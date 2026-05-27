# batch-reallocation 设计文档

## 1. 概述

`batch-reallocation` 是挂在 `oms-agent` 下的危险批量操作 skill。

它不是纯执行器，而是一个对话式流程入口：

1. 查询
2. 分析
3. 聊天表单决策
4. 二次确认
5. 执行

目标场景：
- Imported
- Exception
- Deallocated
- On Hold

核心原则：
- 不直接执行
- 必须先分析
- 必须通过聊天表单收集用户选择
- 必须二次确认
- 只允许处理未履约数量 ≠ 0 的 SKU
- 绝不能超发

用户只感知到一个 skill：`batch-reallocation`。
内部虽然拆成分析、表单、执行、安全校验模块，但不额外暴露为多个用户可见 skill。

---

## 2. 数据来源与运行时约束

### 2.1 参考资料

设计和实现必须参考：
- `docs/oms-agent/oms-v3.openapi.json`
- `docs/oms-agent/OMS本体知识文件.json`
- `docs/oms-agent/07-测试环境配置.md`

### 2.2 运行时变量

变量由前端页面在调用 agent/session 时传入，遵循现有 OMS skill 约定。

主变量：
- `OMS_BASE_URL`
- `OMS_TENANT_ID`
- `CRM_MERCHANT_CODE`
- `OMS_MERCHANT_NO`（兼容兜底）
- `OMS_ACCESS_TOKEN`
- `USER`

兼容现有 `oms_query_engine/config.py` 的别名逻辑：
- `baseUrl`, `BASE_URL`
- `tenantId`, `TENANT_ID`, `x-tenant-id`
- `merchantNo`, `merchant_no`, `merchant`
- `OMS_SESSION_TOKEN`, `ACCESS_TOKEN`, `AUTH_TOKEN`, `OMS_TOKEN`, `authorization`

约束：
- 查询阶段缺 `USER` 可以继续分析
- 执行阶段缺 `USER` 不允许执行
- 不在 skill 内写死 URL、token、tenant、merchant、username
- 不使用 OpenAPI 中的示例 token/header 值

---

## 3. 业务边界

### 3.1 支持的状态场景

- `Imported`
- `Exception`
- `Deallocated`
- `On Hold`
- `Ineligible`（分析可见但不可执行）

### 3.2 场景处理原则

#### Imported / Exception
- 支持整单批量勾选执行
- 默认走整单 recover/reallocation 语义

#### Deallocated
- 默认订单层展示
- 执行前按未履约 SKU 再判断整单还是部分 recover

#### On Hold
- 默认 SKU 层展示
- 必须单独询问用户选择
- 必须明确是否先 release hold
- 不允许直接粗粒度整单批量执行

#### 其他状态
- 只分析
- 明确返回不可执行原因

### 3.3 绝对安全基线

只允许对 `未履约数量 != 0` 的 SKU 做重新分仓。

强规则：
- `reallocate_qty <= unfulfilled_qty`
- 已履约 / 已下发 / 不可恢复部分不能被超发
- 用户确认后执行前必须再次校验状态和数量

---

## 4. 对话交互流程

### 4.1 固定五步流程

1. 收集输入订单
2. 批量查询与归类
3. 返回聊天窗口结构化表单
4. 用户提交选择
5. 二次确认后执行

### 4.2 表单分组

#### A. Imported / Exception
整单批量表单，展示：
- orderNo
- 当前状态
- 异常摘要（exception 时）
- 可重分 SKU 数
- 可重分总未履约数量
- 风险提示

支持：
- 多单勾选
- 一次性确认执行

#### B. Deallocated
订单层为主，必要时可展开 SKU 明细，展示：
- orderNo
- 当前状态
- recover check 结果
- 可重分 SKU 数
- 未履约数量摘要

支持：
- 勾选订单
- 展开查看 SKU 明细
- 决定整单恢复或部分恢复

#### C. On Hold
SKU 层表单，展示：
- hold reason / hold status
- SKU 列表
- 每个 SKU 的 ordered qty / fulfilled or shipped qty / unfulfilled qty / hold qty or hold flag / 是否允许重分仓

支持：
- 先决定是否 release hold
- 再选择哪些 SKU 参与后续重分仓
- 或整单仅对可重分部分继续处理

### 4.3 最终确认

执行前必须展示确认摘要：
- 本次操作订单数
- SKU 数
- 预计整单 recover 数
- 预计部分 recover 数
- 是否包含 hold release
- 风险提示

风险提示至少包含：
- 只处理未履约数量不为 0 的 SKU
- 执行前会再次校验状态
- 状态变化的订单会被跳过或报失败

### 4.4 前端表单协议方向

skill 输出需包含结构化字段，供聊天窗口渲染：
- `form_type`
- `groups`
- `order_candidates`
- `sku_candidates`
- `warnings`
- `requires_confirmation`
- `next_action`

---

## 5. API 映射与执行策略

### 5.1 查询与预检接口

订单识别与基础查询：
- `POST /app-api/tracking-assistant/search-order-no`
- `GET /app-api/sale-order/{orderNo}`
- `GET /app-api/orderLog/list`

recover 预检：
- `GET /app-api/dispatch/recover/check/{orderNo}`
- `GET /app-api/dispatch/recover/query/{orderNo}`

用途：
- 统一解析订单号
- 获取订单状态、订单行、数量信息
- 获取异常 / hold / deallocate 日志摘要
- 判断订单是否允许 recover
- 判断是否存在可恢复 dispatch

### 5.2 执行接口

#### Imported / Exception
优先整单：
- `POST /app-api/dispatch/recover/dispatch`

必要时降级部分处理：
- `POST /app-api/dispatch/recover/dispatch/part`

第一版产品语义仍以整单批量操作为主。

#### Deallocated
- 整单：`POST /app-api/dispatch/recover/dispatch`
- 部分：`POST /app-api/dispatch/recover/dispatch/part`

规则：
- 所有可操作 SKU 满足未履约数量 > 0 且 recover 条件一致时，可整单
- 仅部分 SKU 可恢复时，必须走 partial recover
- 混有已履约/已下发与未履约部分时，优先 partial recover

#### On Hold
默认先 release hold，再决定 recover：
- `POST /app-api/order-hold/release`
- 或 `POST /app-api/opc/order-hold/release`
- 然后按情况走：
  - `POST /app-api/dispatch/recover/dispatch`
  - `POST /app-api/dispatch/recover/dispatch/part`

规则：
- on hold 不直接进入批量整单 recover
- 必须让用户确认是否先 release hold
- release 后再决定整单还是指定 SKU 恢复
- 仍不可操作的 hold SKU 不纳入 recover 候选

### 5.3 deallocate 接口角色

扩展点接口：
- `POST /app-api/dispatch/deallocate/{dispatchNo}`

第一版不作为默认批量链路主入口。
只保留为后续增强点，用于未来“先 deallocate 再重分仓”的场景。

---

## 6. 防超发与执行前复核

### 6.1 SKU 资格判断

SKU 进入执行 payload 的前提：
- `unfulfilled_qty > 0`
- 当前状态允许 recover / reallocation
- 不属于已完全履约部分
- 属于用户选中的 SKU / 订单
- 不属于仍被 hold 且未释放的 SKU

### 6.2 数量上限

任何 SKU 必须满足：
- `requested_qty <= unfulfilled_qty`

即使接口是整单 recover，也必须先确认该订单不存在会导致超发的 SKU。

### 6.3 执行前复核

用户确认后、真正调用执行接口前，再拉一次订单快照：
- 订单状态是否变化
- `unfulfilled_qty` 是否变化
- hold 状态是否变化

如果变化：
- 标记 `stale`
- 不直接执行
- 返回“需重新分析”结果

---

## 7. 内部模块结构

### 7.1 对外暴露

只新增 1 个用户入口 skill：
- `batch-reallocation`

### 7.2 推荐目录结构

```text
.kiro/skills/oms-agent/
  batch-reallocation/
    SKILL.md
    references/
      api-mapping.md
      form-protocol.md
    scripts/
      batch_reallocation/
        __init__.py
        models.py
        config.py
        analyzer.py
        eligibility.py
        form_builder.py
        executor.py
        api_client.py
        result_formatter.py
    tests/
      test_analyzer.py
      test_eligibility.py
      test_form_builder.py
      test_executor.py
```

### 7.3 模块职责

- `models.py`：定义请求、候选、表单、执行计划、执行结果结构
- `config.py`：对齐 OMS skill 环境变量读取逻辑
- `api_client.py`：封装 OMS 查询与执行接口、统一 headers 和错误归一化
- `analyzer.py`：做批量分析、分组、候选生成
- `eligibility.py`：实现安全硬规则和资格判断
- `form_builder.py`：把分析结果转成前端聊天表单协议
- `executor.py`：读取用户选择、复核、组装 payload、执行真实接口
- `result_formatter.py`：输出用户摘要和结构化执行结果

### 7.4 与 oms-agent 现有结构的关系

需同步更新：
- `SKILL_REGISTRY.md`：新增 `batch-reallocation`
- `WORKFLOWS.md`：新增 `batch_reallocation_workflow`
- `mcp_server.py`：如需工具化，仅暴露最小稳定入口，例如：
  - `batch_reallocation_analyze`
  - `batch_reallocation_execute`

原则：
- 用户只看到一个 skill
- 内部实现模块不额外增加用户理解负担
- tool 暴露面保持最小

---

## 8. 第一版范围

### 8.1 第一版必须支持
- 批量输入订单号
- 批量分析并分组：`imported` / `exception` / `deallocated` / `on_hold` / `ineligible`
- 聊天窗口结构化表单
- imported / exception 整单批量确认
- deallocated 单独决策
- on hold 单独决策
- 执行前二次校验
- 真实调用 hold release / recover dispatch / partial recover dispatch

### 8.2 第一版明确不做
- 自动搜索“最近一批异常单”后直接执行
- 跨 merchant 批处理
- 自动 deallocate 再 recover 的联动链
- 混合多动作编排
- 后台异步任务中心
- 大规模分页批处理编排
- 智能猜测用户意图后自动执行

---

## 9. 测试策略

### 9.1 规则单测
重点覆盖：
- 状态分组
- `unfulfilled_qty > 0` 过滤
- on hold 是否必须单独决策
- deallocated 是否优先 partial recover
- 缺少 `USER` 时是否禁止执行

### 9.2 表单协议单测
重点覆盖：
- imported / exception 是否生成整单批量勾选区
- deallocated 是否生成订单层区块
- on hold 是否生成 SKU 层区块
- 最终确认区是否包含风险提示

### 9.3 API client 集成测试
重点覆盖：
- header 组装
- `Authorization` / `x-tenant-id` / `USER` 透传
- 查询和执行错误的归一化

### 9.4 真实环境联调
真实联调时，以 `docs/oms-agent/07-测试环境配置.md` 为唯一测试环境参考。

真实联调最少覆盖：
- imported 可整单执行
- exception 可整单执行
- deallocated 含部分可恢复 SKU
- on hold 含可恢复与不可恢复 SKU 混合

### 9.5 联调顺序
1. 只做 analyze
2. 打 check/query，不执行
3. 单单执行验证
4. 小批量执行验证（2~5 单，混合状态）

---

## 10. 第一版安全闸门

- 无确认不执行
- 无 `USER` 不执行
- 状态漂移则该单中止并返回 `stale_state`
- `requested_qty > unfulfilled_qty` 时拒绝执行该单

---

## 11. 上线顺序

### Phase 1
只上线：
- models
- config
- api_client
- analyzer
- eligibility
- form_builder
- 只分析不执行

### Phase 2
上线执行器：
- executor
- result_formatter
- imported / exception 执行链
- deallocated 执行链

### Phase 3
上线 on hold 完整链路：
- hold release
- release 后 recover / partial recover
- 更细的失败原因展示

---

## 12. 结论

第一版产品目标不是“万能批量操作框架”，而是：

> 一个可扩展的 batch-reallocation 首版实现

内部按框架方式组织，外部按单一危险批量操作 skill 交付。

这样既能满足当前 OMS 运营批量重分仓需求，也为未来批量释放 hold、批量重试 dispatch、批量异常恢复等动作保留扩展空间。