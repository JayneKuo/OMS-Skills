"""库存域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class SkuInventoryItem(BaseModel):
    sku: str
    warehouse_no: str | None = None
    warehouse_name: str | None = None
    available_qty: int | None = None
    on_hand_qty: int | None = None
    reserved_qty: int | None = None


class InventoryInfo(BaseModel):
    sku_inventory: list[SkuInventoryItem] | None = None
    inventory_summary: str | None = None
    inventory_movement_summary: str | None = None
