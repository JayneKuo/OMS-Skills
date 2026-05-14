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


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class InventoryAdapter:
    def __init__(self, client):
        self._client = client

    def fetch_sku_facts(self, merchant_no: str | None, sku: str | None) -> dict | None:
        if not sku:
            return None
        self._client._ensure_token()
        response = self._client.post(
            "/api/linker-oms/opc/app-api/inventory/list",
            {"merchantNo": merchant_no, "sku": sku},
        )
        rows = [
            row
            for row in _extract_list(response.get("data", response))
            if str(row.get("sku") or row.get("productSku") or "") == sku
        ]
        if not rows:
            return {"sku": sku, "inventory_records": 0}

        available_qty = sum(_number(row.get("availableQty") or row.get("availableQuantity")) for row in rows)
        on_hand_qty = sum(_number(row.get("onHandQty") or row.get("quantity") or row.get("qty")) for row in rows)
        first_price = next((row.get("price") or row.get("salePrice") for row in rows if row.get("price") or row.get("salePrice")), None)
        first_currency = next((row.get("currency") for row in rows if row.get("currency")), None)

        facts = {
            "sku": sku,
            "available_qty": int(available_qty) if available_qty.is_integer() else available_qty,
            "on_hand_qty": int(on_hand_qty) if on_hand_qty.is_integer() else on_hand_qty,
            "inventory_records": len(rows),
        }
        if first_price is not None:
            facts["price"] = _number(first_price)
        if first_currency:
            facts["currency"] = first_currency
        return facts
