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
