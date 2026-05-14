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
            ("sku", "sku"),
            ("spu", "spu"),
            ("product_id", "productId"),
            ("channel_code", "channel_code"),
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
            ("sku", "sku"),
            ("spu", "spu"),
            ("product_id", "productId"),
            ("channel_product_id", "productId"),
            ("channel_code", "channel_code"),
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
    def _normalize_channel_product(raw: dict) -> dict:
        return {
            "channel_product_id": raw.get("id") or raw.get("productId") or raw.get("channelProductId"),
            "channel_code": raw.get("channelCode") or raw.get("channel_code") or raw.get("channel"),
            "shop_id": raw.get("shopId") or raw.get("storeId") or raw.get("shop_id"),
            "listing_status": raw.get("publishStatus") or raw.get("listingStatus") or raw.get("shelfState"),
            "audit_status": raw.get("auditStatus") or raw.get("auditState"),
            "sync_status": raw.get("syncStatus"),
            "title": raw.get("title") or raw.get("productName") or raw.get("name"),
            "raw": raw,
        }
