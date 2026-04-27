"""WarehouseProvider - 仓库域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.warehouse import WarehouseInfo
from .base import BaseProvider

WAREHOUSE_LIST = "/opc/app-api/facility/v2/page"


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


class WarehouseProvider(BaseProvider):
    """仓库列表、能力、限制、地址、时区。"""

    name = "warehouse"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        merchant_no = context.merchant_no
        if not merchant_no:
            result.errors.append("缺少 merchantNo")
            return result

        try:
            resp = self._fetch_post(
                WAREHOUSE_LIST,
                {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 100},
                f"warehouses:{merchant_no}", QueryCache.TTL_STATIC,
            )
            data = self._get_data(resp)
            result.called_apis.append(WAREHOUSE_LIST)
        except Exception as e:
            result.errors.append(f"warehouse: {e}")
            result.failed_apis.append(WAREHOUSE_LIST)
            return result

        warehouses = _extract_list(data)

        # 从订单详情中提取已分配仓库
        detail = context.order_detail
        allocated_code = detail.get("warehouseCode") or detail.get("accountingCode") if detail else None
        allocated_name = None

        # 匹配已分配仓库的详细信息
        wh_info = WarehouseInfo(
            allocated_warehouse=allocated_code,
        )

        for w in warehouses:
            ac = w.get("accountingCode", "")
            if allocated_code and ac == allocated_code:
                wh_info.warehouse_no = w.get("warehouseId")
                wh_info.warehouse_name = w.get("facility_name")
                wh_info.warehouse_type = w.get("type")
                wh_info.warehouse_accounting_code = ac
                wh_info.warehouse_address = _build_address(w)
                wh_info.warehouse_capabilities = _extract_capabilities(w)
                wh_info.warehouse_constraints = _extract_constraints(w)
                wh_info.warehouse_status_desc = w.get("status")
                break

        # 如果没有匹配到已分配仓库但有仓库列表，至少填充第一个
        if not wh_info.warehouse_name and warehouses:
            w = warehouses[0]
            wh_info.warehouse_name = w.get("facility_name")
            wh_info.warehouse_no = w.get("warehouseId")

        result.success = True
        result.data = {
            "warehouse_info": wh_info,
            "raw_warehouses": warehouses,
        }
        return result


def _build_address(w: dict) -> str | None:
    parts = [w.get("address1"), w.get("city"), w.get("state"), w.get("zipCode"), w.get("country")]
    addr = ", ".join(p for p in parts if p)
    return addr or None


def _extract_capabilities(w: dict) -> list[str] | None:
    caps = []
    if w.get("fulfillmentSwitch"):
        caps.append("履约")
    if w.get("inventorySwitch"):
        caps.append("库存管理")
    ver = w.get("warehouseVersion")
    if ver and ver != "UNASSIGNED":
        caps.append(f"WMS: {ver}")
    tz = w.get("time_zone")
    if tz:
        caps.append(f"时区: {tz}")
    wms_list = w.get("wmsVersionList", [])
    if wms_list:
        caps.append(f"支持版本: {', '.join(wms_list)}")
    return caps or None


def _extract_constraints(w: dict) -> list[str] | None:
    constraints = []
    zr = w.get("zipcodeRange")
    if zr:
        constraints.append(f"邮编范围: {zr}")
    if w.get("status") != "ENABLE":
        constraints.append(f"状态: {w.get('status', '未知')}")
    return constraints or None
