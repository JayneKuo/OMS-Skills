"""InventoryProvider - 库存域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.inventory import InventoryInfo, SkuInventoryItem
from .base import BaseProvider

INVENTORY_LIST = "/api/linker-oms/opc/app-api/inventory/list"
INVENTORY_MOVEMENT = "/api/linker-oms/opc/app-api/inventory/movement-history"


def _extract_list(data) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


class InventoryProvider(BaseProvider):
    """SKU 库存、可用库存、库存变动。"""

    name = "inventory"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        merchant_no = context.merchant_no or "LAN0000002"

        # 1. 库存列表
        inv_items = []
        try:
            resp = self._fetch_post(
                INVENTORY_LIST,
                {"merchantNo": merchant_no},
                f"inventory:{merchant_no}", QueryCache.TTL_STATIC,
            )
            data = self._get_data(resp)
            result.called_apis.append(INVENTORY_LIST)
            inv_items = _extract_list(data)
        except Exception as e:
            result.errors.append(f"inventory: {e}")
            result.failed_apis.append(INVENTORY_LIST)
            return result        # 2. 库存变动（如果有具体 SKU）
        movement_summary = None
        if context.skus:
            try:
                resp = self._fetch_post(
                    INVENTORY_MOVEMENT,
                    {"merchantNo": merchant_no, "skus": context.skus[:5]},
                    f"inv_movement:{merchant_no}:{','.join(context.skus[:3])}", 60,
                )
                mv_data = self._get_data(resp)
                result.called_apis.append(INVENTORY_MOVEMENT)
                mv_list = _extract_list(mv_data)
                if mv_list:
                    movement_summary = f"最近 {len(mv_list)} 条库存变动记录"
            except Exception as e:
                result.failed_apis.append(INVENTORY_MOVEMENT)
                result.errors.append(f"inventory movement: {e}")

        # 构建结构化库存
        sku_inventory = []
        for item in inv_items:
            sku_inventory.append(SkuInventoryItem(
                sku=item.get("sku", ""),
                warehouse_no=item.get("warehouseNo") or item.get("warehouseId"),
                warehouse_name=item.get("warehouseName") or item.get("facilityName"),
                available_qty=item.get("availableQty") or item.get("available"),
                on_hand_qty=item.get("onHandQty") or item.get("onHand"),
                reserved_qty=item.get("reservedQty") or item.get("reserved"),
            ))

        # 按 SKU 过滤（如果有指定 SKU）
        if context.skus:
            target_skus = set(s.upper() for s in context.skus)
            filtered = [i for i in sku_inventory if i.sku.upper() in target_skus]
            if filtered:
                sku_inventory = filtered

        total_available = sum(i.available_qty or 0 for i in sku_inventory)
        total_on_hand = sum(i.on_hand_qty or 0 for i in sku_inventory)

        result.success = True
        result.data = {
            "inventory_info": InventoryInfo(
                sku_inventory=sku_inventory or None,
                inventory_summary=f"共 {len(sku_inventory)} 条库存记录，可用 {total_available}，实物 {total_on_hand}",
                inventory_movement_summary=movement_summary,
            ),
        }
        return result
