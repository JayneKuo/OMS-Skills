# Batch Reallocation User View Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-facing view builder for `batch-reallocation` so agents can render business-safe confirmation and execution summaries without exposing internal JSON payloads.

**Architecture:** Keep the existing internal JSON protocol (`form_builder.py`, `result_formatter.py`, MCP JSON returns) unchanged. Add a new `user_view_builder.py` that converts `AnalyzeResponse` and `ExecuteResponse` into sanitized view models, then document and test that these view models exclude internal protocol fields while preserving the business facts agents need for the 5-section output.

**Tech Stack:** Python 3.12, Pydantic models already used in `batch_reallocation.models`, pytest.

---

## File Structure

### New files
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/user_view_builder.py` — builds sanitized user-facing analysis, confirmation, and execution view models from existing response objects.
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py` — TDD coverage for visible business fields and hidden technical fields.

### Modified files
- `docs/superpowers/specs/2026-05-26-batch-reallocation-user-view-builder-design.md` — already written spec; no content changes expected during implementation.
- `.kiro/skills/oms-agent/batch-reallocation/SKILL.md` — optional final wording adjustment only if implementation names require it; do not change unless tests or code shape force it.
- `.kiro/skills/oms-agent/batch-reallocation/AGENT_PROMPT.md` — optional final wording adjustment only if implementation names require it; do not change unless tests or code shape force it.

### Existing files to read before coding
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py` — source of `AnalyzeResponse`, `FormGroup`, `OrderCandidate`, `SkuCandidate`, `ExecuteResponse`.
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/form_builder.py` — internal analysis payload builder that must remain unchanged.
- `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/result_formatter.py` — internal execution result formatter that must remain unchanged.
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py` — confirms existing internal payload contract.
- `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py` — confirms MCP JSON contract must remain intact.

---

### Task 1: Add failing tests for sanitized analysis and execution views

**Files:**
- Create: `.kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py`
- Read: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/models.py`

- [ ] **Step 1: Write the failing test for analysis view business fields**

```python
from batch_reallocation.models import AnalyzeResponse, FormGroup, OrderCandidate, SkuCandidate
from batch_reallocation.user_view_builder import build_analysis_view


def test_build_analysis_view_returns_business_safe_order_summary():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="on_hold",
                title="On Hold orders",
                selection_mode="sku",
                orders=[
                    OrderCandidate(
                        order_no="SO1001",
                        scenario="on_hold",
                        status="On Hold",
                        eligible=True,
                        reason="requires_hold_release",
                        hold_reason="risk-review",
                        skus=[
                            SkuCandidate(
                                sku="SKU-A",
                                ordered_qty=3,
                                fulfilled_qty=1,
                                unfulfilled_qty=2,
                                hold_qty=2,
                                eligible=True,
                                reason="eligible",
                            ),
                            SkuCandidate(
                                sku="SKU-B",
                                ordered_qty=1,
                                fulfilled_qty=1,
                                unfulfilled_qty=0,
                                hold_qty=0,
                                eligible=False,
                                reason="unfulfilled_qty_zero",
                            ),
                        ],
                    )
                ],
            )
        ],
        warnings=["状态可能变化，执行前会再次校验"],
    )

    view = build_analysis_view(response)

    assert view["requires_confirmation"] is True
    assert view["global_warnings"] == ["状态可能变化，执行前会再次校验"]
    assert len(view["orders"]) == 1
    assert view["orders"][0]["order_no"] == "SO1001"
    assert view["orders"][0]["current_status"] == "On Hold"
    assert view["orders"][0]["scenario_group"] == "on_hold"
    assert view["orders"][0]["exception_or_hold_summary"] == "risk-review"
    assert view["orders"][0]["eligibility"]["supported"] is True
    assert view["orders"][0]["eligibility"]["action_mode"] == "sku"
    assert view["orders"][0]["eligibility"]["executable_scope_summary"] == "可执行 1 个 SKU"
    assert view["orders"][0]["eligibility"]["ineligible_scope_summary"] == "不可执行 1 个 SKU"
    assert view["orders"][0]["sku_facts"] == [
        {"sku": "SKU-A", "ordered_qty": 3, "fulfilled_qty": 1, "unfulfilled_qty": 2},
        {"sku": "SKU-B", "ordered_qty": 1, "fulfilled_qty": 1, "unfulfilled_qty": 0},
    ]
```

- [ ] **Step 2: Write the failing test for hidden technical fields**

```python
from batch_reallocation.models import AnalyzeResponse
from batch_reallocation.user_view_builder import build_analysis_view


def test_build_analysis_view_hides_internal_protocol_fields():
    view = build_analysis_view(AnalyzeResponse())

    serialized = str(view)
    assert "form_type" not in view
    assert "next_action" not in view
    assert "payload" not in serialized
    assert "endpoint" not in serialized
    assert "raw_response" not in serialized
    assert "MCP" not in serialized
```

- [ ] **Step 3: Write the failing test for confirmation view**

```python
from batch_reallocation.models import AnalyzeResponse, FormGroup, OrderCandidate, SkuCandidate
from batch_reallocation.user_view_builder import build_confirmation_view


def test_build_confirmation_view_marks_editable_choices_and_waiting_status():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="deallocated",
                title="Deallocated orders",
                selection_mode="sku",
                orders=[
                    OrderCandidate(
                        order_no="SO2001",
                        scenario="deallocated",
                        status="Deallocated",
                        eligible=True,
                        skus=[
                            SkuCandidate(sku="SKU-X", ordered_qty=2, fulfilled_qty=0, unfulfilled_qty=2, eligible=True),
                            SkuCandidate(sku="SKU-Y", ordered_qty=1, fulfilled_qty=1, unfulfilled_qty=0, eligible=False, reason="unfulfilled_qty_zero"),
                        ],
                    )
                ],
            )
        ],
        warnings=["部分 SKU 已履约，必须按 SKU 选择"],
    )

    decisions = {
        "decisions": [
            {
                "order_no": "SO2001",
                "action_mode": "partial_sku",
                "selected_skus": ["SKU-X"],
                "release_hold": False,
            }
        ]
    }

    view = build_confirmation_view(response, decisions)

    assert view["status"] == "waiting_for_confirmation"
    assert view["order_nos"] == ["SO2001"]
    assert view["scenario_groups"] == ["deallocated"]
    assert view["action_mode_summary"] == "partial_sku"
    assert view["includes_release_hold"] is False
    assert view["selected_skus_by_order"] == [{"order_no": "SO2001", "selected_skus": ["SKU-X"]}]
    assert "selected_skus" in view["editable_choices"]
    assert "order status: Deallocated" in view["readonly_facts"]
    assert view["risks"] == ["部分 SKU 已履约，必须按 SKU 选择"]
```

- [ ] **Step 4: Write the failing test for execution view**

```python
from batch_reallocation.models import ExecuteResponse
from batch_reallocation.user_view_builder import build_execution_view


def test_build_execution_view_returns_business_summary_without_transport_details():
    response = ExecuteResponse(
        submitted_orders=3,
        succeeded_orders=["SO1"],
        partial_succeeded_orders=["SO2"],
        failed_orders={"SO3": "order no longer recoverable"},
        skipped_orders={"SO4": "status changed before execution"},
        warnings=["SO2 仅部分 SKU 提交成功"],
    )

    view = build_execution_view(response)

    assert view["executed"] is True
    assert view["submitted_orders"] == ["SO1", "SO2", "SO3"]
    assert view["succeeded_orders"] == ["SO1"]
    assert view["partial_succeeded_orders"] == ["SO2"]
    assert view["failed_orders"] == [{"order_no": "SO3", "reason": "order no longer recoverable"}]
    assert view["skipped_orders"] == [{"order_no": "SO4", "reason": "status changed before execution"}]
    assert view["warnings"] == ["SO2 仅部分 SKU 提交成功"]
    assert "endpoint" not in str(view)
    assert "payload" not in str(view)
    assert "raw_response" not in str(view)
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'batch_reallocation.user_view_builder'`

- [ ] **Step 6: Commit**

```bash
git add .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py
git commit -m "test(oms-agent): add failing tests for batch reallocation user views"
```

---

### Task 2: Implement the minimal user view builder to satisfy analysis and execution tests

**Files:**
- Create: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/user_view_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py`

- [ ] **Step 1: Write the minimal analysis/confirmation/execution builder implementation**

```python
from __future__ import annotations

from batch_reallocation.models import AnalyzeResponse, ExecuteResponse


def _sku_facts(order) -> list[dict]:
    return [
        {
            "sku": sku.sku,
            "ordered_qty": sku.ordered_qty,
            "fulfilled_qty": sku.fulfilled_qty,
            "unfulfilled_qty": sku.unfulfilled_qty,
        }
        for sku in order.skus
    ]


def _eligible_count(order) -> int:
    return sum(1 for sku in order.skus if sku.eligible)


def _ineligible_count(order) -> int:
    return sum(1 for sku in order.skus if not sku.eligible)


def build_analysis_view(result: AnalyzeResponse) -> dict:
    orders: list[dict] = []
    for group in result.groups:
        for order in group.orders:
            orders.append(
                {
                    "order_no": order.order_no,
                    "current_status": order.status,
                    "scenario_group": group.scenario,
                    "exception_or_hold_summary": order.hold_reason or order.exception_summary,
                    "sku_facts": _sku_facts(order),
                    "eligibility": {
                        "supported": order.eligible and group.scenario != "ineligible",
                        "action_mode": group.selection_mode,
                        "executable_scope_summary": f"可执行 {_eligible_count(order)} 个 SKU",
                        "ineligible_scope_summary": f"不可执行 {_ineligible_count(order)} 个 SKU",
                        "reasons": [order.reason] if order.reason else [],
                        "risks": [warning for warning in result.warnings],
                    },
                }
            )
    return {
        "orders": orders,
        "global_warnings": list(result.warnings),
        "requires_confirmation": result.requires_confirmation,
    }


def build_confirmation_view(result: AnalyzeResponse, decisions: dict | None = None) -> dict:
    decisions = decisions or {"decisions": []}
    order_map = {
        order.order_no: order
        for group in result.groups
        for order in group.orders
    }
    selected_skus_by_order = [
        {
            "order_no": item["order_no"],
            "selected_skus": list(item.get("selected_skus") or []),
        }
        for item in decisions.get("decisions", [])
    ]
    action_mode_summary = ", ".join(
        sorted({str(item.get("action_mode")) for item in decisions.get("decisions", []) if item.get("action_mode")})
    )
    order_nos = [item["order_no"] for item in decisions.get("decisions", [])]
    scenario_groups = [
        order_map[order_no].scenario
        for order_no in order_nos
        if order_no in order_map
    ]
    readonly_facts = [
        f"order status: {order_map[order_no].status}"
        for order_no in order_nos
        if order_no in order_map
    ]
    return {
        "order_nos": order_nos,
        "scenario_groups": scenario_groups,
        "action_mode_summary": action_mode_summary,
        "selected_skus_by_order": selected_skus_by_order,
        "includes_release_hold": any(bool(item.get("release_hold")) for item in decisions.get("decisions", [])),
        "editable_choices": ["action_mode", "selected_skus", "release_hold"],
        "readonly_facts": readonly_facts,
        "risks": list(result.warnings),
        "status": "waiting_for_confirmation",
    }


def build_execution_view(result: ExecuteResponse) -> dict:
    submitted_orders = list(result.succeeded_orders) + list(result.partial_succeeded_orders) + list(result.failed_orders.keys())
    return {
        "executed": result.submitted_orders > 0,
        "submitted_orders": submitted_orders,
        "succeeded_orders": list(result.succeeded_orders),
        "partial_succeeded_orders": list(result.partial_succeeded_orders),
        "failed_orders": [
            {"order_no": order_no, "reason": reason}
            for order_no, reason in result.failed_orders.items()
        ],
        "skipped_orders": [
            {"order_no": order_no, "reason": reason}
            for order_no, reason in result.skipped_orders.items()
        ],
        "warnings": list(result.warnings),
    }
```

- [ ] **Step 2: Run test to verify the new tests pass**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py -v`
Expected: PASS

- [ ] **Step 3: Read the implementation and remove any unnecessary helper or field**

Check:
- no `form_type` or `next_action` leaks into returned views
- no endpoint/payload/raw-response wording appears anywhere
- no extra abstraction beyond `_sku_facts`, `_eligible_count`, `_ineligible_count`

Expected: code stays as one focused module with three public builders

- [ ] **Step 4: Re-run the same test file after cleanup**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/user_view_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py
git commit -m "feat(oms-agent): add batch reallocation user view builder"
```

---

### Task 3: Verify the new user view layer does not break existing internal contracts

**Files:**
- Read: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/form_builder.py`
- Read: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/result_formatter.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Re-run the existing internal payload contract tests**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v`
Expected: PASS

- [ ] **Step 2: If any existing contract test fails, fix imports only — do not change internal payload shape**

Allowed changes:
```python
# Example only if needed
from batch_reallocation.user_view_builder import build_analysis_view
```

Not allowed:
```python
# Do not replace internal JSON with user-facing view model here
return build_analysis_view(result)
```

Expected: MCP tools still return internal JSON payloads exactly as before

- [ ] **Step 3: Re-run all user-view and internal-contract tests together**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/user_view_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py
git commit -m "test(oms-agent): verify batch reallocation user views preserve internal contracts"
```

---

### Task 4: Document the implementation boundary for future agent work

**Files:**
- Modify: `.kiro/skills/oms-agent/batch-reallocation/SKILL.md:51-73`
- Modify: `.kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md:6-25`
- Test: none (doc-only)

- [ ] **Step 1: Update SKILL.md output section to mention the concrete module name**

Replace the output section so it explicitly mentions `user_view_builder.py` as the source of user-facing views while keeping internal payload wording intact.

```markdown
## Outputs
### User-facing analysis output
- 中文业务摘要
- 逐单资格判断
- 确认表单视图（由 `user_view_builder.py` 生成用户视图模型后组织输出）
- `requires_confirmation = true`
- `next_action = collect_user_decision`

### Internal execution context
- `form_type = batch-reallocation-analysis`
- `groups[]`：按 `imported / exception / deallocated / on_hold / ineligible` 分组
- `selection_mode = order | sku`
- `warnings[]`
- 用于执行的结构化 payload
```

- [ ] **Step 2: Update form-protocol.md to name the new boundary explicitly**

Replace the protocol note with this exact text block under the internal sections:

```markdown
说明：
- `form_builder.py` 和 `result_formatter.py` 继续服务于内部协议与 MCP 返回。
- `user_view_builder.py` 负责把分析结果和执行结果转换为默认用户可见的业务视图模型。
- 最终用户默认不直接看到内部 JSON，agent 应优先消费用户视图模型组织业务输出。
```

- [ ] **Step 3: Review the docs for contradictions**

Check that:
- docs do not say MCP now returns user-facing view models
- docs do not say users directly receive JSON payloads by default
- docs do not introduce new module names beyond `user_view_builder.py`

Expected: docs match the implemented boundary exactly

- [ ] **Step 4: Commit**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/SKILL.md .kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md
git commit -m "docs(oms-agent): document batch reallocation user view boundary"
```

---

### Task 5: Final verification before handoff

**Files:**
- Read: `.kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/user_view_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py`
- Test: `.kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py`

- [ ] **Step 1: Run the focused verification suite**

Run: `pytest .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_form_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_mcp.py -v`
Expected: PASS

- [ ] **Step 2: Manually inspect the user view builder output contract**

Confirm these public function names exist exactly:
```python
build_analysis_view
build_confirmation_view
build_execution_view
```

Confirm these names do not appear in return payloads:
```python
form_type
next_action
payload
endpoint
raw_response
```

- [ ] **Step 3: Commit the final verified state**

```bash
git add .kiro/skills/oms-agent/batch-reallocation/scripts/batch_reallocation/user_view_builder.py .kiro/skills/oms-agent/tests/test_batch_reallocation_user_view_builder.py .kiro/skills/oms-agent/batch-reallocation/SKILL.md .kiro/skills/oms-agent/batch-reallocation/references/form-protocol.md
git commit -m "feat(oms-agent): add user-facing batch reallocation views"
```
