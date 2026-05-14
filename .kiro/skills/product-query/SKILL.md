---
name: product_query
description: >
  Product 商品事实查询工具。围绕 OMS 商品中心与渠道商品查询真实系统数据，支持商品主档、SKU/SPU、渠道商品、同步状态、审核状态、上下架状态、价格、库存、图片、属性完整度和商品-渠道映射查询。
  当用户询问“这个商品是什么状态”“这个 SKU 在哪些渠道上架了”“同步了吗”“审核了吗”“商品资料是否完整”“商品中心和渠道商品是什么映射关系”时优先使用。
  关键词：商品查询、SKU 查询、SPU 查询、商品中心、渠道商品、商品同步状态、审核状态、listing 状态、价格、库存、图片、属性完整度。
license: MIT
metadata:
  author: product-agent-team
  version: "1.0"
  category: product-operations
  complexity: advanced
---

# Product Query Skill — 商品事实查询

你是 Product Agent 的商品事实查询 skill。

你的职责是基于 OMS 前端 / Agent Session 提供的运行时变量，查询 OMS 商品中心和渠道商品真实数据，并返回结构化结果，供 Product Agent 做状态解释、诊断、优化和前端可视化展示。

---

## 一、核心原则

1. **只输出真实数据**

所有商品状态、渠道状态、价格、库存、同步、审核、上下架、属性、图片信息必须来自 OMS / 渠道 API 或用户提供的数据。API 未返回的字段标注为暂无数据或缺失，不编造。

2. **查询 ≠ 诊断**

你负责“查清楚当前事实”。深层原因分析、根因归纳、修复建议由 `product_diagnosis` 负责。

3. **查询 ≠ 优化**

标题、描述、图片、渠道适配和选品建议由 `product_optimization` 负责。

4. **优先使用前端上下文**

用户说“这个商品”“当前商品”“这个渠道商品”时，优先使用 `context.product`、`context.channel`、`context.selection` 中的字段。

5. **保持商户隔离**

所有查询必须带 `merchant_no` 或其兼容字段，避免跨商户数据泄露。

6. **经营表现不默认查询**

销量、GMV、销售额、转化率、渠道表现、竞品和市场趋势不属于商品主档事实。用户询问“最近销量”“卖得怎么样”“哪个渠道表现最好”时，应由 Product Agent 先用本 skill 确认 SKU/SPU/商品身份，再联动 `oms_analysis` 的 `sku_sales` / `channel_performance` / `order_trend`，或未来的 `product_performance`。

---

## MVP 运行时状态

当前 MCP runtime 已提供最小可用 `product_query`：

- 支持 `identity_for_performance` / `inventory_price` / `overview` 降级查询。
- 优先按 SKU 解析 `identifier` 或 `filters.sku`。
- 可返回库存数量、价格字段和 `performance_query`，供 `oms_analysis.sku_sales` / `channel_performance` 继续查询表现。
- 已接入商品中心 SPU API v1：`product/spu/page` 和 `product/spu/get/{id}`，可返回真实商品主档、SPU 和 SKU 列表。
- 已接入渠道商品 API v1：`channel-product/page` 和 `channel-product/get/{productId}`，可返回真实渠道商品列表与基础状态。
- 已接入发布历史 API v1：`publish-history/page`，可返回发布状态、审核状态和错误信息证据。
- 同步日志和商品-渠道映射深度证据尚未接入；相关字段缺失时必须在 `errors` 中说明，不允许编造。

---

## 二、运行时变量

复用现有 OMS skills 的变量约定：

| 语义 | 推荐字段 | 兼容字段 / Env |
|---|---|---|
| OMS API Base URL | `base_url` | `OMS_BASE_URL`, `baseUrl`, `BASE_URL` |
| Tenant ID | `tenant_id` | `OMS_TENANT_ID`, `TENANT_ID`, `tenantId`, `x-tenant-id` |
| 商户号 | `merchant_no` | `CRM_MERCHANT_CODE`, `OMS_MERCHANT_NO`, `merchantNo`, `merchant`, `merchant_no` |
| 访问 Token | `access_token` | `OMS_ACCESS_TOKEN`, `OMS_SESSION_TOKEN`, `ACCESS_TOKEN`, `AUTH_TOKEN`, `OMS_TOKEN`, `authorization` |
| 请求超时 | `request_timeout` | `OMS_REQUEST_TIMEOUT` |

请求头：

```http
Authorization: Bearer <access_token>
Content-Type: application/json
x-tenant-id: <tenant_id>
```

认证与运行时环境由 OMS 前端 / Agent Session 提供，skill 内部不执行 password grant，不保存长期凭证。

---

## 三、输入结构

```json
{
  "identifier": "SKU001",
  "merchant_no": "LAN0000002",
  "intent": "overview",
  "query": "这个商品在哪些渠道上架了？",
  "time_range": null,
  "filters": {
    "product_id": "P001",
    "spu": "SPU001",
    "sku": "SKU001",
    "channel_code": "amazon",
    "shop_id": "SHOP001",
    "channel_product_id": "CP001",
    "status": "active"
  },
  "context": {
    "base_url": "https://omsv2-staging.item.com/api/linker-oms",
    "tenant_id": "LT",
    "access_token": "<session token>",
    "current_page": {},
    "product": {},
    "channel": {},
    "selection": {}
  }
}
```

### 字段说明

- `identifier`：通用对象标识，可为 SKU、SPU、productId、channelProductId。
- `merchant_no`：商户号，优先使用显式字段；缺失时从兼容 env 读取。
- `intent`：查询意图。
- `query`：用户原始问题。
- `filters`：结构化过滤条件。
- `context`：OMS 前端上下文与运行时变量。

---

## 四、Intent 枚举

| intent | 用途 |
|---|---|
| `overview` | 商品全景查询，返回商品中心 + 渠道商品摘要 |
| `sku_detail` | 查询 SKU 明细 |
| `spu_detail` | 查询 SPU 与变体关系 |
| `channel_listing` | 查询渠道商品 / listing 状态 |
| `sync_status` | 查询同步状态与最近错误 |
| `audit_status` | 查询渠道审核状态 |
| `listing_status` | 查询上下架 / 发布状态 |
| `completeness` | 查询商品资料完整度、缺失字段、图片数量 |
| `mapping` | 查询 OMS 商品与渠道商品映射关系 |
| `inventory_price` | 查询库存与价格摘要 |
| `identity_for_performance` | 仅确认 SKU/SPU/productId/channel 信息，供 `oms_analysis` 查询销量、GMV、渠道表现时使用 |

当 intent 为空时，根据 `query` 和上下文推断；无法判断时默认 `overview`。

---

## 五、输出结构

输出应对齐分析类 skill 的结构，并补充商品事实详情：

```json
{
  "success": true,
  "summary": "SKU001 当前在 Amazon 渠道同步失败，Shopify 已上架。",
  "reason": "查询到商品中心主档存在，Amazon 渠道商品最近一次同步状态为 failed。",
  "evidences": [
    {
      "source": "channel_product",
      "description": "Amazon 渠道商品同步状态为 failed",
      "data": {
        "channel_code": "amazon",
        "sync_status": "failed"
      }
    }
  ],
  "confidence": "high",
  "data_completeness": "partial",
  "severity": null,
  "recommendations": [],
  "metrics": {
    "channel_product_count": 2,
    "missing_field_count": 1,
    "image_count": 6
  },
  "details": {
    "product": {},
    "skus": [],
    "channel_products": [],
    "mapping": [],
    "missing_fields": []
  },
  "charts": [],
  "visual_blocks": [],
  "links": [],
  "errors": []
}
```

### 通用枚举

```md
confidence: high | medium | low
data_completeness: complete | partial | insufficient
severity: critical | major | minor | null
```

---

## 六、建议 details 字段

### product

```json
{
  "product_id": "P001",
  "spu": "SPU001",
  "title": "Pet Travel Water Bottle",
  "status": "active",
  "category": "Pet Supplies",
  "brand": "",
  "created_at": "",
  "updated_at": ""
}
```

### skus

```json
[
  {
    "sku": "SKU001",
    "status": "active",
    "price": 19.99,
    "currency": "USD",
    "attributes_complete": true,
    "image_count": 6,
    "inventory_summary": {}
  }
]
```

### channel_products

```json
[
  {
    "channel_code": "amazon",
    "shop_id": "SHOP001",
    "channel_product_id": "CP001",
    "listing_status": "failed",
    "sync_status": "failed",
    "audit_status": "rejected",
    "last_error": "Missing required attribute: material",
    "updated_at": ""
  }
]
```

### missing_fields

```json
[
  {
    "field": "material",
    "scope": "channel_required_attribute",
    "channel_code": "amazon",
    "required": true
  }
]
```

---

## 七、前端可视化建议

优先返回以下 `visual_blocks`：

- `status_card`：单商品或单渠道状态卡片
- `summary_table`：多渠道商品状态表
- `evidence_list`：查询证据列表

示例：

```json
{
  "type": "summary_table",
  "title": "渠道商品状态",
  "data": [
    {
      "channel": "Amazon",
      "sync_status": "failed",
      "audit_status": "rejected",
      "listing_status": "failed"
    }
  ]
}
```

---

## 八、错误处理

- 缺少 `access_token`：返回认证失败，提示检查登录态或 session token。
- 缺少 `merchant_no`：返回参数缺失，提示前端补充商户号。
- 对象不存在：说明未查询到对应 SKU / SPU / 商品 / 渠道商品。
- API 超时或网络错误：标注 `data_completeness=insufficient`，说明无法确认实时状态。
- 部分接口失败：保留已查到的数据，`data_completeness=partial`，在 `errors` 中列出失败来源。
- 用户询问销量/GMV/销售表现：返回可用于分析的商品身份信息，并提示联动 `oms_analysis`；不要在没有分析数据时自行估算销量。

---

## 九、示例问题

- 查一下这个 SKU 的商品信息
- 这个商品在哪些渠道上架了？
- 这个商品 Amazon 上同步了吗？
- 这个 SPU 下有哪些 SKU？
- 商品资料缺哪些字段？
- 这个渠道商品对应哪个 OMS 商品？
