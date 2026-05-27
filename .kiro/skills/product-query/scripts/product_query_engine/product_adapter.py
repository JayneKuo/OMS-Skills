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


class ProductApiAdapter:
    def __init__(self, client):
        self._client = client

    def find_product(self, merchant_no: str | None, filters: dict) -> dict | None:
        self._client._ensure_token()
        product_id = filters.get("product_id") or filters.get("internal_item_id")
        if product_id and not filters.get("item_name"):
            return self.get_product_detail(product_id)

        result = self.search_products(merchant_no, dict(filters, page_no=1, page_size=10))
        products = result["products"]
        return products[0] if products else None

    def search_products(self, merchant_no: str | None, filters: dict) -> dict:
        self._client._ensure_token()
        page_no = int(filters.get("page_no") or filters.get("pageNo") or 1)
        page_size = int(filters.get("page_size") or filters.get("pageSize") or 10)
        params = {"merchantNo": merchant_no, "pageNo": page_no, "pageSize": page_size}
        field_mapping = {
            "sku": "sku",
            "spu": "spu",
            "item_name": "itemName",
            "seller_parent_sku": "sellerParentSku",
            "internal_sku_id": "internalSkuId",
            "internal_item_id": "internalItemId",
            "keyword": "keyword",
        }
        for source, target in field_mapping.items():
            if filters.get(source):
                params[target] = filters[source]
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/product/spu/page", params)
        data = response.get("data", response)
        rows = _extract_list(data)
        total = data.get("total") if isinstance(data, dict) else len(rows)
        if total is None:
            total = len(rows)
        return {
            "products": [self._normalize_product(row) for row in rows],
            "pagination": {
                "page_no": page_no,
                "page_size": page_size,
                "total": total,
                "has_more": page_no * page_size < total,
            },
        }

    def get_product_detail(self, product_id: str) -> dict | None:
        self._client._ensure_token()
        response = self._client.get(f"/api/linker-oms/baseservice/rpc-api/product/spu/get/{product_id}")
        data = response.get("data", response)
        return self._normalize_product(data) if isinstance(data, dict) else None

    @staticmethod
    def _normalize_sku(raw: dict) -> dict:
        return {
            "record_id": raw.get("id"),
            "internal_sku_id": raw.get("internalSkuId"),
            "seller_sku": raw.get("sellerSku"),
            "sku": raw.get("sku") or raw.get("sellerSku") or raw.get("internalSkuId"),
            "status": raw.get("status"),
            "price": raw.get("salesPrice") or raw.get("price"),
            "currency": raw.get("salesPriceUnit") or raw.get("currency"),
            "discount_price": raw.get("discountPrice"),
            "discount_currency": raw.get("discountPriceUnit"),
            "image_count": len(raw.get("imageInfo") or []),
            "raw": raw,
        }

    @staticmethod
    def _normalize_mapping(raw: dict) -> dict:
        return {
            "channel": raw.get("dataChannel") or raw.get("channel"),
            "channel_no": raw.get("channelNo") or raw.get("channel_no"),
            "external_sku_id": raw.get("externalSkuId"),
            "external_sku_code": raw.get("externalSkuCode"),
            "mapping_type": raw.get("mappingType"),
            "status": raw.get("status"),
            "raw": raw,
        }

    @staticmethod
    def _published_channels(raw_value) -> list[str]:
        if isinstance(raw_value, list):
            return [str(value) for value in raw_value if value]
        if isinstance(raw_value, str):
            return [value.strip() for value in raw_value.split(",") if value.strip()]
        return []

    @staticmethod
    def _normalize_product(raw: dict) -> dict:
        child_skus = raw.get("childSkus") or raw.get("skuList") or raw.get("skus") or raw.get("sku_list") or []
        mappings = raw.get("mappings") or []
        product_id = raw.get("productId") or raw.get("spuId")
        if product_id is None and isinstance(raw.get("id"), str):
            product_id = raw["id"]
        return {
            "record_id": raw.get("id"),
            "product_id": product_id,
            "internal_item_id": raw.get("internalItemId"),
            "seller_parent_sku": raw.get("sellerParentSku"),
            "spu": raw.get("spu") or raw.get("spuCode"),
            "title": raw.get("itemName") or raw.get("productName") or raw.get("title") or raw.get("name"),
            "brand": raw.get("brandName") or raw.get("brand"),
            "status": raw.get("status") or raw.get("productStatus"),
            "category": raw.get("categoryName") or raw.get("category"),
            "published_channels": ProductApiAdapter._published_channels(raw.get("publishedChannels")),
            "price": raw.get("salesPrice") or raw.get("price"),
            "currency": raw.get("salesPriceUnit") or raw.get("currency"),
            "discount_price": raw.get("discountPrice"),
            "discount_currency": raw.get("discountPriceUnit"),
            "image_count": len(raw.get("imageInfo") or []),
            "skus": [ProductApiAdapter._normalize_sku(sku) for sku in child_skus if isinstance(sku, dict)],
            "mapping": [ProductApiAdapter._normalize_mapping(mapping) for mapping in mappings if isinstance(mapping, dict)],
            "raw": raw,
        }
