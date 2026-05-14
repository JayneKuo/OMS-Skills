# Product Query Real API v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `product_query` from inventory-only MVP to use confirmed Product SPU APIs from the frontend code.

**Architecture:** Add a `ProductApiAdapter` beside the existing inventory adapter. `ProductQueryEngine` accepts the adapter optionally and uses it for `overview`, `sku_detail`, and `spu_detail`, while preserving inventory fallback and `performance_query` generation.

**Tech Stack:** Python 3.12, pytest, existing `OMSAPIClient.get()`.

---

## File Structure

- Create `.kiro/skills/product-query/scripts/product_query_engine/product_adapter.py`: Product SPU page/detail API adapter.
- Modify `.kiro/skills/product-query/scripts/product_query_engine/engine.py`: integrate optional `product_adapter`.
- Modify `.kiro/skills/product-query/tests/test_product_query_engine.py`: TDD tests for adapter and engine integration.
- Modify `.kiro/skills/oms-agent/mcp_server.py`: pass `ProductApiAdapter` into `ProductQueryEngine` for `product_query` and `product_performance`.
- Modify `.kiro/skills/oms-agent/tests/test_navigation_routes.py`: assert MCP wiring still works with product adapter.
- Modify `.kiro/skills/product-query/SKILL.md` and `docs/product-agent/01-落地行动方案.md`: document real API v1.

---

### Task 1: ProductApiAdapter fetches product by SKU through SPU page API

**Files:**
- Create: `.kiro/skills/product-query/scripts/product_query_engine/product_adapter.py`
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`

- [ ] **Step 1: Write failing test**

Append to `.kiro/skills/product-query/tests/test_product_query_engine.py`:

```python
from product_query_engine.product_adapter import ProductApiAdapter


def test_product_adapter_finds_product_by_sku_from_spu_page():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/product/spu/page"
            assert params == {"merchantNo": "M001", "sku": "SKU-A", "pageNo": 1, "pageSize": 10}
            return {
                "data": {
                    "list": [
                        {
                            "id": "SPU-1",
                            "spu": "SPU-A",
                            "skuList": [{"sku": "SKU-A", "price": 12.5}],
                            "productName": "Travel Bottle",
                            "categoryName": "Pet Supplies",
                            "status": "active",
                        }
                    ]
                }
            }

    product = ProductApiAdapter(FakeClient()).find_product("M001", {"sku": "SKU-A"})

    assert product == {
        "product_id": "SPU-1",
        "spu": "SPU-A",
        "title": "Travel Bottle",
        "status": "active",
        "category": "Pet Supplies",
        "raw": {
            "id": "SPU-1",
            "spu": "SPU-A",
            "skuList": [{"sku": "SKU-A", "price": 12.5}],
            "productName": "Travel Bottle",
            "categoryName": "Pet Supplies",
            "status": "active",
        },
    }
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_product_adapter_finds_product_by_sku_from_spu_page -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'product_query_engine.product_adapter'`.

- [ ] **Step 3: Implement adapter**

Create `.kiro/skills/product-query/scripts/product_query_engine/product_adapter.py`:

```python
from __future__ import annotations

from typing import Any


def _extract_list(data: Any) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = _extract_list(value)
                if nested:
                    return nested
    return []


class ProductApiAdapter:
    def __init__(self, client):
        self._client = client

    def find_product(self, merchant_no: str | None, filters: dict) -> dict | None:
        self._client._ensure_token()
        sku = filters.get("sku")
        spu = filters.get("spu")
        product_id = filters.get("product_id")
        if product_id:
            return self.get_product_detail(product_id)

        params = {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 10}
        if sku:
            params["sku"] = sku
        if spu:
            params["spu"] = spu
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/product/spu/page", params)
        rows = _extract_list(response.get("data", response))
        if not rows:
            return None
        return self._normalize_product(rows[0])

    def get_product_detail(self, product_id: str) -> dict | None:
        self._client._ensure_token()
        response = self._client.get(f"/api/linker-oms/baseservice/rpc-api/product/spu/get/{product_id}")
        data = response.get("data", response)
        return self._normalize_product(data) if isinstance(data, dict) else None

    @staticmethod
    def _normalize_product(raw: dict) -> dict:
        return {
            "product_id": raw.get("id") or raw.get("productId") or raw.get("spuId"),
            "spu": raw.get("spu") or raw.get("spuCode"),
            "title": raw.get("productName") or raw.get("title") or raw.get("name"),
            "status": raw.get("status") or raw.get("productStatus"),
            "category": raw.get("categoryName") or raw.get("category"),
            "raw": raw,
        }
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_product_adapter_finds_product_by_sku_from_spu_page -q`

Expected: PASS.

---

### Task 2: ProductApiAdapter fetches product detail by product_id

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_product_adapter_fetches_product_detail_by_product_id():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/product/spu/get/SPU-1"
            assert params is None
            return {"data": {"id": "SPU-1", "spu": "SPU-A", "productName": "Travel Bottle"}}

    product = ProductApiAdapter(FakeClient()).find_product("M001", {"product_id": "SPU-1"})

    assert product["product_id"] == "SPU-1"
    assert product["spu"] == "SPU-A"
    assert product["title"] == "Travel Bottle"
```

- [ ] **Step 2: Run test**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_product_adapter_fetches_product_detail_by_product_id -q`

Expected: PASS if Task 1 implementation is complete.

---

### Task 3: ProductQueryEngine includes product API facts

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Modify: `.kiro/skills/product-query/scripts/product_query_engine/engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_product_query_engine_uses_product_adapter_for_overview():
    class FakeProductAdapter:
        def find_product(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"sku": "SKU-A"}
            return {
                "product_id": "SPU-1",
                "spu": "SPU-A",
                "title": "Travel Bottle",
                "status": "active",
                "category": "Pet Supplies",
                "raw": {"skuList": [{"sku": "SKU-A", "price": 12.5}]},
            }

    result = ProductQueryEngine(product_adapter=FakeProductAdapter()).query(
        identifier=None,
        merchant_no="M001",
        intent="overview",
        filters={"sku": "SKU-A"},
    )

    assert result["details"]["product"] == {
        "product_id": "SPU-1",
        "spu": "SPU-A",
        "title": "Travel Bottle",
        "status": "active",
        "category": "Pet Supplies",
        "raw": {"skuList": [{"sku": "SKU-A", "price": 12.5}]},
    }
    assert result["details"]["skus"] == [{"sku": "SKU-A", "price": 12.5}]
    assert result["details"]["performance_query"] == {"sku": "SKU-A", "spu": "SPU-A", "product_id": "SPU-1"}
    assert result["confidence"] == "high"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_product_query_engine_uses_product_adapter_for_overview -q`

Expected: FAIL with `TypeError: ProductQueryEngine.__init__() got an unexpected keyword argument 'product_adapter'`.

- [ ] **Step 3: Update engine**

Replace `.kiro/skills/product-query/scripts/product_query_engine/engine.py` with:

```python
from __future__ import annotations


def _extract_skus(product: dict | None, fallback_sku: str | None) -> list[dict]:
    if product:
        raw = product.get("raw") or {}
        for key in ("skuList", "skus", "sku_list"):
            value = raw.get(key)
            if isinstance(value, list) and value:
                return value
    return [{"sku": fallback_sku}] if fallback_sku else []


class ProductQueryEngine:
    def __init__(self, inventory_adapter=None, product_adapter=None):
        self._inventory_adapter = inventory_adapter
        self._product_adapter = product_adapter

    def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
        filters = filters or {}
        resolved_sku = filters.get("sku") or identifier
        product = None
        errors = ["渠道商品 API 尚未接入"]

        if self._product_adapter and intent in ("overview", "sku_detail", "spu_detail", None):
            try:
                product_filters = dict(filters)
                if resolved_sku and not product_filters.get("sku") and not product_filters.get("product_id"):
                    product_filters["sku"] = resolved_sku
                product = self._product_adapter.find_product(merchant_no, product_filters)
            except Exception as e:
                errors.append(f"商品 API 查询失败: {e}")

        performance_query = {}
        if resolved_sku:
            performance_query["sku"] = resolved_sku
        if product:
            if product.get("spu"):
                performance_query["spu"] = product["spu"]
            if product.get("product_id"):
                performance_query["product_id"] = product["product_id"]
        for key in ("channel_code", "shop_id"):
            if filters.get(key):
                performance_query[key] = filters[key]

        sku_fact = None
        if self._inventory_adapter and resolved_sku and (intent in ("inventory_price", "overview", None)):
            try:
                sku_fact = self._inventory_adapter.fetch_sku_facts(merchant_no, resolved_sku)
            except Exception as e:
                errors.append(f"库存 API 查询失败: {e}")

        product_detail = product or ({"sku": resolved_sku} if resolved_sku else {})
        skus = _extract_skus(product, resolved_sku)
        if sku_fact and sku_fact.get("inventory_records", 0) > 0:
            skus = [dict(skus[0], **sku_fact)] if skus else [sku_fact]

        metrics = {}
        confidence = "high" if product else ("medium" if resolved_sku else "low")
        data_completeness = "partial" if (product or resolved_sku) else "insufficient"
        if sku_fact and sku_fact.get("inventory_records", 0) > 0:
            metrics = {
                "sku_count": len(skus),
                "available_qty": sku_fact.get("available_qty", 0),
                "on_hand_qty": sku_fact.get("on_hand_qty", 0),
            }

        return {
            "success": True,
            "summary": f"已确认 {resolved_sku or product_detail.get('spu') or product_detail.get('product_id')} 可用于商品表现分析。" if (resolved_sku or product_detail) else "已生成商品表现分析查询条件。",
            "reason": "返回已确认的商品主档、SKU、库存和表现分析过滤条件；渠道商品 API 尚未接入。",
            "evidences": [],
            "confidence": confidence,
            "data_completeness": data_completeness,
            "severity": None,
            "recommendations": [],
            "metrics": metrics,
            "details": {
                "product": product_detail,
                "skus": skus,
                "channel_products": [],
                "mapping": [],
                "missing_fields": [],
                "performance_query": performance_query,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": errors,
        }
```

- [ ] **Step 4: Run product-query tests**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py -q`

Expected: PASS.

---

### Task 4: MCP wires ProductApiAdapter into product_query and product_performance

**Files:**
- Modify: `.kiro/skills/oms-agent/mcp_server.py`
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`

- [ ] **Step 1: Update MCP tests to expect product adapter**

In `test_product_query_mcp_parses_filters_and_returns_result`, change fake engine init to capture product adapter:

```python
class FakeProductQueryEngine:
    def __init__(self, inventory_adapter=None, product_adapter=None):
        captured["has_inventory_adapter"] = inventory_adapter is not None
        captured["has_product_adapter"] = product_adapter is not None
```

Add assertion:

```python
assert captured["has_product_adapter"] is True
```

Add fake module:

```python
class FakeProductApiAdapter:
    def __init__(self, client):
        pass

monkeypatch.setitem(sys.modules, "product_query_engine.product_adapter", types.SimpleNamespace(ProductApiAdapter=FakeProductApiAdapter))
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_query_mcp_parses_filters_and_returns_result -q`

Expected: FAIL because MCP does not pass `product_adapter` yet.

- [ ] **Step 3: Wire adapter**

In `.kiro/skills/oms-agent/mcp_server.py`, import and pass adapter in `product_query` and `product_performance`:

```python
from product_query_engine.product_adapter import ProductApiAdapter
```

Use:

```python
engine = ProductQueryEngine(
    inventory_adapter=InventoryAdapter(client),
    product_adapter=ProductApiAdapter(client),
)
```

And:

```python
product_result = ProductQueryEngine(
    inventory_adapter=InventoryAdapter(client),
    product_adapter=ProductApiAdapter(client),
).query(...)
```

- [ ] **Step 4: Run MCP tests**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py -q`

Expected: PASS.

---

### Task 5: Docs and final verification

**Files:**
- Modify: `.kiro/skills/product-query/SKILL.md`
- Modify: `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Update product-query doc**

Add to MVP runtime state:

```markdown
- 已接入商品中心 SPU API v1：`product/spu/page` 和 `product/spu/get/{id}`，可返回真实商品主档、SPU 和 SKU 列表。
```

- [ ] **Step 2: Update Product Agent plan**

Under Phase 3 status add:

```markdown
- 已接入前端确认的商品中心 SPU 接口：`/baseservice/rpc-api/product/spu/page` 与 `/baseservice/rpc-api/product/spu/get/{id}`。
```

- [ ] **Step 3: Run final tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

- [ ] **Step 4: Cleanup caches**

Run: `rm -rf .kiro/skills/product-diagnosis/tests/__pycache__ .kiro/skills/product-query/tests/__pycache__ .kiro/skills/oms-agent/tests/__pycache__ .kiro/skills/oms-analysis/tests/__pycache__`

Expected: no output.

---

## Self-Review

- Spec coverage: SPU page, SPU detail, engine integration, MCP wiring, docs, and final tests are covered.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: `ProductApiAdapter.find_product(merchant_no, filters)` and `ProductQueryEngine(..., product_adapter=...)` are used consistently.
