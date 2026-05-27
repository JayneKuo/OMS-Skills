# Batch Reallocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single `batch-reallocation` OMS Agent capability that analyzes mixed-status orders, collects user choices through chat-form payloads, and safely executes batch reallocation only for eligible unfulfilled SKU quantities.

**Architecture:** Add one user-facing skill under `.kiro/skills/oms-agent/batch-reallocation/` and implement its logic as focused internal Python modules for config, API access, eligibility rules, analysis, form building, execution, and result formatting. Expose only two MCP entrypoints in `mcp_server.py` (`batch_reallocation_analyze` and `batch_reallocation_execute`), then register the capability in OMS Agent docs/workflows so the top-level agent can route dangerous batch reallocation requests through a query → analyze → form → confirm → execute flow.

**Tech Stack:** Python 3.12, FastMCP, Pydantic, requests/http client patterns already used by OMS skills, pytest.

---

## File Structure

### New files
- `.kiro/skills/oms-agent/batch-reallocation/SKILL.md` — user-facing skill definition, trigger boundaries, safety rules, and chat-form workflow
- `.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md` — human-readable mapping from business scenarios to OMS APIs
- `.kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md` — structured payload contract for chat-window forms
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/__init__.py` — package exports
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py` — request/result/form/result Pydantic models
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/config.py` — runtime env resolution aligned with OMS query config plus `USER`
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py` — OMS query/execute API wrapper for search, sale order, logs, recover, hold release
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py` — scenario grouping and unfulfilled-qty safety rules
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py` — batch order analysis orchestration
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/form_builder.py` — form payload generation from analyzed candidates
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py` — confirm-time recheck and execution orchestration
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/result_formatter.py` — user summary and structured execution result formatting
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_config.py` — env parsing tests
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py` — scenario and quantity guard tests
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py` — form schema tests
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py` — analyzer orchestration tests
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py` — executor safety and routing tests
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py` — MCP tool contract tests

### Modified files
- `.kiro/skills/oms-agent/mcp_server.py` — add sys.path for new package and expose `batch_reallocation_analyze` / `batch_reallocation_execute`
- `.kiro/skills/oms-agent/SKILL_REGISTRY.md` — register `batch-reallocation`
- `.kiro/skills/oms-agent/WORKFLOWS.md` — add `batch_reallocation_workflow`

---

### Task 1: Add config and core models

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/__init__.py`
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py`
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/config.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_config.py`

- [ ] **Step 1: Write the failing config tests**

```python
from batch_reallocation.config import BatchReallocationConfig


def test_config_reads_standard_runtime_env(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("USER", "lantester@item.com")

    cfg = BatchReallocationConfig()

    assert cfg.base_url == "https://oms.example.com"
    assert cfg.tenant_id == "LT"
    assert cfg.merchant_no == "LAN0000002"
    assert cfg.access_token == "token-123"
    assert cfg.user == "lantester@item.com"


def test_config_allows_analysis_without_user(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")
    monkeypatch.delenv("USER", raising=False)

    cfg = BatchReallocationConfig()

    assert cfg.user is None
    cfg.validate_for_analysis()


def test_config_blocks_execution_without_user(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")
    monkeypatch.delenv("USER", raising=False)

    cfg = BatchReallocationConfig()

    try:
        cfg.validate_for_execution()
    except ValueError as exc:
        assert "USER" in str(exc)
    else:
        raise AssertionError("expected validate_for_execution to fail")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'batch_reallocation'`

- [ ] **Step 3: Write minimal package exports**

```python
from .config import BatchReallocationConfig
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ExecuteRequest,
    ExecuteResponse,
)

__all__ = [
    "BatchReallocationConfig",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "ExecuteRequest",
    "ExecuteResponse",
]
```

- [ ] **Step 4: Write minimal request/result models**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Scenario = Literal["imported", "exception", "deallocated", "on_hold", "ineligible"]
ActionMode = Literal["whole_order", "partial_sku", "release_hold_then_recover"]


class OrderInput(BaseModel):
    raw_identifier: str
    order_no: str | None = None


class SkuCandidate(BaseModel):
    sku: str
    ordered_qty: int = 0
    fulfilled_qty: int = 0
    unfulfilled_qty: int = 0
    hold_qty: int = 0
    selected: bool = False
    eligible: bool = False
    reason: str | None = None


class OrderCandidate(BaseModel):
    order_no: str
    scenario: Scenario
    status: str
    eligible: bool
    reason: str | None = None
    exception_summary: str | None = None
    hold_reason: str | None = None
    skus: list[SkuCandidate] = Field(default_factory=list)


class FormGroup(BaseModel):
    scenario: Scenario
    title: str
    selection_mode: Literal["order", "sku"]
    orders: list[OrderCandidate] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    identifiers: list[str]
    merchant_no: str | None = None


class AnalyzeResponse(BaseModel):
    form_type: Literal["batch-reallocation-analysis"] = "batch-reallocation-analysis"
    groups: list[FormGroup] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    next_action: str = "collect_user_decision"


class OrderDecision(BaseModel):
    order_no: str
    action_mode: ActionMode
    selected_skus: list[str] = Field(default_factory=list)
    release_hold: bool = False


class ExecuteRequest(BaseModel):
    decisions: list[OrderDecision]
    merchant_no: str | None = None


class ExecuteResponse(BaseModel):
    submitted_orders: int = 0
    succeeded_orders: list[str] = Field(default_factory=list)
    partial_succeeded_orders: list[str] = Field(default_factory=list)
    failed_orders: dict[str, str] = Field(default_factory=dict)
    skipped_orders: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 5: Write minimal config implementation**

```python
from __future__ import annotations

import os

from pydantic import BaseModel, model_validator


class BatchReallocationConfig(BaseModel):
    base_url: str | None = None
    tenant_id: str | None = None
    merchant_no: str | None = None
    access_token: str | None = None
    user: str | None = None
    request_timeout: int = 30

    @model_validator(mode="before")
    @classmethod
    def _override_from_env(cls, values: dict) -> dict:
        values = dict(values or {})

        def _env(*keys: str) -> str | None:
            for key in keys:
                env_val = os.environ.get(key)
                if env_val not in (None, ""):
                    return env_val
            return None

        values.setdefault("base_url", _env("OMS_BASE_URL", "baseUrl", "BASE_URL"))
        values.setdefault("tenant_id", _env("OMS_TENANT_ID", "TENANT_ID", "tenantId", "x-tenant-id"))
        values.setdefault("merchant_no", _env("CRM_MERCHANT_CODE", "OMS_MERCHANT_NO", "merchantNo", "merchant_no", "merchant"))
        values.setdefault("access_token", _env("OMS_ACCESS_TOKEN", "OMS_SESSION_TOKEN", "ACCESS_TOKEN", "AUTH_TOKEN", "OMS_TOKEN", "authorization"))
        values.setdefault("user", _env("USER", "username", "user"))
        return values

    def validate_for_analysis(self) -> None:
        missing = [
            name
            for name, value in {
                "OMS_BASE_URL": self.base_url,
                "OMS_TENANT_ID": self.tenant_id,
                "OMS_ACCESS_TOKEN": self.access_token,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing analysis runtime env: {', '.join(missing)}")

    def validate_for_execution(self) -> None:
        self.validate_for_analysis()
        if not self.user:
            raise ValueError("Missing USER in agent session env")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/__init__.py .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/config.py .kiro/skills/oms-agent/tests/test_batch_reallocation_config.py
git commit -m "feat(oms-agent): add batch reallocation config and models"
```

### Task 2: Implement eligibility rules for scenario grouping and quantity guards

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py`

- [ ] **Step 1: Write the failing eligibility tests**

```python
from batch_reallocation.eligibility import build_sku_candidate, classify_order_scenario, choose_action_mode


def test_imported_order_with_unfulfilled_qty_is_eligible_whole_order():
    order = {"status": "Imported", "orderNo": "SO1"}
    sku_lines = [{"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0}]

    scenario = classify_order_scenario(order)
    sku = build_sku_candidate(sku_lines[0])
    mode = choose_action_mode(scenario=scenario, skus=[sku], recoverable=True)

    assert scenario == "imported"
    assert sku.unfulfilled_qty == 3
    assert sku.eligible is True
    assert mode == "whole_order"


def test_deallocated_mixed_fulfillment_forces_partial_sku():
    order = {"status": "Deallocated", "orderNo": "SO2"}
    skus = [
        build_sku_candidate({"sku": "SKU-A", "quantity": 5, "fulfilledQty": 5, "hold": 0}),
        build_sku_candidate({"sku": "SKU-B", "quantity": 4, "fulfilledQty": 1, "hold": 0}),
    ]

    mode = choose_action_mode(scenario=classify_order_scenario(order), skus=skus, recoverable=True)

    assert skus[0].eligible is False
    assert skus[1].unfulfilled_qty == 3
    assert mode == "partial_sku"


def test_on_hold_sku_requires_release_hold_then_recover():
    order = {"status": "On Hold", "orderNo": "SO3", "holdReason": "fraud-check"}
    skus = [build_sku_candidate({"sku": "SKU-C", "quantity": 2, "fulfilledQty": 0, "hold": 2})]

    mode = choose_action_mode(scenario=classify_order_scenario(order), skus=skus, recoverable=True)

    assert classify_order_scenario(order) == "on_hold"
    assert mode == "release_hold_then_recover"


def test_zero_unfulfilled_qty_is_ineligible():
    sku = build_sku_candidate({"sku": "SKU-Z", "quantity": 2, "fulfilledQty": 2, "hold": 0})

    assert sku.unfulfilled_qty == 0
    assert sku.eligible is False
    assert sku.reason == "unfulfilled_qty_zero"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbols from `batch_reallocation.eligibility`

- [ ] **Step 3: Write minimal eligibility implementation**

```python
from __future__ import annotations

from batch_reallocation.models import ActionMode, Scenario, SkuCandidate


def _status_text(order: dict) -> str:
    return str(order.get("status") or order.get("statusName") or "").strip().lower()


def classify_order_scenario(order: dict) -> Scenario:
    status = _status_text(order)
    if status == "imported":
        return "imported"
    if status == "exception":
        return "exception"
    if status == "deallocated":
        return "deallocated"
    if status in {"on hold", "on_hold", "hold"}:
        return "on_hold"
    return "ineligible"


def build_sku_candidate(line: dict) -> SkuCandidate:
    ordered_qty = int(line.get("quantity") or line.get("orderedQty") or 0)
    fulfilled_qty = int(line.get("fulfilledQty") or line.get("shippedQty") or 0)
    hold_qty = int(line.get("hold") or line.get("holdQty") or 0)
    unfulfilled_qty = max(ordered_qty - fulfilled_qty, 0)
    eligible = unfulfilled_qty > 0
    reason = None if eligible else "unfulfilled_qty_zero"
    return SkuCandidate(
        sku=str(line.get("sku") or line.get("skuCode") or ""),
        ordered_qty=ordered_qty,
        fulfilled_qty=fulfilled_qty,
        unfulfilled_qty=unfulfilled_qty,
        hold_qty=hold_qty,
        eligible=eligible,
        reason=reason,
    )


def choose_action_mode(*, scenario: Scenario, skus: list[SkuCandidate], recoverable: bool) -> ActionMode:
    if scenario == "on_hold":
        return "release_hold_then_recover"
    eligible_skus = [sku for sku in skus if sku.eligible]
    if scenario == "deallocated" and len(eligible_skus) != len(skus):
        return "partial_sku"
    if scenario == "deallocated" and any(sku.fulfilled_qty > 0 for sku in skus):
        return "partial_sku"
    return "whole_order"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py .kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py
git commit -m "feat(oms-agent): add batch reallocation eligibility rules"
```

### Task 3: Implement analyzer orchestration over OMS query endpoints

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py`
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`

- [ ] **Step 1: Write the failing analyzer tests**

```python
from batch_reallocation.analyzer import BatchReallocationAnalyzer
from batch_reallocation.config import BatchReallocationConfig


class FakeOMSClient:
    def resolve_order(self, identifier):
        return {"orderNo": identifier}

    def get_sale_order(self, order_no):
        return {
            "orderNo": order_no,
            "status": "Imported" if order_no == "SO1" else "On Hold",
            "holdReason": None if order_no == "SO1" else "address-risk",
            "items": [
                {"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0},
                {"sku": "SKU-B", "quantity": 2, "fulfilledQty": 2, "hold": 0},
            ],
        }

    def get_order_logs(self, order_no, merchant_no):
        return [{"remark": f"log-for-{order_no}"}]

    def get_recover_check(self, order_no):
        return True

    def get_recover_query(self, order_no):
        return {"recoverable": True}


def test_analyzer_groups_orders_and_filters_zero_unfulfilled_qty():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeOMSClient(),
    )

    result = analyzer.analyze(["SO1", "SO2"])

    groups = {group.scenario: group for group in result.groups}
    assert len(groups["imported"].orders) == 1
    assert len(groups["on_hold"].orders) == 1
    imported_order = groups["imported"].orders[0]
    assert [sku.sku for sku in imported_order.skus if sku.eligible] == ["SKU-A"]
    assert result.requires_confirmation is True
    assert result.next_action == "collect_user_decision"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py -v`
Expected: FAIL with missing `BatchReallocationAnalyzer` or `api_client`

- [ ] **Step 3: Write minimal API client methods**

```python
from __future__ import annotations

import requests

from batch_reallocation.config import BatchReallocationConfig


class BatchReallocationAPIClient:
    def __init__(self, config: BatchReallocationConfig):
        self.config = config

    def _headers(self, include_user: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "x-tenant-id": self.config.tenant_id or "",
            "locale": "zh-CN",
        }
        if include_user and self.config.user:
            headers["USER"] = self.config.user
        return headers

    def resolve_order(self, identifier: str) -> dict:
        resp = requests.post(
            f"{self.config.base_url}/app-api/tracking-assistant/search-order-no",
            json={"searchValue": identifier},
            headers=self._headers(),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def get_sale_order(self, order_no: str) -> dict:
        resp = requests.get(
            f"{self.config.base_url}/app-api/sale-order/{order_no}",
            headers=self._headers(),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def get_order_logs(self, order_no: str, merchant_no: str) -> list[dict]:
        resp = requests.get(
            f"{self.config.base_url}/app-api/orderLog/list",
            params={"omsOrderNo": order_no, "merchantNo": merchant_no},
            headers=self._headers(),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or []

    def get_recover_check(self, order_no: str) -> bool:
        resp = requests.get(
            f"{self.config.base_url}/app-api/dispatch/recover/check/{order_no}",
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return bool(resp.json().get("data"))

    def get_recover_query(self, order_no: str) -> dict:
        resp = requests.get(
            f"{self.config.base_url}/app-api/dispatch/recover/query/{order_no}",
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}
```

- [ ] **Step 4: Write minimal analyzer implementation**

```python
from __future__ import annotations

from batch_reallocation.api_client import BatchReallocationAPIClient
from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.eligibility import build_sku_candidate, choose_action_mode, classify_order_scenario
from batch_reallocation.models import AnalyzeResponse, FormGroup, OrderCandidate


class BatchReallocationAnalyzer:
    def __init__(self, config: BatchReallocationConfig, client: BatchReallocationAPIClient):
        self.config = config
        self.client = client

    def analyze(self, identifiers: list[str], merchant_no: str | None = None) -> AnalyzeResponse:
        self.config.validate_for_analysis()
        resolved_merchant = merchant_no or self.config.merchant_no or ""
        groups: dict[str, FormGroup] = {}

        for raw_identifier in identifiers:
            order_ref = self.client.resolve_order(raw_identifier)
            order_no = order_ref.get("orderNo") or raw_identifier
            order = self.client.get_sale_order(order_no)
            logs = self.client.get_order_logs(order_no, resolved_merchant)
            recoverable = self.client.get_recover_check(order_no)
            recover_query = self.client.get_recover_query(order_no)
            scenario = classify_order_scenario(order)
            sku_candidates = [build_sku_candidate(line) for line in order.get("items") or order.get("orderItems") or []]
            action_mode = choose_action_mode(scenario=scenario, skus=sku_candidates, recoverable=recoverable)
            candidate = OrderCandidate(
                order_no=order_no,
                scenario=scenario,
                status=str(order.get("status") or order.get("statusName") or ""),
                eligible=any(sku.eligible for sku in sku_candidates),
                reason=None if recover_query.get("recoverable", True) else "recover_check_failed",
                exception_summary=(logs[0].get("remark") if logs else None),
                hold_reason=order.get("holdReason"),
                skus=sku_candidates,
            )
            title = {
                "imported": "Imported orders",
                "exception": "Exception orders",
                "deallocated": "Deallocated orders",
                "on_hold": "On Hold orders",
                "ineligible": "Ineligible orders",
            }[scenario]
            selection_mode = "sku" if action_mode == "release_hold_then_recover" else "order"
            groups.setdefault(scenario, FormGroup(scenario=scenario, title=title, selection_mode=selection_mode, orders=[])).orders.append(candidate)

        return AnalyzeResponse(groups=list(groups.values()), warnings=[])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py
git commit -m "feat(oms-agent): add batch reallocation analyzer"
```

### Task 4: Build the chat-form payload contract

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/form_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py`
- Docs: `.kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md`

- [ ] **Step 1: Write the failing form builder tests**

```python
from batch_reallocation.form_builder import build_form_payload
from batch_reallocation.models import AnalyzeResponse, FormGroup, OrderCandidate, SkuCandidate


def test_form_builder_emits_order_and_sku_groups_with_confirmation_flags():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="imported",
                title="Imported orders",
                selection_mode="order",
                orders=[
                    OrderCandidate(
                        order_no="SO1",
                        scenario="imported",
                        status="Imported",
                        eligible=True,
                        skus=[SkuCandidate(sku="SKU-A", ordered_qty=3, fulfilled_qty=0, unfulfilled_qty=3, eligible=True)],
                    )
                ],
            ),
            FormGroup(
                scenario="on_hold",
                title="On Hold orders",
                selection_mode="sku",
                orders=[
                    OrderCandidate(
                        order_no="SO2",
                        scenario="on_hold",
                        status="On Hold",
                        eligible=True,
                        hold_reason="risk",
                        skus=[SkuCandidate(sku="SKU-B", ordered_qty=2, fulfilled_qty=0, unfulfilled_qty=2, hold_qty=2, eligible=True)],
                    )
                ],
            ),
        ]
    )

    payload = build_form_payload(response)

    assert payload["form_type"] == "batch-reallocation-analysis"
    assert payload["requires_confirmation"] is True
    assert payload["groups"][0]["selection_mode"] == "order"
    assert payload["groups"][1]["selection_mode"] == "sku"
    assert payload["groups"][1]["orders"][0]["hold_reason"] == "risk"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py -v`
Expected: FAIL with missing `build_form_payload`

- [ ] **Step 3: Write minimal form builder implementation**

```python
from __future__ import annotations

from batch_reallocation.models import AnalyzeResponse


def build_form_payload(result: AnalyzeResponse) -> dict:
    return {
        "form_type": result.form_type,
        "groups": [
            {
                "scenario": group.scenario,
                "title": group.title,
                "selection_mode": group.selection_mode,
                "orders": [
                    {
                        "order_no": order.order_no,
                        "status": order.status,
                        "eligible": order.eligible,
                        "reason": order.reason,
                        "exception_summary": order.exception_summary,
                        "hold_reason": order.hold_reason,
                        "skus": [
                            {
                                "sku": sku.sku,
                                "ordered_qty": sku.ordered_qty,
                                "fulfilled_qty": sku.fulfilled_qty,
                                "unfulfilled_qty": sku.unfulfilled_qty,
                                "hold_qty": sku.hold_qty,
                                "eligible": sku.eligible,
                                "reason": sku.reason,
                            }
                            for sku in order.skus
                        ],
                    }
                    for order in group.orders
                ],
            }
            for group in result.groups
        ],
        "warnings": result.warnings,
        "requires_confirmation": result.requires_confirmation,
        "next_action": result.next_action,
    }
```

- [ ] **Step 4: Document the form protocol**

```markdown
# batch-reallocation form protocol

## Analysis response payload
- `form_type`: always `batch-reallocation-analysis`
- `groups[]`: scenario groups for imported / exception / deallocated / on_hold / ineligible
- `groups[].selection_mode`: `order` or `sku`
- `groups[].orders[].skus[]`: includes quantity and eligibility fields
- `warnings[]`: non-blocking safety notes
- `requires_confirmation`: always true before execution
- `next_action`: `collect_user_decision`

## Execution request payload
- `decisions[]`
- `decisions[].order_no`
- `decisions[].action_mode`
- `decisions[].selected_skus[]`
- `decisions[].release_hold`
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/form_builder.py .kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py
git commit -m "feat(oms-agent): add batch reallocation form protocol"
```

### Task 5: Implement execution orchestration with recheck and safe API routing

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py`
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/result_formatter.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`

- [ ] **Step 1: Write the failing executor tests**

```python
from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.executor import BatchReallocationExecutor
from batch_reallocation.models import ExecuteRequest, OrderDecision


class FakeExecuteClient:
    def __init__(self):
        self.calls = []

    def get_sale_order(self, order_no):
        if order_no == "STALE":
            return {"orderNo": order_no, "status": "Shipped", "items": [{"sku": "SKU-A", "quantity": 1, "fulfilledQty": 1, "hold": 0}]}
        return {"orderNo": order_no, "status": "Imported", "items": [{"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0}]}

    def get_recover_check(self, order_no):
        return True

    def get_recover_query(self, order_no):
        return {"recoverable": True}

    def release_hold(self, order_no):
        self.calls.append(("release_hold", order_no))
        return True

    def recover_dispatch(self, order_no):
        self.calls.append(("recover_dispatch", order_no))
        return True

    def recover_dispatch_part(self, order_no, selected_skus):
        self.calls.append(("recover_dispatch_part", order_no, selected_skus))
        return True


def test_executor_skips_stale_orders_and_executes_whole_order():
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=FakeExecuteClient(),
    )

    result = executor.execute(
        ExecuteRequest(
            decisions=[
                OrderDecision(order_no="SO1", action_mode="whole_order"),
                OrderDecision(order_no="STALE", action_mode="whole_order"),
            ]
        )
    )

    assert result.succeeded_orders == ["SO1"]
    assert result.skipped_orders == {"STALE": "stale_state"}


def test_executor_uses_partial_route_for_selected_skus():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    result = executor.execute(
        ExecuteRequest(
            decisions=[OrderDecision(order_no="SO2", action_mode="partial_sku", selected_skus=["SKU-A"])]
        )
    )

    assert result.succeeded_orders == ["SO2"]
    assert client.calls == [("recover_dispatch_part", "SO2", ["SKU-A"])]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py -v`
Expected: FAIL with missing executor implementation

- [ ] **Step 3: Extend API client with execution methods**

```python
    def release_hold(self, order_no: str) -> bool:
        resp = requests.post(
            f"{self.config.base_url}/app-api/order-hold/release",
            params={"orderNo": order_no},
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return bool(resp.json().get("data"))

    def recover_dispatch(self, order_no: str) -> bool:
        resp = requests.post(
            f"{self.config.base_url}/app-api/dispatch/recover/dispatch",
            json={"orderNo": order_no},
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return True

    def recover_dispatch_part(self, order_no: str, selected_skus: list[str]) -> bool:
        resp = requests.post(
            f"{self.config.base_url}/app-api/dispatch/recover/dispatch/part",
            json={"orderNo": order_no, "skus": selected_skus},
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return True
```

- [ ] **Step 4: Write minimal executor implementation**

```python
from __future__ import annotations

from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.eligibility import build_sku_candidate, classify_order_scenario
from batch_reallocation.models import ExecuteRequest, ExecuteResponse


class BatchReallocationExecutor:
    def __init__(self, config: BatchReallocationConfig, client):
        self.config = config
        self.client = client

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        self.config.validate_for_execution()
        result = ExecuteResponse(submitted_orders=len(request.decisions))

        for decision in request.decisions:
            order = self.client.get_sale_order(decision.order_no)
            scenario = classify_order_scenario(order)
            skus = [build_sku_candidate(line) for line in order.get("items") or order.get("orderItems") or []]
            if not any(sku.eligible for sku in skus):
                result.skipped_orders[decision.order_no] = "stale_state"
                continue
            if scenario == "ineligible":
                result.skipped_orders[decision.order_no] = "stale_state"
                continue

            if decision.action_mode == "release_hold_then_recover":
                self.client.release_hold(decision.order_no)
                if decision.selected_skus:
                    self.client.recover_dispatch_part(decision.order_no, decision.selected_skus)
                else:
                    self.client.recover_dispatch(decision.order_no)
            elif decision.action_mode == "partial_sku":
                self.client.recover_dispatch_part(decision.order_no, decision.selected_skus)
            else:
                self.client.recover_dispatch(decision.order_no)

            result.succeeded_orders.append(decision.order_no)

        return result
```

- [ ] **Step 5: Write minimal result formatter**

```python
from __future__ import annotations

from batch_reallocation.models import ExecuteResponse


def format_execution_result(result: ExecuteResponse) -> dict:
    return {
        "submitted_orders": result.submitted_orders,
        "succeeded_orders": result.succeeded_orders,
        "partial_succeeded_orders": result.partial_succeeded_orders,
        "failed_orders": result.failed_orders,
        "skipped_orders": result.skipped_orders,
        "warnings": result.warnings,
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/result_formatter.py .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py
git commit -m "feat(oms-agent): add batch reallocation executor"
```

### Task 6: Expose minimal MCP tools and test their contracts

**Files:**
- Modify: `.kiro/skills/oms-agent/mcp_server.py`
- Create: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Write the failing MCP tool tests**

```python
import json
import sys
import types

from test_navigation_routes import load_mcp_server


def test_batch_reallocation_analyze_returns_form_payload(monkeypatch):
    module = load_mcp_server()

    class FakeAnalyzer:
        def __init__(self, config, client):
            pass

        def analyze(self, identifiers, merchant_no=None):
            from batch_reallocation.models import AnalyzeResponse
            return AnalyzeResponse()

    class FakeClient:
        def __init__(self, config):
            pass

    monkeypatch.setitem(sys.modules, "batch_reallocation.analyzer", types.SimpleNamespace(BatchReallocationAnalyzer=FakeAnalyzer))
    monkeypatch.setitem(sys.modules, "batch_reallocation.api_client", types.SimpleNamespace(BatchReallocationAPIClient=FakeClient))

    result = json.loads(module.batch_reallocation_analyze('["SO1"]'))

    assert result["form_type"] == "batch-reallocation-analysis"
    assert result["requires_confirmation"] is True


def test_batch_reallocation_execute_returns_execution_summary(monkeypatch):
    module = load_mcp_server()

    class FakeExecutor:
        def __init__(self, config, client):
            pass

        def execute(self, request):
            from batch_reallocation.models import ExecuteResponse
            return ExecuteResponse(submitted_orders=1, succeeded_orders=["SO1"])

    class FakeClient:
        def __init__(self, config):
            pass

    monkeypatch.setitem(sys.modules, "batch_reallocation.executor", types.SimpleNamespace(BatchReallocationExecutor=FakeExecutor))
    monkeypatch.setitem(sys.modules, "batch_reallocation.api_client", types.SimpleNamespace(BatchReallocationAPIClient=FakeClient))

    result = json.loads(module.batch_reallocation_execute('{"decisions":[{"order_no":"SO1","action_mode":"whole_order"}]}'))

    assert result["submitted_orders"] == 1
    assert result["succeeded_orders"] == ["SO1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v`
Expected: FAIL with missing MCP functions

- [ ] **Step 3: Add new package path in `mcp_server.py`**

```python
sys.path.insert(0, os.path.join(_SKILLS_DIR, "oms-agent", "batch-reallocation", "scripts"))
```

Add it with the existing `sys.path.insert` block near:
- `.kiro/skills/oms-agent/mcp_server.py:30-35`

- [ ] **Step 4: Add `batch_reallocation_analyze` MCP tool**

```python
@mcp.tool()
def batch_reallocation_analyze(identifiers_json: str, merchant_no: str | None = None) -> str:
    """Analyze candidate orders for dangerous batch reallocation and return chat-form payload."""
    from batch_reallocation.api_client import BatchReallocationAPIClient
    from batch_reallocation.analyzer import BatchReallocationAnalyzer
    from batch_reallocation.config import BatchReallocationConfig
    from batch_reallocation.form_builder import build_form_payload

    identifiers = json.loads(identifiers_json)
    config = BatchReallocationConfig()
    analyzer = BatchReallocationAnalyzer(config=config, client=BatchReallocationAPIClient(config))
    result = analyzer.analyze(identifiers=identifiers, merchant_no=_resolve_merchant_no(merchant_no))
    return json.dumps(build_form_payload(result), ensure_ascii=False, indent=2)
```

- [ ] **Step 5: Add `batch_reallocation_execute` MCP tool**

```python
@mcp.tool()
def batch_reallocation_execute(request_json: str, merchant_no: str | None = None) -> str:
    """Execute confirmed batch reallocation decisions after runtime recheck."""
    from batch_reallocation.api_client import BatchReallocationAPIClient
    from batch_reallocation.config import BatchReallocationConfig
    from batch_reallocation.executor import BatchReallocationExecutor
    from batch_reallocation.models import ExecuteRequest
    from batch_reallocation.result_formatter import format_execution_result

    payload = json.loads(request_json)
    if merchant_no:
        payload["merchant_no"] = merchant_no
    else:
        payload.setdefault("merchant_no", _resolve_merchant_no(None))
    request = ExecuteRequest(**payload)
    config = BatchReallocationConfig(merchant_no=request.merchant_no)
    executor = BatchReallocationExecutor(config=config, client=BatchReallocationAPIClient(config))
    result = executor.execute(request)
    return json.dumps(format_execution_result(result), ensure_ascii=False, indent=2)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .kiro/skills/oms-agent/mcp_server.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py
git commit -m "feat(oms-agent): expose batch reallocation MCP tools"
```

### Task 7: Register the skill and workflow in OMS Agent docs

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/SKILL.md`
- Create: `.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md`
- Modify: `.kiro/skills/oms-agent/SKILL_REGISTRY.md`
- Modify: `.kiro/skills/oms-agent/WORKFLOWS.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: batch-reallocation
description: Use when OMS operators need to analyze and safely execute batch reallocation for imported, exception, deallocated, or on-hold orders through a chat form with explicit confirmation.
---

# Batch Reallocation

## Purpose
Handle dangerous OMS batch reallocation requests through a strict analyze → form → confirm → execute workflow.

## Use When
- 批量重新分仓 imported 订单
- 批量处理 exception 订单后重新分仓
- 处理 deallocated 订单的重新分仓
- 处理 on hold 订单中可恢复 SKU 的重新分仓

## Safety Rules
- Never execute before explicit user confirmation.
- Only act on SKU lines where unfulfilled quantity is not zero.
- On Hold orders require separate SKU-level decisions.
- Missing `USER` means analyze only, never execute.

## Runtime Inputs
- `OMS_BASE_URL`
- `OMS_TENANT_ID`
- `CRM_MERCHANT_CODE` / `OMS_MERCHANT_NO`
- `OMS_ACCESS_TOKEN`
- `USER` (execution only)
```

- [ ] **Step 2: Write the API mapping reference**

```markdown
# batch-reallocation API mapping

## Query APIs
- `POST /app-api/tracking-assistant/search-order-no`
- `GET /app-api/sale-order/{orderNo}`
- `GET /app-api/orderLog/list`
- `GET /app-api/dispatch/recover/check/{orderNo}`
- `GET /app-api/dispatch/recover/query/{orderNo}`

## Execute APIs
- `POST /app-api/dispatch/recover/dispatch`
- `POST /app-api/dispatch/recover/dispatch/part`
- `POST /app-api/order-hold/release`
- `POST /app-api/opc/order-hold/release`

## Notes
- `POST /app-api/dispatch/deallocate/{dispatchNo}` is reserved as a future extension.
- OpenAPI example tokens must never be copied into implementation.
```

- [ ] **Step 3: Add a `batch-reallocation` registry entry to `SKILL_REGISTRY.md`**

```markdown
## 4.6 batch-reallocation（🚧 新增规划实现中）

### Purpose
危险批量重分仓能力。面向运营人员在 Imported、Exception、Deallocated、On Hold 场景下，通过聊天窗口表单完成“分析 → 选择 → 确认 → 执行”的安全批量重分仓流程。

### Use When
当用户请求以下任务时优先使用：
- 批量重新分仓 imported 订单
- 批量处理 exception 后重新分仓
- 批量处理 deallocated 订单
- 批量处理 on hold 订单中的可恢复 SKU

### Inputs
- order identifiers[]
- merchant_no（可选，默认从 agent session env 读取）
- 用户表单确认结果

### Outputs
- 分组候选订单
- 聊天表单 payload
- 执行结果摘要
- 失败与跳过原因

### Constraints
- 无确认不执行
- 无 USER 不执行
- 只允许处理未履约数量不为 0 的 SKU
- on hold 必须单独决策

### Upstream Dependencies
- oms_query 风格 runtime env
- OMS batch reallocation MCP tools

### Downstream Consumers
- oms main agent
```
```

- [ ] **Step 4: Add a workflow entry to `WORKFLOWS.md`**

```markdown
## 6. batch_reallocation_workflow

### Trigger
当用户请求：
- 批量重新分仓
- imported 订单批量分仓
- exception 订单批量重新分仓
- deallocated / on hold 订单批量重分仓

### Steps
1. 收集订单号列表
2. 调用 `batch_reallocation_analyze`
3. 返回聊天表单并收集用户决定
4. 对 deallocated / on hold 做单独决策
5. 展示最终确认摘要
6. 调用 `batch_reallocation_execute`
7. 输出成功、失败、跳过明细

### Outputs
- scenario_groups
- form_payload
- execution_summary
- failure_reasons
- skipped_reasons
```
```

- [ ] **Step 5: Run focused documentation sanity check**

Run: `python - <<'PY'
from pathlib import Path
for path in [
    Path('.kiro/skills/oms-agent/batch-reallocation/SKILL.md'),
    Path('.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md'),
    Path('.kiro/skills/oms-agent/SKILL_REGISTRY.md'),
    Path('.kiro/skills/oms-agent/WORKFLOWS.md'),
]:
    text = path.read_text(encoding='utf-8')
    assert 'TODO' not in text
    assert 'TBD' not in text
print('ok')
PY`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/SKILL.md .kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md .kiro/skills/oms-agent/SKILL_REGISTRY.md .kiro/skills/oms-agent/WORKFLOWS.md
git commit -m "feat(oms-agent): register batch reallocation skill"
```

### Task 8: Run final targeted verification

**Files:**
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_config.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Run the full batch reallocation test set**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_config.py .kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v`
Expected: all PASS

- [ ] **Step 2: Run the existing oms-agent MCP regression subset**

Run: `pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py -v`
Expected: PASS

- [ ] **Step 3: Manual dry-run verify analysis payload shape**

Run: `python - <<'PY'
import json
from pathlib import Path
text = Path('.kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md').read_text(encoding='utf-8')
assert 'form_type' in text
assert 'requires_confirmation' in text
assert 'selected_skus' in text
print('protocol-ok')
PY`
Expected: `protocol-ok`

- [ ] **Step 4: Commit**

```bash
git add .kiro/skills/oms-agent/tests/test_batch_reallocation_config.py .kiro/skills/oms-agent/tests/test_batch_reallocation_eligibility.py .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py .kiro/skills/oms-agent/mcp_server.py .kiro/skills/oms-agent/SKILL_REGISTRY.md .kiro/skills/oms-agent/WORKFLOWS.md .kiro/skills/oms-agent/batch-reallocation
git commit -m "test(oms-agent): verify batch reallocation workflow"
```

---

## Self-Review

### Spec coverage
- Query/analyze/form/confirm/execute flow: covered by Tasks 3, 4, 5, 6, 7.
- Runtime variables aligned with OMS env and `USER`: covered by Task 1 and Task 6.
- Imported / Exception / Deallocated / On Hold scenario rules: covered by Task 2 and Task 5.
- Chat form payload and final confirmation contract: covered by Task 4.
- MCP exposure and OMS Agent registration: covered by Tasks 6 and 7.
- Testing strategy and targeted verification: covered by Task 8.

### Placeholder scan
- No `TODO`, `TBD`, or “similar to previous task” placeholders remain.
- Every code-writing step includes concrete code.
- Every verification step includes an exact command and expected output.

### Type consistency
- `AnalyzeRequest`, `AnalyzeResponse`, `ExecuteRequest`, `ExecuteResponse`, `OrderDecision`, `OrderCandidate`, and `SkuCandidate` names are consistent across all tasks.
- MCP tool names are consistent: `batch_reallocation_analyze` and `batch_reallocation_execute`.
- Scenario names are consistent: `imported`, `exception`, `deallocated`, `on_hold`, `ineligible`.
