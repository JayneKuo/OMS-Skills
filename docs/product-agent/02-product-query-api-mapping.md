# Product Query MVP API Mapping

## 1. MVP 定位

本文档定义 Product Agent 第一版可依赖的 `product_query` 数据来源、支持问题、降级边界和验收场景。

第一版目标是 **可用、可解释、不编造**：

- 已接入的数据可以作为事实和 evidence 使用。
- 未接入的数据必须明确标注为缺失、部分支持或暂不支持。
- 诊断、优化和刊登规划必须基于 `product_query` 返回的 evidence，不得补全系统没有返回的状态、错误原因或市场结论。

## 2. Runtime 输入

`product_query` 第一版使用以下输入：

| 字段 | 用途 | MVP 说明 |
|---|---|---|
| `identifier` | 通用商品标识 | 可为 SKU、SPU、productId 或 channelProductId，优先结合 `filters` 判断 |
| `merchant_no` | 商户隔离 | 必须用于查询约束，避免跨商户数据混淆 |
| `intent` | 查询意图 | 支持 `overview`、`inventory_price`、`identity_for_performance` 等 MVP intent |
| `filters` | 结构化过滤条件 | 支持 SKU、SPU、product_id、channel_code、shop_id、channel_product_id |
| `context` | OMS 前端 / Agent Session 上下文 | 可提供 base_url、tenant_id、access_token、当前商品、当前渠道和页面选择 |

运行时变量来源：

| 语义 | 推荐字段 | 兼容字段 / Env |
|---|---|---|
| OMS API Base URL | `base_url` | `OMS_BASE_URL`、`baseUrl`、`BASE_URL` |
| Tenant ID | `tenant_id` | `OMS_TENANT_ID`、`TENANT_ID`、`tenantId`、`x-tenant-id` |
| 商户号 | `merchant_no` | `CRM_MERCHANT_CODE`、`OMS_MERCHANT_NO`、`merchantNo`、`merchant` |
| Access Token | `access_token` | `OMS_ACCESS_TOKEN`、`OMS_SESSION_TOKEN`、`ACCESS_TOKEN`、`AUTH_TOKEN`、`OMS_TOKEN`、`authorization` |

## 3. MVP API Mapping

| 能力项 | 当前 API / Runtime 来源 | 入参来源 | 输出字段 | Evidence 来源 | 当前限制 |
|---|---|---|---|---|---|
| 商品身份确认 | `product_query` identity resolution | `identifier`、`filters.sku`、`filters.spu`、`filters.product_id`、`context.product` | SKU、SPU、productId、channelProductId、channel_code、shop_id | 请求入参、前端上下文、已查到的商品/渠道商品记录 | 无法保证所有 identifier 类型都能自动识别；失败时需要用户补 SKU/SPU/productId |
| 商品中心 SPU 列表 | `/baseservice/rpc-api/product/spu/page` | `merchant_no`、SKU/SPU/product filters | SPU 摘要、商品主档摘要、SKU 列表摘要 | SPU page 返回记录 | SKU 独立主数据 API 尚未作为 MVP 强依赖 |
| 商品中心 SPU 详情 | `/baseservice/rpc-api/product/spu/get/{id}` | productId / SPU id | SPU 详情、变体、基础属性 | SPU get 返回详情 | 字段完整度按已返回字段判断，不推断渠道必填项 |
| 渠道商品列表 | `/baseservice/rpc-api/channel-product/page` | `merchant_no`、productId、SKU/SPU、channel_code、shop_id | 渠道商品列表、渠道、店铺、基础状态 | channel-product page 返回记录 | 深度商品-渠道映射链路未接入 |
| 渠道商品详情 | `/baseservice/rpc-api/channel-product/get/{productId}` | channel product id / product id | 渠道商品详情、基础 listing 状态 | channel-product get 返回详情 | 渠道侧完整错误详情以 API 返回为准，不补全 |
| 发布/审核/上架证据 | `/baseservice/rpc-api/publish-history/page` | productId、channel_product_id、channel_code、shop_id | 发布状态、审核状态、错误信息、时间 | publish-history page 返回记录 | 只能说明发布历史可见的失败信息；精准根因仍依赖同步日志或渠道错误详情 |
| 库存/价格摘要 | 现有 `InventoryAdapter` / `inventory_price` runtime | SKU、merchant_no、shop/channel filters | 库存数量、价格摘要、可用库存相关字段 | 库存 API / adapter 返回结果 | 多仓、多渠道价格规则和促销价不是 MVP 强承诺 |
| 销售表现衔接 | `identity_for_performance` + `performance_query` + `oms_analysis` / `product_performance` | SKU/SPU/productId、channel_code、shop_id、time_range | 可传给 `sku_sales`、`channel_performance` 的查询条件 | product_query 身份确认结果 + oms_analysis 返回结果 | `product_query` 本身不输出销量、GMV、转化率；必须联动分析能力 |

## 4. MVP 支持的 Intent

| intent | MVP 支持程度 | 第一版行为 |
|---|---|---|
| `overview` | 支持 | 返回商品中心摘要、渠道商品摘要、发布历史摘要和可用 evidence |
| `sku_detail` | 部分支持 | 优先通过 SPU / 商品记录中的 SKU 信息回答；独立 SKU API 未确认时标注限制 |
| `spu_detail` | 支持 | 使用 SPU page/get 返回商品主档和变体信息 |
| `channel_listing` | 支持 | 使用 channel-product page/get 返回渠道商品和基础状态 |
| `sync_status` | 部分支持 | 使用 publish history 和渠道商品状态说明可见状态；同步日志未接入时不输出精准根因 |
| `audit_status` | 部分支持 | 使用 publish history 中的审核状态和错误信息作为证据 |
| `listing_status` | 部分支持 | 使用 channel-product 状态与 publish history 说明上架/发布状态 |
| `completeness` | 部分支持 | 只能基于商品主档已返回字段做粗略缺失提示，不承诺渠道类目必填字段完整校验 |
| `mapping` | 部分支持 | 只能基于 productId、channelProductId、SKU/SPU 和渠道商品记录说明可见映射 |
| `inventory_price` | 支持 | 使用现有库存/价格摘要能力返回 SKU 库存和价格信息 |
| `identity_for_performance` | 支持 | 返回 `performance_query`，供 `oms_analysis` 或 `product_performance` 查询销量/GMV/渠道表现 |

## 5. 第一版可以回答的问题

### 5.1 商品当前是什么状态？

可以回答商品中心是否查到、SPU/SKU 基础信息、渠道商品是否存在、可见渠道状态和最近发布历史。

如果缺少同步日志，应说明：当前只能看到发布/渠道状态，无法确认更深层同步链路根因。

### 5.2 这个 SKU 在哪些渠道有渠道商品？

可以基于 channel-product 列表返回渠道、店铺、channelProductId 和基础状态。

如果 SKU 到 SPU / productId 的映射不足，应要求补充 productId 或使用前端当前商品上下文。

### 5.3 为什么发布、审核或上架失败？

可以基于 publish-history 中的状态、错误信息和时间做初步诊断 evidence。

如果 publish-history 没有错误详情，应回答证据不足，并提示需要同步日志、渠道错误详情或更完整的 channel product detail。

### 5.4 这个 SKU 库存和价格是多少？

可以使用 `inventory_price` 返回现有库存和价格摘要。

如果涉及多仓、促销价、渠道价差或未来库存，应说明这些不是第一版强承诺能力。

### 5.5 这个商品最近卖得怎么样？

`product_query` 只负责确认 SKU/SPU/productId/channel/shop，并返回 `performance_query`。

销量、GMV、订单数和渠道表现必须由 `oms_analysis.sku_sales`、`oms_analysis.channel_performance` 或 `product_performance` 返回。

## 6. 第一版不能强承诺的问题

| 问题类型 | MVP 回答方式 |
|---|---|
| 精准同步失败根因 | 只能基于 publish history / channel product 可见错误初步判断；缺同步日志时必须说明证据不足 |
| 商品-渠道深度映射链路 | 只能展示可见 productId、channelProductId、SKU/SPU 关系；不还原完整链路 |
| 渠道类目必填字段完整度 | 只能基于已返回字段提示，不承诺按渠道类目规则完整校验 |
| 图片同步详情 | 未接入图片同步日志时，不判断具体图片同步失败原因 |
| 市场、竞品、关键词、趋势 | 当前不支持；除非用户提供数据或后续接入外部市场数据 skill |
| 转化率、广告表现、Review pain points | 当前不支持；不能用 OMS 商品资料推断 |

## 7. 降级回答规则

1. API 未接入时，不编造字段、状态或原因。
2. API 返回为空时，区分“查无数据”和“查询条件不足”。
3. evidence 不完整时，`data_completeness` 应标注为 `partial` 或 `insufficient`。
4. 能看到状态但看不到原因时，应明确说“当前只能确认状态，不能确认根因”。
5. 身份无法解析时，应要求用户补充 SKU、SPU、productId 或 channelProductId。
6. 涉及销售表现时，必须通过 `performance_query` 联动 `oms_analysis`，不能由商品资料直接推断销量或 GMV。

## 8. MVP 输出结构要求

`product_query` 第一版输出应保持统一结构：

```json
{
  "success": true,
  "summary": "当前商品中心存在该商品，并查到 2 个渠道商品。",
  "reason": "商品中心 SPU 接口和渠道商品接口均返回有效记录。",
  "evidences": [
    {
      "source": "product_spu",
      "description": "商品中心返回 SPU 记录",
      "data": {}
    }
  ],
  "confidence": "medium",
  "data_completeness": "partial",
  "metrics": {},
  "details": {},
  "visual_blocks": [],
  "links": [],
  "errors": []
}
```

字段要求：

| 字段 | 要求 |
|---|---|
| `summary` | 用业务语言概括查询结果 |
| `reason` | 说明结论来自哪些数据源 |
| `evidences` | 每个关键状态必须有来源 |
| `confidence` | 根据 evidence 完整度给出 high / medium / low |
| `data_completeness` | 使用 complete / partial / insufficient 表示数据完整度 |
| `metrics` | 放库存数量、渠道商品数量、发布历史数量等摘要指标 |
| `details` | 放商品、渠道商品、发布历史、performance_query 等结构化明细 |
| `visual_blocks` | 供前端渲染状态卡、表格或提示块 |
| `links` | 只放可跳转的 OMS 前端链接 |
| `errors` | 放缺失 API、查询失败或证据不足说明 |

## 9. MVP 验收场景

### 场景 1：overview 查询

输入：SKU 或 productId。

预期：返回商品中心摘要、渠道商品摘要、发布历史摘要；如果某类数据缺失，`errors` 中说明缺失原因。

### 场景 2：channel_listing 查询

输入：SKU/SPU/productId + 可选 channel_code。

预期：返回渠道商品列表、渠道、店铺、channelProductId、基础状态和 evidence。

### 场景 3：listing_status / audit_status 查询

输入：channelProductId 或 productId + channel_code。

预期：返回 publish-history 可见的发布/审核状态、错误信息和时间；没有错误详情时不编造根因。

### 场景 4：inventory_price 查询

输入：SKU + merchant_no。

预期：返回库存和价格摘要；如果只查到库存或只查到价格，标注 `data_completeness=partial`。

### 场景 5：identity_for_performance 查询

输入：SKU/SPU/productId + 可选 channel_code/shop_id。

预期：返回 `performance_query`，其中包含可传给 `oms_analysis.sku_sales` 或 `oms_analysis.channel_performance` 的过滤条件。

### 场景 6：证据不足降级

输入：无法解析的 identifier 或缺少 merchant_no。

预期：返回低置信度结果或失败结果，明确要求补充 SKU、SPU、productId、channelProductId 或 merchant_no，不输出猜测状态。
