# Channel Product API v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real channel product facts to `product_query` using confirmed frontend channel-product APIs.

**Architecture:** Add `ChannelProductApiAdapter` beside the product and inventory adapters. `ProductQueryEngine` accepts it optionally and uses it for `overview`, `channel_listing`, `mapping`, `listing_status`, and `audit_status`, filling `details.channel_products` without changing existing product, inventory, or performance behavior.

**Tech Stack:** Python 3.12, pytest, existing `OMSAPIClient.get()`.

---

## File Structure

- Create `.kiro/skills/product-query/scripts/product_query_engine/channel_product_adapter.py`: channel product page/detail adapter.
- Modify `.kiro/skills/product-query/scripts/product_query_engine/engine.py`: integrate optional channel product adapter.
- Modify `.kiro/skills/product-query/tests/test_product_query_engine.py`: adapter and engine tests.
- Modify `.kiro/skills/oms-agent/mcp_server.py`: pass `ChannelProductApiAdapter` to `ProductQueryEngine` in `product_query` and `product_performance`.
- Modify `.kiro/skills/oms-agent/tests/test_navigation_routes.py`: MCP wiring tests.
- Modify `.kiro/skills/product-query/SKILL.md` and `docs/product-agent/01-落地行动方案.md`: document channel product API v1.

---

### Task 1: ChannelProductApiAdapter fetches channel product list

**Files:**
- Create: `.kiro/skills/product-query/scripts/product_query_engine/channel_product_adapter.py`
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from product_query_engine.channel_product_adapter import ChannelProductApiAdapter


def test_channel_product_adapter_lists_channel_products():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/channel-product/page"
            assert params == {"merchantNo": "M001", "sku": "SKU-A", "channel_code": "amazon", "pageNo": 1, "pageSize": 10}
            return {
                "data": {
                    "list": [
                        {
                            "id": "CP-1",
                            "channelCode": "amazon",
                            "shopId": "SHOP-1",
                            "publishStatus": "published",
                            "auditStatus": "approved",
                            "syncStatus": "success",
                            "title": "Amazon Travel Bottle",
                        }
                    ]
                }
            }

    products = ChannelProductApiAdapter(FakeClient()).list_channel_products(
        "M001",
        {"sku": "SKU-A", "channel_code": "amazon"},
    )

    assert products == [
        {
            "channel_product_id": "CP-1",
            "channel_code": "amazon",
            "shop_id": "SHOP-1",
            "listing_status": "published",
            "audit_status": "approved",
            "sync_status": "success",
            "title": "Amazon Travel Bottle",
            "raw": {
                "id": "CP-1",
                "channelCode": "amazon",
                "shopId": "SHOP-1",
                "publishStatus": "published",
                "auditStatus": "approved",
                "syncStatus": "success",
                "title": "Amazon Travel Bottle",
            },
        }
    ]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_channel_product_adapter_lists_channel_products -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'product_query_engine.channel_product_adapter'`.

- [ ] **Step 3: Implement adapter**

Create `.kiro/skills/product-query/scripts/product_query_engine/channel_product_adapter.py`:

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


class ChannelProductApiAdapter:
    def __init__(self, client):
        self._client = client

    def list_channel_products(self, merchant_no: str | None, filters: dict) -> list[dict]:
        self._client._ensure_token()
        params = {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 10}
        for source, target in (
            ("sku", "sku"),
            ("spu", "spu"),
            ("product_id", "productId"),
            ("channel_code", "channel_code"),
            ("shop_id", "shopId"),
        ):
            if filters.get(source):
                params[target] = filters[source]
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/channel-product/page", params)
        return [self._normalize_channel_product(row) for row in _extract_list(response.get("data", response))]

    def get_channel_product_detail(self, product_id: str) -> dict | None:
        self._client._ensure_token()
        response = self._client.get(f"/api/linker-oms/baseservice/rpc-api/channel-product/get/{product_id}")
        data = response.get("data", response)
        return self._normalize_channel_product(data) if isinstance(data, dict) else None

    @staticmethod
    def _normalize_channel_product(raw: dict) -> dict:
        return {
            "channel_product_id": raw.get("id") or raw.get("productId") or raw.get("channelProductId"),
            "channel_code": raw.get("channelCode") or raw.get("channel_code") or raw.get("channel"),
            "shop_id": raw.get("shopId") or raw.get("storeId") or raw.get("shop_id"),
            "listing_status": raw.get("publishStatus") or raw.get("listingStatus") or raw.get("shelfState"),
            "audit_status": raw.get("auditStatus") or raw.get("auditState"),
            "sync_status": raw.get("syncStatus"),
            "title": raw.get("title") or raw.get("productName") or raw.get("name"),
            "raw": raw,
        }
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_channel_product_adapter_lists_channel_products -q`

Expected: PASS.

---

### Task 2: ChannelProductApiAdapter fetches channel product detail

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`

- [ ] **Step 1: Add test**

Append:

```python

def test_channel_product_adapter_fetches_detail():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/channel-product/get/CP-1"
            assert params is None
            return {"data": {"id": "CP-1", "channelCode": "amazon", "title": "Amazon Travel Bottle"}}

    product = ChannelProductApiAdapter(FakeClient()).get_channel_product_detail("CP-1")

    assert product["channel_product_id"] == "CP-1"
    assert product["channel_code"] == "amazon"
    assert product["title"] == "Amazon Travel Bottle"
```

- [ ] **Step 2: Run test**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_channel_product_adapter_fetches_detail -q`

Expected: PASS if Task 1 implementation is complete.

---

### Task 3: ProductQueryEngine includes channel products

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Modify: `.kiro/skills/product-query/scripts/product_query_engine/engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_product_query_engine_uses_channel_product_adapter_for_channel_listing():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"sku": "SKU-A", "channel_code": "amazon"}
            return [{"channel_product_id": "CP-1", "channel_code": "amazon", "listing_status": "published"}]

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="channel_listing",
        filters={"channel_code": "amazon"},
    )

    assert result["details"]["channel_products"] == [
        {"channel_product_id": "CP-1", "channel_code": "amazon", "listing_status": "published"}
    ]
    assert result["metrics"]["channel_product_count"] == 1
    assert result["confidence"] == "high"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_product_query_engine_uses_channel_product_adapter_for_channel_listing -q`

Expected: FAIL with `TypeError: ProductQueryEngine.__init__() got an unexpected keyword argument 'channel_product_adapter'`.

- [ ] **Step 3: Update ProductQueryEngine**

Modify `.kiro/skills/product-query/scripts/product_query_engine/engine.py`:

- Change constructor:

```python
    def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
        self._inventory_adapter = inventory_adapter
        self._product_adapter = product_adapter
        self._channel_product_adapter = channel_product_adapter
```

- After product lookup and before metrics, add:

```python
        channel_products = []
        if self._channel_product_adapter and intent in ("overview", "channel_listing", "mapping", "listing_status", "audit_status", None):
            try:
                channel_filters = dict(filters)
                if resolved_sku and not channel_filters.get("sku"):
                    channel_filters["sku"] = resolved_sku
                channel_products = self._channel_product_adapter.list_channel_products(merchant_no, channel_filters)
            except Exception as e:
                errors.append(f"渠道商品 API 查询失败: {e}")
```

- Replace `"channel_products": []` with:

```python
                "channel_products": channel_products,
```

- After inventory metrics block, add:

```python
        if channel_products:
            metrics["channel_product_count"] = len(channel_products)
            confidence = "high"
```

- [ ] **Step 4: Run product-query tests**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py -q`

Expected: PASS.

---

### Task 4: Wire ChannelProductApiAdapter into MCP

**Files:**
- Modify: `.kiro/skills/oms-agent/mcp_server.py`
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`

- [ ] **Step 1: Update MCP fake test**

In `test_product_query_mcp_parses_filters_and_returns_result`, update fake constructor:

```python
class FakeProductQueryEngine:
    def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
        captured["has_inventory_adapter"] = inventory_adapter is not None
        captured["has_product_adapter"] = product_adapter is not None
        captured["has_channel_product_adapter"] = channel_product_adapter is not None
```

Add fake:

```python
class FakeChannelProductApiAdapter:
    def __init__(self, client):
        pass

monkeypatch.setitem(sys.modules, "product_query_engine.channel_product_adapter", types.SimpleNamespace(ChannelProductApiAdapter=FakeChannelProductApiAdapter))
```

Add assertion:

```python
assert captured["has_channel_product_adapter"] is True
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_query_mcp_parses_filters_and_returns_result -q`

Expected: FAIL because MCP does not pass `channel_product_adapter`.

- [ ] **Step 3: Update MCP wiring**

In `.kiro/skills/oms-agent/mcp_server.py`, import:

```python
from product_query_engine.channel_product_adapter import ChannelProductApiAdapter
```

Pass:

```python
ProductQueryEngine(
    inventory_adapter=InventoryAdapter(client),
    product_adapter=ProductApiAdapter(client),
    channel_product_adapter=ChannelProductApiAdapter(client),
)
```

Apply to both `product_query(...)` and `product_performance(...)`.

- [ ] **Step 4: Run MCP tests**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py -q`

Expected: PASS.

---

### Task 5: Docs and final verification

**Files:**
- Modify: `.kiro/skills/product-query/SKILL.md`
- Modify: `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Update docs**

Add to product-query MVP runtime state:

```markdown
- 已接入渠道商品 API v1：`channel-product/page` 和 `channel-product/get/{productId}`，可返回真实渠道商品列表与基础状态。
```

Add under Phase 3/7 status in `docs/product-agent/01-落地行动方案.md`:

```markdown
- 已接入前端确认的渠道商品接口：`/baseservice/rpc-api/channel-product/page` 与 `/baseservice/rpc-api/channel-product/get/{productId}`。
```

- [ ] **Step 2: Run final tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

- [ ] **Step 3: Cleanup caches**

Run: `rm -rf .kiro/skills/product-diagnosis/tests/__pycache__ .kiro/skills/product-query/tests/__pycache__ .kiro/skills/oms-agent/tests/__pycache__ .kiro/skills/oms-analysis/tests/__pycache__`

Expected: no output.

---

## Self-Review

- Spec coverage: channel product page/detail, normalization, engine integration, MCP wiring, docs, final tests covered.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: `ChannelProductApiAdapter.list_channel_products(merchant_no, filters)` and `ProductQueryEngine(..., channel_product_adapter=...)` are used consistently.
