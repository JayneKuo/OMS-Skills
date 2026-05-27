import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_diagnosis_engine.engine import ProductDiagnosisEngine
from product_diagnosis_engine.platform_requirements.shopify import evaluate_shopify_readiness


def test_shopify_requirements_module_reports_missing_title_and_variant_price():
    result = evaluate_shopify_readiness(
        product={"title": "", "image_count": 1},
        skus=[{"seller_sku": "SKU-A", "price": None, "currency": "USD"}],
        channel_summary=[],
        channel_code="SHOPIFY",
    )

    assert result["ready_to_publish"] is False
    assert [issue["code"] for issue in result["blocking_issues"]] == [
        "missing_product_title",
        "missing_variant_price",
    ]



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


def test_shopify_readiness_reports_missing_fields_for_official_admin_api():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SHOPIFY-SKU",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {"title": "", "image_count": 0},
                    "skus": [
                        {"seller_sku": "", "price": None, "currency": None}
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["success"] is True
    assert result["summary"] == "SHOPIFY-SKU 不满足 Shopify 发布前置条件，发现 5 个阻塞项。"
    assert result["details"]["issue_type"] == "platform_readiness_failed"
    assert result["details"]["platform"] == "SHOPIFY"
    assert result["details"]["ready_to_publish"] is False
    assert result["metrics"] == {"blocking_issue_count": 5}
    assert [issue["code"] for issue in result["details"]["blocking_issues"]] == [
        "missing_product_title",
        "missing_variant_sku",
        "missing_variant_price",
        "missing_variant_currency",
        "missing_product_media",
    ]
    assert all(issue["source"] == "shopify_admin_graphql_api" for issue in result["details"]["blocking_issues"])
    assert result["recommendations"][0]["action"] == "complete_shopify_required_product_data"


def test_shopify_readiness_includes_blocked_checklist_items():
    result = ProductDiagnosisEngine().diagnose(
        identifier="SHOPIFY-SKU",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {"title": "", "image_count": 0},
                    "skus": [
                        {"seller_sku": "", "price": None, "currency": None}
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["details"]["readiness_checklist"] == [
        {"item": "商品标题", "status": "blocked", "evidence": "缺少 Shopify 商品标题", "issue_code": "missing_product_title"},
        {"item": "Variant", "status": "ready", "evidence": "1 个 variant 可用"},
        {"item": "Variant SKU", "status": "blocked", "evidence": "缺少可追踪的 variant SKU", "issue_code": "missing_variant_sku"},
        {"item": "Variant 价格", "status": "blocked", "evidence": "缺少 variant 价格", "issue_code": "missing_variant_price"},
        {"item": "Variant 币种", "status": "blocked", "evidence": "缺少 variant 币种", "issue_code": "missing_variant_currency"},
        {"item": "商品图片", "status": "blocked", "evidence": "缺少商品 media/image", "issue_code": "missing_product_media"},
        {"item": "OMS Shopify 渠道类型", "status": "ready", "evidence": "SHOPIFY 可用于当前发布服务"},
    ]


def test_shopify_readiness_reports_multivariant_options_and_shopifyv3_connector_issue():
    result = ProductDiagnosisEngine().diagnose(
        identifier="0324fan",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "ShopifyV3"},
        context={
            "product_query_result": {
                "details": {
                    "product": {"title": "fanfanfan", "image_count": 1},
                    "skus": [
                        {"seller_sku": "SKU-RED", "price": 10, "currency": "USD"},
                        {"seller_sku": "SKU-BLUE", "price": 10, "currency": "USD"},
                    ],
                    "channel_summary": [
                        {
                            "channel_code": "ShopifyV3",
                            "errors": ["Unsupported channel type: ShopifyV3. Supported channels: [SHEIN, SHOPIFY]"],
                        }
                    ],
                }
            }
        },
    )

    assert result["summary"] == "0324fan 不满足 Shopify 发布前置条件，发现 2 个阻塞项。"
    assert [issue["code"] for issue in result["details"]["blocking_issues"]] == [
        "missing_variant_options",
        "unsupported_oms_shopify_channel_type",
    ]
    assert result["details"]["blocking_issues"][0]["source"] == "shopify_admin_graphql_api"
    assert result["details"]["blocking_issues"][1]["source"] == "oms_publish_error"


def test_shopify_readiness_passes_for_complete_single_variant_product():
    result = ProductDiagnosisEngine().diagnose(
        identifier="READY-SKU",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {"title": "Ready Product", "image_count": 1},
                    "skus": [
                        {"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["summary"] == "READY-SKU 满足 Shopify 发布前置条件。"
    assert result["details"]["issue_type"] == "platform_readiness_passed"
    assert result["details"]["ready_to_publish"] is True
    assert result["details"]["blocking_issues"] == []
    assert result["metrics"] == {"blocking_issue_count": 0}
    assert result["details"]["readiness_checklist"] == [
        {"item": "商品标题", "status": "ready", "evidence": "Ready Product"},
        {"item": "Variant", "status": "ready", "evidence": "1 个 variant 可用"},
        {"item": "Variant SKU", "status": "ready", "evidence": "variant SKU 已提供"},
        {"item": "Variant 价格", "status": "ready", "evidence": "variant 价格已提供"},
        {"item": "Variant 币种", "status": "ready", "evidence": "variant 币种已提供"},
        {"item": "商品图片", "status": "ready", "evidence": "商品 media/image 已提供"},
        {"item": "OMS Shopify 渠道类型", "status": "ready", "evidence": "SHOPIFY 可用于当前发布服务"},
    ]


def test_shopify_readiness_reports_missing_variant_option_values():
    result = ProductDiagnosisEngine().diagnose(
        identifier="READY-PARENT",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {
                        "title": "Ready Multi Variant Product",
                        "image_count": 1,
                        "options": [{"name": "Color", "values": ["Red", "Blue"]}],
                    },
                    "skus": [
                        {"seller_sku": "READY-RED", "price": 10, "currency": "USD"},
                        {"seller_sku": "READY-BLUE", "price": 10, "currency": "USD"},
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["details"]["ready_to_publish"] is False
    assert [issue["code"] for issue in result["details"]["blocking_issues"]] == ["missing_variant_options"]


def test_shopify_readiness_reports_incomplete_variant_option_values():
    result = ProductDiagnosisEngine().diagnose(
        identifier="READY-PARENT",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {
                        "title": "Ready Multi Variant Product",
                        "image_count": 1,
                        "options": [
                            {"name": "Color", "values": ["Red", "Blue"]},
                            {"name": "Size", "values": ["S", "M"]},
                        ],
                    },
                    "skus": [
                        {"seller_sku": "READY-RED", "price": 10, "currency": "USD", "option_values": [{"name": "Color", "value": "Red"}]},
                        {"seller_sku": "READY-BLUE", "price": 10, "currency": "USD", "option_values": [{"name": "Color", "value": "Blue"}]},
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["details"]["ready_to_publish"] is False
    assert [issue["code"] for issue in result["details"]["blocking_issues"]] == ["missing_variant_options"]


def test_shopify_readiness_passes_for_complete_multi_variant_product_with_options():
    result = ProductDiagnosisEngine().diagnose(
        identifier="READY-PARENT",
        merchant_no="M001",
        intent="platform_readiness",
        filters={"channel_code": "SHOPIFY"},
        context={
            "product_query_result": {
                "details": {
                    "product": {
                        "title": "Ready Multi Variant Product",
                        "image_count": 1,
                        "options": [{"name": "Color", "values": ["Red", "Blue"]}],
                    },
                    "skus": [
                        {"seller_sku": "READY-RED", "price": 10, "currency": "USD", "option_values": [{"name": "Color", "value": "Red"}]},
                        {"seller_sku": "READY-BLUE", "price": 10, "currency": "USD", "option_values": [{"name": "Color", "value": "Blue"}]},
                    ],
                    "channel_summary": [],
                }
            }
        },
    )

    assert result["summary"] == "READY-PARENT 满足 Shopify 发布前置条件。"
    assert result["details"]["ready_to_publish"] is True
    assert result["details"]["blocking_issues"] == []


def test_shopify_readiness_uses_0324fan_product_query_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "product_query_0324fan.json"
    product_query_result = json.loads(fixture_path.read_text(encoding="utf-8"))

    result = ProductDiagnosisEngine().diagnose(
        identifier="0324fan",
        merchant_no="LAN0000002",
        intent="platform_readiness",
        filters={"channel_code": "ShopifyV3"},
        context={"product_query_result": product_query_result},
    )

    assert result["details"]["ready_to_publish"] is False
    assert result["metrics"] == {"blocking_issue_count": 1}
    assert result["details"]["blocking_issues"] == [
        {
            "code": "unsupported_oms_shopify_channel_type",
            "message": "当前 OMS 发布错误显示 ShopifyV3 不被发布服务支持，应确认是否使用 SHOPIFY channel type。",
            "source": "oms_publish_error",
            "field": "channel_code",
        }
    ]
    assert result["recommendations"] == [
        {
            "action": "use_supported_shopify_channel_type",
            "precondition": "确认 OMS 渠道配置中存在 SHOPIFY channel type",
            "risk": "继续使用 ShopifyV3 会被当前 OMS 发布服务拒绝",
            "priority": "high",
            "expected_effect": "改用 SHOPIFY 后可进入 Shopify 发布前置校验或发布流程",
        }
    ]
    assert result["details"]["readiness_checklist"][-1] == {
        "item": "OMS Shopify 渠道类型",
        "status": "blocked",
        "evidence": "ShopifyV3 不被当前 OMS 发布服务支持",
        "issue_code": "unsupported_oms_shopify_channel_type",
    }
