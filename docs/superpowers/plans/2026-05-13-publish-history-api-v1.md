# Publish History API v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add publish history facts to `product_query` so later diagnosis can use real publishing/audit failure evidence.

**Architecture:** Extend `ChannelProductApiAdapter` with a `list_publish_history` method calling the confirmed frontend endpoint. `ProductQueryEngine` includes `details.publish_history` for channel/listing/audit views while preserving current product, channel product, inventory, and performance outputs.

**Tech Stack:** Python 3.12, pytest, existing `OMSAPIClient.get()`.

---

## File Structure

- Modify `.kiro/skills/product-query/scripts/product_query_engine/channel_product_adapter.py`: add publish history API method and normalizer.
- Modify `.kiro/skills/product-query/scripts/product_query_engine/engine.py`: include publish history in output.
- Modify `.kiro/skills/product-query/tests/test_product_query_engine.py`: adapter and engine tests.
- Modify `.kiro/skills/product-query/SKILL.md` and `docs/product-agent/01-落地行动方案.md`: document publish history v1.

---

### Task 1: ChannelProductApiAdapter fetches publish history

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Modify: `.kiro/skills/product-query/scripts/product_query_engine/channel_product_adapter.py`

- [ ] **Step 1: Write failing test**

Append to `.kiro/skills/product-query/tests/test_product_query_engine.py`:

```python

def test_channel_product_adapter_lists_publish_history():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/publish-history/page"
            assert params == {"merchantNo": "M001", "sku": "SKU-A", "channel_code": "amazon", "pageNo": 1, "pageSize": 10}
            return {
                "data": {
                    "list": [
                        {
                            "id": "PH-1",
                            "channelCode": "amazon",
                            "publishStatus": "failed",
                            "auditStatus": "rejected",
                            "errorMessage": "Missing material",
                            "title": "Amazon Travel Bottle",
                        }
                    ]
                }
            }

    history = ChannelProductApiAdapter(FakeClient()).list_publish_history(
        "M001",
        {"sku": "SKU-A", "channel_code": "amazon"},
    )

    assert history == [
        {
            "publish_history_id": "PH-1",
            "channel_code": "amazon",
            "status": "failed",
            "audit_status": "rejected",
            "error_message": "Missing material",
            "title": "Amazon Travel Bottle",
            "raw": {
                "id": "PH-1",
                "channelCode": "amazon",
                "publishStatus": "failed",
                "auditStatus": "rejected",
                "errorMessage": "Missing material",
                "title": "Amazon Travel Bottle",
            },
        }
    ]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_channel_product_adapter_lists_publish_history -q`

Expected: FAIL with `AttributeError: 'ChannelProductApiAdapter' object has no attribute 'list_publish_history'`.

- [ ] **Step 3: Implement method**

Add to `ChannelProductApiAdapter`:

```python
    def list_publish_history(self, merchant_no: str | None, filters: dict) -> list[dict]:
        self._client._ensure_token()
        params = {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 10}
        for source, target in (
            ("sku", "sku"),
            ("spu", "spu"),
            ("product_id", "productId"),
            ("channel_product_id", "productId"),
            ("channel_code", "channel_code"),
            ("shop_id", "shopId"),
        ):
            if filters.get(source):
                params[target] = filters[source]
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/publish-history/page", params)
        return [self._normalize_publish_history(row) for row in _extract_list(response.get("data", response))]
```

Add normalizer:

```python
    @staticmethod
    def _normalize_publish_history(raw: dict) -> dict:
        return {
            "publish_history_id": raw.get("id") or raw.get("publishHistoryId"),
            "channel_code": raw.get("channelCode") or raw.get("channel_code") or raw.get("channel"),
            "status": raw.get("publishStatus") or raw.get("status"),
            "audit_status": raw.get("auditStatus") or raw.get("auditState"),
            "error_message": raw.get("errorMessage") or raw.get("lastError") or raw.get("message"),
            "title": raw.get("title") or raw.get("productName") or raw.get("name"),
            "raw": raw,
        }
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_channel_product_adapter_lists_publish_history -q`

Expected: PASS.

---

### Task 2: ProductQueryEngine outputs publish history

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Modify: `.kiro/skills/product-query/scripts/product_query_engine/engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_product_query_engine_includes_publish_history_for_listing_status():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            return []

        def list_publish_history(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"channel_code": "amazon", "sku": "SKU-A"}
            return [{"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}]

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="listing_status",
        filters={"channel_code": "amazon"},
    )

    assert result["details"]["publish_history"] == [
        {"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}
    ]
    assert result["metrics"]["publish_history_count"] == 1
    assert result["confidence"] == "high"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_product_query_engine_includes_publish_history_for_listing_status -q`

Expected: FAIL because `details.publish_history` is missing.

- [ ] **Step 3: Update engine**

In `.kiro/skills/product-query/scripts/product_query_engine/engine.py`:

- After channel product lookup, add:

```python
        publish_history = []
        if self._channel_product_adapter and intent in ("overview", "channel_listing", "listing_status", "audit_status", None):
            try:
                history_filters = dict(filters)
                if resolved_sku and not history_filters.get("sku"):
                    history_filters["sku"] = resolved_sku
                publish_history = self._channel_product_adapter.list_publish_history(merchant_no, history_filters)
            except Exception as e:
                errors.append(f"发布历史 API 查询失败: {e}")
```

- After channel product metrics, add:

```python
        if publish_history:
            metrics["publish_history_count"] = len(publish_history)
            confidence = "high"
```

- In details, add:

```python
                "publish_history": publish_history,
```

- [ ] **Step 4: Run product-query tests**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py -q`

Expected: PASS.

---

### Task 3: Docs and final verification

**Files:**
- Modify: `.kiro/skills/product-query/SKILL.md`
- Modify: `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Update docs**

Add to product-query MVP runtime state:

```markdown
- 已接入发布历史 API v1：`publish-history/page`，可返回发布状态、审核状态和错误信息证据。
```

Add under Phase 3/8 status in `docs/product-agent/01-落地行动方案.md`:

```markdown
- 已接入前端确认的发布历史接口：`/baseservice/rpc-api/publish-history/page`，用于后续诊断发布/审核失败。
```

- [ ] **Step 2: Run final tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

- [ ] **Step 3: Cleanup caches**

Run: `rm -rf .kiro/skills/product-diagnosis/tests/__pycache__ .kiro/skills/product-query/tests/__pycache__ .kiro/skills/oms-agent/tests/__pycache__ .kiro/skills/oms-analysis/tests/__pycache__`

Expected: no output.

---

## Self-Review

- Spec coverage: publish-history endpoint, normalization, engine output, metrics, docs, final tests covered.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: `list_publish_history(merchant_no, filters)` and `details.publish_history` are used consistently.
