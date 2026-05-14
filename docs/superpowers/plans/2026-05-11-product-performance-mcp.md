# Product Performance MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `product_performance` MCP tool that answers product performance questions by composing `product_query` identity resolution with `oms_analysis` SKU/channel analysis.

**Architecture:** Implement a thin orchestration tool in `.kiro/skills/oms-agent/mcp_server.py`. It reuses `ProductQueryEngine` to build `performance_query`, then creates `AnalysisRequest` objects for `sku_sales` and optional `channel_performance`, returning a unified JSON payload without inventing facts.

**Tech Stack:** Python 3.12, pytest, existing MCP server, `product_query_engine`, `oms_analysis_engine`.

---

## File Structure

- Modify `.kiro/skills/oms-agent/mcp_server.py`: add `product_performance(...)` MCP tool and reuse existing JSON parsing style.
- Modify `.kiro/skills/oms-agent/tests/test_navigation_routes.py`: add TDD coverage for composition and error handling.
- Modify `docs/product-agent/01-落地行动方案.md`: record Phase 4 MVP status.

---

### Task 1: Add failing composition test

**Files:**
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`

- [ ] **Step 1: Write the failing test**

Append:

```python

def test_product_performance_composes_product_query_and_sku_sales(monkeypatch):
    module = load_mcp_server()
    captured = {"analysis_requests": []}

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None):
            pass

        def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
            captured["product_query"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
            }
            return {
                "success": True,
                "details": {
                    "product": {"sku": "SKU-A"},
                    "skus": [{"sku": "SKU-A", "available_qty": 3}],
                    "performance_query": {"sku": "SKU-A", "channel_code": "amazon"},
                },
                "errors": ["渠道商品 API 尚未接入"],
            }

    class FakeInventoryAdapter:
        def __init__(self, client):
            pass

    class FakeDataFetcher:
        def __init__(self, *args, **kwargs):
            pass

    class FakeOMSAnalysisEngine:
        def __init__(self, data_fetcher=None):
            pass

        def analyze(self, request):
            captured["analysis_requests"].append(request)

            class FakeResponse:
                def model_dump(self):
                    return {"success": True, "metrics": {"total_quantity": 2, "total_revenue": 100}}

            return FakeResponse()

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeInventoryAdapter))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.engine_v2", types.SimpleNamespace(OMSQueryEngine=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.data_fetcher", types.SimpleNamespace(DataFetcher=FakeDataFetcher))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.engine", types.SimpleNamespace(OMSAnalysisEngine=FakeOMSAnalysisEngine))

    result = json.loads(module.product_performance(
        identifier="SKU-A",
        merchant_no="M001",
        filters='{"channel_code":"amazon"}',
    ))

    assert result["success"] is True
    assert captured["product_query"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "identity_for_performance",
        "filters": {"channel_code": "amazon"},
    }
    assert len(captured["analysis_requests"]) == 1
    assert captured["analysis_requests"][0].intent == "sku_sales"
    assert captured["analysis_requests"][0].filters == {"sku": "SKU-A", "channel_code": "amazon"}
    assert result["metrics"] == {"total_quantity": 2, "total_revenue": 100}
    assert result["details"]["product_query"]["details"]["product"] == {"sku": "SKU-A"}
    assert result["details"]["sku_sales"]["metrics"] == {"total_quantity": 2, "total_revenue": 100}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_performance_composes_product_query_and_sku_sales -q`

Expected: FAIL with `AttributeError: module 'oms_agent_mcp_server' has no attribute 'product_performance'`.

---

### Task 2: Implement minimal product_performance tool

**Files:**
- Modify: `.kiro/skills/oms-agent/mcp_server.py`

- [ ] **Step 1: Add MCP tool**

Add after `product_query(...)`:

```python
@mcp.tool()
def product_performance(
    identifier: str | None = None,
    merchant_no: str | None = None,
    filters: str | None = None,
    time_range: str | None = None,
    include_channel: bool = False,
) -> str:
    """Product Agent 商品表现入口。组合 product_query 与 oms_analysis，返回 SKU 销售表现和可选渠道表现。"""
    from datetime import datetime
    from product_query_engine.engine import ProductQueryEngine
    from product_query_engine.inventory_adapter import InventoryAdapter
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig
    from oms_query_engine.engine_v2 import OMSQueryEngine
    from oms_analysis_engine.data_fetcher import DataFetcher
    from oms_analysis_engine.engine import OMSAnalysisEngine
    from oms_analysis_engine.models.request import AnalysisRequest, TimeRange

    try:
        parsed_filters = json.loads(filters) if filters else {}
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": "invalid_filters_json", "message": str(e)}, ensure_ascii=False, indent=2)

    parsed_time_range = None
    if time_range:
        try:
            raw_time_range = json.loads(time_range)
            parsed_time_range = TimeRange(
                start=datetime.fromisoformat(raw_time_range["start"].replace("Z", "+00:00")),
                end=datetime.fromisoformat(raw_time_range["end"].replace("Z", "+00:00")),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return json.dumps({"success": False, "error": "invalid_time_range_json", "message": str(e)}, ensure_ascii=False, indent=2)

    try:
        resolved_merchant_no = _resolve_merchant_no(merchant_no)
    except ValueError as e:
        return json.dumps({"success": False, "error": "missing_merchant_no", "message": str(e)}, ensure_ascii=False, indent=2)

    client = OMSAPIClient(EngineConfig())
    product_result = ProductQueryEngine(inventory_adapter=InventoryAdapter(client)).query(
        identifier=identifier,
        merchant_no=resolved_merchant_no,
        intent="identity_for_performance",
        filters=parsed_filters,
    )
    performance_filters = product_result.get("details", {}).get("performance_query", {})

    analysis_engine = OMSAnalysisEngine(data_fetcher=DataFetcher(OMSQueryEngine()))
    sku_sales = analysis_engine.analyze(AnalysisRequest(
        identifier=identifier,
        merchant_no=resolved_merchant_no,
        intent="sku_sales",
        filters=performance_filters,
        time_range=parsed_time_range,
    )).model_dump()

    channel_performance = None
    if include_channel:
        channel_performance = analysis_engine.analyze(AnalysisRequest(
            identifier=identifier,
            merchant_no=resolved_merchant_no,
            intent="channel_performance",
            filters=performance_filters,
            time_range=parsed_time_range,
        )).model_dump()

    errors = []
    errors.extend(product_result.get("errors", []))
    errors.extend(sku_sales.get("errors", []))
    if channel_performance:
        errors.extend(channel_performance.get("errors", []))

    result = {
        "success": bool(product_result.get("success", True) and sku_sales.get("success", True)),
        "summary": "已生成商品表现分析。",
        "metrics": sku_sales.get("metrics", {}),
        "details": {
            "product_query": product_result,
            "sku_sales": sku_sales,
        },
        "errors": errors,
    }
    if channel_performance:
        result["details"]["channel_performance"] = channel_performance
    return json.dumps(result, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: Run composition test**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_performance_composes_product_query_and_sku_sales -q`

Expected: PASS.

---

### Task 3: Add include_channel and error tests

**Files:**
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`

- [ ] **Step 1: Add failing tests**

Append:

```python

def test_product_performance_include_channel_runs_second_analysis(monkeypatch):
    module = load_mcp_server()
    intents = []

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None):
            pass

        def query(self, **kwargs):
            return {"success": True, "details": {"performance_query": {"sku": "SKU-A"}}, "errors": []}

    class FakeInventoryAdapter:
        def __init__(self, client):
            pass

    class FakeDataFetcher:
        def __init__(self, *args, **kwargs):
            pass

    class FakeOMSAnalysisEngine:
        def __init__(self, data_fetcher=None):
            pass

        def analyze(self, request):
            intents.append(request.intent)

            class FakeResponse:
                def model_dump(self):
                    return {"success": True, "metrics": {request.intent: 1}, "errors": []}

            return FakeResponse()

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeInventoryAdapter))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.engine_v2", types.SimpleNamespace(OMSQueryEngine=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.data_fetcher", types.SimpleNamespace(DataFetcher=FakeDataFetcher))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.engine", types.SimpleNamespace(OMSAnalysisEngine=FakeOMSAnalysisEngine))

    result = json.loads(module.product_performance(identifier="SKU-A", merchant_no="M001", include_channel=True))

    assert intents == ["sku_sales", "channel_performance"]
    assert result["details"]["channel_performance"]["metrics"] == {"channel_performance": 1}


def test_product_performance_returns_error_for_invalid_time_range_json():
    module = load_mcp_server()

    result = json.loads(module.product_performance(identifier="SKU-A", merchant_no="M001", time_range="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_time_range_json"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_performance_include_channel_runs_second_analysis .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_performance_returns_error_for_invalid_time_range_json -q`

Expected: PASS if Task 2 implementation is complete.

---

### Task 4: Update docs and final verification

**Files:**
- Modify: `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Update docs**

Add after Phase 3 MVP status:

```markdown
## 8. Phase 4：商品表现组合入口

### MVP 状态

已新增 `product_performance(...)` 组合入口：

- 先调用 `product_query(identity_for_performance)` 生成 `performance_query`。
- 再调用 `oms_analysis(intent=sku_sales)` 查询 SKU 销量、GMV 和订单表现。
- `include_channel=true` 时额外调用 `oms_analysis(intent=channel_performance)` 查询渠道表现。
- 返回 `product_query`、`sku_sales`、可选 `channel_performance` 的统一 JSON，避免调用方手动编排多工具。
```

- [ ] **Step 2: Run final tests**

Run: `python -m pytest .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

- [ ] **Step 3: Cleanup caches**

Run: `rm -rf .kiro/skills/product-query/tests/__pycache__ .kiro/skills/oms-agent/tests/__pycache__ .kiro/skills/oms-analysis/tests/__pycache__`

Expected: no output.

---

## Self-Review

- Spec coverage: product_query + sku_sales composition, optional channel_performance, JSON/time range errors, missing merchant through existing helper, docs, and final tests are covered.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: `product_performance(identifier, merchant_no, filters, time_range, include_channel)` is used consistently in tests and implementation.
