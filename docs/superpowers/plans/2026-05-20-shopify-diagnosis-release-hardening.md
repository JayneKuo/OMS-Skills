# Shopify Diagnosis Release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `product-diagnosis` Shopify platform readiness output complete enough for the first product agent release.

**Architecture:** Keep Shopify-specific logic isolated in `platform_requirements/shopify.py`, and keep `engine.py` responsible for shaping diagnosis responses. Add checklist and clearer remediation metadata without adding live Shopify calls, publishing, retries, or non-Shopify channel rules.

**Tech Stack:** Python 3.12, pytest, rule-based diagnosis engine under `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine`.

---

## File Structure

- Modify `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/platform_requirements/shopify.py`
  - Keep Shopify readiness rule evaluation here.
  - Add a `readiness_checklist` output beside `blocking_issues` and `ready_to_publish`.
- Modify `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`
  - Pass Shopify checklist through `details.readiness_checklist`.
  - Add clearer ShopifyV3 remediation recommendation when connector/channel-type issue is detected.
- Modify `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
  - Add failing tests before implementation for checklist and ShopifyV3 recommendation behavior.
  - Keep existing tests unchanged unless output contract intentionally expands.
- Modify `.kiro/skills/product-diagnosis/CAPABILITY_STATUS.md`
  - Update Shopify release scope and verified coverage after tests pass.

---

### Task 1: Add Shopify readiness checklist contract

**Files:**
- Modify: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Modify: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/platform_requirements/shopify.py`
- Modify: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`

- [ ] **Step 1: Write failing test for blocked checklist items**

Add this test to `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py` after `test_shopify_readiness_reports_missing_fields_for_official_admin_api`:

```python
def test_shopify_readiness_includes_blocked_checklist_items():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SHOPIFY-SKU",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {"title": "", "image_count": 0},
                    "skus": [
                        {"seller_sku": "", "price": None, "currency": None}
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["details"]["readiness_checklist"] == [
        {"item": "商品标题", "status": "blocked", "evidence": "缺少 Shopify 商品标题", "issue_code": "missing_product_title"},
        {"item": "Variant", "status": "ready", "evidence": "1 个 variant 可用"},
        {"item": "Variant SKU", "status": "blocked", "evidence": "缺少可追踪的 variant SKU", "issue_code": "missing_variant_sku"},
        {"item": "Variant 价格", "status": "blocked", "evidence": "缺少 variant 价格", "issue_code": "missing_variant_price"},
        {"item": "Variant 币种", "status": "blocked", "evidence": "缺少 variant 币种", "issue_code": "missing_variant_currency"},
        {"item": "商品图片", "status": "blocked", "evidence": "缺少商品 media/image", "issue_code": "missing_product_media"},
        {"item": "OMS Shopify 渠道类型", "status": "ready", "evidence": "SHOPIFY 可用于当前发布服务"},
    ]
```

- [ ] **Step 2: Run the focused test and verify red state**

Run:

```bash
python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_shopify_readiness_includes_blocked_checklist_items -v
```

Expected: FAIL because `details.readiness_checklist` is missing.

- [ ] **Step 3: Implement checklist in Shopify evaluator**

In `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/platform_requirements/shopify.py`, update `evaluate_shopify_readiness()` to build checklist entries while preserving existing issue codes and order:

```python
def _checklist_item(item: str, status: str, evidence: str, issue_code: str | None = None) -> dict:
    result = {"item": item, "status": status, "evidence": evidence}
    if issue_code:
        result["issue_code"] = issue_code
    return result
```

Inside `evaluate_shopify_readiness()`, after `issues = []`, add local booleans for each condition and append checklist entries in this order:

```python
has_title = bool(product.get("title"))
has_variants = bool(skus)
has_variant_sku = all(sku.get("seller_sku") or sku.get("sku") for sku in skus) if skus else True
has_variant_price = all(sku.get("price") not in (None, "") for sku in skus) if skus else True
has_variant_currency = all(bool(sku.get("currency")) for sku in skus) if skus else True
needs_options = len(skus) > 1
has_options = bool(product.get("salesAttributes") or product.get("sales_attributes") or product.get("options"))
has_media = (product.get("image_count") or 0) > 0 or bool(product.get("imageInfo"))
has_unsupported_shopifyv3_error = False
```

When detecting ShopifyV3 unsupported channel type, set `has_unsupported_shopifyv3_error = True` before appending the existing `unsupported_oms_shopify_channel_type` issue.

Before the return statement, construct:

```python
checklist = [
    _checklist_item("商品标题", "ready", str(product.get("title")))
    if has_title else _checklist_item("商品标题", "blocked", "缺少 Shopify 商品标题", "missing_product_title"),
    _checklist_item("Variant", "ready", f"{len(skus)} 个 variant 可用")
    if has_variants else _checklist_item("Variant", "blocked", "缺少 Shopify variant", "missing_variant"),
    _checklist_item("Variant SKU", "ready", "variant SKU 已提供")
    if has_variant_sku else _checklist_item("Variant SKU", "blocked", "缺少可追踪的 variant SKU", "missing_variant_sku"),
    _checklist_item("Variant 价格", "ready", "variant 价格已提供")
    if has_variant_price else _checklist_item("Variant 价格", "blocked", "缺少 variant 价格", "missing_variant_price"),
    _checklist_item("Variant 币种", "ready", "variant 币种已提供")
    if has_variant_currency else _checklist_item("Variant 币种", "blocked", "缺少 variant 币种", "missing_variant_currency"),
]
if needs_options:
    checklist.append(
        _checklist_item("Variant Options", "ready", "多 variant options 已提供")
        if has_options else _checklist_item("Variant Options", "blocked", "缺少多 variant options", "missing_variant_options")
    )
checklist.extend([
    _checklist_item("商品图片", "ready", "商品 media/image 已提供")
    if has_media else _checklist_item("商品图片", "blocked", "缺少商品 media/image", "missing_product_media"),
    _checklist_item("OMS Shopify 渠道类型", "blocked", "ShopifyV3 不被当前 OMS 发布服务支持", "unsupported_oms_shopify_channel_type")
    if has_unsupported_shopifyv3_error else _checklist_item("OMS Shopify 渠道类型", "ready", "SHOPIFY 可用于当前发布服务"),
])
```

Return checklist:

```python
return {
    "ready_to_publish": not issues,
    "blocking_issues": issues,
    "readiness_checklist": checklist,
}
```

- [ ] **Step 4: Pass checklist through engine details**

In `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`, inside `_diagnose_shopify_readiness()`, add this under `"blocking_issues": issues,`:

```python
"readiness_checklist": readiness["readiness_checklist"],
```

- [ ] **Step 5: Run the focused test and verify green state**

Run:

```bash
python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_shopify_readiness_includes_blocked_checklist_items -v
```

Expected: PASS.

---

### Task 2: Add ready checklist coverage

**Files:**
- Modify: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Modify if needed: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/platform_requirements/shopify.py`

- [ ] **Step 1: Write failing test for complete Shopify checklist**

Add this assertion block to the existing `test_shopify_readiness_passes_for_complete_single_variant_product`:

```python
    assert result["details"]["readiness_checklist"] == [
        {"item": "商品标题", "status": "ready", "evidence": "Ready Product"},
        {"item": "Variant", "status": "ready", "evidence": "1 个 variant 可用"},
        {"item": "Variant SKU", "status": "ready", "evidence": "variant SKU 已提供"},
        {"item": "Variant 价格", "status": "ready", "evidence": "variant 价格已提供"},
        {"item": "Variant 币种", "status": "ready", "evidence": "variant 币种已提供"},
        {"item": "商品图片", "status": "ready", "evidence": "商品 media/image 已提供"},
        {"item": "OMS Shopify 渠道类型", "status": "ready", "evidence": "SHOPIFY 可用于当前发布服务"},
    ]
```

- [ ] **Step 2: Run focused pass-case test**

Run:

```bash
python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_shopify_readiness_passes_for_complete_single_variant_product -v
```

Expected: PASS if Task 1 implementation is correct; if it fails, adjust checklist evidence to match the exact contract above.

---

### Task 3: Make ShopifyV3 remediation explicit

**Files:**
- Modify: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Modify: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`

- [ ] **Step 1: Write failing test for ShopifyV3 recommendation**

Add these assertions to `test_shopify_readiness_uses_0324fan_product_query_fixture`:

```python
    assert result["recommendations"] == [
        {
            "action": "use_supported_shopify_channel_type",
            "precondition": "确认 OMS 渠道配置中存在 SHOPIFY channel type",
            "risk": "继续使用 ShopifyV3 会被当前 OMS 发布服务拒绝",
            "priority": "high",
            "expected_effect": "改用 SHOPIFY 后可进入 Shopify 发布前置校验或发布流程",
        }
    ]
    assert result["details"]["readiness_checklist"][-1] == {
        "item": "OMS Shopify 渠道类型",
        "status": "blocked",
        "evidence": "ShopifyV3 不被当前 OMS 发布服务支持",
        "issue_code": "unsupported_oms_shopify_channel_type",
    }
```

- [ ] **Step 2: Run focused fixture test and verify red state**

Run:

```bash
python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_shopify_readiness_uses_0324fan_product_query_fixture -v
```

Expected: FAIL because recommendations still use the generic `complete_shopify_required_product_data` action.

- [ ] **Step 3: Implement ShopifyV3 recommendation selection**

In `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`, inside `_diagnose_shopify_readiness()` after `ready = readiness["ready_to_publish"]`, add:

```python
has_unsupported_channel_type = any(issue.get("code") == "unsupported_oms_shopify_channel_type" for issue in issues)
recommendation = (
    {
        "action": "use_supported_shopify_channel_type",
        "precondition": "确认 OMS 渠道配置中存在 SHOPIFY channel type",
        "risk": "继续使用 ShopifyV3 会被当前 OMS 发布服务拒绝",
        "priority": "high",
        "expected_effect": "改用 SHOPIFY 后可进入 Shopify 发布前置校验或发布流程",
    }
    if has_unsupported_channel_type
    else {
        "action": "complete_shopify_required_product_data",
        "precondition": "确认 OMS 商品主档、SKU、价格、选项和图片字段",
        "risk": "缺失字段会导致 Shopify productSet/productCreate/productVariantsBulkCreate 发布失败或发布后商品不可售",
        "priority": "high" if issues else "low",
        "expected_effect": "满足 Shopify 发布前置条件后再执行真实发布",
    }
)
```

Replace the current `recommendations` list with:

```python
"recommendations": [recommendation],
```

- [ ] **Step 4: Run focused fixture test and verify green state**

Run:

```bash
python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_shopify_readiness_uses_0324fan_product_query_fixture -v
```

Expected: PASS.

---

### Task 4: Update capability status and verify release scope

**Files:**
- Modify: `.kiro/skills/product-diagnosis/CAPABILITY_STATUS.md`

- [ ] **Step 1: Update status document**

Edit `.kiro/skills/product-diagnosis/CAPABILITY_STATUS.md`:

- Change `Last updated` to `2026-05-20`.
- Under Shopify readiness MVP, add bullets:

```markdown
- Outputs `details.readiness_checklist` for Shopify release readiness display.
- Uses a ShopifyV3-specific recommendation when OMS publish history shows the connector/channel type is unsupported.
```

- Under verified coverage, add bullets:

```markdown
- Shopify readiness checklist for blocked product data.
- Shopify readiness checklist for complete single-variant product data.
- ShopifyV3-specific remediation recommendation for the real `0324fan` fixture.
```

- Under boundaries, keep explicit:

```markdown
- First release scope is Shopify only; SHEIN/Amazon/TikTok readiness rules are intentionally deferred.
```

- [ ] **Step 2: Run full product-diagnosis tests**

Run:

```bash
python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py
```

Expected: all tests pass.

- [ ] **Step 3: Run product-listing-planner tests for integration confidence**

Run:

```bash
python -m pytest .kiro/skills/product-listing-planner/tests
```

Expected: all tests pass.

- [ ] **Step 4: Check git diff**

Run:

```bash
git diff -- .kiro/skills/product-diagnosis .kiro/skills/product-listing-planner docs/superpowers/plans/2026-05-20-shopify-diagnosis-release-hardening.md
```

Expected: diff only includes Shopify diagnosis release hardening, status doc updates, and this plan.

---

## Self-Review

- Spec coverage: The plan covers Shopify-only release hardening, readiness checklist output, ShopifyV3 remediation, docs/status update, and verification. It intentionally excludes SHEIN, live Shopify API calls, publishing, retries, and mutation behavior.
- Placeholder scan: No TBD/TODO/fill-in-later placeholders are present.
- Type consistency: `evaluate_shopify_readiness()` returns `ready_to_publish`, `blocking_issues`, and `readiness_checklist`; `engine.py` passes those fields under `details` and keeps recommendation output as a single-item list.
