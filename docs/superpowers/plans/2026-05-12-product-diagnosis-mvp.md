# Product Diagnosis MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal `product_diagnosis` runtime that diagnoses product issues only from provided snapshots/errors, without API calls or fabricated facts.

**Architecture:** Create a small rule engine under `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/` and expose it through `.kiro/skills/oms-agent/mcp_server.py`. The engine consumes `context` and `filters` dictionaries, detects missing fields and failure errors, and returns the existing Product Agent JSON shape.

**Tech Stack:** Python 3.12, pytest, existing MCP server.

---

## File Structure

- Create `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/__init__.py`: package export.
- Create `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`: rule-based diagnosis.
- Create `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`: engine tests.
- Modify `.kiro/skills/oms-agent/mcp_server.py`: add script path and `product_diagnosis(...)` MCP tool.
- Modify `.kiro/skills/oms-agent/tests/test_navigation_routes.py`: MCP parsing/error tests.
- Modify `.kiro/skills/product-diagnosis/SKILL.md`: document MVP runtime boundary.
- Modify `docs/product-agent/01-落地行动方案.md`: update Phase 5 status.

---

### Task 1: Engine diagnoses missing required fields

**Files:**
- Create: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Create: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/__init__.py`
- Create: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`

- [ ] **Step 1: Write failing test**

```python
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_diagnosis_engine.engine import ProductDiagnosisEngine


def test_diagnoses_missing_required_fields_from_context():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SKU-A",
        merchant_no="M001",
        intent="missing_required_fields",
        filters={"channel_code": "amazon"},
        context={
            "product_snapshot": {"sku": "SKU-A"},
            "missing_fields": [
                {"field": "material", "scope": "channel_required_attribute", "channel_code": "amazon", "required": True}
            ],
        },
    )

    assert result["success"] is True
    assert result["summary"] == "SKU-A 缺少 1 个必填字段。"
    assert result["confidence"] == "high"
    assert result["severity"] == "major"
    assert result["metrics"] == {"missing_required_field_count": 1}
    assert result["details"]["issue_type"] == "missing_required_fields"
    assert result["details"]["requires_manual_fix"] is True
    assert result["evidences"][0]["data"]["field"] == "material"
    assert result["recommendations"][0]["action"] == "complete_required_attribute"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_diagnoses_missing_required_fields_from_context -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'product_diagnosis_engine'`.

- [ ] **Step 3: Implement minimal engine**

Create `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/__init__.py`:

```python
from product_diagnosis_engine.engine import ProductDiagnosisEngine

__all__ = ["ProductDiagnosisEngine"]
```

Create `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`:

```python
from __future__ import annotations


class ProductDiagnosisEngine:
    def diagnose(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
        filters = filters or {}
        context = context or {}
        missing_fields = context.get("missing_fields") or context.get("product_snapshot", {}).get("missing_fields") or []
        required_missing = [field for field in missing_fields if field.get("required", True)]

        if required_missing:
            return {
                "success": True,
                "summary": f"{identifier} 缺少 {len(required_missing)} 个必填字段。",
                "reason": "输入上下文包含必填字段缺失信息。",
                "evidences": [
                    {
                        "source": "missing_fields",
                        "description": f"缺少必填字段 {field.get('field')}",
                        "data": field,
                    }
                    for field in required_missing
                ],
                "confidence": "high",
                "data_completeness": "partial",
                "severity": "major",
                "recommendations": [
                    {
                        "action": "complete_required_attribute",
                        "precondition": "确认缺失字段的准确值",
                        "risk": "字段不准确可能导致再次审核或同步失败",
                        "priority": "high",
                        "expected_effect": "补齐必填字段后可继续同步或提交审核",
                    }
                ],
                "metrics": {"missing_required_field_count": len(required_missing)},
                "details": {
                    "issue_type": "missing_required_fields",
                    "failed_stage": "field_validation",
                    "affected_objects": [{"type": "sku", "id": identifier}] if identifier else [],
                    "retryable": True,
                    "requires_manual_fix": True,
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }

        return {
            "success": True,
            "summary": "现有上下文不足以确认商品异常原因。",
            "reason": "未提供 missing_fields、sync_errors、audit_errors 或 last_error。",
            "evidences": [],
            "confidence": "low",
            "data_completeness": "insufficient",
            "severity": None,
            "recommendations": [
                {
                    "action": "provide_product_query_context",
                    "precondition": "先获取商品快照、渠道状态或错误信息",
                    "risk": "缺少证据时无法确认根因",
                    "priority": "high",
                    "expected_effect": "补充证据后可输出可信诊断",
                }
            ],
            "metrics": {},
            "details": {"issue_type": intent or "unknown", "retryable": None, "requires_manual_fix": None},
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": ["缺少可诊断的商品上下文"],
        }
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_diagnoses_missing_required_fields_from_context -q`

Expected: PASS.

---

### Task 2: Engine diagnoses sync/audit/listing errors

**Files:**
- Modify: `.kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py`
- Modify: `.kiro/skills/product-diagnosis/scripts/product_diagnosis_engine/engine.py`

- [ ] **Step 1: Add failing test**

Append:

```python

def test_diagnoses_sync_failed_from_sync_errors():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SKU-A",
        merchant_no="M001",
        intent="sync_failed",
        filters={"channel_code": "amazon"},
        context={
            "channel_product_snapshot": {"channel_product_id": "CP-1", "sync_status": "failed"},
            "sync_errors": [{"error_code": "missing_required_attribute", "message": "Missing material"}],
        },
    )

    assert result["summary"] == "SKU-A 同步失败，发现 1 条错误证据。"
    assert result["confidence"] == "high"
    assert result["details"]["issue_type"] == "sync_failed"
    assert result["details"]["failed_stage"] == "sync"
    assert result["evidences"][0]["data"]["error_code"] == "missing_required_attribute"
    assert result["recommendations"][0]["action"] == "review_channel_error_and_fix_source_data"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py::test_diagnoses_sync_failed_from_sync_errors -q`

Expected: FAIL because engine returns insufficient context or wrong issue type.

- [ ] **Step 3: Implement error diagnosis**

In `ProductDiagnosisEngine.diagnose`, before the fallback return and after missing-fields handling, add:

```python
        error_sources = {
            "sync_failed": ("sync_errors", "sync"),
            "audit_failed": ("audit_errors", "audit"),
            "listing_failed": ("listing_errors", "listing"),
        }
        if intent in error_sources:
            error_key, failed_stage = error_sources[intent]
            errors = context.get(error_key) or []
            last_error = context.get("channel_product_snapshot", {}).get("last_error")
            if last_error and not errors:
                errors = [{"message": last_error}]
            if errors:
                return {
                    "success": True,
                    "summary": f"{identifier} {self._intent_label(intent)}，发现 {len(errors)} 条错误证据。",
                    "reason": "输入上下文包含渠道商品错误信息。",
                    "evidences": [
                        {"source": error_key, "description": error.get("message") or str(error), "data": error}
                        for error in errors
                    ],
                    "confidence": "high",
                    "data_completeness": "partial",
                    "severity": "major",
                    "recommendations": [
                        {
                            "action": "review_channel_error_and_fix_source_data",
                            "precondition": "确认渠道错误信息对应的商品字段或渠道规则",
                            "risk": "未修正源数据前重试可能继续失败",
                            "priority": "high",
                            "expected_effect": "修正源数据后可重新同步或提交审核",
                        }
                    ],
                    "metrics": {"error_count": len(errors)},
                    "details": {
                        "issue_type": intent,
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

Also add method inside class:

```python
    @staticmethod
    def _intent_label(intent: str) -> str:
        return {
            "sync_failed": "同步失败",
            "audit_failed": "审核失败",
            "listing_failed": "上架失败",
        }.get(intent, "存在异常")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests/test_product_diagnosis_engine.py -q`

Expected: PASS.

---

### Task 3: Expose product_diagnosis MCP tool

**Files:**
- Modify: `.kiro/skills/oms-agent/mcp_server.py`
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`

- [ ] **Step 1: Add failing MCP test**

Append to `.kiro/skills/oms-agent/tests/test_navigation_routes.py`:

```python

def test_product_diagnosis_mcp_parses_context_and_filters(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeProductDiagnosisEngine:
        def diagnose(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
            captured["args"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
                "context": context,
            }
            return {"success": True, "summary": "diagnosed"}

    monkeypatch.setitem(sys.modules, "product_diagnosis_engine.engine", types.SimpleNamespace(ProductDiagnosisEngine=FakeProductDiagnosisEngine))

    result = json.loads(module.product_diagnosis(
        identifier="SKU-A",
        merchant_no="M001",
        intent="missing_required_fields",
        filters='{"channel_code":"amazon"}',
        context='{"missing_fields":[{"field":"material","required":true}]}',
    ))

    assert result == {"success": True, "summary": "diagnosed"}
    assert captured["args"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "missing_required_fields",
        "filters": {"channel_code": "amazon"},
        "context": {"missing_fields": [{"field": "material", "required": True}]},
    }
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_diagnosis_mcp_parses_context_and_filters -q`

Expected: FAIL with missing `product_diagnosis` attribute.

- [ ] **Step 3: Add script path and MCP tool**

In `.kiro/skills/oms-agent/mcp_server.py`, add near other path inserts:

```python
sys.path.insert(0, os.path.join(_SKILLS_DIR, "product-diagnosis", "scripts"))
```

Add after `product_query(...)`:

```python
@mcp.tool()
def product_diagnosis(
    identifier: str | None = None,
    merchant_no: str | None = None,
    intent: str | None = None,
    filters: str | None = None,
    context: str | None = None,
) -> str:
    """Product Agent 商品异常诊断 MVP。只基于调用方传入的商品快照、缺失字段和错误信息做诊断。"""
    from product_diagnosis_engine.engine import ProductDiagnosisEngine

    try:
        parsed_filters = json.loads(filters) if filters else {}
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": "invalid_filters_json", "message": str(e)}, ensure_ascii=False, indent=2)

    try:
        parsed_context = json.loads(context) if context else {}
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": "invalid_context_json", "message": str(e)}, ensure_ascii=False, indent=2)

    try:
        resolved_merchant_no = _resolve_merchant_no(merchant_no)
    except ValueError as e:
        return json.dumps({"success": False, "error": "missing_merchant_no", "message": str(e)}, ensure_ascii=False, indent=2)

    result = ProductDiagnosisEngine().diagnose(
        identifier=identifier,
        merchant_no=resolved_merchant_no,
        intent=intent,
        filters=parsed_filters,
        context=parsed_context,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_diagnosis_mcp_parses_context_and_filters -q`

Expected: PASS.

---

### Task 4: MCP error handling and docs

**Files:**
- Modify: `.kiro/skills/oms-agent/tests/test_navigation_routes.py`
- Modify: `.kiro/skills/product-diagnosis/SKILL.md`
- Modify: `docs/product-agent/01-落地行动方案.md`

- [ ] **Step 1: Add context JSON error test**

Append:

```python

def test_product_diagnosis_returns_error_for_invalid_context_json():
    module = load_mcp_server()

    result = json.loads(module.product_diagnosis(identifier="SKU-A", merchant_no="M001", context="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_context_json"
```

- [ ] **Step 2: Run error test**

Run: `python -m pytest .kiro/skills/oms-agent/tests/test_navigation_routes.py::test_product_diagnosis_returns_error_for_invalid_context_json -q`

Expected: PASS if Task 3 implementation is complete.

- [ ] **Step 3: Update skill doc**

Add after Product Diagnosis core principles:

```markdown
## MVP 运行时状态

当前 MCP runtime 已提供最小可用 `product_diagnosis`：

- 只基于调用方传入的 `context`、商品快照、渠道快照、`missing_fields`、`sync_errors`、`audit_errors` 和 `listing_errors` 做诊断。
- 支持 `missing_required_fields`、`sync_failed`、`audit_failed`、`listing_failed` 的规则型诊断。
- 不主动查询 API，不补全渠道状态，不编造错误原因。
- 当证据不足时返回 `confidence=low`、`data_completeness=insufficient`，并提示补充 `product_query` 上下文。
```

- [ ] **Step 4: Update action plan**

Add under Phase 5 in `docs/product-agent/01-落地行动方案.md`:

```markdown
### MVP 状态

已落地最小可用 `product_diagnosis` runtime：

- `product_diagnosis(...)` MCP tool 可接收 `identifier` / `merchant_no` / `intent` / `filters` / `context`。
- 支持基于 `missing_fields` 诊断必填字段缺失。
- 支持基于 `sync_errors` / `audit_errors` / `listing_errors` / `last_error` 诊断同步、审核、上架失败。
- 当前不主动调用商品 API；诊断可信度完全取决于调用方传入证据。
```

- [ ] **Step 5: Run final tests**

Run: `python -m pytest .kiro/skills/product-diagnosis/tests .kiro/skills/product-query/tests .kiro/skills/oms-agent/tests .kiro/skills/oms-analysis/tests -q`

Expected: all tests PASS.

---

## Self-Review

- Spec coverage: missing-field diagnosis, sync/audit/listing error diagnosis, MCP JSON parsing, no API calls, docs, and final tests are covered.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: `ProductDiagnosisEngine.diagnose(identifier, merchant_no, intent, filters, context)` is used consistently in tests and MCP tool.
