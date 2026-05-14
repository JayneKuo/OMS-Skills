# Product Query MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal runtime `product_query` MCP capability so Product Agent can resolve SKU/product identity and inventory/price facts before calling `oms_analysis` for performance.

**Architecture:** Add a focused product query engine under `.kiro/skills/product-query/scripts/product_query_engine/` and expose it through `.kiro/skills/oms-agent/mcp_server.py`. The MVP only uses existing OMS API client/inventory data and never guesses product-center or channel-listing endpoints; unsupported channel facts are returned as empty arrays with explicit errors.

**Tech Stack:** Python 3.12, pytest, Pydantic-free dict results for MCP compatibility, existing `oms_query_engine.api_client.OMSAPIClient`.

---

## File Structure

- Create `.kiro/skills/product-query/scripts/product_query_engine/__init__.py`: package export.
- Create `.kiro/skills/product-query/scripts/product_query_engine/engine.py`: `ProductQueryEngine` orchestration and response shaping.
- Create `.kiro/skills/product-query/scripts/product_query_engine/inventory_adapter.py`: inventory API calls and SKU fact extraction.
- Create `.kiro/skills/product-query/tests/test_product_query_engine.py`: adapter/engine behavior tests.
- Modify `.kiro/skills/oms-agent/mcp_server.py`: add product-query script path and `product_query(...)` MCP tool.
- Modify `.kiro/skills/oms-agent/tests/test_navigation_routes.py`: MCP parsing and output tests.
- Modify `.kiro/skills/product-query/SKILL.md`: document MVP runtime boundary.
- Modify `docs/product-agent/01-落地行动方案.md`: update Phase 3 status.

---

### Task 1: Product query engine returns identity and performance filters

**Files:**
- Create: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Create: `.kiro/skills/product-query/scripts/product_query_engine/__init__.py`
- Create: `.kiro/skills/product-query/scripts/product_query_engine/engine.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_query_engine.engine import ProductQueryEngine


def test_identity_for_performance_uses_sku_filter_and_identifier():
    result = ProductQueryEngine().query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="identity_for_performance",
        filters={"channel_code": "amazon", "shop_id": "SHOP-1"},
    )

    assert result["success"] is True
    assert result["summary"] == "已确认 SKU-A 可用于商品表现分析。"
    assert result["details"]["product"] == {"sku": "SKU-A"}
    assert result["details"]["skus"] == [{"sku": "SKU-A"}]
    assert result["details"]["performance_query"] == {
        "sku": "SKU-A",
        "channel_code": "amazon",
        "shop_id": "SHOP-1",
    }
    assert result["details"]["channel_products"] == []
    assert "渠道商品 API 尚未接入" in result["errors"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_identity_for_performance_uses_sku_filter_and_identifier -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'product_query_engine'`.

- [ ] **Step 3: Write minimal implementation**

Create `.kiro/skills/product-query/scripts/product_query_engine/__init__.py`:

```python
from product_query_engine.engine import ProductQueryEngine

__all__ = ["ProductQueryEngine"]
```

Create `.kiro/skills/product-query/scripts/product_query_engine/engine.py`:

```python
from __future__ import annotations


class ProductQueryEngine:
    def __init__(self, inventory_adapter=None):
        self._inventory_adapter = inventory_adapter

    def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
        filters = filters or {}
        resolved_sku = filters.get("sku") or identifier
        performance_query = {}
        if resolved_sku:
            performance_query["sku"] = resolved_sku
        for key in ("channel_code", "shop_id"):
            if filters.get(key):
                performance_query[key] = filters[key]

        product = {"sku": resolved_sku} if resolved_sku else {}
        skus = [{"sku": resolved_sku}] if resolved_sku else []

        return {
            "success": True,
            "summary": f"已确认 {resolved_sku} 可用于商品表现分析。" if resolved_sku else "已生成商品表现分析查询条件。",
            "reason": "MVP 仅基于输入标识确认商品表现分析身份，不编造商品主档或渠道商品状态。",
            "evidences": [],
            "confidence": "medium" if resolved_sku else "low",
            "data_completeness": "partial" if resolved_sku else "insufficient",
            "severity": None,
            "recommendations": [],
            "metrics": {},
            "details": {
                "product": product,
                "skus": skus,
                "channel_products": [],
                "mapping": [],
                "missing_fields": [],
                "performance_query": performance_query,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": ["渠道商品 API 尚未接入"],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_identity_for_performance_uses_sku_filter_and_identifier -q`

Expected: PASS.

---

### Task 2: Inventory adapter extracts SKU inventory and price facts

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Create: `.kiro/skills/product-query/scripts/product_query_engine/inventory_adapter.py`
- Modify: `.kiro/skills/product-query/scripts/product_query_engine/engine.py`

- [ ] **Step 1: Write the failing test**

Append to `.kiro/skills/product-query/tests/test_product_query_engine.py`:

```python
from product_query_engine.inventory_adapter import InventoryAdapter


def test_inventory_adapter_filters_sku_and_summarizes_quantity_and_price():
    class FakeClient:
        def _ensure_token(self):
            pass

        def post(self, path, payload):
            assert path == "/api/linker-oms/opc/app-api/inventory/list"
            assert payload == {"merchantNo": "M001", "sku": "SKU-A"}
            return {
                "data": {
                    "list": [
                        {"sku": "SKU-A", "availableQty": 3, "onHandQty": 5, "price": 10.5, "currency": "USD"},
                        {"sku": "SKU-B", "availableQty": 99, "onHandQty": 100, "price": 99, "currency": "USD"},
                    ]
                }
            }

    facts = InventoryAdapter(FakeClient()).fetch_sku_facts("M001", "SKU-A")

    assert facts == {
        "sku": "SKU-A",
        "available_qty": 3,
        "on_hand_qty": 5,
        "price": 10.5,
        "currency": "USD",
        "inventory_records": 1,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_inventory_adapter_filters_sku_and_summarizes_quantity_and_price -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'product_query_engine.inventory_adapter'`.

- [ ] **Step 3: Write minimal implementation**

Create `.kiro/skills/product-query/scripts/product_query_engine/inventory_adapter.py`:

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


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class InventoryAdapter:
    def __init__(self, client):
        self._client = client

    def fetch_sku_facts(self, merchant_no: str | None, sku: str | None) -> dict | None:
        if not sku:
            return None
        self._client._ensure_token()
        response = self._client.post(
            "/api/linker-oms/opc/app-api/inventory/list",
            {"merchantNo": merchant_no, "sku": sku},
        )
        rows = [row for row in _extract_list(response.get("data", response)) if str(row.get("sku") or row.get("productSku") or "") == sku]
        if not rows:
            return {"sku": sku, "inventory_records": 0}

        available_qty = sum(_number(row.get("availableQty") or row.get("availableQuantity")) for row in rows)
        on_hand_qty = sum(_number(row.get("onHandQty") or row.get("quantity") or row.get("qty")) for row in rows)
        first_price = next((row.get("price") or row.get("salePrice") for row in rows if row.get("price") or row.get("salePrice")), None)
        first_currency = next((row.get("currency") for row in rows if row.get("currency")), None)

        facts = {
            "sku": sku,
            "available_qty": int(available_qty) if available_qty.is_integer() else available_qty,
            "on_hand_qty": int(on_hand_qty) if on_hand_qty.is_integer() else on_hand_qty,
            "inventory_records": len(rows),
        }
        if first_price is not None:
            facts["price"] = _number(first_price)
        if first_currency:
            facts["currency"] = first_currency
        return facts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_inventory_adapter_filters_sku_and_summarizes_quantity_and_price -q`

Expected: PASS.

---

### Task 3: Engine uses inventory facts for inventory_price and overview

**Files:**
- Modify: `.kiro/skills/product-query/tests/test_product_query_engine.py`
- Modify: `.kiro/skills/product-query/scripts/product_query_engine/engine.py`

- [ ] **Step 1: Write the failing test**

Append:

```python

def test_inventory_price_includes_inventory_facts_when_adapter_available():
    class FakeInventoryAdapter:
        def fetch_sku_facts(self, merchant_no, sku):
            assert merchant_no == "M001"
            assert sku == "SKU-A"
            return {"sku": "SKU-A", "available_qty": 3, "on_hand_qty": 5, "price": 10.5, "currency": "USD", "inventory_records": 1}

    result = ProductQueryEngine(inventory_adapter=FakeInventoryAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="inventory_price",
        filters={},
    )

    assert result["metrics"] == {"sku_count": 1, "available_qty": 3, "on_hand_qty": 5}
    assert result["details"]["skus"] == [
        {"sku": "SKU-A", "available_qty": 3, "on_hand_qty": 5, "price": 10.5, "currency": "USD", "inventory_records": 1}
    ]
    assert result["confidence"] == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py::test_inventory_price_includes_inventory_facts_when_adapter_available -q`

Expected: FAIL because `metrics` is `{}` and SKU facts are not enriched.

- [ ] **Step 3: Write minimal implementation**

Replace `.kiro/skills/product-query/scripts/product_query_engine/engine.py` with:

```python
from __future__ import annotations


class ProductQueryEngine:
    def __init__(self, inventory_adapter=None):
        self._inventory_adapter = inventory_adapter

    def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
        filters = filters or {}
        resolved_sku = filters.get("sku") or identifier
        performance_query = {}
        if resolved_sku:
            performance_query["sku"] = resolved_sku
        for key in ("channel_code", "shop_id"):
            if filters.get(key):
                performance_query[key] = filters[key]

        sku_fact = None
        errors = ["渠道商品 API 尚未接入"]
        if self._inventory_adapter and resolved_sku and (intent in ("inventory_price", "overview", None)):
            try:
                sku_fact = self._inventory_adapter.fetch_sku_facts(merchant_no, resolved_sku)
            except Exception as e:
                errors.append(f"库存 API 查询失败: {e}")

        product = {"sku": resolved_sku} if resolved_sku else {}
        skus = [sku_fact or {"sku": resolved_sku}] if resolved_sku else []
        metrics = {}
        confidence = "medium" if resolved_sku else "low"
        data_completeness = "partial" if resolved_sku else "insufficient"
        if sku_fact and sku_fact.get("inventory_records", 0) > 0:
            metrics = {
                "sku_count": 1,
                "available_qty": sku_fact.get("available_qty", 0),
                "on_hand_qty": sku_fact.get("on_hand_qty", 0),
            }
            confidence = "high"

        return {
            "success": True,
            "summary": f"已确认 {resolved_sku} 可用于商品表现分析。" if resolved_sku else "已生成商品表现分析查询条件。",
            "reason": "MVP 仅返回已确认的 SKU、库存和表现分析过滤条件，不编造商品主档或渠道商品状态。",
            "evidences": [],
            "confidence": confidence,
            "data_completeness": data_completeness,
            "severity": None,
            "recommendations": [],
            "metrics": metrics,
            "details": {
                "product": product,
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

- [ ] **Step 4: Run product-query engine tests**

Run: `python -m pytest .kiro/skills/product-query/tests/test_product_query_engine.py -q`

Expected: all tests PASS.

---

### Task 4: Expose product_query through OMS Agent MCP server

**Files:**
- Modify: `.kiro/skills/oms-agent/mcp_server.py`
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `.kiro/skills/oms-agent/tests/test_navigation_routes.py`:

```python

def test_product_query_mcp_parses_filters_and_returns_result(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None):
            captured["has_inventory_adapter"] = inventory_adapter is not None

        def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
            captured["query"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
            }
            return {"success": True, "details": {"performance_query": filters}}

    class FakeInventoryAdapter:
        def __init__(self, client):
            pass

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeInventoryAdapter))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))

    result = json.loads(module.product_query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="identity_for_performance",
        filters='{"channel_code":"amazon"}',
    ))

    assert result["success"] is True
    assert captured["has_inventory_adapter"] is True
    assert captured["query"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "identity_for_performance",
        "filters": {"channel_code": "amazon"},
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_query_mcp_parses_filters_and_returns_result -q`

Expected: FAIL with `AttributeError: module 'oms_agent_mcp_server' has no attribute 'product_query'`.

- [ ] **Step 3: Add script path and MCP tool**

Modify `.kiro/skills/oms-agent/mcp_server.py` near existing `sys.path.insert` calls:

```python
sys.path.insert(0, os.path.join(_SKILLS_DIR, "product-query", "scripts"))
```

Add this tool after `oms_query(...)`:

```python
@mcp.tool()
def product_query(
    identifier: str | None = None,
    merchant_no: str | None = None,
    intent: str | None = None,
    filters: str | None = None,
) -> str:
    """Product Agent 商品事实查询 MVP。支持 SKU 身份确认、库存价格摘要和表现分析过滤条件生成。

    Args:
        identifier: SKU / SPU / product_id / channel_product_id；MVP 优先按 SKU 处理
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
        intent: identity_for_performance / inventory_price / overview
        filters: JSON 字符串，如 {"sku":"SKU001","channel_code":"amazon","shop_id":"SHOP001"}
    """
    from product_query_engine.engine import ProductQueryEngine
    from product_query_engine.inventory_adapter import InventoryAdapter
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    try:
        parsed_filters = json.loads(filters) if filters else {}
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": "invalid_filters_json", "message": str(e)}, ensure_ascii=False, indent=2)

    try:
        resolved_merchant_no = _resolve_merchant_no(merchant_no)
    except ValueError as e:
        return json.dumps({"success": False, "error": "missing_merchant_no", "message": str(e)}, ensure_ascii=False, indent=2)

    client = OMSAPIClient(EngineConfig())
    engine = ProductQueryEngine(inventory_adapter=InventoryAdapter(client))
    result = engine.query(
        identifier=identifier,
        merchant_no=resolved_merchant_no,
        intent=intent or "overview",
        filters=parsed_filters,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run MCP test**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_query_mcp_parses_filters_and_returns_result -q`

Expected: PASS.

---

### Task 5: MCP error handling for product_query bad JSON and missing merchant

**Files:**
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`
- Modify: `.kiro/skills/oms-agent/mcp_server.py` only if Task 4 code does not already satisfy tests

- [ ] **Step 1: Write failing tests**

Append:

```python

def test_product_query_returns_error_for_invalid_filters_json():
    module = load_mcp_server()

    result = json.loads(module.product_query(identifier="SKU-A", merchant_no="M001", filters="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_filters_json"


def test_product_query_returns_error_when_merchant_missing(monkeypatch):
    module = load_mcp_server()
    monkeypatch.delenv("CRM_MERCHANT_CODE", raising=False)
    monkeypatch.delenv("OMS_MERCHANT_NO", raising=False)

    result = json.loads(module.product_query(identifier="SKU-A"))

    assert result["success"] is False
    assert result["error"] == "missing_merchant_no"
```

- [ ] **Step 2: Run tests to verify status**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_query_returns_error_for_invalid_filters_json .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_query_returns_error_when_merchant_missing -q`

Expected: PASS if Task 4 implementation already covered both; if FAIL, update `product_query(...)` exactly as shown in Task 4 Step 3.

- [ ] **Step 3: Run all MCP tests**

Run: `python -m pytest .kiro/skills/oms-agent/tests -q`

Expected: PASS.

---

### Task 6: Update docs for Product Query MVP boundary

**Files:**
- Modify: `.kiro/skills/product-query/SKILL.md`
- Modify: `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Update Product Query skill doc**

Add under `.kiro/skills/product-query/SKILL.md` after the core principles:

```markdown
## MVP 运行时状态

当前 MCP runtime 已提供最小可用 `product_query`：

- 支持 `identity_for_performance` / `inventory_price` / `overview` 降级查询。
- 优先按 SKU 解析 `identifier` 或 `filters.sku`。
- 可返回库存数量、价格字段和 `performance_query`，供 `oms_analysis.sku_sales` / `channel_performance` 继续查询表现。
- 渠道商品、同步状态、审核状态、上架状态和商品-渠道映射 API 尚未接入；相关字段必须返回空数组并在 `errors` 中说明，不允许编造。
```

- [ ] **Step 2: Update Product Agent action plan**

In `docs/product-agent/01-落地行动方案.md`, update Phase 3 status with:

```markdown
### MVP 状态

已落地最小可用 `product_query` runtime：

- `product_query(...)` MCP tool 可接收 `identifier` / `merchant_no` / `intent` / `filters`。
- `identity_for_performance` 可输出 `performance_query`，直接衔接 Phase 2 `oms_analysis`。
- `inventory_price` 可基于现有库存 API 返回 SKU 库存和价格摘要。
- 商品中心主档、渠道商品、同步/审核/上架状态仍需后续确认真实 API 后接入。
```

- [ ] **Step 3: Run related tests**

Run: `python -m pytest .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: PASS.

---

### Task 7: Final verification and cleanup

**Files:**
- Verify all changed files.

- [ ] **Step 1: Remove generated caches**

Run: `rm -rf .kiro/skills/product-query/tests/__pycache__ .kiro/skills/oms-agent/tests/__pycache__ .kiro/skills/oms-analysis/tests/__pycache__`

Expected: no output.

- [ ] **Step 2: Review status**

Run: `git status --short -- .kiro/skills/product-query .kiro/skills/oms-agent .kiro/skills/oms-analysis docs/product-agent`

Expected: only source, test, and docs changes; no `__pycache__` files.

- [ ] **Step 3: Run final tests**

Run: `python -m pytest .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

---

## Self-Review

- Spec coverage: MVP `product_query` identity, inventory/price, degraded overview, performance filters, unsupported channel-products error, MCP entry, JSON parsing, and docs are covered.
- Placeholder scan: no TBD/TODO/implement-later placeholders remain.
- Type consistency: `ProductQueryEngine.query(identifier, merchant_no, intent, filters)` is used consistently by engine tests and MCP tests; `InventoryAdapter.fetch_sku_facts(merchant_no, sku)` is used consistently by engine and adapter tests.
