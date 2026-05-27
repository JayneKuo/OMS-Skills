import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_query_engine.engine import ProductQueryEngine
from product_query_engine.inventory_adapter import InventoryAdapter
from product_query_engine.product_adapter import ProductApiAdapter
from product_query_engine.channel_product_adapter import ChannelProductApiAdapter
from product_query_engine.config import EngineConfig
from product_query_engine.api_client import ProductOMSAPIClient


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
    assert result["errors"] == []


def test_channel_product_adapter_lists_channel_products():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/channel-product/page"
            assert params == {"merchantNo": "M001", "sellerSku": "SKU-A", "channel": "amazon", "pageNo": 1, "pageSize": 10}
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

    assert len(products) == 1
    assert products[0]["channel_product_id"] == "CP-1"
    assert products[0]["channel_code"] == "amazon"
    assert products[0]["shop_id"] == "SHOP-1"
    assert products[0]["listing_status"] == "published"
    assert products[0]["audit_status"] == "approved"
    assert products[0]["sync_status"] == "success"
    assert products[0]["title"] == "Amazon Travel Bottle"
    assert products[0]["raw"] == {
        "id": "CP-1",
        "channelCode": "amazon",
        "shopId": "SHOP-1",
        "publishStatus": "published",
        "auditStatus": "approved",
        "syncStatus": "success",
        "title": "Amazon Travel Bottle",
    }



def test_channel_product_adapter_lists_publish_history():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/publish-history/page"
            assert params == {"merchantNo": "M001", "sellerSku": "SKU-A", "channel": "amazon", "pageNo": 1, "pageSize": 10}
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


def test_channel_product_adapter_normalizes_nested_oms_and_publish_result():
    raw = {
        "id": "2043875824395292674",
        "channel": "SHEIN",
        "channelNo": "C00000453",
        "channelName": "LAN-SHEIN",
        "auditState": "DRAFT",
        "auditStateDesc": "Draft",
        "omsProductInfo": {
            "spuInfo": {
                "id": 1240,
                "itemName": "fanfanfan",
                "brandName": "wbtest",
                "categoryName": "Bags & Luggage>Wallets & Cardholders>Coin Purses",
                "sellerParentSku": "0324fan",
                "internalItemId": "ITM202603240230200039",
            },
            "skuInfoList": [
                {
                    "id": "2036366676172017665",
                    "sellerSku": "0324fan",
                    "internalSkuId": "SKU202603240230200045Z",
                    "salesPrice": 1999,
                    "salesPriceUnit": "USD",
                    "discountPrice": 1998,
                    "discountPriceUnit": "USD",
                    "inventory": 1,
                    "status": "ACTIVE",
                }
            ],
        },
        "publishResult": {
            "success": False,
            "errorMessage": "Validation failed: 2 field(s) are missing or invalid",
            "validationErrors": [
                "SKC list cannot be empty",
                "Product attribute list cannot be empty",
            ],
        },
    }

    product = ChannelProductApiAdapter._normalize_channel_product(raw)

    assert product["channel_product_id"] == "2043875824395292674"
    assert product["channel_code"] == "SHEIN"
    assert product["channel_no"] == "C00000453"
    assert product["channel_name"] == "LAN-SHEIN"
    assert product["audit_status"] == "DRAFT"
    assert product["audit_status_desc"] == "Draft"
    assert product["publish_success"] is False
    assert product["last_error"] == "Validation failed: 2 field(s) are missing or invalid"
    assert product["validation_errors"] == [
        "SKC list cannot be empty",
        "Product attribute list cannot be empty",
    ]
    assert product["oms_product"] == {
        "record_id": 1240,
        "internal_item_id": "ITM202603240230200039",
        "seller_parent_sku": "0324fan",
        "title": "fanfanfan",
        "brand": "wbtest",
        "category": "Bags & Luggage>Wallets & Cardholders>Coin Purses",
    }
    assert product["oms_skus"] == [
        {
            "record_id": "2036366676172017665",
            "seller_sku": "0324fan",
            "internal_sku_id": "SKU202603240230200045Z",
            "status": "ACTIVE",
            "price": 1999,
            "currency": "USD",
            "discount_price": 1998,
            "discount_currency": "USD",
            "inventory": 1,
        }
    ]


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

    assert product["product_id"] == "SPU-1"
    assert product["record_id"] == "SPU-1"
    assert product["spu"] == "SPU-A"
    assert product["title"] == "Travel Bottle"
    assert product["status"] == "active"
    assert product["category"] == "Pet Supplies"
    assert product["raw"] == {
        "id": "SPU-1",
        "spu": "SPU-A",
        "skuList": [{"sku": "SKU-A", "price": 12.5}],
        "productName": "Travel Bottle",
        "categoryName": "Pet Supplies",
        "status": "active",
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


def test_product_adapter_normalizes_oms_item_fields_and_child_skus():
    raw = {
        "id": 1249,
        "internalItemId": "ITM202605141000400016",
        "sellerParentSku": "www-bbbb",
        "itemName": "www-bbbb",
        "brandName": "ww-brand",
        "categoryName": "Uncategorized",
        "status": "ACTIVE",
        "publishedChannels": "SHEIN,SHOPIFY,ShopifyV3",
        "salesPrice": 8888.0,
        "salesPriceUnit": "USD",
        "discountPrice": 99999.0,
        "discountPriceUnit": "USD",
        "imageInfo": [{"imageUrl": "https://example.test/main.png"}],
        "childSkus": [
            {
                "id": "2054864465852801025",
                "internalSkuId": "SKU20260514100040002CT",
                "sellerSku": "www-bbbb-red",
                "salesPrice": 8888.0,
                "salesPriceUnit": "USD",
                "discountPrice": 99999.0,
                "discountPriceUnit": "USD",
                "status": "ACTIVE",
                "imageInfo": [{"imageUrl": "https://example.test/sku.png"}],
            }
        ],
        "mappings": [
            {
                "dataChannel": "SHOPIFY",
                "channelNo": "C00000141",
                "externalSkuId": "45037584678982",
                "externalSkuCode": "www-bbbb-red",
                "mappingType": 1,
                "status": 1,
            }
        ],
    }

    product = ProductApiAdapter._normalize_product(raw)

    assert product["record_id"] == 1249
    assert product["product_id"] is None
    assert product["internal_item_id"] == "ITM202605141000400016"
    assert product["seller_parent_sku"] == "www-bbbb"
    assert product["title"] == "www-bbbb"
    assert product["brand"] == "ww-brand"
    assert product["published_channels"] == ["SHEIN", "SHOPIFY", "ShopifyV3"]
    assert product["image_count"] == 1
    assert product["skus"] == [
        {
            "record_id": "2054864465852801025",
            "internal_sku_id": "SKU20260514100040002CT",
            "seller_sku": "www-bbbb-red",
            "sku": "www-bbbb-red",
            "status": "ACTIVE",
            "price": 8888.0,
            "currency": "USD",
            "discount_price": 99999.0,
            "discount_currency": "USD",
            "image_count": 1,
            "raw": raw["childSkus"][0],
        }
    ]
    assert product["mapping"] == [
        {
            "channel": "SHOPIFY",
            "channel_no": "C00000141",
            "external_sku_id": "45037584678982",
            "external_sku_code": "www-bbbb-red",
            "mapping_type": 1,
            "status": 1,
            "raw": raw["mappings"][0],
        }
    ]


def test_product_adapter_search_products_returns_products_and_pagination():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/linker-oms/baseservice/rpc-api/product/spu/page"
            assert params == {"merchantNo": "M001", "keyword": "fan", "pageNo": 2, "pageSize": 2}
            return {
                "data": {
                    "list": [
                        {"id": 1249, "internalItemId": "ITM-1", "itemName": "Fan A", "childSkus": []},
                        {"id": 1240, "internalItemId": "ITM-2", "itemName": "Fan B", "childSkus": []},
                    ],
                    "total": 5,
                }
            }

    result = ProductApiAdapter(FakeClient()).search_products(
        "M001",
        {"keyword": "fan", "page_no": 2, "page_size": 2},
    )

    assert result["pagination"] == {"page_no": 2, "page_size": 2, "total": 5, "has_more": True}
    assert [product["title"] for product in result["products"]] == ["Fan A", "Fan B"]


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


def test_product_query_engine_reports_channel_only_match_when_oms_product_missing():
    class FakeProductAdapter:
        def find_product(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"channel_code": "SHEIN", "sku": "0324fan"}
            return None

    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"channel_code": "SHEIN", "sku": "0324fan"}
            return [
                {
                    "channel_product_id": "2043875824395292674",
                    "channel_code": "SHEIN",
                    "audit_status": "DRAFT",
                }
            ]

        def list_publish_history(self, merchant_no, filters):
            return []

    result = ProductQueryEngine(
        product_adapter=FakeProductAdapter(),
        channel_product_adapter=FakeChannelProductAdapter(),
    ).query(
        identifier="0324fan",
        merchant_no="M001",
        intent="overview",
        filters={"channel_code": "SHEIN"},
    )

    assert result["summary"] == "未找到 OMS 商品主档，但找到 1 个渠道商品。"
    assert result["details"]["product"] == {"sku": "0324fan"}
    assert result["details"]["channel_products"] == [
        {"channel_product_id": "2043875824395292674", "channel_code": "SHEIN", "audit_status": "DRAFT"}
    ]
    assert result["details"]["resolution"] == {
        "found_in_oms_product": False,
        "found_in_product_list": False,
        "found_in_channel_product": True,
        "found_in_publish_history": False,
        "best_match_type": "channel_product",
        "identifier_type": "sku",
    }
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


def test_product_query_engine_returns_keyword_product_list():
    class FakeProductAdapter:
        def search_products(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"keyword": "fan", "page_no": 1, "page_size": 2}
            return {
                "products": [
                    {"record_id": 1249, "title": "Fan A", "skus": [{"seller_sku": "FAN-A"}]},
                    {"record_id": 1240, "title": "Fan B", "skus": []},
                ],
                "pagination": {"page_no": 1, "page_size": 2, "total": 225, "has_more": True},
            }

    result = ProductQueryEngine(product_adapter=FakeProductAdapter()).query(
        identifier=None,
        merchant_no="M001",
        intent="overview",
        filters={"keyword": "fan", "page_no": 1, "page_size": 2},
    )

    assert result["summary"] == "找到 225 个匹配商品，当前返回 2 个。"
    assert result["metrics"]["product_count"] == 2
    assert result["metrics"]["product_total"] == 225
    assert result["details"]["product"] == {}
    assert result["details"]["products"] == [
        {"record_id": 1249, "title": "Fan A", "skus": [{"seller_sku": "FAN-A"}]},
        {"record_id": 1240, "title": "Fan B", "skus": []},
    ]
    assert result["details"]["pagination"] == {"page_no": 1, "page_size": 2, "total": 225, "has_more": True}
    assert result["confidence"] == "high"


def test_product_query_engine_groups_channel_products_by_channel():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            return [
                {
                    "channel_product_id": "SHEIN-1",
                    "channel_code": "SHEIN",
                    "channel_no": "C-SHEIN",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Missing attributes",
                    "validation_errors": ["Product attribute list cannot be empty"],
                },
                {
                    "channel_product_id": "SHOPIFY-1",
                    "channel_code": "SHOPIFY",
                    "channel_no": "C-SHOPIFY",
                    "audit_status": "LISTED",
                    "publish_success": True,
                },
                {
                    "channel_product_id": "SHOPIFY-2",
                    "channel_code": "SHOPIFY",
                    "channel_no": "C-SHOPIFY",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Variant missing image",
                },
            ]

        def list_publish_history(self, merchant_no, filters):
            return []

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="channel_listing",
        filters={},
    )

    assert result["details"]["channel_summary"] == [
        {
            "channel_code": "SHEIN",
            "channel_no": "C-SHEIN",
            "channel_product_count": 1,
            "publish_history_count": 0,
            "audit_statuses": ["DRAFT"],
            "listing_statuses": [],
            "publish_success_count": 0,
            "publish_failure_count": 1,
            "errors": ["Missing attributes", "Product attribute list cannot be empty"],
        },
        {
            "channel_code": "SHOPIFY",
            "channel_no": "C-SHOPIFY",
            "channel_product_count": 2,
            "publish_history_count": 0,
            "audit_statuses": ["DRAFT", "LISTED"],
            "listing_statuses": [],
            "publish_success_count": 1,
            "publish_failure_count": 1,
            "errors": ["Variant missing image"],
        },
    ]
    assert result["metrics"]["channel_count"] == 2


def test_product_query_engine_merges_publish_history_into_channel_summary():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            return [
                {
                    "channel_product_id": "SHEIN-1",
                    "channel_code": "SHEIN",
                    "channel_no": "C-SHEIN",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Missing attributes",
                }
            ]

        def list_publish_history(self, merchant_no, filters):
            return [
                {
                    "publish_history_id": "PH-1",
                    "channel_code": "SHEIN",
                    "status": "failed",
                    "audit_status": "DRAFT",
                    "error_message": "Missing attributes",
                },
                {
                    "publish_history_id": "PH-2",
                    "channel_code": "SHOPIFY",
                    "status": "success",
                    "audit_status": "LISTED",
                },
            ]

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="overview",
        filters={},
    )

    assert result["details"]["channel_summary"] == [
        {
            "channel_code": "SHEIN",
            "channel_no": "C-SHEIN",
            "channel_product_count": 1,
            "publish_history_count": 1,
            "audit_statuses": ["DRAFT"],
            "listing_statuses": [],
            "publish_success_count": 0,
            "publish_failure_count": 2,
            "errors": ["Missing attributes"],
        },
        {
            "channel_code": "SHOPIFY",
            "channel_no": None,
            "channel_product_count": 0,
            "publish_history_count": 1,
            "audit_statuses": ["LISTED"],
            "listing_statuses": [],
            "publish_success_count": 1,
            "publish_failure_count": 0,
            "errors": [],
        },
    ]
    assert result["metrics"]["channel_count"] == 2


def test_product_query_engine_accepts_item_name_lookup_for_overview():
    class FakeProductAdapter:
        def find_product(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"item_name": "Babolat Pure Drive"}
            return {
                "product_id": "SPU-1001",
                "spu": "SPU-PD",
                "title": "Babolat Pure Drive",
                "status": "active",
                "category": "Rackets",
                "raw": {"skuList": [{"sku": "PD-G2", "price": 199.99}]},
            }

    result = ProductQueryEngine(product_adapter=FakeProductAdapter()).query(
        identifier="Babolat Pure Drive",
        merchant_no="M001",
        intent="overview",
        filters={},
    )

    assert result["details"]["product"]["title"] == "Babolat Pure Drive"
    assert result["details"]["skus"] == [{"sku": "PD-G2", "price": 199.99}]
    assert result["details"]["performance_query"] == {"spu": "SPU-PD", "product_id": "SPU-1001"}
    assert result["confidence"] == "high"


def test_product_query_engine_accepts_parent_sku_lookup_for_overview():
    class FakeProductAdapter:
        def find_product(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"seller_parent_sku": "PARENT-100"}
            return {
                "product_id": "SPU-2001",
                "spu": "SPU-2001",
                "title": "Travel Bottle Set",
                "status": "active",
                "category": "Outdoor",
                "raw": {"skuList": [{"sku": "SKU-CHILD-1"}]},
            }

    result = ProductQueryEngine(product_adapter=FakeProductAdapter()).query(
        identifier="PARENT-100",
        merchant_no="M001",
        intent="overview",
        filters={"match_hint": "seller_parent_sku"},
    )

    assert result["details"]["product"]["product_id"] == "SPU-2001"
    assert result["details"]["performance_query"] == {"spu": "SPU-2001", "product_id": "SPU-2001"}


def test_product_query_engine_accepts_internal_item_id_lookup_for_overview():
    class FakeProductAdapter:
        def find_product(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"internal_item_id": "ITEM-1001"}
            return {
                "product_id": "SPU-1001",
                "spu": "SPU-PD",
                "title": "Babolat Pure Drive",
                "status": "active",
                "category": "Rackets",
                "raw": {"skuList": [{"sku": "PD-G2"}]},
            }

    result = ProductQueryEngine(product_adapter=FakeProductAdapter()).query(
        identifier="ITEM-1001",
        merchant_no="M001",
        intent="overview",
        filters={"match_hint": "internal_item_id"},
    )

    assert result["details"]["product"]["product_id"] == "SPU-1001"
    assert result["details"]["performance_query"] == {"spu": "SPU-PD", "product_id": "SPU-1001"}


def test_product_query_engine_accepts_skc_lookup_for_channel_listing():
    class FakeChannelProductAdapter:
        def list_channel_products(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"skc": "SKC-RED-01", "channel_code": "shein"}
            return [{"channel_product_id": "CP-9", "channel_code": "shein", "listing_status": "published"}]

        def list_publish_history(self, merchant_no, filters):
            assert merchant_no == "M001"
            assert filters == {"skc": "SKC-RED-01", "channel_code": "shein"}
            return []

    result = ProductQueryEngine(channel_product_adapter=FakeChannelProductAdapter()).query(
        identifier="SKC-RED-01",
        merchant_no="M001",
        intent="channel_listing",
        filters={"match_hint": "skc", "channel_code": "shein"},
    )

    assert result["details"]["channel_products"] == [
        {"channel_product_id": "CP-9", "channel_code": "shein", "listing_status": "published"}
    ]
    assert result["metrics"]["channel_product_count"] == 1
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


def test_engine_config_reads_runtime_env(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")

    config = EngineConfig()

    assert config.base_url == "https://oms.example.com"
    assert config.tenant_id == "LT"
    assert config.merchant_no == "LAN0000002"
    assert config.access_token == "token-123"


def test_product_api_client_uses_runtime_headers_and_normalizes_path():
    config = EngineConfig(
        base_url="https://oms.example.com",
        tenant_id="LT",
        merchant_no="LAN0000002",
        access_token="token-123",
    )
    client = ProductOMSAPIClient(config)

    assert client.base_url == "https://oms.example.com/api/linker-oms"
    assert client.headers == {
        "Authorization": "Bearer token-123",
        "Content-Type": "application/json",
        "x-tenant-id": "LT",
    }


def test_product_api_client_fetches_token_via_password_grant_when_missing(monkeypatch):
    monkeypatch.setenv("OMS_USERNAME", "lantester@item.com")
    monkeypatch.setenv("OMS_PASSWORD", "LANLT")
    config = EngineConfig(
        base_url="https://oms.example.com",
        tenant_id="LT",
        merchant_no="LAN0000002",
        access_token=None,
    )

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"access_token": "fresh-token"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("product_query_engine.api_client.requests.post", fake_post)

    client = ProductOMSAPIClient(config)
    client._ensure_token()

    assert client.headers["Authorization"] == "Bearer fresh-token"
    assert captured == {
        "url": "https://oms.example.com/api/linker-oms/opc/iam/token",
        "headers": {"Content-Type": "application/json"},
        "json": {"grantType": "password", "username": "lantester@item.com", "password": "LANLT"},
        "timeout": 30,
    }


def test_product_publish_workflow_creates_product_and_channel_product():
    from product_query_engine.publish_workflow import ProductPublishWorkflow

    captured = {}

    class FakeClient:
        def _ensure_token(self):
            captured["token_checked"] = True

        def post(self, path, payload):
            if path == "/api/linker-oms/baseservice/rpc-api/product/spu/create-complete":
                captured["product_payload"] = payload
                return {
                    "data": {
                        "spuInfo": {"id": "SPU-1001", "internalItemId": "ITEM-1001"},
                        "skuInfoList": [
                            {"internalSkuId": "SKU-1"},
                            {"internalSkuId": "SKU-2"},
                            {"internalSkuId": "SKU-3"},
                        ],
                    }
                }
            if path == "/api/linker-oms/baseservice/rpc-api/channel-product/create-from-spu":
                captured["channel_payload"] = payload
                return {
                    "code": 200,
                    "data": {
                        "successCount": 1,
                        "failureCount": 0,
                        "successList": [{"productId": "SPU-1001", "channelProductId": "CP-1", "success": True}],
                        "failList": [],
                    },
                }
            raise AssertionError(path)

    result = ProductPublishWorkflow(FakeClient()).publish(
        merchant_no="M001",
        request={
            "product": {
                "name": "Babolat Pure Drive",
                "brand": "百宝力",
                "model": "PD",
                "categoryName": "网球球拍",
                "variants": [
                    {"sellerSku": "PD-G1", "gripSize": "一号", "price": 199.99},
                    {"sellerSku": "PD-G2", "gripSize": "二号", "price": 199.99},
                    {"sellerSku": "PD-G3", "gripSize": "三号", "price": 199.99},
                ],
            },
            "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
        },
    )

    assert result["success"] is True
    assert captured["token_checked"] is True
    assert captured["product_payload"]["spuInfo"]["merchantNo"] == "M001"
    assert captured["product_payload"]["spuInfo"]["itemName"] == "Babolat Pure Drive"
    assert captured["product_payload"]["skuInfoList"][0]["sellerSku"] == "PD-G1"
    assert captured["product_payload"]["salesAttributes"][0]["attributeName"] == "Grip Size"
    assert captured["channel_payload"] == {
        "merchantNo": "M001",
        "internalProducts": [
            {
                "spuId": "SPU-1001",
                "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
                "internalSkuIds": ["SKU-1", "SKU-2", "SKU-3"],
            }
        ],
    }
    assert result["details"]["created_product"]["spuInfo"]["id"] == "SPU-1001"
    assert result["details"]["channel_sync"]["data"]["successCount"] == 1


def test_product_publish_workflow_rebuilds_sales_attributes_like_frontend():
    from product_query_engine.publish_workflow import ProductPublishWorkflow

    captured = {}

    class FakeClient:
        def _ensure_token(self):
            pass

        def post(self, path, payload):
            if path == "/api/linker-oms/baseservice/rpc-api/product/spu/create-complete":
                captured["product_payload"] = payload
                return {"code": 200, "data": {"spuInfo": {"id": "SPU-1"}, "skuInfoList": [{"internalSkuId": "SKU-1"}, {"internalSkuId": "SKU-2"}]}}
            if path == "/api/linker-oms/baseservice/rpc-api/channel-product/create-from-spu":
                return {"code": 200, "data": {"successCount": 1}}
            raise AssertionError(path)

    ProductPublishWorkflow(FakeClient()).publish(
        merchant_no="M001",
        request={
            "product": {
                "name": "Tennis Racket",
                "categoryId": 1002292,
                "categoryName": "Tennis Rackets",
                "variants": [
                    {"sellerSku": "RKT-G2", "price": 199.99, "salesAttributeValues": [{"attributeName": "Grip Size", "attributeValue": "G2"}, {"attributeName": "Color", "attributeValue": "Black"}]},
                    {"sellerSku": "RKT-G3", "price": 199.99, "salesAttributeValues": [{"attributeName": "Grip Size", "attributeValue": "G3"}, {"attributeName": "Color", "attributeValue": "Black"}]},
                ],
            },
            "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
        },
    )

    assert captured["product_payload"]["spuInfo"]["categoryId"] == 1002292
    assert captured["product_payload"]["spuInfo"]["channelCategory"] == []
    assert captured["product_payload"]["skuInfoList"][0]["salesAttributeValues"] == [
        {"attributeName": "Grip Size", "attributeValue": "G2"},
        {"attributeName": "Color", "attributeValue": "Black"},
    ]
    assert captured["product_payload"]["salesAttributes"] == [
        {
            "attributeId": None,
            "attributeChannelId": None,
            "channel": "OMS",
            "productTypeId": None,
            "attributeName": "Grip Size",
            "attributeIsShow": True,
            "attributeType": 1,
            "attributeLabel": 1,
            "attributeValues": [
                {"attributeValueId": None, "attributeChannelValueId": None, "channel": "OMS", "attributeValue": "G2", "isShow": True, "isCustomAttributeValue": False, "customValue": None},
                {"attributeValueId": None, "attributeChannelValueId": None, "channel": "OMS", "attributeValue": "G3", "isShow": True, "isCustomAttributeValue": False, "customValue": None},
            ],
        },
        {
            "attributeId": None,
            "attributeChannelId": None,
            "channel": "OMS",
            "productTypeId": None,
            "attributeName": "Color",
            "attributeIsShow": True,
            "attributeType": 1,
            "attributeLabel": 0,
            "attributeValues": [
                {"attributeValueId": None, "attributeChannelValueId": None, "channel": "OMS", "attributeValue": "Black", "isShow": True, "isCustomAttributeValue": False, "customValue": None},
            ],
        },
    ]


def test_product_publish_workflow_returns_missing_spu_id_with_raw_response_details():
    from product_query_engine.publish_workflow import ProductPublishWorkflow

    class FakeClient:
        def _ensure_token(self):
            pass

        def post(self, path, payload):
            if path == "/api/linker-oms/baseservice/rpc-api/product/spu/create-complete":
                return {"code": 200, "data": None, "message": "created but no body"}
            raise AssertionError(path)

    result = ProductPublishWorkflow(FakeClient()).publish(
        merchant_no="M001",
        request={
            "product": {
                "name": "Smoke Product",
                "categoryName": "网球球拍",
                "variants": [{"sellerSku": "SMOKE-1", "gripSize": "一号", "price": 199.99}],
            },
            "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
        },
    )

    assert result["success"] is False
    assert result["error"] == "missing_spu_id"
    assert result["details"]["created_product_response"] == {"code": 200, "data": None, "message": "created but no body"}


def test_product_publish_workflow_extracts_spu_from_top_level_response():
    from product_query_engine.publish_workflow import ProductPublishWorkflow

    class FakeClient:
        def _ensure_token(self):
            pass

        def post(self, path, payload):
            if path == "/api/linker-oms/baseservice/rpc-api/product/spu/create-complete":
                return {
                    "code": 200,
                    "message": "ok",
                    "spuInfo": {"id": "SPU-ROOT-1"},
                    "skuInfoList": [{"internalSkuId": "SKU-ROOT-1"}],
                }
            if path == "/api/linker-oms/baseservice/rpc-api/channel-product/create-from-spu":
                return {"code": 200, "data": {"successCount": 1}}
            raise AssertionError(path)

    result = ProductPublishWorkflow(FakeClient()).publish(
        merchant_no="M001",
        request={
            "product": {
                "name": "Smoke Product",
                "categoryName": "网球球拍",
                "variants": [{"sellerSku": "SMOKE-1", "gripSize": "一号", "price": 199.99}],
            },
            "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
        },
    )

    assert result["success"] is True
    assert result["details"]["created_product"]["spuInfo"]["id"] == "SPU-ROOT-1"
    assert result["details"]["channel_sync"]["data"]["successCount"] == 1


def test_product_publish_workflow_surfaces_create_business_error_response():
    from product_query_engine.publish_workflow import ProductPublishWorkflow

    class FakeClient:
        def _ensure_token(self):
            pass

        def post(self, path, payload):
            if path == "/api/linker-oms/baseservice/rpc-api/product/spu/create-complete":
                return {"code": 500, "data": None, "msg": "System exception"}
            raise AssertionError(path)

    result = ProductPublishWorkflow(FakeClient()).publish(
        merchant_no="M001",
        request={
            "product": {
                "name": "Smoke Product",
                "categoryName": "网球球拍",
                "variants": [{"sellerSku": "SMOKE-1", "gripSize": "一号", "price": 199.99}],
            },
            "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
        },
    )

    assert result["success"] is False
    assert result["error"] == "product_create_failed"
    assert result["message"] == "System exception"
    assert result["details"]["created_product_response"] == {"code": 500, "data": None, "msg": "System exception"}
    assert result["details"]["upstream_error"] is True


def test_channel_product_create_workflow_creates_channel_product():
    from product_query_engine.publish_workflow import ChannelProductCreateWorkflow

    captured = {}

    class FakeClient:
        def _ensure_token(self):
            captured["token_checked"] = True

        def post(self, path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"code": 200, "data": {"channelProductId": "CP-1", "success": True}, "msg": "ok"}

    result = ChannelProductCreateWorkflow(FakeClient()).create(
        request={"merchantNo": "M001", "internalProducts": [{"spuId": "SPU-1", "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}], "internalSkuIds": ["SKU-1"]}]}
    )

    assert result["success"] is True
    assert captured["token_checked"] is True
    assert captured["path"] == "/api/linker-oms/opc/rpc-api/channel-product/create"
    assert captured["payload"] == {"merchantNo": "M001", "internalProducts": [{"spuId": "SPU-1", "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}], "internalSkuIds": ["SKU-1"]}]}
    assert result["details"]["channel_product_create_response"]["data"]["channelProductId"] == "CP-1"


def test_channel_product_create_workflow_returns_missing_merchant_no():
    from product_query_engine.publish_workflow import ChannelProductCreateWorkflow

    class FakeClient:
        def _ensure_token(self):
            raise AssertionError("should not fetch token")

        def post(self, path, payload):
            raise AssertionError(path)

    result = ChannelProductCreateWorkflow(FakeClient()).create(
        request={"internalProducts": [{"spuId": "SPU-1", "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}]}]}
    )

    assert result["success"] is False
    assert result["error"] == "missing_merchant_no"


def test_channel_product_create_workflow_surfaces_business_error():
    from product_query_engine.publish_workflow import ChannelProductCreateWorkflow

    class FakeClient:
        def _ensure_token(self):
            pass

        def post(self, path, payload):
            return {"code": 500, "data": None, "msg": "System exception"}

    result = ChannelProductCreateWorkflow(FakeClient()).create(
        request={"merchantNo": "M001", "internalProducts": [{"spuId": "SPU-1", "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}], "internalSkuIds": ["SKU-1"]}]}
    )

    assert result["success"] is False
    assert result["error"] == "channel_product_create_failed"
    assert result["message"] == "System exception"
    assert result["details"]["upstream_error"] is True
    assert result["details"]["channel_product_create_response"] == {"code": 500, "data": None, "msg": "System exception"}
