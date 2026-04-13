---
模块迭代记录:
  - 版本: v8.0
    日期: 2026-04-08
    变更: 在 OMS 全域运营强查询基础上，新增集成中心（Integration Center）查询域；
          支持查询已连接渠道、连接器配置、认证状态、支持能力、同步对象、失败信息与可连接范围；
          统一整合订单、商品、库存、仓库、规则、履约、发运、同步、日志、事件与集成配置能力；
          模块名从 order_query 升级为 oms_query
  - 版本: v7.0
    日期: 2026-04-08
    变更: 从"订单查询"升级为"OMS 全域运营强查询"；全面纳入订单、商品、库存、仓库、
          规则、分仓、履约、发运、同步、日志、事件、状态感知增强查询；增强标准输出结构与场景化编排
  - 版本: v6.0
    日期: 2026-04-08
    变更: 整合全面优化建议；模块定位升级为"订单运营态强查询"；新增来源/店铺/仓执行态/时长指标/
          状态感知增强查询；补充已发运/Hold/Exception/Deallocated专项查询模型；增强标准输出结构；
          完善查询编排、降级、缓存与验收标准
  - 版本: v5.0
    日期: 2026-04-08
    变更: 基于前端代码扫描全面修正；更新降级矩阵（所有查询对象均有API）；更新反查链路（全部可走通）；
          新增查询编排策略；新增输出结构中的商品行/地址/渠道字段；删除过时的"需后端补接口"描述
  - 版本: v4.0
    日期: 2026-04-08
    变更: 新增降级矩阵/反查链路/Shipping Mapping定位/订单类型/批量查询/缓存策略
  - 版本: v3.0
    日期: 2026-04-08
    变更: 基于强订单查询目标整体重写
  - 版本: v1.0
    日期: 2026-04-08
    变更: 初始版本
---

# oms_query 需求规格

## 1. 模块定位

`oms_query` 是 OMS Agent 的核心全域强查询 Skill，负责围绕 OMS 关键业务对象执行多源查询、
状态归一化、状态感知增强查询、查询级解释与结构化输出，向上提供 **OMS 全链路运营态全景信息**。

它不是一个只会"查订单状态"的 Skill，而是一个统一的 OMS 查询入口，能够以订单、shipment、
tracking、SKU、仓库、规则、渠道、连接器等为入口，联动查询订单、商品、库存、仓库、分仓、规则、
履约、发运、同步、日志、事件、集成中心配置等核心对象。

### 1.1 核心目标

当用户给出一个订单号、shipment 号、tracking 号、eventId、SKU、仓库名、规则条件、渠道名、
店铺名、连接器名称或自然语言问题时，Skill 应尽量在一次响应中回答用户最想知道的内容，
而不是只返回一个字段后让用户继续追问。

Skill 应尽量覆盖以下问题：

- 这个订单来自哪个渠道、哪个店铺、哪个平台单号
- 当前是什么状态，是否异常、是否 Hold、是否 Deallocated
- 当前卡在哪个环节
- 订单商品是什么，数量多少，关键属性是什么
- 这个订单库存够不够，库存在哪些仓，是否有可用库存
- 当前分到哪个仓，为什么是这个仓
- 仓库当前是什么状态，有什么能力限制
- 仓内对应的单号是什么，履约到哪一步了
- 是否已发运，承运商什么服务，tracking 是什么
- 当前运输进度、预计到达时间、签收情况如何
- 发运信息是否同步到三方平台，是否成功
- 最近发生了什么关键事件
- 从进单到当前多久，仓库作业了多久，在途多久
- 命中了哪些规则，规则为什么生效
- 这个 merchant / 店铺已经连接了哪些渠道
- 这些连接器是怎么配置的
- 当前连接器认证是否正常，支持同步哪些对象
- 能连接什么平台，哪些能力已启用，哪些未启用
- 最近同步失败的原因是什么，配置缺了什么

### 1.2 模块定位边界

`oms_query` 的定位是：

**强查询 + 查询级解释 + 结构化运营态输出**

但不负责：

- 深层根因分析
- 修复建议或自动修复
- 推荐仓库 / 推荐承运商 / 推荐服务
- 运费 / 时效 / 成本优化
- 装箱优化
- 流程动作执行
- 自动变更连接器配置
- 自动修复集成错误


---

## 2. 业务语义统一口径

| 概念 | 中文 | 含义 | 不等于 |
|------|------|------|--------|
| Exception | 异常 | 流程出错、失败、命中异常分支，需要排查原因 | Hold |
| Hold | 暂停履约 | 订单被拦住，暂不继续履约，可能由规则拦截或人工控制触发 | Exception |
| Deallocated | 已解除分配 | 原有仓分配被撤销，当前未保持原分仓结果 | Hold / Exception |
| Shipped | 已发运 | 已产生发运结果并进入运输过程 | Delivered |
| Inventory Available | 可用库存 | 当前可被 OMS / 履约链路使用的库存 | On Hand |
| On Hand | 实物库存 | 仓内实际存在库存 | Available |
| Warehouse Process Status | 仓执行状态 | 仓内履约执行阶段，如 Picking / Packing / Loaded | OMS 主订单状态 |
| Connector | 连接器 | OMS 与外部平台 / 系统的集成实例 | 渠道本身 |
| Channel | 渠道 | 订单 / 库存 / 发运等业务来源或交互平台，如 Shopify/Amazon/Walmart | Connector 配置实例 |
| Integration Capability | 集成能力 | 某连接器支持的对象与动作，如订单拉取、库存同步、发运回传 | 认证状态 |

输出中必须分开呈现，不得混用。

---

## 3. 核心能力总览

### 3.1 按对象划分的能力域

| 能力域 | 说明 |
|--------|------|
| 订单查询域 | 订单详情、状态、来源、地址、商品行、上下文 |
| 商品查询域 | SKU、商品名称、数量、重量、尺寸、标签、商品属性 |
| 库存查询域 | SKU 库存、可用库存、占用库存、库存变动 |
| 仓库查询域 | 仓库列表、仓库状态、能力、地址、仓限制 |
| 分仓查询域 | 当前分仓结果、候选仓、分仓原因、解除分配 |
| 规则查询域 | 路由规则、自定义规则、Hold 规则、SKU 仓规则、映射规则 |
| 履约执行域 | fulfillment、仓内执行状态、仓内单号、包裹信息 |
| 发运追踪域 | shipment、carrier、service、tracking、ETA、签收 |
| 同步回传域 | 发运信息是否同步到三方，是否成功 |
| 日志事件域 | 时间线、日志、异常事件、拆单详情 |
| 集成中心查询域 | 已连接渠道、连接器配置、认证状态、启用能力、同步对象、失败信息 |
| 状态增强域 | Hold / Exception / Deallocated / Shipped 自动补充查询 |
| 批量统计域 | 订单状态统计、列表查询、时间范围筛选 |

---

## 4. 核心能力清单

| 编号 | 能力 | 说明 | 对应 API / 对象 |
|------|------|------|----------------|
| OQ-1 | 多对象标识识别 | 识别 orderNo / shipmentNo / trackingNo / eventId / sku / referenceNo / connectorName | search-order-no 及对象识别逻辑 |
| OQ-2 | 订单主查询 | 查询订单详情、状态、商品行、地址、来源、商户、渠道 | sale-order/{orderNo} |
| OQ-3 | 商品查询 | 查询订单商品、SKU 属性、标签、数量、物理属性 | sale-order/{orderNo} / 商品相关字段 |
| OQ-4 | 库存查询 | 查询 SKU 当前库存、可用库存、占用库存、库存变动 | inventory/list, inventory/movement-history |
| OQ-5 | 仓库查询 | 查询仓库列表、地址、能力、限制、属性 | facility/v2/page |
| OQ-6 | 分仓结果查询 | 查询当前分配仓、候选仓、分配/解除分配信息 | dispatch/recover/query/{orderNo}, dispatch/hand/item/{orderNo} |
| OQ-7 | 分仓规则查询 | 查询路由规则、自定义规则、SKU 仓指定规则 | routing/v2/rules, routing/v2/custom-rule, sku-warehouse/page |
| OQ-8 | Hold 查询 | 查询 Hold 状态、Hold 规则、阻塞原因、恢复线索 | hold-rule-data/page + sale-order/{orderNo} |
| OQ-9 | 异常查询 | 查询异常状态、异常事件、异常阶段、错误信息 | orderLog/list, dispatch-log/{eventId} |
| OQ-10 | 关键事件查询 | 查询时间线、日志、最近事件 | payment/time-line/{orderNo}, orderLog/list |
| OQ-11 | 履约执行查询 | 查询 fulfillment、仓执行状态、仓内单号、包裹信息 | tracking-assistant/*, shipment/detail |
| OQ-12 | 发运履约态查询 | 查询 carrier、service、tracking、发运时间、ETA、签收 | tracking-assistant/*, shipment/detail |
| OQ-13 | 物流节点追踪查询 | 查询运输节点、最新轨迹、签收状态、在途异常 | tracking-status/{orderNo} |
| OQ-14 | 发运回传状态查询 | 查询发运信息是否同步到三方平台以及结果 | shipment / sync / integration 相关字段或日志 |
| OQ-15 | 来源与店铺查询 | 返回渠道、店铺、平台单号 | sale-order/{orderNo} 及来源字段 |
| OQ-16 | 时长计算 | 返回订单龄、分仓耗时、仓处理耗时、在途时长 | 基于订单详情 / 时间线 / 日志计算 |
| OQ-17 | 状态感知增强查询 | 根据当前状态自动补充关键上下文 | 多 API 编排 |
| OQ-18 | 集成中心连接查询 | 查询已连接的渠道 / 平台 / 连接器实例 | connector/channel management 相关接口 |
| OQ-19 | 集成配置查询 | 查询连接器如何配置、认证信息状态、启用开关 | connector detail / auth / config 相关接口 |
| OQ-20 | 集成能力查询 | 查询连接器能同步什么对象、支持什么能力 | connector capability / template / metadata |
| OQ-21 | 集成健康状态查询 | 查询连接状态、最近同步情况、最近失败信息 | test connection / logs / run status |
| OQ-22 | 可连接范围查询 | 查询当前系统可连接哪些平台、有哪些连接器模板 | connector catalog / template list |
| OQ-23 | 批量统计查询 | 支持状态统计、列表、时间范围筛选 | sale-order/status/num, sale-order/page |


---

## 5. 适用场景

### 5.1 直接触发

| 用户问法 | 触发 |
|---------|------|
| "帮我查一下这个订单" / "SO00168596 现在什么状态" | ✅ |
| "这个 shipment 现在到哪一步了" | ✅ |
| "这个订单有没有异常" / "为什么 Hold" | ✅ |
| "这个订单命中了什么规则" / "为什么分到 Ontario 仓" | ✅ |
| "这个订单库存够不够" / "仓库有什么限制" | ✅ |
| "这个订单来自哪个渠道哪个店铺" | ✅ |
| "这个订单仓库现在处理到哪一步了" | ✅ |
| "这个订单已经发货了没有，什么时候发的，预计什么时候到" | ✅ |
| "发运信息有没有同步到 Amazon / Shopify / Walmart" | ✅ |
| "帮我看这个 SKU 在哪些仓有库存" | ✅ |
| "Ontario 仓支持什么能力 / 有什么配置" | ✅ |
| "现在有哪些 Hold 规则 / 路由规则 / SKU 仓规则" | ✅ |
| "这个 merchant 已经接了哪些渠道" | ✅ |
| "这个 Shopify 连接器怎么配置的" | ✅ |
| "这个连接器能同步什么，订单/库存/发运都支持吗" | ✅ |
| "这个连接器认证正常吗，最近有没有失败" | ✅ |
| "当前系统还能连接什么平台" | ✅ |
| "今天有多少异常订单" / "最近 1 小时拆单失败的订单" | ✅（批量） |

### 5.2 不触发（转其他 Skill）

| 用户问法 | 转给 |
|---------|------|
| "失败的根因到底是什么" | order_analysis |
| "应该分哪个仓" / "推荐走哪个承运商" | warehouse_allocation / shipping_rate |
| "怎么装箱" / "整体怎么发最优" | cartonization / workflow 编排 |
| "这个问题怎么修复 / 怎么自动恢复" | order_analysis / workflow |
| "帮我改连接器配置 / 重置认证 / 重新授权" | integration_manage / admin workflow |

---

## 6. 输入规格

### 6.1 支持的输入类型

| 类型 | 说明 | 识别线索 |
|------|------|---------|
| orderNo | OMS 订单号 | SO / PO / WO 开头 |
| shipmentNo | shipment 编号 | SH 开头 |
| trackingNo | 物流追踪号 | 承运商 tracking 格式 |
| eventId | 拆单事件 ID | evt_ 前缀或事件 ID |
| sku | 商品 SKU | SKU 编码格式 |
| warehouseKey | 仓库标识 | warehouseNo / warehouseName |
| ruleKey | 规则标识 | ruleName / ruleId / ruleType |
| connectorKey | 连接器标识 | connectorName / channelName / storeName |
| referenceNo | 通用参考号 | 其他业务参考号格式 |
| batchQuery | 批量查询条件 | "多少单 / 今天 / 最近1小时 / 统计 / 列表"等语义 |

### 6.2 输入识别原则

1. 优先做模式识别
2. 订单类输入统一优先调用 `search-order-no` 作为主解析入口
3. 若返回唯一命中，则解析为最终主对象
4. 若返回多个候选，则返回候选列表并标识歧义
5. 若无法解析，则停止主链路查询
6. 批量查询不走单单详情链路，直接进入批量查询计划
7. 渠道 / 连接器 / 仓库 / 规则类查询按对应对象入口执行，不强制走订单链路

---

## 7. 反查链路与主键依赖

### 7.1 订单主链路

```text
任意订单相关标识
  → POST search-order-no
  → orderNo
  → GET sale-order/{orderNo}
  → 订单完整详情（含商品行、地址、状态、来源）
```

### 7.2 OMS 对象联查链路

```text
任意订单标识 → search-order-no → orderNo

orderNo
  → sale-order/{orderNo}
  → tracking-assistant/{orderNo}
  → fulfillment-orders/{orderNo}
  → tracking-status/{orderNo}
  → payment/time-line/{orderNo}
  → orderLog/list?omsOrderNo=
  → dispatch/recover/query/{orderNo}
  → shipment/detail
  → shipment/page

orderLog/list
  → 提取 eventId
  → dispatch-log/{eventId}

sale-order/{orderNo}
  → 提取 merchantNo / sku / channel / store / source / order config

merchantNo
  → inventory/list
  → facility/v2/page
  → routing/v2/rules
  → routing/v2/custom-rule
  → hold-rule-data/page

merchantNo + sku
  → sku-warehouse/page

connectorKey / channelKey / storeKey
  → connector list / connector detail / connector capability
  → auth config / run status / sync logs
```

### 7.3 主键依赖说明

| 查询对象 | 主要依赖键 |
|---------|-----------|
| 订单详情 | orderNo |
| shipment / tracking | orderNo |
| 时间线 | orderNo |
| 日志 | orderNo |
| 拆单详情 | eventId |
| 库存 | merchantNo + sku |
| 仓库 | merchantNo |
| 路由规则 | merchantNo |
| Hold 规则 | merchantNo |
| SKU 仓规则 | merchantNo + sku |
| 连接器列表 | merchantNo / workspace / merchant context |
| 连接器详情 | connectorId / connectorName |
| 连接能力 | connector template / connector type |
| 集成健康状态 | connectorId |


---

## 8. 查询对象与 API 映射

### 8.1 OMS 基础对象

| 查询对象 | API | 支持度 |
|---------|-----|--------|
| 订单详情 | GET /api/linker-oms/opc/app-api/sale-order/{orderNo} | ✅ |
| 订单列表 | GET /api/linker-oms/opc/app-api/sale-order/page | ✅ |
| 状态统计 | GET /api/linker-oms/opc/app-api/sale-order/status/num | ✅ |
| 时间线 | GET /api/linker-oms/opc/app-api/payment/time-line/{orderNo} | ✅ |
| 多类型搜索 | POST /api/linker-oms/opc/app-api/tracking-assistant/search-order-no | ✅ |
| 追踪详情 | GET /api/linker-oms/opc/app-api/tracking-assistant/{orderNo} | ✅ |
| 履行订单 | GET /api/linker-oms/opc/app-api/tracking-assistant/fulfillment-orders/{orderNo} | ✅ |
| 包裹状态 | GET /api/linker-oms/opc/app-api/tracking-assistant/tracking-status/{orderNo} | ✅ |
| 日志列表 | GET /api/linker-oms/opc/app-api/orderLog/list | ✅ |
| 拆单详情 | GET /api/linker-oms/oas/rpc-api/dispatch-log/{eventId} | ✅ |
| 库存 | POST /api/linker-oms/opc/app-api/inventory/list | ✅ |
| 库存变动 | POST /api/linker-oms/opc/app-api/inventory/movement-history | ✅ |
| 仓库列表 | POST /api/linker-oms/opc/app-api/facility/v2/page | ✅ |
| Shipment | GET /api/linker-oms/opc/app-api/shipment/page, /shipment/detail | ✅ |
| 承运商 | POST /api/wms-bam/carrier/search-by-paging | ✅ |
| Hold 规则 | GET /api/linker-oms/opc/app-api/hold-rule-data/page | ✅ |
| 路由规则 | GET /api/linker-oms/opc/app-api/routing/v2/rules | ✅ |
| 自定义规则 | GET /api/linker-oms/opc/app-api/routing/v2/custom-rule | ✅ |
| 分配查询 | GET /api/linker-oms/opc/app-api/dispatch/recover/query/{orderNo} | ✅ |
| 映射 | POST /api/linker-oms/oas/app-api/mapping/single | ✅ |
| SKU仓规则 | GET /api/linker-oms/opc/app-api/sku-warehouse/page | ✅ |

### 8.2 集成中心对象

以下为能力要求层面的对象映射，具体接口名以集成中心实际前端扫描/API 定义为准。

| 查询对象 | API / 对象 | 支持度 |
|---------|-----------|--------|
| 已连接连接器列表 | connector list / channel instance list | ✅ |
| 连接器详情 | connector detail | ✅ |
| 认证配置 | auth config / credential status | ✅ |
| 连接测试结果 | test connection / connection status | ✅ |
| 支持能力 | connector capability / template metadata | ✅ |
| 同步对象范围 | supported objects / order inventory shipment return etc | ✅ |
| 最近运行状态 | run status / job status | ✅ |
| 最近同步失败信息 | sync logs / error logs | ✅ |
| 可连接平台列表 | connector catalog / template list | ✅ |


---

## 9. 标准输出结构

```yaml
OMSQueryResult:

  query_input:
    input_value: string
    identified_type: string | null
    primary_object_type: string | null      # order / sku / warehouse / connector / rule / batch
    resolved_primary_key: string | null
    candidate_matches: list | null

  order_identity:
    order_no: string | null
    customer_order_no: string | null
    external_order_no: string | null
    merchant_no: string | null

  source_info:
    order_source: string | null
    channel_no: string | null
    channel_name: string | null
    store_no: string | null
    store_name: string | null
    platform_order_no: string | null

  order_context:
    order_type: string | null
    order_type_tags: list | null
    related_order_no: string | null

  current_status:
    status_code: int | null
    status_name: string | null
    status_category: string | null
    main_status: string | null
    fulfillment_status: string | null
    shipment_status: string | null
    warehouse_process_status: string | null
    is_exception: bool | null
    is_hold: bool | null
    is_deallocated: bool | null
    hold_reason: string | null
    exception_reason: string | null
    deallocated_reason: string | null

  product_info:
    items:
      - sku: string
        product_name: string | null
        quantity: int
        description: string | null
        weight: float | null
        dimensions: string | null
        tags: list | null
    product_summary: string | null

  shipping_address:
    country: string | null
    state: string | null
    city: string | null
    zipcode: string | null
    address1: string | null

  inventory_info:
    sku_inventory:
      - sku: string
        warehouse_no: string | null
        warehouse_name: string | null
        available_qty: number | null
        on_hand_qty: number | null
        reserved_qty: number | null
    inventory_summary: string | null
    inventory_movement_summary: string | null

  warehouse_info:
    allocated_warehouse: string | null
    warehouse_no: string | null
    warehouse_name: string | null
    warehouse_type: string | null
    warehouse_accounting_code: string | null
    warehouse_address: string | null
    warehouse_capabilities: list | null
    warehouse_constraints: list | null
    warehouse_status_desc: string | null

  warehouse_execution_info:
    warehouse_no: string | null
    warehouse_name: string | null
    warehouse_order_no: string | null
    fulfillment_order_no: string | null
    shipment_no: string | null
    package_no_list: list | null

  warehouse_status_info:
    warehouse_process_status: string | null
    warehouse_status_desc: string | null
    warehouse_received_time: datetime | null
    warehouse_processing_start_time: datetime | null
    picked_time: datetime | null
    packed_time: datetime | null
    loaded_time: datetime | null
    shipped_time: datetime | null

  shipment_info:
    shipment_no: string | null
    fulfillment_order_no: string | null
    warehouse_order_no: string | null
    carrier_name: string | null
    carrier_scac: string | null
    carrier_service_code: string | null
    carrier_service_name: string | null
    delivery_service: string | null
    tracking_no: string | null
    pro_no: string | null
    bol_no: string | null
    shipment_status: string | null
    shipment_status_desc: string | null
    shipped_time: datetime | null
    estimated_delivery_time: datetime | null
    actual_delivery_time: datetime | null
    signed_by: string | null
    package_count: int | null

  tracking_progress_info:
    current_tracking_status: string | null
    current_tracking_desc: string | null
    latest_tracking_event_time: datetime | null
    latest_tracking_location: string | null
    latest_tracking_event: string | null
    estimated_delivery_time: datetime | null
    delivery_attempt_count: int | null
    is_delivered: bool | null
    is_exception_in_transit: bool | null
    tracking_events: list | null

  shipment_sync_info:
    sync_targets:
      - target_system: string | null
        target_store: string | null
        sync_object: string | null
        sync_status: string | null
        sync_time: datetime | null
        external_reference_no: string | null
        sync_result_message: string | null
    all_sync_success: bool | null
    last_sync_time: datetime | null
    failed_sync_targets: list | null

  allocation_info:
    allocation_status: string | null
    allocation_reason: string | null
    candidate_warehouses: list | null
    dispatch_strategies: list | null
    filter_strategies: list | null
    backup_strategy: string | null

  warehouse_decision_explanation:
    final_warehouse_no: string | null
    final_warehouse_name: string | null
    decision_summary: string | null
    decision_factors: list | null
    candidate_warehouses: list | null
    filtered_out_warehouses: list | null

  hold_detail_info:
    is_on_hold: bool | null
    hold_status: string | null
    hold_reason_code: string | null
    hold_reason_name: string | null
    hold_reason_desc: string | null
    hold_source: string | null
    hold_rule_id: string | null
    hold_rule_name: string | null
    hold_rule_type: string | null
    hold_start_time: datetime | null
    hold_duration_minutes: int | null
    hold_operator: string | null
    hold_scope: string | null
    release_condition: string | null
    release_hint: string | null

  exception_detail_info:
    is_in_exception: bool | null
    exception_stage: string | null
    exception_code: string | null
    exception_type: string | null
    exception_reason: string | null
    exception_event_id: string | null
    exception_start_time: datetime | null
    exception_duration_minutes: int | null
    latest_failed_step: string | null
    latest_failed_action: string | null
    latest_error_message: string | null
    recoverable_hint: string | null

  deallocation_detail_info:
    is_deallocated: bool | null
    deallocated_time: datetime | null
    deallocated_reason: string | null
    deallocated_operator: string | null
    previous_warehouse_no: string | null
    previous_warehouse_name: string | null
    current_allocation_status: string | null
    candidate_warehouses: list | null
    reallocation_hint: string | null

  rule_info:
    routing_rules: list | null
    custom_rules: list | null
    hold_rules: list | null
    sku_warehouse_rules: list | null
    mapping_rules: list | null

  integration_info:
    connected_channels:
      - connector_id: string | null
        connector_name: string | null
        connector_type: string | null
        platform_name: string | null
        store_name: string | null
        status: string | null
        auth_status: string | null
        enabled_objects: list | null
    connector_detail:
      connector_id: string | null
      connector_name: string | null
      connector_type: string | null
      platform_name: string | null
      store_name: string | null
      environment: string | null
      auth_type: string | null
      auth_status: string | null
      test_connection_status: string | null
      last_test_time: datetime | null
      config_summary: string | null
      supported_objects: list | null
      supported_actions: list | null
      sync_directions: list | null
      webhook_enabled: bool | null
      polling_enabled: bool | null
      draft_status: string | null
      recent_error_message: string | null
      recent_run_status: string | null
      last_sync_time: datetime | null
    available_connector_catalog: list | null

  milestone_times:
    order_created_time: datetime | null
    order_imported_time: datetime | null
    allocated_time: datetime | null
    warehouse_received_time: datetime | null
    warehouse_processing_start_time: datetime | null
    picked_time: datetime | null
    packed_time: datetime | null
    loaded_time: datetime | null
    shipped_time: datetime | null
    actual_delivery_time: datetime | null
    latest_update_time: datetime | null

  duration_metrics:
    order_age_minutes: int | null
    warehouse_processing_minutes: int | null
    hold_duration_minutes: int | null
    exception_duration_minutes: int | null
    time_to_allocate_minutes: int | null
    time_to_release_to_warehouse_minutes: int | null
    time_to_ship_minutes: int | null
    time_in_transit_minutes: int | null

  event_info:
    timeline: list | null
    latest_event_type: string | null
    latest_event_time: datetime | null
    latest_exception_event: string | null
    latest_hold_event: string | null
    order_logs: list | null

  query_explanation:
    current_step: string | null
    why_hold: string | null
    why_exception: string | null
    why_deallocated: string | null
    why_this_warehouse: string | null
    hold_impact: string | null
    release_hint: string | null
    shipment_summary: string | null
    sync_summary: string | null
    integration_summary: string | null

  data_completeness:
    completeness_level: string           # full / partial / minimal
    missing_fields: list
    data_sources: list
```


---

## 10. 查询编排策略

oms_query 不应对所有请求一律调用全部 API，而应采用：
**对象识别 + 核心链路 + 按需扩展 + 状态感知增强**

### 10.1 核心查询（订单类必调）

| 步骤 | API | 目的 |
|------|-----|------|
| 1 | POST search-order-no | 将任意订单相关输入统一解析为 orderNo |
| 2 | GET sale-order/{orderNo} | 获取订单基础详情、状态、商品、地址、来源 |
| 3 | GET orderLog/list | 获取日志、异常事件、eventId |

### 10.2 对象型扩展查询

| 对象 / 关注点 | 额外调用 |
|--------------|---------|
| 商品 | 订单商品字段 / SKU 相关字段 |
| 库存 | inventory/list, inventory/movement-history |
| 仓库 | facility/v2/page |
| 分仓 | dispatch/recover/query/{orderNo}, dispatch/hand/item/{orderNo} |
| 规则 | routing/v2/rules, routing/v2/custom-rule, sku-warehouse/page, mapping/single |
| Hold | hold-rule-data/page |
| 时间线 | payment/time-line/{orderNo} |
| 发运 / 追踪 | tracking-assistant/{orderNo}, fulfillment-orders/{orderNo}, tracking-status/{orderNo}, shipment/detail |
| 拆单详情 | dispatch-log/{eventId} |
| 集成中心 | connector list / connector detail / capability / auth / logs / test connection |

### 10.3 状态感知增强查询

#### a. Shipped / Partially shipped

自动补充：
- shipment_info
- tracking_progress_info
- shipment_sync_info
- time_in_transit

#### b. On Hold

自动补充：
- hold_detail_info
- hold_rules
- why_hold
- hold_impact
- release_hint

#### c. Exception

自动补充：
- exception_detail_info
- latest_exception_event
- dispatch-log（若存在 eventId）
- why_exception

#### d. Deallocated

自动补充：
- deallocation_detail_info
- previous warehouse
- candidate warehouses
- why_deallocated

### 10.4 集成中心查询计划

#### a. 用户问"接了哪些渠道 / 已连接哪些"

调用：
- connector list
- channel instance list
- merchant 下连接器汇总

#### b. 用户问"怎么配置的"

调用：
- connector detail
- auth config status
- config summary
- enabled objects
- supported actions

#### c. 用户问"能连接什么 / 支持什么"

调用：
- connector catalog / template list
- connector capability metadata

#### d. 用户问"是否正常 / 最近有没有失败"

调用：
- test connection result
- recent run status
- sync logs / recent errors

### 10.5 批量查询

| 场景 | API |
|------|-----|
| 状态统计 | sale-order/status/num |
| 列表 | sale-order/page |

### 10.6 场景化查询计划

| 用户问题 | 查询计划 |
|---------|---------|
| 什么状态 | core |
| 为什么 Hold | core + hold |
| 为什么 Exception | core + logs + dispatch-log |
| 为什么 Deallocated | core + dispatch + logs |
| 为什么分到这个仓 | core + dispatch + rules + sku-warehouse + facility |
| tracking 到哪一步 | core + shipment + tracking |
| 发货了没有 / 什么时候发的 / 预计什么时候到 | core + shipment + tracking |
| 发运信息同步三方是否成功 | core + shipment + shipment sync |
| 仓库处理到哪一步 | core + warehouse + timeline |
| SKU 在哪些仓有库存 | inventory + facility |
| 当前有哪些规则 | rules |
| 接了哪些渠道 | integration list |
| 这个连接器怎么配置的 | integration detail |
| 这个连接器能同步什么 | integration capability |
| 这个连接器健康不健康 | integration detail + run status + logs |
| 全景 | core + shipment + dispatch + rules + inventory + hold + timeline + state-aware enhancement |

### 10.7 编排原则

1. 先识别对象，再决定查询链路
2. 订单类问题先查核心链路
3. 扩展查询按用户问题触发
4. 关键状态触发自动增强
5. 集成中心问题按连接器对象链路执行，不强行绕订单
6. 不对简单问题无差别调用全部 API
7. 同一 workflow 内已获取的数据不得重复调用


---

## 11. 状态归一化规则

### 11.1 状态字段输出原则

- 原始状态码保留在 `status_code`
- 原始状态名保留在 `status_name`
- 标准分类写入 `status_category`
- Exception / Hold / Deallocated 必须通过独立布尔字段呈现

### 11.2 状态布尔映射

- status_code = 10 → is_exception = true
- status_code = 16 → is_hold = true
- status_code = 25 → is_deallocated = true

### 11.3 查询级解释规则

| 场景 | 解释口径 |
|------|---------|
| Hold | 基于状态 + Hold 规则 + 日志解释当前为何暂停 |
| Exception | 基于状态 + 异常日志 + dispatch log 解释当前异常态 |
| Deallocated | 基于状态 + 分仓信息 + 日志解释当前解除分配 |
| 分仓 | 基于分仓结果 + 规则 + SKU 仓规则解释为何落仓 |
| 已发运 | 基于 shipment + tracking 解释运输进度 |
| 集成中心 | 基于连接器配置 + 能力 + 认证状态 + 最近运行情况解释当前集成状态 |

---

## 12. 缓存与降级策略

### 12.1 缓存策略

| 缓存对象 | TTL | 说明 |
|---------|-----|------|
| access_token | expires_in - 30s | 提前过期 |
| search-order-no | 60s | 同一输入短时间复用 |
| sale-order | 60s | 订单详情短缓存 |
| orderLog/list | 60s | 日志短缓存 |
| tracking-status | 30s | 变化较快 |
| inventory/list | 30~60s | 建议 workflow 内缓存 |
| 仓库 / 路由规则 / Hold 规则 | 300s | 变化频率低 |
| connector detail / capability | 300s | 配置类数据变化较低 |
| connector health / recent logs | 30~60s | 变化较快 |

### 12.2 降级输出规则

| 场景 | 输出级别 |
|------|---------|
| 主对象与关键扩展均成功 | full |
| 主对象成功，部分扩展失败 | partial |
| 仅识别少量对象信息 | minimal |

### 12.3 缓存失效规则

- 用户明确要求"刷新"时跳过缓存
- 查询失败结果不缓存
- workflow 内缓存全程有效

---

## 13. 职责边界

### 13.1 负责

- 订单 / 商品 / 库存 / 仓库 / 分仓 / 规则 / 履约 / 发运 / 同步 / 日志 / 事件 / 集成中心 查询
- 状态归一化
- 状态感知增强
- 查询级解释
- 结构化输出

### 13.2 不负责

- 深层根因分析
- 推荐仓 / 推荐承运商 / 推荐服务
- 运费 / 时效 / 成本计算
- 自动修复或执行动作
- 修改连接器配置 / 重置认证 / 重新授权

---

## 14. 与下游 Skill 的关系

| 下游 Skill | 使用 oms_query 输出的内容 |
|-----------|-------------------------|
| order_analysis | 状态、异常、Hold、Deallocated、日志、规则、分仓上下文 |
| warehouse_allocation | 当前仓、规则链、库存、仓能力、候选仓 |
| shipping_rate | shipment、carrier、service、tracking |
| cartonization | 商品、数量、重量、尺寸 |
| integration_manage | connector detail、auth status、capability、recent errors |
| Agent 直接展示 | OMS 全景信息 |

---

## 15. 验收标准

| 编号 | 验收项 |
|------|--------|
| AC-1 | 能识别 orderNo / shipmentNo / trackingNo / eventId / sku / connectorKey 等主要输入类型 |
| AC-2 | 订单类核心查询（search + detail + logs）在正常网络下 3 秒内返回 |
| AC-3 | Exception / Hold / Deallocated 必须分开展示 |
| AC-4 | 当状态为 On Hold 且存在 Hold 规则时，返回 is_hold=true 且 why_hold 非空 |
| AC-5 | 当状态为 Exception 且存在异常事件时，返回 is_exception=true 且 why_exception 非空 |
| AC-6 | 当状态为 Deallocated 时，返回 is_deallocated=true 且 why_deallocated 非空 |
| AC-7 | 当存在分仓结果且至少查到一类规则依据时，返回 why_this_warehouse 非空 |
| AC-8 | 当订单为已发运状态时，返回 tracking / carrier / service / shipped_time / ETA 等字段 |
| AC-9 | 当存在发运回传信息时，返回 shipment_sync_info 并体现成功/失败状态 |
| AC-10 | 当用户查询 SKU/库存/仓库/规则时，应返回对应对象信息，而不是只返回订单字段 |
| AC-11 | 当用户查询集成中心时，应能返回已连接渠道、配置摘要、认证状态、支持能力、最近运行状态 |
| AC-12 | 当用户询问"能连接什么"时，应返回可连接平台/连接器模板列表 |
| AC-13 | 当用户询问"怎么配置的"时，应返回连接器配置摘要与启用对象 |
| AC-14 | 扩展查询失败不阻断主结果，返回 partial 并标记 missing_fields |
| AC-15 | 输出结构固定稳定，可被下游 Skill 直接复用 |
| AC-16 | 对 Hold / Exception / Deallocated / Shipped / Connector Health 等关键状态，应自动展开重点信息，减少用户二次追问 |

---

## 16. 展示原则

oms_query 的结果展示不应只是字段堆砌，而应优先输出用户最关心的结论。

### 16.1 订单类展示顺序建议

1. 当前结论：状态、是否异常、是否 Hold、是否已发运
2. 来源：渠道、店铺、平台单号
3. 商品与库存：商品行、SKU、库存摘要
4. 仓库与分仓：当前仓、仓内状态、仓内单号、为什么是这个仓
5. 发运与追踪：carrier、service、tracking、ETA、当前运输进度
6. 同步与回传：是否同步三方、成功失败情况
7. 时长：订单龄、仓处理时长、在途时长
8. 最近事件

### 16.2 集成中心展示顺序建议

1. 当前连接器 / 渠道名称
2. 当前状态：已连接 / 草稿 / 认证异常 / 运行异常
3. 配置摘要：认证方式、环境、启用对象
4. 支持能力：支持订单 / 库存 / 发运 / 回传哪些能力
5. 健康状态：最近测试连接、最近同步、最近失败
6. 可继续追问：怎么配置、能同步什么、最近失败原因

### 16.3 超级查询原则

当用户给出一个主对象时，Skill 应尽量一次性补全该对象当前状态下最关键的信息，
尽量减少用户二次追问。

---

## 17. 推荐架构（实现指导）

### 17.1 整体架构

```
对外：oms_query（统一 Skill 入口）
  │
  ├── OMSQueryEngine（顶层编排器）
  │     ├── ObjectResolver（多对象识别器）
  │     ├── QueryPlanGenerator（查询计划生成器）
  │     ├── StateAwareEnhancer（状态感知增强器）
  │     └── ResultMerger（结果合并器）
  │
  ├── 能力域 Provider（每个域一个独立模块）
  │     ├── OrderProvider        → 订单详情/状态/来源/商品/地址
  │     ├── InventoryProvider    → 库存/库存变动
  │     ├── WarehouseProvider    → 仓库列表/能力/限制
  │     ├── AllocationProvider   → 分仓结果/候选仓/解除分配
  │     ├── RuleProvider         → 路由规则/自定义规则/Hold规则/SKU仓规则
  │     ├── FulfillmentProvider  → 履约执行/仓内状态/包裹
  │     ├── ShipmentProvider     → 发运/追踪/ETA/签收
  │     ├── SyncProvider         → 发运同步/回传状态
  │     ├── EventProvider        → 时间线/日志/异常事件/拆单详情
  │     ├── IntegrationProvider  → 连接器/渠道/认证/能力/健康
  │     └── BatchProvider        → 批量统计/列表查询
  │
  └── 共享基础设施
        ├── OMSAPIClient（认证/HTTP）
        ├── QueryCache（缓存）
        ├── StatusNormalizer（状态归一化）
        └── errors.py（错误定义）
```

### 17.2 Provider 接口约定

每个 Provider 实现统一接口：

```python
class BaseProvider:
    def __init__(self, client: OMSAPIClient, cache: QueryCache): ...
    def query(self, context: QueryContext) -> ProviderResult: ...
```

- `QueryContext` 包含：primary_key、merchant_no、intents、已获取的上游数据
- `ProviderResult` 包含：data（域特定结果）、called_apis、failed_apis、errors

### 17.3 现有代码迁移策略

| 现有模块 | 迁移方式 |
|---------|---------|
| api_client.py / cache.py / config.py / errors.py | 直接复用 |
| status_normalizer.py | 直接复用，增加 Deallocated 布尔 |
| identifier_resolver.py | 升级为 ObjectResolver，增加 SKU/仓库/连接器识别 |
| query_orchestrator.py | 拆分：编排逻辑上移到 OMSQueryEngine，API 调用下沉到各 Provider |
| result_assembler.py | 拆分：各 Provider 自己组装子结果，顶层只做合并 |
| models.py | 拆分为 models/ 包，每个域一个子模块 |
