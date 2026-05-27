# Product Listing Planner Execution Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `product-listing-planner` from readiness planning into a safe listing loop that analyzes existing channel products, builds a confirmation form, submits existing channel products through OMS, and verifies the real business result.

**Architecture:** Keep planning logic in `ProductListingPlannerEngine`, and add a small execution adapter interface so tests can use fakes while real callers can provide an OMS client-backed adapter. First release supports existing channel products via `POST /rpc-api/channel-product/submit`; new channel creation via `create-from-spu` remains a later phase. Execution is gated by explicit confirmation and always followed by live verification using channel product detail and publish history.

**Tech Stack:** Python 3.12, pytest, existing skill package layout under `.kiro/skills/product-listing-planner`, OMS OpenAPI contract from `docs/oms-agent/oms-v3.openapi.json`.

---

## File Structure

- Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`
  - Add `execution_adapter` dependency injection.
  - Keep `plan()` for analysis/form generation.
  - Add `execute()` for confirmed execution + verification.
  - Add small private helpers for channel lookup, form payload, final conclusion, and verification diff.

- Create `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/execution.py`
  - Define `OmsListingExecutionAdapter` that wraps an injected OMS API client.
  - Methods: `get_channel_product()`, `list_publish_history_by_channel_product()`, `submit_channel_product()`.
  - Use endpoints from `docs/oms-agent/oms-v3.openapi.json`:
    - `GET /api/linker-oms/baseservice/rpc-api/channel-product/get/{id}`
    - `GET /api/linker-oms/baseservice/rpc-api/publish-history/list/by-channel-product/{channelProductId}`
    - `POST /api/linker-oms/baseservice/rpc-api/channel-product/submit`

- Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/__init__.py`
  - Export `ProductListingPlannerEngine` and `OmsListingExecutionAdapter`.

- Modify `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`
  - Add tests for confirmation form and execution loop.
  - Use fake adapters only; do not call live OMS in unit tests.

- Modify `.kiro/skills/product-listing-planner/SKILL.md`
  - Update capability from pure planner to safe listing loop.
  - Document required confirmation and final conclusion vocabulary.

- Modify `.kiro/skills/product-listing-planner/CAPABILITY_STATUS.md`
  - Record new first-phase execution scope and boundaries.

---

### Task 1: Add a confirmation form for existing channel product submit

**Files:**
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Write the failing test**

Add this test to `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`:

```python
def test_listing_planner_returns_confirmation_form_for_existing_channel_product_submit():
    product_query_result = {
        "details": {
            "product": {
                "title": "Ready Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_products": [
                {
                    "channel_product_id": "CP-READY-1",
                    "channel_code": "SHOPIFY",
                    "listing_status": "DRAFT",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Previous publish failed",
                }
            ],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": ["Previous publish failed"],
                }
            ],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="listing_execution_plan",
        filters={"target_channels": ["SHOPIFY"], "action": "submit_existing_channel_product"},
        context={"product_query_result": product_query_result},
    )

    assert result["success"] is True
    assert result["details"]["execution_form"] == {
        "requires_confirmation": True,
        "next_action": "collect_user_decision",
        "action": "submit_existing_channel_product",
        "merchant_no": "LAN0000002",
        "identifier": "READY-SKU",
        "targets": [
            {
                "channel_product_id": "CP-READY-1",
                "channel_code": "SHOPIFY",
                "current_listing_status": "DRAFT",
                "current_audit_status": "DRAFT",
                "allowed": True,
                "warnings": ["Previous publish failed"],
            }
        ],
    }
    assert result["details"]["execution_allowed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_listing_planner_returns_confirmation_form_for_existing_channel_product_submit" -v
```

Expected: FAIL because `execution_form` and `execution_allowed` do not exist.

- [ ] **Step 3: Implement minimal form generation**

In `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`, add these helpers above `ProductListingPlannerEngine`:

```python
def _errors_for_channel(channel_summary: list[dict], channel_code: str | None) -> list[str]:
    for item in channel_summary:
        if item.get("channel_code") == channel_code:
            return item.get("errors") or []
    return []


def _build_execution_form(identifier, merchant_no, filters: dict, details: dict) -> dict:
    action = filters.get("action") or "submit_existing_channel_product"
    target_channels = filters.get("target_channels") or []
    channel_summary = details.get("channel_summary") or []
    channel_products = details.get("channel_products") or []
    targets = []

    for channel_product in channel_products:
        channel_code = channel_product.get("channel_code")
        if target_channels and channel_code not in target_channels:
            continue
        channel_product_id = channel_product.get("channel_product_id")
        warnings = []
        if channel_product.get("last_error"):
            warnings.append(channel_product["last_error"])
        warnings.extend(error for error in _errors_for_channel(channel_summary, channel_code) if error not in warnings)
        targets.append({
            "channel_product_id": channel_product_id,
            "channel_code": channel_code,
            "current_listing_status": channel_product.get("listing_status"),
            "current_audit_status": channel_product.get("audit_status"),
            "allowed": bool(channel_product_id),
            "warnings": warnings,
        })

    return {
        "requires_confirmation": True,
        "next_action": "collect_user_decision",
        "action": action,
        "merchant_no": merchant_no,
        "identifier": identifier,
        "targets": targets,
    }
```

Then inside `plan()`, after `details = product_query_result.get("details") or {}`, keep using `details` for the rest of the method and add this before the final return:

```python
        execution_form = _build_execution_form(identifier, merchant_no, filters, details)
        execution_allowed = any(target.get("allowed") for target in execution_form["targets"])
```

Add these keys inside the final return `details` object:

```python
                "execution_form": execution_form,
                "execution_allowed": execution_allowed,
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_listing_planner_returns_confirmation_form_for_existing_channel_product_submit" -v
```

Expected: PASS.

---

### Task 2: Add execution adapter for OMS submit and verification reads

**Files:**
- Create: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/execution.py`
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/__init__.py`
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Write the failing adapter test**

Add this test to `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`:

```python
def test_oms_listing_execution_adapter_calls_submit_and_verification_endpoints():
    from product_listing_planner_engine.execution import OmsListingExecutionAdapter

    class FakeClient:
        def __init__(self):
            self.calls = []

        def _ensure_token(self):
            self.calls.append(("ensure_token", None, None))

        def get(self, path, params=None):
            self.calls.append(("get", path, params))
            return {"code": 200, "data": {"id": "CP-1"}}

        def post(self, path, payload):
            self.calls.append(("post", path, payload))
            return {"code": 200, "data": True}

    client = FakeClient()
    adapter = OmsListingExecutionAdapter(client)

    assert adapter.get_channel_product("CP-1") == {"code": 200, "data": {"id": "CP-1"}}
    assert adapter.list_publish_history_by_channel_product("CP-1") == {"code": 200, "data": {"id": "CP-1"}}
    assert adapter.submit_channel_product({"id": "CP-1"}) == {"code": 200, "data": True}
    assert client.calls == [
        ("ensure_token", None, None),
        ("get", "/api/linker-oms/baseservice/rpc-api/channel-product/get/CP-1", None),
        ("ensure_token", None, None),
        ("get", "/api/linker-oms/baseservice/rpc-api/publish-history/list/by-channel-product/CP-1", None),
        ("ensure_token", None, None),
        ("post", "/api/linker-oms/baseservice/rpc-api/channel-product/submit", {"id": "CP-1"}),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_oms_listing_execution_adapter_calls_submit_and_verification_endpoints" -v
```

Expected: FAIL because `product_listing_planner_engine.execution` does not exist.

- [ ] **Step 3: Create adapter implementation**

Create `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/execution.py`:

```python
from __future__ import annotations


class OmsListingExecutionAdapter:
    def __init__(self, client):
        self._client = client

    def get_channel_product(self, channel_product_id: str) -> dict:
        self._client._ensure_token()
        return self._client.get(
            f"/api/linker-oms/baseservice/rpc-api/channel-product/get/{channel_product_id}"
        )

    def list_publish_history_by_channel_product(self, channel_product_id: str) -> dict:
        self._client._ensure_token()
        return self._client.get(
            f"/api/linker-oms/baseservice/rpc-api/publish-history/list/by-channel-product/{channel_product_id}"
        )

    def submit_channel_product(self, payload: dict) -> dict:
        self._client._ensure_token()
        return self._client.post(
            "/api/linker-oms/baseservice/rpc-api/channel-product/submit",
            payload,
        )
```

Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/__init__.py`:

```python
from product_listing_planner_engine.engine import ProductListingPlannerEngine
from product_listing_planner_engine.execution import OmsListingExecutionAdapter

__all__ = ["ProductListingPlannerEngine", "OmsListingExecutionAdapter"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_oms_listing_execution_adapter_calls_submit_and_verification_endpoints" -v
```

Expected: PASS.

---

### Task 3: Add confirmed execution loop for existing channel product submit

**Files:**
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Write failing execution test**

Add this test to `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`:

```python
def test_execute_requires_confirmation_before_submit():
    class FakeAdapter:
        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called without confirmation")

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": False,
            "action": "submit_existing_channel_product",
            "targets": [{"channel_product_id": "CP-1", "channel_code": "SHOPIFY"}],
        }
    )

    assert result == {
        "success": False,
        "summary": "缺少用户确认，未执行发布提交。",
        "final_conclusion": "Execution failed",
        "errors": ["confirmation_required"],
    }


def test_execute_submits_channel_product_and_verifies_successful_business_result():
    class FakeAdapter:
        def __init__(self):
            self.submitted_payloads = []

        def get_channel_product(self, channel_product_id):
            return {"code": 200, "data": {"id": channel_product_id, "publishStatus": "PUBLISHING"}}

        def list_publish_history_by_channel_product(self, channel_product_id):
            return {"code": 200, "data": [{"id": "PH-2", "status": "PUBLISHING"}]}

        def submit_channel_product(self, payload):
            self.submitted_payloads.append(payload)
            return {"code": 200, "data": True}

    adapter = FakeAdapter()
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={
            "confirmed": True,
            "action": "submit_existing_channel_product",
            "merchant_no": "LAN0000002",
            "targets": [{"channel_product_id": "CP-1", "channel_code": "SHOPIFY"}],
        }
    )

    assert adapter.submitted_payloads == [{"id": "CP-1", "channelProductId": "CP-1"}]
    assert result["success"] is True
    assert result["final_conclusion"] == "Executed successfully"
    assert result["details"]["executions"][0]["endpoint"] == "/rpc-api/channel-product/submit"
    assert result["details"]["executions"][0]["raw_response"] == {"code": 200, "data": True}
    assert result["details"]["verification"][0]["business_result_changed"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_requires_confirmation_before_submit" ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_submits_channel_product_and_verifies_successful_business_result" -v
```

Expected: FAIL because `ProductListingPlannerEngine.__init__` does not accept `execution_adapter` and `execute()` does not exist.

- [ ] **Step 3: Implement execution loop**

Modify `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py`.

Change class start to:

```python
class ProductListingPlannerEngine:
    def __init__(self, execution_adapter=None):
        self._execution_adapter = execution_adapter
```

Add these methods inside the class:

```python
    def execute(self, request=None):
        request = request or {}
        if not request.get("confirmed"):
            return {
                "success": False,
                "summary": "缺少用户确认，未执行发布提交。",
                "final_conclusion": "Execution failed",
                "errors": ["confirmation_required"],
            }
        if request.get("action") != "submit_existing_channel_product":
            return {
                "success": False,
                "summary": "当前仅支持已有渠道商品提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["unsupported_action"],
            }
        if not self._execution_adapter:
            return {
                "success": False,
                "summary": "缺少 OMS 执行适配器，无法提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["missing_execution_adapter"],
            }

        executions = []
        verification = []
        api_failed = False
        changed = False

        for target in request.get("targets") or []:
            channel_product_id = target.get("channel_product_id")
            if not channel_product_id:
                api_failed = True
                executions.append({
                    "channel_product_id": None,
                    "endpoint": "/rpc-api/channel-product/submit",
                    "request_payload": {},
                    "raw_response": None,
                    "error": "missing_channel_product_id",
                })
                continue

            before_product = self._execution_adapter.get_channel_product(channel_product_id)
            before_history = self._execution_adapter.list_publish_history_by_channel_product(channel_product_id)
            payload = {"id": channel_product_id, "channelProductId": channel_product_id}
            raw_response = self._execution_adapter.submit_channel_product(payload)
            after_product = self._execution_adapter.get_channel_product(channel_product_id)
            after_history = self._execution_adapter.list_publish_history_by_channel_product(channel_product_id)
            response_code = raw_response.get("code") if isinstance(raw_response, dict) else None
            response_success = response_code in (None, 0, 200, "0", "200")
            if not response_success:
                api_failed = True

            business_result_changed = self._business_result_changed(before_product, after_product, before_history, after_history)
            changed = changed or business_result_changed
            executions.append({
                "channel_product_id": channel_product_id,
                "endpoint": "/rpc-api/channel-product/submit",
                "request_payload": payload,
                "raw_response": raw_response,
            })
            verification.append({
                "channel_product_id": channel_product_id,
                "before_channel_product": before_product,
                "after_channel_product": after_product,
                "before_publish_history": before_history,
                "after_publish_history": after_history,
                "business_result_changed": business_result_changed,
            })

        final_conclusion = self._final_conclusion(api_failed, changed)
        return {
            "success": final_conclusion != "Execution failed",
            "summary": self._execution_summary(final_conclusion),
            "final_conclusion": final_conclusion,
            "details": {"executions": executions, "verification": verification},
            "errors": [] if final_conclusion != "Execution failed" else ["submit_failed"],
        }

    @staticmethod
    def _business_result_changed(before_product, after_product, before_history, after_history):
        return before_product != after_product or before_history != after_history

    @staticmethod
    def _final_conclusion(api_failed, changed):
        if api_failed:
            return "Execution failed"
        if changed:
            return "Executed successfully"
        return "Submitted successfully but business result did not take effect"

    @staticmethod
    def _execution_summary(final_conclusion):
        if final_conclusion == "Executed successfully":
            return "发布提交已执行，回查显示业务状态或发布历史发生变化。"
        if final_conclusion == "Submitted successfully but business result did not take effect":
            return "接口已接受发布提交，但回查未发现渠道商品或发布历史变化。"
        return "发布提交失败。"
```

- [ ] **Step 4: Run execution tests**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_requires_confirmation_before_submit" ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_submits_channel_product_and_verifies_successful_business_result" -v
```

Expected: PASS.

---

### Task 4: Add no-business-effect verification path

**Files:**
- Modify: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`
- Modify: `.kiro/skills/product-listing-planner/scripts/product_listing_planner_engine/engine.py` only if needed

- [ ] **Step 1: Write failing or confirming test**

Add this test:

```python
def test_execute_reports_submitted_but_not_effective_when_state_does_not_change():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            return {"code": 200, "data": {"id": channel_product_id, "publishStatus": "DRAFT"}}

        def list_publish_history_by_channel_product(self, channel_product_id):
            return {"code": 200, "data": [{"id": "PH-1", "status": "PUBLISH_FAILED"}]}

        def submit_channel_product(self, payload):
            return {"code": 200, "data": True}

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            "action": "submit_existing_channel_product",
            "targets": [{"channel_product_id": "CP-1", "channel_code": "SHOPIFY"}],
        }
    )

    assert result["success"] is True
    assert result["final_conclusion"] == "Submitted successfully but business result did not take effect"
    assert result["details"]["verification"][0]["business_result_changed"] is False
```

- [ ] **Step 2: Run test**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py::test_execute_reports_submitted_but_not_effective_when_state_does_not_change" -v
```

Expected: PASS if Task 3 implementation is correct. If it fails, adjust only `_business_result_changed()` or `_final_conclusion()` to match the three allowed conclusions.

---

### Task 5: Update skill documentation and capability status

**Files:**
- Modify: `.kiro/skills/product-listing-planner/SKILL.md`
- Modify: `.kiro/skills/product-listing-planner/CAPABILITY_STATUS.md`

- [ ] **Step 1: Update SKILL.md behavior contract**

In `.kiro/skills/product-listing-planner/SKILL.md`, update the core principles section so execution is no longer described as impossible. Replace the old “规划不等于执行” text with:

```markdown
3. **规划与执行分阶段**

默认先输出刊登规划和结构化确认表单。只有用户明确确认后，才允许执行发布类动作。执行后必须重新查询 OMS live 状态，不能只根据接口 success 判断业务完成。
```

Add this section after the output structure section:

```markdown
## 执行闭环规则

第一阶段支持已有渠道商品提交发布：

- 执行接口：`POST /rpc-api/channel-product/submit`
- 执行前必须具备 `channel_product_id`
- 执行前必须有 `requires_confirmation = true` 的表单结果
- 执行请求必须包含用户确认后的 `confirmed = true`
- 执行后必须重新查询渠道商品详情和发布历史

最终结论只能使用以下三种：

- `Executed successfully`
- `Submitted successfully but business result did not take effect`
- `Execution failed`
```

- [ ] **Step 2: Update CAPABILITY_STATUS.md**

Add this under current implemented capabilities:

```markdown
### Confirmed submit execution loop

The skill now supports first-phase execution for existing channel products:

1. Build a confirmation form from `product_query_result.details.channel_products`.
2. Require explicit user confirmation before execution.
3. Submit existing channel products through `POST /rpc-api/channel-product/submit`.
4. Re-read channel product detail and publish history.
5. Return one of three final conclusions: `Executed successfully`, `Submitted successfully but business result did not take effect`, or `Execution failed`.

Current execution boundary: it does not create new channel products yet. New channel creation should use `POST /rpc-api/channel-product/create-from-spu` in a later phase.
```

- [ ] **Step 3: Run documentation grep sanity check**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all product listing planner tests PASS.

---

### Task 6: Final verification

**Files:**
- Test: `.kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py`

- [ ] **Step 1: Run focused test suite**

Run:

```bash
python -m pytest ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run related product skill tests**

Run:

```bash
python -m pytest ".kiro/skills/product-query/tests/test_product_query_engine.py" ".kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py" ".kiro/skills/product-listing-planner/tests/test_product_listing_planner_engine.py" -v
```

Expected: all tests PASS.

- [ ] **Step 3: Review git diff**

Run:

```bash
git diff -- .kiro/skills/product-listing-planner docs/superpowers/plans/2026-05-26-product-listing-planner-execution-loop.md
```

Expected: diff only includes the planner engine, adapter, tests, docs, and this plan.

---

## Self-Review

- Spec coverage: The plan covers analysis form generation, explicit confirmation, `channel-product/submit`, post-submit verification, and the three final conclusions. New channel creation is intentionally excluded from this first implementation phase and documented as later work.
- Placeholder scan: No `TBD`, `TODO`, vague “handle edge cases”, or undefined implementation steps remain.
- Type consistency: The plan uses `ProductListingPlannerEngine(execution_adapter=...)`, `plan()`, `execute()`, `OmsListingExecutionAdapter`, `channel_product_id`, and the three final conclusion strings consistently across tests and implementation.
