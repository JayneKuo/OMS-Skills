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
        sku = filters.get("sku")
        spu = filters.get("spu")
        product_id = filters.get("product_id")
        if product_id:
            return self.get_product_detail(product_id)

        params = {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 10}
        if sku:
            params["sku"] = sku
        if spu:
            params["spu"] = spu
        response = self._client.get("/api/linker-oms/baseservice/rpc-api/product/spu/page", params)
        rows = _extract_list(response.get("data", response))
        if not rows:
            return None
        return self._normalize_product(rows[0])

    def get_product_detail(self, product_id: str) -> dict | None:
        self._client._ensure_token()
        response = self._client.get(f"/api/linker-oms/baseservice/rpc-api/product/spu/get/{product_id}")
        data = response.get("data", response)
        return self._normalize_product(data) if isinstance(data, dict) else None

    @staticmethod
    def _normalize_product(raw: dict) -> dict:
        return {
            "product_id": raw.get("id") or raw.get("productId") or raw.get("spuId"),
            "spu": raw.get("spu") or raw.get("spuCode"),
            "title": raw.get("productName") or raw.get("title") or raw.get("name"),
            "status": raw.get("status") or raw.get("productStatus"),
            "category": raw.get("categoryName") or raw.get("category"),
            "raw": raw,
        }
