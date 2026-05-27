import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_optimization_engine.engine import ProductOptimizationEngine


def test_product_creation_brief_generates_tennis_shopify_payload():
    result = ProductOptimizationEngine().optimize(
        identifier="tennis",
        merchant_no="LAN0000002",
        intent="product_creation_brief",
        filters={"target_channel": "ShopifyV3", "market": "US", "language": "en"},
        context={},
    )

    assert result["success"] is True
    assert result["confidence"] == "medium"
    assert result["data_completeness"] == "estimated"
    assert result["recommendations"][0]["action"] == "create_test_product_after_confirmation"

    brief = result["details"]["creation_brief"]
    assert brief["product"]["name"] == "AI Test ProSpin Tennis Training Set"
    assert brief["product"]["brand"] == "CourtLab"
    assert brief["product"]["categoryName"] == "Tennis Training Equipment"
    assert brief["product"]["price"] == 49.99
    assert brief["product"]["keywords"] == ["tennis", "training", "practice", "sports"]
    assert brief["product"]["variants"] == [
        {
            "sellerSku": "TENNIS-AI-TEST",
            "price": 49.99,
            "salesPriceUnit": "USD",
            "inventory": 20,
            "weight": 1.2,
            "weightUnit": "KG",
            "length": 35,
            "width": 25,
            "height": 8,
            "dimensionUnit": "CM",
            "salesAttributeValues": [
                {"attributeName": "Package", "attributeValue": "Standard"}
            ],
        }
    ]
    assert brief["channels"] == [{"channel": "ShopifyV3"}]
    assert "用户只提供 tennis" in result["details"]["assumptions"][0]


def test_product_creation_brief_accepts_chinese_tennis_and_sku_suffix():
    result = ProductOptimizationEngine().optimize(
        identifier="网球",
        merchant_no="LAN0000002",
        intent="product_creation_brief",
        filters={"target_channel": "ShopifyV3", "sku_suffix": "20260521A"},
        context={},
    )

    brief = result["details"]["creation_brief"]
    assert brief["product"]["parentSku"] == "TENNIS-AI-20260521A"
    assert brief["product"]["variants"][0]["sellerSku"] == "TENNIS-AI-20260521A"
    assert brief["channels"] == [{"channel": "ShopifyV3"}]
