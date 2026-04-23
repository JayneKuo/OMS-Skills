# OMS API 接口参考 — order_query skill

> 迭代记录:
> - v3.0 (2026-04-08): 基于前端代码扫描整体重写；新增 OPC 模块完整 API；修正路径前缀和认证方式
> - v1.0 (2026-04-07): 初始版本

Base URL: `OMS_BASE_URL`

---

## 1. 认证

由前端 / agent session 直接提供 token，不在 skill 内执行 password grant。

后续所有请求需携带:
- `Authorization: Bearer <session token>`
- `x-tenant-id: <OMS_TENANT_ID>`

---

## 2. 订单查询（OPC 模块）

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 订单详情 | GET | /api/linker-oms/opc/app-api/sale-order/{orderNo} | 按 orderNo 查完整详情 |
| 订单列表 | GET | /api/linker-oms/opc/app-api/sale-order/page | 分页查询 |
| 状态统计 | GET | /api/linker-oms/opc/app-api/sale-order/status/num | 各状态订单数 |
| 订单时间线 | GET | /api/linker-oms/opc/app-api/payment/time-line/{orderNo} | 时间线事件 |
| 订单原始数据 | GET | /api/linker-oms/opc/app-api/sale-order/raw/data/{orderNo} | 原始 JSON |

## 3. 订单追踪

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 多类型搜索 | POST | /api/linker-oms/opc/app-api/tracking-assistant/search-order-no | 支持 orderNo/shipmentNo/trackingNo |
| 追踪详情 | GET | /api/linker-oms/opc/app-api/tracking-assistant/{orderNo} | 订单追踪全景 |
| 履行订单 | GET | /api/linker-oms/opc/app-api/tracking-assistant/fulfillment-orders/{orderNo} | 履行订单列表 |
| 包裹状态 | GET | /api/linker-oms/opc/app-api/tracking-assistant/tracking-status/{orderNo} | 包裹追踪 |

## 4. 订单日志

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 日志列表 | GET | /api/linker-oms/opc/app-api/orderLog/list | 按 merchantNo + omsOrderNo 查询 |
| 拆单日志详情 | GET | /api/linker-oms/oas/rpc-api/dispatch-log/{eventId} | 按 eventId 查拆单详情 |
| 事件类型 | GET | /api/linker-oms/opc/app-api/orderLog/orderLogEventType | 事件类型枚举 |
| 事件子类型 | GET | /api/linker-oms/opc/app-api/orderLog/orderLogEventSubType | 事件子类型枚举 |

## 5. 库存

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 库存列表 | POST | /api/linker-oms/opc/app-api/inventory/list | 支持 SKU/仓库/分组查询 |
| 库存变动历史 | POST | /api/linker-oms/opc/app-api/inventory/movement-history | 库存变动记录 |

## 6. 仓库

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 仓库列表 | POST | /api/linker-oms/opc/app-api/facility/v2/page | 分页查询 |

## 7. Fulfillment / Shipment

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| Fulfillment 列表 | GET | /api/linker-oms/opc/app-api/shipment/page | 分页查询 |
| Fulfillment 详情 | GET | /api/linker-oms/opc/app-api/shipment/detail | 按 shipmentNo 查 |
| 状态统计 | GET | /api/linker-oms/opc/app-api/shipment/status/num | 各状态数量 |

## 8. 规则

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| Hold 规则 | GET | /api/linker-oms/opc/app-api/hold-rule-data/page | Hold 规则列表 |
| 路由规则 | GET | /api/linker-oms/opc/app-api/routing/v2/rules | 路由规则列表 |
| 自定义规则 | GET | /api/linker-oms/opc/app-api/routing/v2/custom-rule | 自定义规则列表 |

## 9. 分配

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 可解除分配查询 | GET | /api/linker-oms/opc/app-api/dispatch/recover/query/{orderNo} | 查询分配信息 |
| 可分配商品 | GET | /api/linker-oms/opc/app-api/dispatch/hand/item/{orderNo} | 查询可分配商品 |

## 10. 映射（OAS 模块）

| API | 方法 | 路径 | 说明 |
|-----|------|------|------|
| 一对一映射 | POST | /api/linker-oms/oas/app-api/mapping/single | 映射列表 |
| Shipping Mapping | GET | /api/linker-oms/oas/app-api/mapping/multiple/rule/page | 规则列表 |
