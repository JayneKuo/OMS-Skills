"""寻仓推荐引擎 — 数据加载层

从 OMS API 加载仓库列表、库存、订单详情，映射为引擎内部模型。
复用 oms_query_engine 的 API client，不重复认证。
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# 确保 oms_query_engine 可导入
_oms_scripts = str(Path(__file__).resolve().parents[3] / "oms-query" / "scripts")
if _oms_scripts not in sys.path:
    sys.path.insert(0, _oms_scripts)

from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.config import EngineConfig

from .models import Address, AllocationRequest, OrderItem, Warehouse

# ── API 路径 ──────────────────────────────────────────────

WAREHOUSE_LIST_API = "/opc/app-api/facility/v2/page"
INVENTORY_LIST_API = "/opc/app-api/inventory/list"
ORDER_DETAIL_API = "/opc/app-api/sale-order/{orderNo}"


# ── 辅助函数 ──────────────────────────────────────────────

def _extract_list(data) -> list:
    """从 API 响应 data 字段中提取列表。"""
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


def _get_data(resp: dict | None):
    """从 API 响应中提取 data 字段。"""
    if resp is None:
        return None
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp


# ── DataLoader ────────────────────────────────────────────


class DataLoader:
    """从 OMS API 加载仓库、库存、订单数据并映射为引擎模型。

    Parameters
    ----------
    oms_engine : object, optional
        OMSQueryEngine (v2) 实例。如果提供，复用其 ``_client`` 和 ``_config``。
    config : EngineConfig, optional
        当不传 oms_engine 时，用此配置创建独立 API client。
    """

    def __init__(self, oms_engine=None, config: EngineConfig | None = None):
        if oms_engine is not None:
            self._client: OMSAPIClient = oms_engine._client
            self._config: EngineConfig = oms_engine._config
        else:
            self._config = config or EngineConfig()
            self._client = OMSAPIClient(self._config)

    # ── 主入口 ────────────────────────────────────────

    def load(
        self, request: AllocationRequest
    ) -> tuple[list[Warehouse], list[OrderItem], Address, list[str]]:
        """加载寻仓所需的全部数据。

        Returns
        -------
        warehouses : list[Warehouse]
            含库存快照的仓库列表。
        items : list[OrderItem]
            订单商品行。
        address : Address
            收货地址。
        degradation_markers : list[str]
            数据降级标记。
        """
        degradation: list[str] = []

        # 1. 解析订单商品行和收货地址
        items, address = self._resolve_items_and_address(request, degradation)

        # 2. 验证必要数据
        if not items:
            raise ValueError("订单商品行为空，无法进行寻仓推荐")
        if address is None:
            raise ValueError("收货地址为空，无法进行寻仓推荐")

        # 3. 加载仓库列表
        warehouses = self._load_warehouses(request.merchant_no, degradation)

        # 4. 加载库存并合并到仓库
        self._merge_inventory(warehouses, request.merchant_no, degradation)

        return warehouses, items, address, degradation

    # ── 订单/商品/地址解析 ────────────────────────────

    def _resolve_items_and_address(
        self,
        request: AllocationRequest,
        degradation: list[str],
    ) -> tuple[list[OrderItem], Address | None]:
        """从请求或 API 获取商品行和收货地址。"""
        items = request.items
        address = request.shipping_address

        # 如果有 order_no 且缺少 items 或 address，从 API 补充
        if request.order_no and (not items or address is None):
            api_items, api_address = self._fetch_order_details(
                request.order_no, degradation
            )
            if not items:
                items = api_items
            if address is None:
                address = api_address

        return items or [], address

    def _fetch_order_details(
        self,
        order_no: str,
        degradation: list[str],
    ) -> tuple[list[OrderItem], Address | None]:
        """调用 sale-order API 获取订单详情。"""
        items: list[OrderItem] = []
        address: Address | None = None

        try:
            path = ORDER_DETAIL_API.format(orderNo=order_no)
            resp = self._client.get(path)
            detail = _get_data(resp)
            if not detail:
                return items, address

            # 提取商品行
            items_raw = (
                detail.get("itemLines")
                or detail.get("items")
                or detail.get("orderItems")
                or []
            )
            for item in items_raw:
                sku = item.get("sku", "")
                qty = item.get("qty", 0) or item.get("quantity", 0)
                weight = item.get("weight")
                if sku and qty > 0:
                    items.append(OrderItem(
                        sku=sku,
                        quantity=int(qty),
                        weight=float(weight) if weight else None,
                    ))

            # 提取收货地址
            addr_raw = detail.get("shipToAddress")
            if addr_raw:
                address = Address(
                    country=addr_raw.get("country", ""),
                    state=addr_raw.get("state"),
                    city=addr_raw.get("city"),
                    zipcode=addr_raw.get("zipCode") or addr_raw.get("zipcode"),
                )
        except Exception as e:
            degradation.append(f"order_fetch_failed={e}")

        return items, address

    # ── 仓库加载 ──────────────────────────────────────

    def _load_warehouses(
        self,
        merchant_no: str,
        degradation: list[str],
    ) -> list[Warehouse]:
        """调用 facility/v2/page API 加载仓库列表。"""
        warehouses: list[Warehouse] = []
        try:
            resp = self._client.post(
                WAREHOUSE_LIST_API,
                {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 100},
            )
            data = _get_data(resp)
            raw_list = _extract_list(data)

            for w in raw_list:
                wh = self._map_warehouse(w)
                if wh is not None:
                    warehouses.append(wh)
        except Exception as e:
            degradation.append(f"warehouse_fetch_failed={e}")

        return warehouses

    @staticmethod
    def _map_warehouse(w: dict) -> Warehouse | None:
        """将 API 仓库数据映射为 Warehouse 模型。"""
        warehouse_id = w.get("warehouseId") or w.get("id") or ""
        accounting_code = w.get("accountingCode") or ""
        if not warehouse_id and not accounting_code:
            return None

        status = (w.get("status") or "").upper()
        fulfillment_switch = w.get("fulfillmentSwitch")
        inventory_switch = w.get("inventorySwitch")

        return Warehouse(
            warehouse_id=str(warehouse_id),
            warehouse_name=w.get("facility_name") or w.get("facilityName") or "",
            accounting_code=accounting_code,
            country=w.get("country") or "",
            state=w.get("state"),
            city=w.get("city"),
            zipcode=w.get("zipCode") or w.get("zipcode"),
            is_active=status == "ENABLE",
            fulfillment_enabled=bool(fulfillment_switch),
            inventory_enabled=bool(inventory_switch),
            daily_capacity=w.get("dailyCapacity"),
            current_load=w.get("currentLoad"),
        )

    # ── 库存加载与合并 ────────────────────────────────

    def _merge_inventory(
        self,
        warehouses: list[Warehouse],
        merchant_no: str,
        degradation: list[str],
    ) -> None:
        """加载库存并按 SKU + warehouse_id 合并到仓库对象。"""
        if not warehouses:
            return

        # 构建 accounting_code → Warehouse 映射（API 库存可能用 warehouseNo 对应 accountingCode）
        code_map: dict[str, Warehouse] = {}
        id_map: dict[str, Warehouse] = {}
        for wh in warehouses:
            if wh.accounting_code:
                code_map[wh.accounting_code] = wh
            if wh.warehouse_id:
                id_map[wh.warehouse_id] = wh

        try:
            resp = self._client.post(
                INVENTORY_LIST_API,
                {"merchantNo": merchant_no},
            )
            data = _get_data(resp)
            inv_items = _extract_list(data)

            for item in inv_items:
                sku = item.get("sku", "")
                if not sku:
                    continue

                on_hand = item.get("onHandQty") or item.get("onHand") or 0
                qty = int(on_hand)

                # 尝试多种字段名匹配仓库
                wh_no = (
                    item.get("warehouseNo")
                    or item.get("warehouseId")
                    or item.get("accountingCode")
                    or ""
                )
                wh_no = str(wh_no)

                # 先按 accounting_code 匹配，再按 warehouse_id 匹配
                target = code_map.get(wh_no) or id_map.get(wh_no)
                if target is not None:
                    target.inventory[sku] = target.inventory.get(sku, 0) + qty

            # 记录降级标记：使用 onHandQty 近似 availableQty
            degradation.append("inventory_degraded=true")

        except Exception as e:
            degradation.append(f"inventory_fetch_failed={e}")
            degradation.append("inventory_degraded=true")

    # ── 路由规则加载 ──────────────────────────────────

    def load_routing_rules(self, merchant_no: str) -> list[dict]:
        """加载商户的路由规则配置。"""
        try:
            resp = self._client.get(
                "/opc/app-api/routing/v2/rules",
                {"merchantNo": merchant_no},
            )
            data = _get_data(resp)
            return _extract_list(data) if isinstance(data, list) else [data] if isinstance(data, dict) else []
        except Exception:
            return []

    def load_sku_warehouse_rules(self, merchant_no: str) -> list[dict]:
        """加载 SKU 指定仓规则（sku-warehouse/page）。"""
        try:
            resp = self._client.post(
                "/opc/app-api/sku-warehouse/page",
                {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 500},
            )
            data = _get_data(resp)
            return _extract_list(data)
        except Exception:
            return []
