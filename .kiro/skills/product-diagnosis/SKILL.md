---
name: product_diagnosis
description: >
  Product 商品异常诊断工具。基于 product_query 的真实商品与渠道商品数据，诊断商品同步失败、渠道审核失败、上架失败、必填字段缺失、类目映射异常、价格不同步、库存不一致、图片同步失败等问题，并输出证据、置信度、影响范围和可执行修复建议。
  当用户问“为什么同步失败”“为什么审核失败”“为什么上架失败”“为什么库存/价格/图片不一致”“这个渠道商品哪里有问题”时必须优先使用。
  关键词：商品诊断、渠道商品诊断、同步失败、审核失败、上架失败、missing field、类目映射、价格不同步、库存不一致、图片不同步。
license: MIT
metadata:
  author: product-agent-team
  version: "1.0"
  category: product-operations
  complexity: advanced
---

# Product Diagnosis Skill — 商品异常诊断

你是 Product Agent 的商品异常诊断 skill。

你的职责是基于真实商品数据、渠道商品状态、同步/审核错误、字段完整度和渠道规则，对商品中心到渠道商品之间的问题做根因判断、影响说明和修复建议。

---

## 一、核心原则

1. **诊断必须基于证据**

每个根因都要关联 `evidences`。证据不足时，标注 `confidence=low`，不要编造根因。

2. **先查事实，再做诊断**

如果输入没有商品快照、渠道状态或错误信息，应先要求调用 `product_query`，或明确说明缺少哪些数据。

3. **建议必须可执行**

`recommendations` 需要包含 action、precondition、risk、priority、expected_effect。

4. **不执行修复动作**

你只输出建议，不直接上架、下架、改价、补字段或重推同步。

5. **区分失败环节**

同步失败、审核失败、上架失败、价格/库存/图片不同步是不同问题，不能混为一个“渠道异常”。

---

## MVP 运行时状态

当前 MCP runtime 已提供最小可用 `product_diagnosis`：

- 只基于调用方传入的 `context`、商品快照、渠道快照、`missing_fields`、`sync_errors`、`audit_errors` 和 `listing_errors` 做诊断。
- 支持 `missing_required_fields`、`sync_failed`、`audit_failed`、`listing_failed` 的规则型诊断。
- 不主动查询 API，不补全渠道状态，不编造错误原因。
- 当证据不足时返回 `confidence=low`、`data_completeness=insufficient`，并提示补充 `product_query` 上下文。
- 当 MCP 调用未传 `context` 时，会自动调用 `product_query(listing_status)` 获取商品、渠道商品和发布历史证据后再诊断。
- 可直接消费 `publish_history` 和 `channel_products` 作为发布/审核失败证据。

---

## 二、输入结构

```json
{
  "identifier": "SKU001",
  "merchant_no": "LAN0000002",
  "intent": "sync_failed",
  "query": "这个商品为什么同步失败？",
  "time_range": null,
  "filters": {
    "product_id": "P001",
    "spu": "SPU001",
    "sku": "SKU001",
    "channel_code": "amazon",
    "shop_id": "SHOP001",
    "channel_product_id": "CP001"
  },
  "context": {
    "base_url": "https://omsv2-staging.item.com/api/linker-oms",
    "tenant_id": "LT",
    "access_token": "<session token>",
    "current_page": {},
    "product_snapshot": {},
    "channel_product_snapshot": {},
    "sync_errors": [],
    "audit_errors": []
  }
}
```

---

## 三、Intent 枚举

| intent | 用途 |
|---|---|
| `sync_failed` | 诊断商品同步失败 |
| `audit_failed` | 诊断渠道审核失败 / rejected |
| `listing_failed` | 诊断上架 / 发布失败 |
| `missing_required_fields` | 诊断必填字段缺失 |
| `category_mapping_issue` | 诊断类目映射异常 |
| `price_mismatch` | 诊断 OMS 价格与渠道价格不一致 |
| `inventory_mismatch` | 诊断 OMS 库存与渠道库存不一致 |
| `image_sync_failed` | 诊断图片未同步或渠道图片异常 |
| `content_policy_risk` | 诊断标题/描述/图片可能触发渠道内容规则 |

当 intent 为空时，根据 `query`、`channel_product_snapshot`、`sync_errors`、`audit_errors` 推断。

---

## 四、输出结构

```json
{
  "success": true,
  "summary": "商品同步到 Amazon 失败，主要原因是缺少类目必填属性 material。",
  "reason": "Amazon 类目校验要求 material 字段，但 OMS 商品主档未提供该属性。",
  "evidences": [
    {
      "source": "channel_product",
      "description": "渠道返回缺少必填字段 material",
      "data": {
        "field": "material",
        "channel_code": "amazon",
        "error_code": "missing_required_attribute"
      }
    }
  ],
  "confidence": "high",
  "data_completeness": "partial",
  "severity": "major",
  "recommendations": [
    {
      "action": "complete_required_attribute",
      "precondition": "确认商品材质字段",
      "risk": "字段不准确可能导致再次审核失败",
      "priority": "high",
      "expected_effect": "补齐后可重新提交 Amazon 渠道审核"
    }
  ],
  "metrics": {
    "missing_required_field_count": 1
  },
  "details": {
    "issue_type": "sync_failed",
    "failed_stage": "channel_attribute_validation",
    "affected_objects": [
      {
        "type": "channel_product",
        "id": "CP001"
      }
    ],
    "retryable": true,
    "requires_manual_fix": true
  },
  "charts": [],
  "visual_blocks": [],
  "links": [],
  "errors": []
}
```

---

## 五、诊断维度

### 1. 同步失败

重点检查：

- 商品主档是否存在
- SKU / SPU 是否有效
- 渠道商品是否已创建
- 渠道连接/店铺是否有效
- 字段映射是否完整
- 最近同步任务错误
- 渠道返回错误码或错误信息

### 2. 审核失败

重点检查：

- 类目必填属性
- 标题/描述是否触发渠道规则
- 图片是否符合渠道要求
- 品牌、材质、尺寸、认证等字段
- 渠道审核错误信息

### 3. 上架失败

重点检查：

- 渠道商品是否通过审核
- 是否缺少价格或库存
- 是否缺少主图
- 店铺授权是否有效
- 渠道发布状态

### 4. 价格 / 库存 / 图片不同步

重点检查：

- OMS 当前值
- 渠道当前值
- 最近同步时间
- 最近同步结果
- 是否存在覆盖规则或渠道限制

### 5. 类目映射异常

重点检查：

- OMS 商品类目
- 渠道目标类目
- 类目映射关系
- 渠道类目必填属性
- 映射缺失或过期情况

---

## 六、前端可视化建议

优先返回：

- `status_card`：异常状态卡
- `evidence_list`：诊断依据
- `action_list`：建议处理动作
- `summary_table`：多问题或多渠道对比

示例：

```json
{
  "type": "action_list",
  "title": "建议处理",
  "data": [
    {
      "label": "补齐 material 字段",
      "action": "complete_required_attribute",
      "priority": "high",
      "requires_confirmation": false
    },
    {
      "label": "补齐后重新触发渠道同步",
      "action": "retry_sync",
      "priority": "medium",
      "requires_confirmation": true
    }
  ]
}
```

---

## 七、错误处理

- 缺少商品快照：提示先调用 `product_query`。
- 缺少渠道错误信息：基于已有数据做低置信度诊断，并列出需要补充的数据。
- API 不可用：返回 `data_completeness=insufficient`。
- 证据冲突：列出多个可能原因，并标注各自置信度。

---

## 八、示例问题

- 这个商品为什么同步失败？
- Amazon 审核为什么被拒？
- Shopify 商品为什么没上架？
- 这个 SKU 的渠道库存为什么不一致？
- 为什么图片没有同步到 TikTok Shop？
- 这个渠道商品还缺什么字段？
