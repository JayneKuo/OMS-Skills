from __future__ import annotations

from typing import Any


def _extract_list(data: Any) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = _extract_list(value)
                if nested:
                    return nested
    return []


class ChannelProductApiAdapter:
    def __init__(self, client):
        self._client = client

    def list_channel_products(self, merchant_no: str | None, filters: dict) -> list[dict]:
        self._client._ensure_token()
        params = {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 10}
        for source, target in (
            ("sku", "sellerSku"),
            ("spu", "spu"),
            ("product_id", "productId"),
            ("item_name", "itemName"),
            ("seller_parent_sku", "sellerParentSku"),
            ("internal_sku_id", "internalSkuId"),
            ("internal_item_id", "internalItemId"),
            ("skc", "skc"),
            ("keyword", "keyword"),
            ("channel_code", "channel"),
            ("shop_id", "shopId"),
        ):
            if filters.get(source):
                params[target] = filters[source]
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/channel-product/page", params)
        return [self._normalize_channel_product(row) for row in _extract_list(response.get("data", response))]

    def get_channel_product_detail(self, product_id: str) -> dict | None:
        self._client._ensure_token()
        response = self._client.get(f"/api/linker-oms/baseservice/rpc-api/channel-product/get/{product_id}")
        data = response.get("data", response)
        return self._normalize_channel_product(data) if isinstance(data, dict) else None

    def list_publish_history(self, merchant_no: str | None, filters: dict) -> list[dict]:
        self._client._ensure_token()
        params = {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 10}
        for source, target in (
            ("sku", "sellerSku"),
            ("spu", "spu"),
            ("product_id", "productId"),
            ("channel_product_id", "productId"),
            ("item_name", "productName"),
            ("seller_parent_sku", "parentSku"),
            ("internal_sku_id", "internalSkuId"),
            ("internal_item_id", "internalItemId"),
            ("skc", "skc"),
            ("keyword", "keyword"),
            ("channel_code", "channel"),
            ("shop_id", "shopId"),
        ):
            if filters.get(source):
                params[target] = filters[source]
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/publish-history/page", params)
        return [self._normalize_publish_history(row) for row in _extract_list(response.get("data", response))]

    @staticmethod
    def _normalize_publish_history(raw: dict) -> dict:
        return {
            "publish_history_id": raw.get("id") or raw.get("publishHistoryId"),
            "channel_code": raw.get("channelCode") or raw.get("channel_code") or raw.get("channel"),
            "status": raw.get("publishStatus") or raw.get("status"),
            "audit_status": raw.get("auditStatus") or raw.get("auditState"),
            "error_message": raw.get("errorMessage") or raw.get("lastError") or raw.get("message"),
            "title": raw.get("title") or raw.get("productName") or raw.get("name"),
            "raw": raw,
        }

    @staticmethod
    def _normalize_oms_product(raw: dict) -> dict:
        return {
            "record_id": raw.get("id"),
            "internal_item_id": raw.get("internalItemId"),
            "seller_parent_sku": raw.get("sellerParentSku"),
            "title": raw.get("itemName") or raw.get("productName") or raw.get("title") or raw.get("name"),
            "brand": raw.get("brandName") or raw.get("brand"),
            "category": raw.get("categoryName") or raw.get("category"),
        }

    @staticmethod
    def _normalize_oms_sku(raw: dict) -> dict:
        return {
            "record_id": raw.get("id"),
            "seller_sku": raw.get("sellerSku"),
            "internal_sku_id": raw.get("internalSkuId"),
            "status": raw.get("status"),
            "price": raw.get("salesPrice") or raw.get("price"),
            "currency": raw.get("salesPriceUnit") or raw.get("currency"),
            "discount_price": raw.get("discountPrice"),
            "discount_currency": raw.get("discountPriceUnit"),
            "inventory": raw.get("inventory"),
        }

    @staticmethod
    def _normalize_channel_product(raw: dict) -> dict:
        oms_product_info = raw.get("omsProductInfo") or {}
        publish_result = raw.get("publishResult") or {}
        sku_info_list = oms_product_info.get("skuInfoList") or []
        oms_product = oms_product_info.get("spuInfo") or {}
        return {
            "channel_product_id": raw.get("id") or raw.get("productId") or raw.get("channelProductId"),
            "channel_code": raw.get("channelCode") or raw.get("channel_code") or raw.get("channel"),
            "channel_no": raw.get("channelNo") or raw.get("channel_no"),
            "channel_name": raw.get("channelName"),
            "shop_id": raw.get("shopId") or raw.get("storeId") or raw.get("shop_id"),
            "listing_status": raw.get("publishStatus") or raw.get("listingStatus") or raw.get("shelfState") or raw.get("listStatus"),
            "audit_status": raw.get("auditStatus") or raw.get("auditState"),
            "audit_status_desc": raw.get("auditStatusDesc") or raw.get("auditStateDesc"),
            "sync_status": raw.get("syncStatus"),
            "title": raw.get("title") or raw.get("productName") or raw.get("name") or oms_product.get("itemName"),
            "publish_success": publish_result.get("success") if isinstance(publish_result, dict) else None,
            "last_error": (
                publish_result.get("errorMessage")
                if isinstance(publish_result, dict)
                else None
            ) or raw.get("errorMessage") or raw.get("lastError") or raw.get("message"),
            "validation_errors": publish_result.get("validationErrors", []) if isinstance(publish_result, dict) else [],
            "oms_product": ChannelProductApiAdapter._normalize_oms_product(oms_product) if oms_product else {},
            "oms_skus": [ChannelProductApiAdapter._normalize_oms_sku(sku) for sku in sku_info_list if isinstance(sku, dict)],
            "raw": raw,
        }
