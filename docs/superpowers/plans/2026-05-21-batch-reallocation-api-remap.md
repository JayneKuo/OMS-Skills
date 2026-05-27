# Batch Reallocation API Remap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the batch-reallocation skill so exception orders use reopen, manual reallocation scenarios use hand-dispatch, on-hold orders release hold before hand-dispatch, and recover is removed from the active execution flow.

**Architecture:** Keep the existing analyze → form → confirm → execute flow and form shape, but replace the internal action model with explicit business actions that map 1:1 to OMS APIs. Analyzer decides among reopen vs whole-hand-dispatch vs SKU-hand-dispatch based on live order status and hand-check/hand-item results; executor routes each confirmed decision to the matching OMS endpoint and treats recover-only cases as unsupported for this flow. User-facing batch behavior remains single-confirmation bulk selection, while executor performs per-order API calls sequentially and aggregates per-order results so OMS single-order APIs do not force repeated user interaction.

**Tech Stack:** Python, Pydantic, requests, pytest, MCP server wrapper

---

## File Structure

### Files to modify
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py`
  - Replace ambiguous action_mode literals with explicit business actions.
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py`
  - Add reopen and hand-dispatch API methods; keep hold-release and hand-check helpers; stop using recover as the active path.
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py`
  - Rework action selection logic to choose reopen vs hand whole vs hand SKU.
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py`
  - Switch analysis from recover-based eligibility to reopen/hand-based eligibility.
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py`
  - Route confirmed actions to reopen / hand-dispatch / release+hand-dispatch.
- `.kiro/skills/oms-agent/batch-reallocation/SKILL.md`
  - Update scenario rules and execution description.
- `.kiro/skills/oms-agent/batch-reallocation/AGENT_PROMPT.md`
  - Update flow language so exception uses reopen and manual dispatch uses hand APIs.
- `.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md`
  - Update documented API mapping.
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`
  - Rewrite analyzer expectations around explicit actions.
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`
  - Rewrite executor expectations around reopen / hand-dispatch.
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`
  - Update MCP wrapper tests to use new action names.

### No new runtime files required
Keep the existing module layout. This is a behavior remap, not a new subsystem.

---

### Task 1: Replace ambiguous action modes with explicit business actions

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Write the failing test for explicit action names**

Add or replace assertions in `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py` so the execute payload uses the new action name:

```python
result = json.loads(module.batch_reallocation_execute(
    '{"confirmed":true,"decisions":[{"order_no":"SO1","action_mode":"reopen_order"}]}'
))

assert result["submitted_orders"] == 1
assert result["succeeded_orders"] == ["SO1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py::test_batch_reallocation_execute_returns_execution_summary -v
```

Expected: FAIL because existing tests and model literals still use `whole_order`.

- [ ] **Step 3: Update the action mode literals in `models.py`**

Change the action type definition and keep the request shape otherwise unchanged:

```python
ActionMode = Literal[
    "reopen_order",
    "hand_whole_dispatch",
    "hand_sku_dispatch",
    "release_hold_then_hand_whole_dispatch",
    "release_hold_then_hand_sku_dispatch",
]
```

Keep the `OrderDecision` model shape:

```python
class OrderDecision(BaseModel):
    order_no: str
    action_mode: ActionMode
    selected_skus: list[str] = Field(default_factory=list)
    release_hold: bool = False
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v
```

Expected: PASS after all usages are updated in later steps; if still failing, continue with the plan before re-running.

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py
git commit -m "refactor(oms-agent): use explicit batch reallocation actions"
```

---

### Task 2: Add reopen and hand-dispatch API methods

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`

- [ ] **Step 1: Write the failing executor test for reopen and hand dispatch calls**

In `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`, update the fake client to record explicit calls and add these expectations:

```python
assert client.calls == [("reopen_order", "EXCEPTION")]
```

and

```python
assert client.calls == [
    (
        "hand_dispatch",
        {
            "orderNo": "PARTIAL",
            "dispatchType": "HAND_SKU_DISPATCH",
            "itemDTOList": [{"sku": "SKU-A", "qty": 3, "uom": "EA"}],
            "warehouseDTOList": [],
            "remark": "",
        },
    )
]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py -k "reopen or hand" -v
```

Expected: FAIL because `api_client.py` does not yet expose `reopen_order` or `hand_dispatch`.

- [ ] **Step 3: Implement the new API client methods**

Add these methods to `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py`:

```python
def reopen_order(self, order_no: str) -> bool:
    resp = requests.post(
        f"{self.config.base_url}/app-api/sale-order/reopen/{order_no}",
        headers=self._headers(include_user=True),
        timeout=self.config.request_timeout,
    )
    resp.raise_for_status()
    return True


def hand_dispatch(self, payload: dict) -> bool:
    resp = requests.post(
        f"{self.config.base_url}/app-api/dispatch/hand",
        json=payload,
        headers=self._headers(include_user=True),
        timeout=self.config.request_timeout,
    )
    resp.raise_for_status()
    return bool(resp.json().get("data", True))
```

Do not remove `release_hold`, `get_hand_check`, or `get_hand_items`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py -k "reopen or hand" -v
```

Expected: PASS once executor wiring is added in Task 5.

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/api_client.py .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py
git commit -m "feat(oms-agent): add reopen and hand dispatch client methods"
```

---

### Task 3: Redefine scenario-to-action selection rules

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`

- [ ] **Step 1: Write the failing analyzer tests for the new decisions**

Update or add these expectations in `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`:

```python
assert result.groups[0].selection_mode == "order"
assert result.groups[0].orders[0].scenario == "exception"
assert result.groups[0].orders[0].eligible is True
```

and for mixed deallocated:

```python
assert result.groups[0].scenario == "deallocated"
assert result.groups[0].selection_mode == "sku"
assert [sku.sku for sku in result.groups[0].orders[0].skus if sku.eligible] == ["SKU-B"]
```

Also add a new imported-order expectation:

```python
assert result.groups["imported"].selection_mode == "order"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py -v
```

Expected: FAIL because action selection still assumes recover semantics.

- [ ] **Step 3: Replace `choose_action_mode` with explicit business mapping**

Update `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py` so the selector returns the new action modes:

```python
def choose_action_mode(*, scenario: Scenario, skus: list[SkuCandidate]) -> ActionMode:
    eligible_skus = [sku for sku in skus if sku.eligible]

    if scenario == "exception":
        return "reopen_order"
    if scenario == "on_hold":
        if len(eligible_skus) != len(skus) or any(sku.fulfilled_qty > 0 for sku in skus):
            return "release_hold_then_hand_sku_dispatch"
        return "release_hold_then_hand_whole_dispatch"
    if scenario == "deallocated":
        if len(eligible_skus) != len(skus) or any(sku.fulfilled_qty > 0 for sku in skus):
            return "hand_sku_dispatch"
        return "hand_whole_dispatch"
    return "hand_whole_dispatch"
```

Do not pass `recoverable` into this selector anymore.

- [ ] **Step 4: Run the focused analyzer tests to verify they pass**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py -v
```

Expected: PASS once analyzer logic is updated in Task 4.

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/eligibility.py .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py
git commit -m "refactor(oms-agent): remap batch reallocation scenarios to reopen and hand dispatch"
```

---

### Task 4: Switch analyzer from recover-based gating to reopen/hand-based gating

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`

- [ ] **Step 1: Write the failing tests for analyzer gating behavior**

Add/update tests so these conditions are explicit:

```python
assert order.reason == "hand_check_failed"
```

for unsupported manual-dispatch cases, and keep exception eligible when the order has unfulfilled quantity and live status is `Exception`.

For the fallback client, update the assertion to verify the analyzer no longer depends on recover check success:

```python
assert result.groups[0].scenario == "exception"
assert order.eligible is True
assert order.exception_summary == "log-for-SO-FALLBACK"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py::test_analyzer_falls_back_to_hand_endpoints_when_recover_check_unavailable -v
```

Expected: FAIL because the analyzer still treats recover endpoints as primary.

- [ ] **Step 3: Update analyzer logic to use scenario-appropriate checks**

Refactor `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py` with these rules:

```python
scenario = classify_order_scenario(order)
item_lines = order.get("items") or order.get("orderItems") or order.get("itemLines") or []
hand_items = None
hand_allowed = False

if scenario != "exception":
    hand_allowed = self.client.get_hand_check(order_no)
    hand_items = self.client.get_hand_items(order_no) if hand_allowed else None
elif not item_lines:
    hand_allowed = self.client.get_hand_check(order_no)
    hand_items = self.client.get_hand_items(order_no) if hand_allowed else None
```

Use fallback `hand_items["itemVOList"]` to build SKU candidates when available:

```python
if hand_items and hand_items.get("itemVOList"):
    item_lines = [
        {
            "sku": item.get("sku"),
            "quantity": item.get("totalQty") or 0,
            "fulfilledQty": (item.get("totalQty") or 0) - (item.get("remaining") or 0),
            "hold": 0,
            "uom": item.get("uom") or "EA",
        }
        for item in hand_items.get("itemVOList") or []
    ]
```

Set order eligibility like this:

```python
has_eligible_skus = any(sku.eligible for sku in sku_candidates)
if scenario == "exception":
    eligible = has_eligible_skus
    reason = None if eligible else "unfulfilled_qty_zero"
elif scenario in {"imported", "deallocated", "on_hold"}:
    eligible = hand_allowed and has_eligible_skus
    reason = None if eligible else ("hand_check_failed" if not hand_allowed else "unfulfilled_qty_zero")
else:
    eligible = False
    reason = "unsupported_status"
```

Derive `selection_mode` from the chosen action mode:

```python
selection_mode = "sku" if action_mode in {"hand_sku_dispatch", "release_hold_then_hand_sku_dispatch"} else "order"
```

- [ ] **Step 4: Run analyzer tests to verify they pass**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/analyzer.py .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py
git commit -m "feat(oms-agent): analyze batch reallocation with reopen and hand dispatch rules"
```

---

### Task 5: Route executor actions to reopen and hand dispatch

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`

- [ ] **Step 1: Write the failing executor tests for each live action**

Update the fake client and add these tests in `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`:

```python
def test_executor_uses_reopen_for_exception_orders():
    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="EXCEPTION", action_mode="reopen_order")],
        )
    )

    assert result.succeeded_orders == ["EXCEPTION"]
    assert client.calls == [("reopen_order", "EXCEPTION")]
```

```python
def test_executor_uses_hand_dispatch_for_selected_skus():
    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="PARTIAL", action_mode="hand_sku_dispatch", selected_skus=["SKU-A"])],
        )
    )

    assert result.succeeded_orders == ["PARTIAL"]
    assert client.calls[0][0] == "hand_dispatch"
```

```python
def test_executor_releases_hold_before_hand_dispatch():
    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="ONHOLD", action_mode="release_hold_then_hand_whole_dispatch")],
        )
    )

    assert result.succeeded_orders == ["ONHOLD"]
    assert client.calls[0] == ("release_hold", "ONHOLD")
    assert client.calls[1][0] == "hand_dispatch"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py -v
```

Expected: FAIL because executor still uses recover routes.

- [ ] **Step 3: Implement explicit executor routing**

Refactor `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py` to:

1. Remove recover-based prechecks.
2. Recompute live action mode with `choose_action_mode(scenario=scenario, skus=skus)`.
3. Build a hand-dispatch payload when needed.

Use this helper inside the file:

```python
def _build_hand_payload(order_no: str, skus: list, selected_skus: list[str], dispatch_type: str) -> dict:
    selected = [sku for sku in skus if sku.sku in set(selected_skus)] if selected_skus else [sku for sku in skus if sku.eligible]
    return {
        "orderNo": order_no,
        "dispatchType": dispatch_type,
        "warehouseDTOList": [],
        "itemDTOList": [
            {"sku": sku.sku, "qty": sku.unfulfilled_qty, "uom": "EA"}
            for sku in selected
        ],
        "remark": "",
    }
```

Route actions like this:

```python
if decision.action_mode == "reopen_order":
    self.client.reopen_order(decision.order_no)
elif decision.action_mode == "hand_whole_dispatch":
    self.client.hand_dispatch(_build_hand_payload(decision.order_no, skus, [], "HAND_WHOLE_DISPATCH"))
elif decision.action_mode == "hand_sku_dispatch":
    self.client.hand_dispatch(_build_hand_payload(decision.order_no, skus, selected_eligible_skus, "HAND_SKU_DISPATCH"))
elif decision.action_mode == "release_hold_then_hand_whole_dispatch":
    self.client.release_hold(decision.order_no)
    self.client.hand_dispatch(_build_hand_payload(decision.order_no, skus, [], "HAND_WHOLE_DISPATCH"))
else:
    self.client.release_hold(decision.order_no)
    self.client.hand_dispatch(_build_hand_payload(decision.order_no, skus, selected_eligible_skus, "HAND_SKU_DISPATCH"))
```

Keep stale-state and selected-SKU guards.

- [ ] **Step 4: Run executor tests to verify they pass**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/executor.py .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py
git commit -m "feat(oms-agent): execute batch reallocation with reopen and hand dispatch"
```

---

### Task 6: Update MCP wrapper compatibility tests

**Files:**
- Modify: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Write the failing MCP tests using the new action names**

Update the execute request fixture in `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`:

```python
result = json.loads(module.batch_reallocation_execute(
    '{"confirmed":true,"decisions":[{"order_no":"SO1","action_mode":"reopen_order"}]}'
))
```

Keep the confirmation failure test, but update its payload too:

```python
module.batch_reallocation_execute('{"decisions":[{"order_no":"SO1","action_mode":"reopen_order"}]}')
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v
```

Expected: FAIL before model and executor changes are in place.

- [ ] **Step 3: Make any small MCP-facing adjustments needed**

If the wrapper assumes old action names anywhere, update it so it only passes through the new names. The key line should remain:

```python
request = ExecuteRequest(**payload)
```

No additional mapping layer should be introduced.

- [ ] **Step 4: Run MCP tests to verify they pass**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py .kiro/skills/oms-agent/mcp_server.py
git commit -m "test(oms-agent): align batch reallocation MCP inputs with explicit actions"
```

---

### Task 7: Update skill docs and API mapping

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/SKILL.md`
- Modify: `.kiro/skills/oms-agent/batch-reallocation/AGENT_PROMPT.md`
- Modify: `.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md`

- [ ] **Step 1: Write the failing doc assertions as a review checklist**

Before editing, verify these statements are absent or wrong in the docs:

```text
- Exception should use reopen, not recover.
- Imported / Deallocated / On Hold manual allocation should use hand-check + hand-item + hand-dispatch.
- Recover endpoints are not part of the active execution flow for this skill.
```

- [ ] **Step 2: Review docs to verify they need changes**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in [
    Path('.kiro/skills/oms-agent/batch-reallocation/SKILL.md'),
    Path('.kiro/skills/oms-agent/batch-reallocation/AGENT_PROMPT.md'),
    Path('.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md'),
]:
    text = path.read_text(encoding='utf-8')
    print(path, 'reopen' in text, 'dispatch/hand' in text)
PY
```

Expected: output shows the current docs are incomplete or misleading.

- [ ] **Step 3: Update the docs with the corrected mapping**

Apply these content changes:

In `SKILL.md`, replace the scenario rules with:

```md
- `Exception`: reopen the order with `/app-api/sale-order/reopen/{orderNo}`
- `Imported`: use manual dispatch APIs
- `Deallocated`: use manual dispatch APIs, preferring SKU-level selection when only part of the order remains unfulfilled
- `On Hold`: release hold first, then use manual dispatch APIs
- Recover endpoints are not part of this skill's active execution flow
```

In `AGENT_PROMPT.md`, replace the execution rules section with:

```md
For exception orders, execute reopen.
For imported, deallocated, and on-hold orders, execute hand dispatch.
For on-hold orders, release hold first, then hand dispatch.
Do not use recover endpoints as the primary execution path in this skill.
```

In `references/api-mapping.md`, replace the execution phase with:

```md
### 6. Reopen exception order
- `POST /app-api/sale-order/reopen/{orderNo}`

### 7. Release hold
- `POST /app-api/order-hold/release`

### 8. Hand dispatch check
- `GET /app-api/dispatch/hand/check/{orderNo}`

### 9. Hand dispatch item query
- `GET /app-api/dispatch/hand/item/{orderNo}`

### 10. Hand dispatch
- `POST /app-api/dispatch/hand`
```

- [ ] **Step 4: Run the review script to verify the docs reflect the new mapping**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('.kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md').read_text(encoding='utf-8')
assert '/app-api/sale-order/reopen/{orderNo}' in text
assert '/app-api/dispatch/hand' in text
assert 'recover whole order' not in text.lower()
print('doc mapping verified')
PY
```

Expected: `doc mapping verified`

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/SKILL.md .kiro/skills/oms-agent/batch-reallocation/AGENT_PROMPT.md .kiro/skills/oms-agent/batch-reallocation/references/api-mapping.md
git commit -m "docs(oms-agent): correct batch reallocation API mapping"
```

---

### Task 8: Run the full targeted test suite

**Files:**
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Run the full batch-reallocation test suite**

Run:

```bash
pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_analyzer.py .kiro/skills/oms-agent/tests/test_batch_reallocation_executor.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v
```

Expected: PASS.

- [ ] **Step 2: Run one real dry analysis against a known exception order**

Run:

```bash
python - <<'PY'
import json, requests, sys
sys.path.insert(0, r'C:/Users/Jayne/Desktop/Skills/.kiro/skills/oms-agent/batch-reallocation/scripts')
from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.api_client import BatchReallocationAPIClient
from batch_reallocation.analyzer import BatchReallocationAnalyzer
from batch_reallocation.form_builder import build_form_payload

base='https://omsv2-staging.item.com/api/linker-oms/opc'
login=requests.post(f'{base}/iam/token', json={'grantType':'password','username':'lantester@item.com','password':'LANLT'}, timeout=30)
login.raise_for_status()
token=(login.json().get('data') or {}).get('access_token') or (login.json().get('data') or {}).get('accessToken') or (login.json().get('data') or {}).get('token')
config=BatchReallocationConfig(base_url=base, tenant_id='LT', merchant_no='LAN0000002', access_token=token, user='lantester@item.com')
client=BatchReallocationAPIClient(config)
result=BatchReallocationAnalyzer(config=config, client=client).analyze(['SO01376502'], merchant_no='LAN0000002')
print(json.dumps(build_form_payload(result), ensure_ascii=False, indent=2))
PY
```

Expected: output shows the exception order as eligible for the exception scenario and the code path no longer depends on recover endpoints.

- [ ] **Step 3: Commit the finished feature**

```bash
git add .kiro/skills/oms-agent/batch-reallocation .kiro/skills/oms-agent/tests
git commit -m "fix(oms-agent): remap batch reallocation to reopen and hand dispatch"
```

---

## Self-Review

### Spec coverage
- Exception → reopen: covered in Tasks 3, 4, 5, 7, 8.
- Imported / deallocated / on-hold → hand dispatch: covered in Tasks 3, 4, 5, 7, 8.
- Release hold before on-hold execution: covered in Task 5 and Task 7.
- Recover removed from active flow: covered in Tasks 4, 5, and 7.
- Tests updated: covered in Tasks 1, 3, 4, 5, 6, 8.

### Placeholder scan
- No `TODO`, `TBD`, or vague “appropriate handling” instructions remain.
- Each code-changing step includes concrete code or assertions.

### Type consistency
- Final action names are consistently:
  - `reopen_order`
  - `hand_whole_dispatch`
  - `hand_sku_dispatch`
  - `release_hold_then_hand_whole_dispatch`
  - `release_hold_then_hand_sku_dispatch`
- These names are used consistently across models, analyzer, executor, and tests.
