# Product Diagnosis Auto Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `product_diagnosis` diagnose publish/audit failures from real `product_query` evidence when no explicit context is provided.

**Architecture:** Extend `ProductDiagnosisEngine` to consume `publish_history` and `channel_products` from context. Update the MCP tool to auto-hydrate context by calling `ProductQueryEngine(listing_status)` when callers omit context, while preserving explicit context behavior.

**Tech Stack:** Python 3.12, pytest, existing Product Agent adapters and MCP server.

---

## File Structure

- Modify `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`: consume publish history and channel products.
- Modify `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`: engine tests.
- Modify `.kiro/skills/oms-agent/mcp_server.py`: auto-hydrate context in `product_diagnosis(...)`.
- Modify `.kiro/skills/oms-agent/tests/test_navigation_routes.py`: MCP auto-hydration tests.
- Modify `.kiro/skills/product-diagnosis/SKILL.md` and `docs/product-agent/01-落地行动方案.md`: document auto evidence.

---

### Task 1: Diagnosis engine consumes publish history listing failure

**Files:**
- Modify: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Modify: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_diagnoses_listing_failed_from_publish_history():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SKU-A",
        merchant_no="M001",
        intent="listing_failed",
        filters={"channel_code": "amazon"},
        context={
            "publish_history": [
                {"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material", "channel_code": "amazon"}
            ]
        },
    )

    assert result["summary"] == "SKU-A 上架失败，发现 1 条发布历史错误证据。"
    assert result["confidence"] == "high"
    assert result["details"]["issue_type"] == "listing_failed"
    assert result["details"]["failed_stage"] == "listing"
    assert result["evidences"][0]["source"] == "publish_history"
    assert result["evidences"][0]["data"]["error_message"] == "Missing material"
    assert result["recommendations"][0]["action"] == "review_publish_history_and_fix_source_data"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_diagnoses_listing_failed_from_publish_history -q`

Expected: FAIL because current engine ignores `publish_history`.

- [ ] **Step 3: Implement publish history diagnosis**

In `ProductDiagnosisEngine.diagnose`, after missing-fields handling and before existing `error_sources` handling, add:

```python
        publish_history = context.get("publish_history") or []
        failed_publish_history = [
            item for item in publish_history
            if item.get("error_message") or str(item.get("status") or "").lower() in {"failed", "fail", "rejected"}
        ]
        if intent in ("listing_failed", "audit_failed", None) and failed_publish_history:
            issue_type = "audit_failed" if any(str(item.get("audit_status") or "").lower() in {"rejected", "failed"} for item in failed_publish_history) else "listing_failed"
            failed_stage = "audit" if issue_type == "audit_failed" else "listing"
            return {
                "success": True,
                "summary": f"{identifier} {self._intent_label(issue_type)}，发现 {len(failed_publish_history)} 条发布历史错误证据。",
                "reason": "输入上下文包含发布历史失败或错误信息。",
                "evidences": [
                    {"source": "publish_history", "description": item.get("error_message") or str(item), "data": item}
                    for item in failed_publish_history
                ],
                "confidence": "high",
                "data_completeness": "partial",
                "severity": "major",
                "recommendations": [
                    {
                        "action": "review_publish_history_and_fix_source_data",
                        "precondition": "确认发布历史错误信息对应的商品字段或渠道规则",
                        "risk": "未修正源数据前重新发布可能继续失败",
                        "priority": "high",
                        "expected_effect": "修正源数据后可重新发布或提交审核",
                    }
                ],
                "metrics": {"publish_history_error_count": len(failed_publish_history)},
                "details": {
                    "issue_type": issue_type,
                    "failed_stage": failed_stage,
                    "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                    "retryable": True,
                    "requires_manual_fix": True,
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py -q`

Expected: PASS.

---

### Task 2: Diagnosis engine consumes channel product rejected audit state

**Files:**
- Modify: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Modify: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_diagnoses_audit_failed_from_channel_product_status():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SKU-A",
        merchant_no="M001",
        intent="audit_failed",
        filters={"channel_code": "amazon"},
        context={
            "channel_products": [
                {"channel_product_id": "CP-1", "channel_code": "amazon", "audit_status": "rejected", "listing_status": "failed"}
            ]
        },
    )

    assert result["summary"] == "SKU-A 审核失败，发现 1 条渠道商品状态证据。"
    assert result["details"]["issue_type"] == "audit_failed"
    assert result["details"]["failed_stage"] == "audit"
    assert result["evidences"][0]["source"] == "channel_products"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_diagnoses_audit_failed_from_channel_product_status -q`

Expected: FAIL because current engine ignores `channel_products`.

- [ ] **Step 3: Implement channel product status diagnosis**

Before fallback return, add:

```python
        channel_products = context.get("channel_products") or []
        rejected_channel_products = [
            item for item in channel_products
            if str(item.get("audit_status") or "").lower() in {"rejected", "failed"}
        ]
        if intent in ("audit_failed", None) and rejected_channel_products:
            return self._status_result(identifier, "audit_failed", "audit", "channel_products", rejected_channel_products, "渠道商品状态")
```

Add class helper:

```python
    def _status_result(self, identifier, issue_type, failed_stage, source, rows, source_label):
        return {
            "success": True,
            "summary": f"{identifier} {self._intent_label(issue_type)}，发现 {len(rows)} 条{source_label}证据。",
            "reason": f"输入上下文包含{source_label}。",
            "evidences": [
                {"source": source, "description": row.get("error_message") or row.get("listing_status") or row.get("audit_status") or str(row), "data": row}
                for row in rows
            ],
            "confidence": "high",
            "data_completeness": "partial",
            "severity": "major",
            "recommendations": [
                {
                    "action": "review_channel_status_and_fix_source_data",
                    "precondition": "确认渠道商品状态对应的商品字段或渠道规则",
                    "risk": "未修正源数据前重试可能继续失败",
                    "priority": "high",
                    "expected_effect": "修正源数据后可重新提交审核或发布",
                }
            ],
            "metrics": {"evidence_count": len(rows)},
            "details": {
                "issue_type": issue_type,
                "failed_stage": failed_stage,
                "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                "retryable": True,
                "requires_manual_fix": True,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": [],
        }
```

- [ ] **Step 4: Run diagnosis tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py -q`

Expected: PASS.

---

### Task 3: MCP auto-hydrates missing context from product_query

**Files:**
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`
- Modify: `.kiro/skills/oms-agent/mcp_server.py`

- [ ] **Step 1: Add failing MCP test**

Append:

```python

def test_product_diagnosis_auto_hydrates_context_when_missing(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
            pass

        def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
            captured["product_query"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
            }
            return {
                "details": {
                    "product": {"sku": "SKU-A"},
                    "skus": [{"sku": "SKU-A"}],
                    "channel_products": [{"channel_product_id": "CP-1", "audit_status": "rejected"}],
                    "publish_history": [{"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}],
                }
            }

    class FakeProductDiagnosisEngine:
        def diagnose(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
            captured["diagnosis_context"] = context
            return {"success": True, "summary": "diagnosed from hydrated context"}

    class FakeAdapter:
        def __init__(self, client):
            pass

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.product_adapter", types.SimpleNamespace(ProductApiAdapter=FakeAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.channel_product_adapter", types.SimpleNamespace(ChannelProductApiAdapter=FakeAdapter))
    monkeypatch.setitem(sys.modules, "product_diagnosis_engine.engine", types.SimpleNamespace(ProductDiagnosisEngine=FakeProductDiagnosisEngine))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))

    result = json.loads(module.product_diagnosis(
        identifier="SKU-A",
        merchant_no="M001",
        intent="listing_failed",
        filters='{"channel_code":"amazon"}',
    ))

    assert result == {"success": True, "summary": "diagnosed from hydrated context"}
    assert captured["product_query"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "listing_status",
        "filters": {"channel_code": "amazon"},
    }
    assert captured["diagnosis_context"]["publish_history"] == [
        {"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}
    ]
    assert captured["diagnosis_context"]["channel_products"] == [
        {"channel_product_id": "CP-1", "audit_status": "rejected"}
    ]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_diagnosis_auto_hydrates_context_when_missing -q`

Expected: FAIL because MCP passes empty context without querying ProductQueryEngine.

- [ ] **Step 3: Implement auto-hydration**

In `product_diagnosis(...)` after resolving merchant and before `ProductDiagnosisEngine().diagnose(...)`, add imports:

```python
    from product_query_engine.engine import ProductQueryEngine
    from product_query_engine.inventory_adapter import InventoryAdapter
    from product_query_engine.product_adapter import ProductApiAdapter
    from product_query_engine.channel_product_adapter import ChannelProductApiAdapter
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig
```

Then add:

```python
    if not parsed_context:
        client = OMSAPIClient(EngineConfig())
        query_result = ProductQueryEngine(
            inventory_adapter=InventoryAdapter(client),
            product_adapter=ProductApiAdapter(client),
            channel_product_adapter=ChannelProductApiAdapter(client),
        ).query(
            identifier=identifier,
            merchant_no=resolved_merchant_no,
            intent="listing_status",
            filters=parsed_filters,
        )
        details = query_result.get("details", {})
        parsed_context = {
            "product_snapshot": details.get("product") or {},
            "skus": details.get("skus") or [],
            "channel_products": details.get("channel_products") or [],
            "publish_history": details.get("publish_history") or [],
        }
```

- [ ] **Step 4: Run MCP test**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_diagnosis_auto_hydrates_context_when_missing -q`

Expected: PASS.

---

### Task 4: Docs and final verification

**Files:**
- Modify `.kiro/skills/product-diagnosis/SKILL.md`
- Modify `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Update docs**

Add to product diagnosis MVP runtime state:

```markdown
- 当 MCP 调用未传 `context` 时，会自动调用 `product_query(listing_status)` 获取商品、渠道商品和发布历史证据后再诊断。
- 可直接消费 `publish_history` 和 `channel_products` 作为发布/审核失败证据。
```

Add under Phase 5 status in action plan:

```markdown
- 已支持未传 `context` 时自动调用 `product_query` 补充 `channel_products` 和 `publish_history` 证据。
```

- [ ] **Step 2: Run final tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

- [ ] **Step 3: Cleanup caches**

Run: `rm -rf .kiro/skills/product-diagnosis/tests/__pycache__ .kiro/skills/product-query/tests/__pycache__ .kiro/skills/oms-agent/tests/__pycache__ .kiro/skills/oms-analysis/tests/__pycache__`

Expected: no output.

---

## Self-Review

- Spec coverage: publish history diagnosis, channel product diagnosis, MCP auto-hydration, explicit context compatibility, docs, final tests covered.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: `publish_history`, `channel_products`, and `product_query(listing_status)` naming is consistent.
