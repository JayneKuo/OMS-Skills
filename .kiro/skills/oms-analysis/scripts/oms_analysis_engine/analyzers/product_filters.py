"""商品维度分析过滤工具"""
from __future__ import annotations
from typing import Any


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def order_channel(order: dict) -> str:
    return normalize(order.get("channelName") or order.get("dataChannel") or order.get("channel") or order.get("channelCode"))


def order_shop(order: dict) -> str:
    return normalize(order.get("shopId") or order.get("storeId") or order.get("shopCode") or order.get("storeCode"))


def order_items(order: dict) -> list[dict]:
    items = order.get("itemLines") or order.get("items") or []
    return items if isinstance(items, list) else []


def item_sku(item: dict) -> str:
    return normalize(item.get("sku") or item.get("productSku") or item.get("sellerSku"))


def order_matches_filters(order: dict, filters: dict) -> bool:
    sku = normalize(filters.get("sku"))
    channel = normalize(filters.get("channel_code") or filters.get("channel") or filters.get("channelName"))
    shop = normalize(filters.get("shop_id") or filters.get("shop") or filters.get("store_id"))

    if channel and order_channel(order) != channel:
        return False
    if shop and order_shop(order) != shop:
        return False
    if sku:
        items = order_items(order)
        if items:
            return any(item_sku(item) == sku for item in items)
        return normalize(order.get("product") or order.get("sku")) == sku
    return True


def matching_items(order: dict, filters: dict) -> list[dict]:
    sku = normalize(filters.get("sku"))
    items = order_items(order)
    if not sku:
        return items
    return [item for item in items if item_sku(item) == sku]
