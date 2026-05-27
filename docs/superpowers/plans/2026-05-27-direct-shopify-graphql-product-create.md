# Direct Shopify GraphQL Product Create Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Direct Shopify GraphQL `productCreate` execution path to `product-listing-planner`, with auth collection, confirmation gating, safe default draft creation, execution, and verification.

**Architecture:** Keep OMS submit and Direct Shopify publish as separate execution actions inside `ProductListingPlannerEngine`. Add a focused Shopify adapter in `execution.py` that calls Shopify Admin GraphQL with caller-provided credentials only; credentials are never persisted. The planner generates a confirmation form and payload preview first, then `execute()` performs strict confirmation, auth validation, productCreate, optional product query verification, and returns one of the existing three final conclusions.

**Tech Stack:** Python 3.12, pytest, standard-library HTTP-compatible injected client pattern, Shopify Admin GraphQL productCreate, existing `.kiro/skills/product-listing-planner` package.

---

## File Structure

- Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`
  - Add `direct_shopify_product_create` planning form.
  - Add auth missing detection for `shop_domain`, `admin_access_token`, and `api_version`.
  - Add Shopify product payload builder from `product_query_result.details.product` and `details.skus`.
  - Extend `execute()` to route to Direct Shopify execution with strict confirmation and form token.

- Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/execution.py`
  - Add `ShopifyGraphqlExecutionAdapter`.
  - Build GraphQL URL from shop domain + API version.
  - Send `X-Shopify-Access-Token` header only through injected client call, never store it.
  - Provide `product_create()` and `get_product()` methods.

- Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/__init__.py`
  - Export `ShopifyGraphqlExecutionAdapter`.

- Modify `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`
  - Add tests for auth collection, draft payload preview, adapter endpoint/header shape, successful create, userErrors, missing auth, and verification no-effect.

- Modify `.kiro/skills/product-listing-planner/SKILL.md`
  - Document Direct Shopify GraphQL as a separate action from OMS submit.
  - Document required credentials and no persistence.
  - Document default `DRAFT` status and explicit confirmation.

- Modify `.kiro/skills/product-listing-planner/CAPABILITY_STATUS.md`
  - Add current capability and boundaries.

---

### Task 1: Add Direct Shopify planning form and auth collection

**Files:**
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`:

```python
def test_direct_shopify_plan_collects_missing_auth_before_execution():
    product_query_result = {
        "details": {
            "product": {"title": "Ready Product", "brand": "Acme", "category": "Bags", "image_count": 1},
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={"action": "direct_shopify_product_create"},
        context={"product_query_result": product_query_result},
    )

    form = result["details"]["execution_form"]
    assert form["action"] == "direct_shopify_product_create"
    assert form["requires_confirmation"] is True
    assert form["next_action"] == "collect_auth_and_user_decision"
    assert form["missing_auth_fields"] == ["shop_domain", "admin_access_token"]
    assert form["api_version"] == "2026-01"
    assert result["details"]["execution_allowed"] is False


def test_direct_shopify_plan_builds_draft_product_payload_when_auth_present():
    product_query_result = {
        "details": {
            "product": {
                "title": "Ready Product",
                "brand": "Acme",
                "category": "Bags",
                "image_count": 1,
                "price": 10,
                "currency": "USD",
            },
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": "example.myshopify.com",
            "admin_access_token": "shpat_test",
        },
        context={"product_query_result": product_query_result},
    )

    form = result["details"]["execution_form"]
    assert form["missing_auth_fields"] == []
    assert form["shop_domain"] == "example.myshopify.com"
    assert form["product_payload"] == {
        "title": "Ready Product",
        "vendor": "Acme",
        "productType": "Bags",
        "status": "DRAFT",
        "variants": [{"sku": "READY-SKU", "price": "10"}],
    }
    assert form["contains_secret"] is False
    assert "admin_access_token" not in form
    assert result["details"]["execution_allowed"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_direct_shopify_plan_collects_missing_auth_before_execution" "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_direct_shopify_plan_builds_draft_product_payload_when_auth_present" -v
```

Expected: FAIL because direct Shopify action is not supported yet.

- [ ] **Step 3: Implement planning helpers**

In `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`, add:

```python
DEFAULT_SHOPIFY_API_VERSION = "2026-01"


def _build_shopify_product_payload(details: dict, requested_status: str | None = None) -> dict:
    product = details.get("product") or {}
    skus = details.get("skus") or []
    status = str(requested_status or "DRAFT").upper()
    payload = {
        "title": product.get("title") or product.get("name") or "Untitled product",
        "vendor": product.get("brand") or "",
        "productType": product.get("category") or "",
        "status": status if status in {"DRAFT", "ACTIVE"} else "DRAFT",
        "variants": [],
    }
    for sku in skus:
        variant = {"sku": sku.get("seller_sku") or sku.get("sku") or sku.get("internal_sku_id")}
        if sku.get("price") not in (None, ""):
            variant["price"] = str(sku["price"])
        payload["variants"].append({key: value for key, value in variant.items() if value not in (None, "")})
    if not payload["variants"] and product.get("price") not in (None, ""):
        payload["variants"].append({"price": str(product["price"])})
    return payload


def _build_direct_shopify_form(identifier, merchant_no, filters: dict, details: dict) -> dict:
    shop_domain = filters.get("shop_domain")
    admin_access_token = filters.get("admin_access_token")
    api_version = filters.get("api_version") or DEFAULT_SHOPIFY_API_VERSION
    missing_auth_fields = []
    if not shop_domain:
        missing_auth_fields.append("shop_domain")
    if not admin_access_token:
        missing_auth_fields.append("admin_access_token")
    product_payload = _build_shopify_product_payload(details, filters.get("shopify_status"))
    targets = [{
        "shop_domain": shop_domain,
        "api_version": api_version,
        "allowed": not missing_auth_fields,
        "product_payload": product_payload,
    }]
    return {
        "requires_confirmation": True,
        "next_action": "collect_auth_and_user_decision" if missing_auth_fields else "collect_user_decision",
        "action": "direct_shopify_product_create",
        "merchant_no": merchant_no,
        "identifier": identifier,
        "shop_domain": shop_domain,
        "api_version": api_version,
        "missing_auth_fields": missing_auth_fields,
        "contains_secret": False,
        "product_payload": product_payload,
        "targets": targets,
        "form_token": _execution_form_token(merchant_no, identifier, "direct_shopify_product_create", targets),
    }
```

Then in `plan()`, before building the existing OMS form, branch:

```python
        action = filters.get("action") or "submit_existing_channel_product"
        if action == "direct_shopify_product_create":
            execution_form = _build_direct_shopify_form(identifier, merchant_no, filters, details)
        else:
            execution_form = _build_execution_form(action, merchant_no, identifier, target_channels, details)
        execution_allowed = any(target.get("allowed") for target in execution_form["targets"])
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

---

### Task 2: Add Shopify GraphQL adapter

**Files:**
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/execution.py`
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/__init__.py`
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Write failing adapter test**

Add:

```python
def test_shopify_graphql_execution_adapter_calls_product_create_and_get_product():
    from product_listing_planner_engine.execution import ShopifyGraphqlExecutionAdapter

    class FakeClient:
        def __init__(self):
            self.calls = []

        def post(self, url, payload, headers=None):
            self.calls.append(("post", url, payload, headers))
            return {"data": {"productCreate": {"product": {"id": "gid://shopify/Product/1"}, "userErrors": []}}}

    client = FakeClient()
    adapter = ShopifyGraphqlExecutionAdapter(client)
    result = adapter.product_create(
        shop_domain="example.myshopify.com",
        api_version="2026-01",
        admin_access_token="shpat_test",
        product_payload={"title": "Ready Product", "status": "DRAFT"},
    )

    assert result["data"]["productCreate"]["product"]["id"] == "gid://shopify/Product/1"
    method, url, payload, headers = client.calls[0]
    assert method == "post"
    assert url == "https://example.myshopify.com/admin/api/2026-01/graphql.json"
    assert headers == {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": "shpat_test",
    }
    assert payload["variables"] == {"product": {"title": "Ready Product", "status": "DRAFT"}}
    assert "productCreate" in payload["query"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_shopify_graphql_execution_adapter_calls_product_create_and_get_product" -v
```

Expected: FAIL because adapter is not exported.

- [ ] **Step 3: Implement adapter**

Append to `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/execution.py`:

```python
PRODUCT_CREATE_MUTATION = """
mutation productCreate($product: ProductCreateInput!) {
  productCreate(product: $product) {
    product {
      id
      title
      status
      handle
    }
    userErrors {
      field
      message
    }
  }
}
"""

PRODUCT_QUERY = """
query product($id: ID!) {
  product(id: $id) {
    id
    title
    status
    handle
  }
}
"""


class ShopifyGraphqlExecutionAdapter:
    def __init__(self, client):
        self._client = client

    def product_create(self, shop_domain: str, api_version: str, admin_access_token: str, product_payload: dict) -> dict:
        return self._client.post(
            self._graphql_url(shop_domain, api_version),
            {"query": PRODUCT_CREATE_MUTATION, "variables": {"product": product_payload}},
            headers=self._headers(admin_access_token),
        )

    def get_product(self, shop_domain: str, api_version: str, admin_access_token: str, product_id: str) -> dict:
        return self._client.post(
            self._graphql_url(shop_domain, api_version),
            {"query": PRODUCT_QUERY, "variables": {"id": product_id}},
            headers=self._headers(admin_access_token),
        )

    @staticmethod
    def _graphql_url(shop_domain: str, api_version: str) -> str:
        normalized_domain = shop_domain.removeprefix("https://").removeprefix("http://").rstrip("/")
        return f"https://{normalized_domain}/admin/api/{api_version}/graphql.json"

    @staticmethod
    def _headers(admin_access_token: str) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": admin_access_token,
        }
```

Update `__init__.py`:

```python
from product_listing_planner_engine.engine import ProductListingPlannerEngine
from product_listing_planner_engine.execution import OmsListingExecutionAdapter, ShopifyGraphqlExecutionAdapter

__all__ = ["ProductListingPlannerEngine", "OmsListingExecutionAdapter", "ShopifyGraphqlExecutionAdapter"]
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

---

### Task 3: Execute Direct Shopify productCreate

**Files:**
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Write failing execution tests**

Add:

```python
def _direct_shopify_execution_request():
    product_query_result = {
        "details": {
            "product": {"title": "Ready Product", "brand": "Acme", "category": "Bags", "price": 10, "currency": "USD"},
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }
    plan = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": "example.myshopify.com",
            "admin_access_token": "shpat_test",
        },
        context={"product_query_result": product_query_result},
    )
    form = plan["details"]["execution_form"]
    return {
        "confirmed": True,
        "action": "direct_shopify_product_create",
        "merchant_no": form["merchant_no"],
        "identifier": form["identifier"],
        "shop_domain": form["shop_domain"],
        "api_version": form["api_version"],
        "admin_access_token": "shpat_test",
        "product_payload": form["product_payload"],
        "targets": form["targets"],
        "form_token": form["form_token"],
    }


def test_execute_direct_shopify_product_create_successfully():
    class FakeShopifyAdapter:
        def product_create(self, shop_domain, api_version, admin_access_token, product_payload):
            assert admin_access_token == "shpat_test"
            return {
                "data": {
                    "productCreate": {
                        "product": {"id": "gid://shopify/Product/1", "title": "Ready Product", "status": "DRAFT", "handle": "ready-product"},
                        "userErrors": [],
                    }
                }
            }

        def get_product(self, shop_domain, api_version, admin_access_token, product_id):
            return {"data": {"product": {"id": product_id, "title": "Ready Product", "status": "DRAFT", "handle": "ready-product"}}}

    result = ProductListingPlannerEngine(shopify_execution_adapter=FakeShopifyAdapter()).execute(
        request=_direct_shopify_execution_request()
    )

    assert result["success"] is True
    assert result["final_conclusion"] == "Executed successfully"
    assert result["details"]["executions"][0]["endpoint"] == "/admin/api/2026-01/graphql.json productCreate"
    assert result["details"]["verification"][0]["shopify_product_id"] == "gid://shopify/Product/1"


def test_execute_direct_shopify_requires_auth_without_submit():
    class FakeShopifyAdapter:
        def product_create(self, *args, **kwargs):
            raise AssertionError("product_create should not be called without auth")

    request = _direct_shopify_execution_request()
    request.pop("admin_access_token")
    result = ProductListingPlannerEngine(shopify_execution_adapter=FakeShopifyAdapter()).execute(request=request)

    assert result["success"] is False
    assert result["final_conclusion"] == "Execution failed"
    assert "missing_shopify_auth" in result["errors"]


def test_execute_direct_shopify_user_errors_fail_execution():
    class FakeShopifyAdapter:
        def product_create(self, shop_domain, api_version, admin_access_token, product_payload):
            return {
                "data": {
                    "productCreate": {
                        "product": None,
                        "userErrors": [{"field": ["title"], "message": "Title can't be blank"}],
                    }
                }
            }

        def get_product(self, *args, **kwargs):
            raise AssertionError("get_product should not be called after userErrors")

    result = ProductListingPlannerEngine(shopify_execution_adapter=FakeShopifyAdapter()).execute(
        request=_direct_shopify_execution_request()
    )

    assert result["success"] is False
    assert result["final_conclusion"] == "Execution failed"
    assert result["details"]["executions"][0]["user_errors"] == [{"field": ["title"], "message": "Title can't be blank"}]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_direct_shopify_product_create_successfully" "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_direct_shopify_requires_auth_without_submit" "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_direct_shopify_user_errors_fail_execution" -v
```

Expected: FAIL because constructor and execute route do not support Shopify adapter/action.

- [ ] **Step 3: Implement execution route**

Change `ProductListingPlannerEngine.__init__` to:

```python
    def __init__(self, execution_adapter=None, shopify_execution_adapter=None):
        self._execution_adapter = execution_adapter
        self._shopify_execution_adapter = shopify_execution_adapter
```

At the start of `execute()` after confirmation and target validation, route Shopify action:

```python
        if request.get("action") == "direct_shopify_product_create":
            return self._execute_direct_shopify_product_create(request)
```

Add method:

```python
    def _execute_direct_shopify_product_create(self, request: dict):
        if not self._shopify_execution_adapter:
            return {"success": False, "summary": "缺少 Shopify 执行适配器，无法创建商品。", "final_conclusion": "Execution failed", "errors": ["missing_shopify_execution_adapter"]}
        if not request.get("shop_domain") or not request.get("admin_access_token"):
            return {"success": False, "summary": "缺少 Shopify 鉴权信息，未执行商品创建。", "final_conclusion": "Execution failed", "errors": ["missing_shopify_auth"]}
        expected_form_token = _execution_form_token(request.get("merchant_no"), request.get("identifier"), request.get("action"), request.get("targets") or [])
        if request.get("form_token") != expected_form_token:
            return {"success": False, "summary": "确认表单校验失败，未执行 Shopify 商品创建。", "final_conclusion": "Execution failed", "errors": ["invalid_execution_form"]}

        product_payload = request.get("product_payload") or {}
        raw_response = self._shopify_execution_adapter.product_create(
            request["shop_domain"],
            request.get("api_version") or DEFAULT_SHOPIFY_API_VERSION,
            request["admin_access_token"],
            product_payload,
        )
        product_create = ((raw_response.get("data") or {}).get("productCreate") or {}) if isinstance(raw_response, dict) else {}
        user_errors = product_create.get("userErrors") or []
        product = product_create.get("product") or {}
        execution = {
            "endpoint": f"/admin/api/{request.get('api_version') or DEFAULT_SHOPIFY_API_VERSION}/graphql.json productCreate",
            "request_payload": {"product": product_payload},
            "raw_response": raw_response,
            "user_errors": user_errors,
        }
        if user_errors or not product.get("id"):
            return {"success": False, "summary": "Shopify 返回错误，商品未创建。", "final_conclusion": "Execution failed", "details": {"executions": [execution], "verification": []}, "errors": ["shopify_user_errors"] if user_errors else ["missing_shopify_product_id"]}

        verification_response = self._shopify_execution_adapter.get_product(
            request["shop_domain"],
            request.get("api_version") or DEFAULT_SHOPIFY_API_VERSION,
            request["admin_access_token"],
            product["id"],
        )
        verified_product = ((verification_response.get("data") or {}).get("product") or {}) if isinstance(verification_response, dict) else {}
        verified = verified_product.get("id") == product["id"]
        conclusion = "Executed successfully" if verified else "Submitted successfully but business result did not take effect"
        return {
            "success": True,
            "summary": "Shopify 商品创建成功。" if verified else "Shopify 接受创建请求，但回查未确认商品存在。",
            "final_conclusion": conclusion,
            "details": {"executions": [execution], "verification": [{"shopify_product_id": product["id"], "raw_response": verification_response, "business_result_changed": verified}]},
            "errors": [],
        }
```

Ensure the existing unsupported action gate does not reject `direct_shopify_product_create` before the new route.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

---

### Task 4: Add Shopify verification no-effect path and default safety tests

**Files:**
- Modify: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py` only if needed

- [ ] **Step 1: Add tests**

Add:

```python
def test_execute_direct_shopify_reports_no_effect_when_verify_cannot_find_product():
    class FakeShopifyAdapter:
        def product_create(self, shop_domain, api_version, admin_access_token, product_payload):
            return {
                "data": {
                    "productCreate": {
                        "product": {"id": "gid://shopify/Product/1", "title": "Ready Product", "status": "DRAFT", "handle": "ready-product"},
                        "userErrors": [],
                    }
                }
            }

        def get_product(self, shop_domain, api_version, admin_access_token, product_id):
            return {"data": {"product": None}}

    result = ProductListingPlannerEngine(shopify_execution_adapter=FakeShopifyAdapter()).execute(
        request=_direct_shopify_execution_request()
    )

    assert result["success"] is True
    assert result["final_conclusion"] == "Submitted successfully but business result did not take effect"
    assert result["details"]["verification"][0]["business_result_changed"] is False


def test_direct_shopify_plan_defaults_to_draft_even_if_invalid_status_requested():
    product_query_result = {
        "details": {
            "product": {"title": "Ready Product", "brand": "Acme", "category": "Bags"},
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": "example.myshopify.com",
            "admin_access_token": "shpat_test",
            "shopify_status": "published",
        },
        context={"product_query_result": product_query_result},
    )

    assert result["details"]["execution_form"]["product_payload"]["status"] == "DRAFT"
```

- [ ] **Step 2: Run tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_direct_shopify_reports_no_effect_when_verify_cannot_find_product" "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_direct_shopify_plan_defaults_to_draft_even_if_invalid_status_requested" -v
```

Expected: PASS if Task 3 implementation is complete. If it fails, adjust only the minimal code path.

---

### Task 5: Update skill docs for Direct Shopify GraphQL

**Files:**
- Modify: `.kiro/skills/product-listing-planner/SKILL.md`
- Modify: `.kiro/skills/product-listing-planner/CAPABILITY_STATUS.md`

- [ ] **Step 1: Update SKILL.md**

Add a section after the confirmed submit execution loop:

```markdown
## Direct Shopify GraphQL 商品创建规则

除 OMS submit 通道外，当前 skill 支持独立的 Direct Shopify GraphQL 商品创建通道：

- action: `direct_shopify_product_create`
- Shopify endpoint: `POST /admin/api/{api_version}/graphql.json`
- GraphQL mutation: `productCreate`
- 默认创建状态：`DRAFT`
- 仅当用户明确要求 `ACTIVE` 且确认后，才允许创建 ACTIVE 商品。

执行前必须收集当前运行上下文中的 Shopify 鉴权信息：

- `shop_domain`，例如 `example.myshopify.com`
- `admin_access_token`，必须具备商品写入权限
- `api_version`，缺省为 `2026-01`

鉴权信息只允许用于当前执行请求，不写入 memory，不写入文档，不落盘保存。

执行前必须输出业务可读确认表单，展示将创建的 Shopify 商品标题、状态、SKU、价格和目标店铺。默认不得向用户展示 access token。

执行后必须检查：

- GraphQL `userErrors`
- 返回的 Shopify product id
- 使用 product id 再次查询是否存在

最终结论只能使用：

- `Executed successfully`
- `Submitted successfully but business result did not take effect`
- `Execution failed`
```

- [ ] **Step 2: Update CAPABILITY_STATUS.md**

Add:

```markdown
### Direct Shopify GraphQL product creation

The skill now supports a separate Direct Shopify execution path for first-party Shopify Admin GraphQL product creation.

Implemented behavior:

1. Build a Shopify product payload from `product_query_result.details.product` and `details.skus`.
2. Default product status to `DRAFT`.
3. Detect missing `shop_domain` and `admin_access_token` before execution.
4. Require explicit confirmation and a generated execution form.
5. Execute `productCreate` through `POST /admin/api/{api_version}/graphql.json` using caller-provided credentials.
6. Treat GraphQL `userErrors` as execution failure.
7. Verify returned product id with a follow-up product query.
8. Return one of the three final conclusions.

Boundaries:

- Shopify credentials are not persisted.
- This path does not update OMS channel product state.
- This path is separate from OMS `channel-product/submit`.
- REST Admin Product API is not used because Shopify recommends GraphQL for new product create flows.
```

- [ ] **Step 3: Run tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

---

### Task 6: Final verification

**Files:**
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Run focused planner tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run related product skill tests**

Run:

```bash
python -m pytest "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-query/tests/test_product_query_engine.py" "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py" "C:/Users/Jayne/Desktop/Skills/.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

- [ ] **Step 3: Review diff scope**

Run:

```bash
git status --short -- .kiro/skills/product-listing-planner docs/superpowers/plans/2026-05-27-direct-shopify-graphql-product-create.md
```

Expected: changes only under product-listing-planner and the plan file.

---

## Self-Review

- Spec coverage: The plan covers auth collection, default draft payload, GraphQL adapter, productCreate execution, userErrors failure, follow-up verification, no-effect conclusion, docs, and final tests.
- Placeholder scan: No `TBD`, `TODO`, vague “handle edge cases”, or missing code steps remain.
- Type consistency: The plan consistently uses `direct_shopify_product_create`, `ShopifyGraphqlExecutionAdapter`, `shop_domain`, `admin_access_token`, `api_version`, `product_payload`, `form_token`, and the existing three final conclusion strings.
