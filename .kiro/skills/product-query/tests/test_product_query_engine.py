import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_query_engine.engine import ProductQueryEngine
from product_query_engine.inventory_adapter import InventoryAdapter
from product_query_engine.product_adapter import ProductApiAdapter
from product_query_engine.channel_product_adapter import ChannelProductApiAdapter


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


def test_channel_product_adapter_lists_channel_products():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/channel-product/page"
            assert params == {"merchantNo": "M001", "sku": "SKU-A", "channel_code": "amazon", "pageNo": 1, "pageSize": 10}
            return {
                "data": {
                    "list": [
                        {
                            "id": "CP-1",
                            "channelCode": "amazon",
                            "shopId": "SHOP-1",
                            "publishStatus": "published",
                            "auditStatus": "approved",
                            "syncStatus": "success",
                            "title": "Amazon Travel Bottle",
                        }
                    ]
                }
            }

    products = ChannelProductApiAdapter(FakeClient()).list_channel_products(
        "M001",
        {"sku": "SKU-A", "channel_code": "amazon"},
    )

    assert products == [
        {
            "channel_product_id": "CP-1",
            "channel_code": "amazon",
            "shop_id": "SHOP-1",
            "listing_status": "published",
            "audit_status": "approved",
            "sync_status": "success",
            "title": "Amazon Travel Bottle",
            "raw": {
                "id": "CP-1",
                "channelCode": "amazon",
                "shopId": "SHOP-1",
                "publishStatus": "published",
                "auditStatus": "approved",
                "syncStatus": "success",
                "title": "Amazon Travel Bottle",
            },
        }
    ]



def test_channel_product_adapter_lists_publish_history():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/publish-history/page"
            assert params == {"merchantNo": "M001", "sku": "SKU-A", "channel_code": "amazon", "pageNo": 1, "pageSize": 10}
            return {
                "data": {
                    "list": [
                        {
                            "id": "PH-1",
                            "channelCode": "amazon",
                            "publishStatus": "failed",
                            "auditStatus": "rejected",
                            "errorMessage": "Missing material",
                            "title": "Amazon Travel Bottle",
                        }
                    ]
                }
            }

    history = ChannelProductApiAdapter(FakeClient()).list_publish_history(
        "M001",
        {"sku": "SKU-A", "channel_code": "amazon"},
    )

    assert history == [
        {
            "publish_history_id": "PH-1",
            "channel_code": "amazon",
            "status": "failed",
            "audit_status": "rejected",
            "error_message": "Missing material",
            "title": "Amazon Travel Bottle",
            "raw": {
                "id": "PH-1",
                "channelCode": "amazon",
                "publishStatus": "failed",
                "auditStatus": "rejected",
                "errorMessage": "Missing material",
                "title": "Amazon Travel Bottle",
            },
        }
    ]


def test_channel_product_adapter_fetches_detail():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/channel-product/get/CP-1"
            assert params is None
            return {"data": {"id": "CP-1", "channelCode": "amazon", "title": "Amazon Travel Bottle"}}

    product = ChannelProductApiAdapter(FakeClient()).get_channel_product_detail("CP-1")

    assert product["channel_product_id"] == "CP-1"
    assert product["channel_code"] == "amazon"
    assert product["title"] == "Amazon Travel Bottle"


def test_product_adapter_finds_product_by_sku_from_spu_page():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/product/spu/page"
            assert params == {"merchantNo": "M001", "sku": "SKU-A", "pageNo": 1, "pageSize": 10}
            return {
                "data": {
                    "list": [
                        {
                            "id": "SPU-1",
                            "spu": "SPU-A",
                            "skuList": [{"sku": "SKU-A", "price": 12.5}],
                            "productName": "Travel Bottle",
                            "categoryName": "Pet Supplies",
                            "status": "active",
                        }
                    ]
                }
            }

    product = ProductApiAdapter(FakeClient()).find_product("M001", {"sku": "SKU-A"})

    assert product == {
        "product_id": "SPU-1",
        "spu": "SPU-A",
        "title": "Travel Bottle",
        "status": "active",
        "category": "Pet Supplies",
        "raw": {
            "id": "SPU-1",
            "spu": "SPU-A",
            "skuList": [{"sku": "SKU-A", "price": 12.5}],
            "productName": "Travel Bottle",
            "categoryName": "Pet Supplies",
            "status": "active",
        },
    }



def test_product_adapter_fetches_product_detail_by_product_id():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/product/spu/get/SPU-1"
            assert params is None
            return {"data": {"id": "SPU-1", "spu": "SPU-A", "productName": "Travel Bottle"}}

    product = ProductApiAdapter(FakeClient()).find_product("M001", {"product_id": "SPU-1"})

    assert product["product_id"] == "SPU-1"
    assert product["spu"] == "SPU-A"
    assert product["title"] == "Travel Bottle"


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


def test_product_query_engine_uses_channel_product_adapter_for_channel_listing():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"channel_code": "amazon", "sku": "SKU-A"}
            return [{"channel_product_id": "CP-1", "channel_code": "amazon", "listing_status": "published"}]

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="channel_listing",
        filters={"channel_code": "amazon"},
    )

    assert result["details"]["channel_products"] == [
        {"channel_product_id": "CP-1", "channel_code": "amazon", "listing_status": "published"}
    ]
    assert result["metrics"]["channel_product_count"] == 1
    assert result["confidence"] == "high"


def test_product_query_engine_includes_publish_history_for_listing_status():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            return []

        def list_publish_history(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"channel_code": "amazon", "sku": "SKU-A"}
            return [{"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}]

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="listing_status",
        filters={"channel_code": "amazon"},
    )

    assert result["details"]["publish_history"] == [
        {"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}
    ]
    assert result["metrics"]["publish_history_count"] == 1
    assert result["confidence"] == "high"


def test_product_query_engine_uses_product_adapter_for_overview():
    class FakeProductAdapter:
        def find_product(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"sku": "SKU-A"}
            return {
                "product_id": "SPU-1",
                "spu": "SPU-A",
                "title": "Travel Bottle",
                "status": "active",
                "category": "Pet Supplies",
                "raw": {"skuList": [{"sku": "SKU-A", "price": 12.5}]},
            }

    result = ProductQueryEngine(product_adapter=FakeProductAdapter()).query(
        identifier=None,
        merchant_no="M001",
        intent="overview",
        filters={"sku": "SKU-A"},
    )

    assert result["details"]["product"] == {
        "product_id": "SPU-1",
        "spu": "SPU-A",
        "title": "Travel Bottle",
        "status": "active",
        "category": "Pet Supplies",
        "raw": {"skuList": [{"sku": "SKU-A", "price": 12.5}]},
    }
    assert result["details"]["skus"] == [{"sku": "SKU-A", "price": 12.5}]
    assert result["details"]["performance_query"] == {"sku": "SKU-A", "spu": "SPU-A", "product_id": "SPU-1"}
    assert result["confidence"] == "high"


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
