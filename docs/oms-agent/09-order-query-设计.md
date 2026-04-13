# order_query Skill 设计

> 基于现有 OMS 代码能力，设计 order_query skill 的稳定输入输出和职责边界。
> 最后更新：2026-04-07

---

## 一、业务目标

order_query 是一个稳定的基础查询 skill，职责是：
- 把订单对象查清楚
- 把拆单结果查清楚
- 把过程日志查清楚
- 输出结构化数据，适合给下游 skill（order_analysis / warehouse_allocation / cartonization / shipping_rate / eta / cost）复用

## 二、适用场景（用户会怎么问）

| 用户问法 | 触发 order_query |
|---------|----------------|
| "帮我查一下这个订单" | ✅ |
| "订单 SO00168596 当前状态是什么" | ✅ |
| "这个订单分到了哪个仓" | ✅ |
| "这个订单用了什么承运商" | ✅ |
| "这个订单拆了几个包" | ✅ |
| "这个订单的拆单日志" | ✅ |
| "这个订单为什么失败" | ❌ → 转 order_analysis |
| "这个订单应该分哪个仓" | ❌ → 转 warehouse_allocation |
| "这个订单运费多少" | ❌ → 转 shipping_rate |

## 三、输入字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| eventId | string | 二选一 | 拆单事件 ID（优先） |
| orderNo | string | 二选一 | 订单号（referenceNo） |
| merchantNo | string | 否 | 商户号，默认使用配置值 |

当前 API 限制：`GET /dispatch-log/{eventId}` 只支持 eventId 查询。
如果用户只提供 orderNo，需要告知用户提供 eventId，或后续扩展按 orderNo 查询的能力。

## 四、输出字段

order_query 的标准化输出结构：

```
OrderQueryResult:
  order_summary:
    order_no: string          # 订单号
    event_id: string          # 事件 ID
    merchant_no: string       # 商户号
    status: string            # "全部分仓成功" / "无可用仓库" / "异常"
    status_code: int          # 1 / 2 / -1
    event_type: string        # 事件类型
    event_time: datetime      # 事件时间
    summary: string           # 摘要
```

注意：当前 API 返回的是 DispatchLogVO 摘要级数据。
完整的拆单明细（策略列表、过程日志、仓库分配、商品行）需要后续扩展 API 或通过其他途径获取。

## 五、当前可直接复用的能力

| 能力 | API | 复用方式 | 说明 |
|------|-----|---------|------|
| 拆单日志摘要查询 | GET /dispatch-log/{eventId} | 直接调用 | 返回 DispatchLogVO 摘要 |
| 认证 | POST /iam/token | 前置调用 | 获取 access_token |

## 六、需要额外拼装的字段

当前 DispatchLogVO 只返回摘要（orderNo, eventId, eventType, summary, status, eventTime），以下字段在 DispatchLogDO 中存在但当前 API 未返回：

| 字段 | 业务含义 | 是否需要 | 获取方式 |
|------|---------|---------|---------|
| dispatchList | 拆单结果（仓库/承运商/商品行） | 需要 | 需扩展 API 或新增接口 |
| dispatchLogs | 过程日志（逐步记录） | 需要 | 同上 |
| filterStrategies | 使用的仓库过滤策略 | 需要 | 同上 |
| dispatchStrategies | 使用的分仓策略 | 需要 | 同上 |
| backupDispatchStrategy | 兜底策略 | 需要 | 同上 |
| deliveryStrategy | 出库单生成策略 | 需要 | 同上 |
| exceptionMsg | 异常信息 | 需要 | 同上 |
| customStrategies | 自定义策略 | 可选 | 同上 |
| dispatchConfig | 拆单配置 | 可选 | 同上 |

关键发现：当前 `GET /dispatch-log/{eventId}` 返回的 DispatchLogVO 是摘要级的，不含完整拆单明细。要让 order_query 真正有用，需要一个返回完整 DispatchLogDTO 的接口。

可能的解决方案：
1. 后端新增一个返回完整 DispatchLogDTO 的接口（推荐）
2. 通过 admin-api/invoke 动态调用 DispatchLogDOMapper 查询（不推荐，安全风险）
3. 先用摘要级数据，后续迭代补全

## 七、上游依赖

| 依赖 | 说明 |
|------|------|
| 认证服务 (POST /iam/token) | 获取 access_token，所有查询的前置步骤 |
| 租户/商户配置 | tenantId=LT, merchantNo=LAN0000002 |

## 八、职责边界

### order_query 负责的（查什么）
- 查询订单拆单状态（成功/失败/异常）
- 查询拆单结果（分到了哪些仓、用了什么承运商）
- 查询拆单过程日志
- 查询使用了哪些策略
- 查询异常摘要信息

### order_query 不负责的（不查什么、不分析什么、不推荐什么）
- 不分析异常根因（→ order_analysis）
- 不推荐仓库（→ warehouse_allocation）
- 不推荐承运商/服务（→ shipping_rate）
- 不计算运费/时效/成本（→ shipping_rate / eta / cost）
- 不做装箱计算（→ cartonization）
- 不查询库存（隐式能力，无独立 API）
- 不查询 SKU 主数据（隐式能力，无独立 API）

### order_query 输出给谁用
- order_analysis：拿到状态、日志、异常信息后做根因分析
- warehouse_allocation：拿到订单信息后做分仓建议
- cartonization：拿到商品行信息后做装箱计算
- shipping_rate：拿到承运商/服务信息后做运费计算
- Agent 直接展示：用户查询订单时直接输出

---

## 九、当前实现状态评估

| 维度 | 状态 | 说明 |
|------|------|------|
| API 可用性 | 部分可用 | GET /dispatch-log/{eventId} 可用，但只返回摘要 |
| 认证机制 | 已明确 | POST /iam/token，password grant |
| 输入标识 | 受限 | 只支持 eventId，不支持 orderNo 查询 |
| 输出完整度 | 不足 | 摘要级，缺少拆单明细/过程日志/策略列表 |
| 脚本实现 | 已有 | scripts/query_oms.py 已创建 |
| SKILL.md | 已有 | 已创建，但需要根据实际 API 返回调整输出模板 |

## 十、下一步建议

1. 先用现有摘要级 API 跑通 order_query 的基本流程
2. 确认 staging 环境连通性（先调 /iam/token 验证认证）
3. 确认 /dispatch-log/{eventId} 的实际返回结构（可能比代码中的 VO 更丰富）
4. 如果摘要不够用，评估是否需要后端新增完整查询接口
5. 根据实际返回调整 SKILL.md 的输出模板和 query_oms.py 的解析逻辑
