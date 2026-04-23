"""FulfillmentProvider - 履约执行域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.fulfillment import WarehouseExecutionInfo, WarehouseStatusInfo
from .base import BaseProvider

FULFILLMENT_ORDERS = "/api/linker-oms/opc/app-api/tracking-assistant/fulfillment-orders/{orderNo}"
SHIPMENT_PAGE = "/api/linker-oms/opc/app-api/shipment/page"


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


def _ts(val) -> str | None:
    """毫秒时间戳转可读字符串。"""
    if val is None:
        return None
    if isinstance(val, (int, float)) and val > 1000000000000:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(val / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(val) if val else None


class FulfillmentProvider(BaseProvider):
    """履约执行、仓内状态、仓内单号、包裹、时间节点。"""

    name = "fulfillment"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        order_no = context.order_no or context.primary_key
        if not order_no:
            result.errors.append("缺少 orderNo")
            return result

        fo_data = None
        shipment_data = None

        # 1. fulfillment orders
        try:
            path = FULFILLMENT_ORDERS.format(orderNo=order_no)
            resp = self._fetch_get(path, f"fulfillment:{order_no}", QueryCache.TTL_ORDER)
            fo_data = self._get_data(resp)
            result.called_apis.append(path)
        except Exception as e:
            result.failed_apis.append("fulfillment_orders")
            result.errors.append(f"fulfillment: {e}")

        # 2. shipment page（获取仓内单号和包裹信息）
        try:
            merchant_no = context.merchant_no
            if not merchant_no:
                result.errors.append("缺少 merchantNo")
                return result
            resp = self._fetch_get(
                SHIPMENT_PAGE, f"shipment_page:{order_no}", QueryCache.TTL_ORDER,
                params={"merchantNo": merchant_no, "orderNo": order_no, "pageNo": 1, "pageSize": 10},
            )
            shipment_data = self._get_data(resp)
            result.called_apis.append(SHIPMENT_PAGE)
        except Exception as e:
            result.failed_apis.append("shipment_page")

        fo_list = _extract_list(fo_data)
        shipment_list = _extract_list(shipment_data)

        # 构建仓内执行信息
        exec_info = WarehouseExecutionInfo()
        status_info = WarehouseStatusInfo()

        if fo_list:
            fo = fo_list[0]
            exec_info.fulfillment_order_no = fo.get("fulfillmentOrderNo") or fo.get("fulfillmentNo")
            exec_info.warehouse_order_no = fo.get("warehouseOrderNo") or fo.get("wmsOrderNo")
            exec_info.warehouse_no = fo.get("warehouseNo") or fo.get("warehouseCode")
            exec_info.warehouse_name = fo.get("warehouseName")
            exec_info.shipment_no = fo.get("shipmentNo")

            # 包裹列表
            packages = fo.get("packages") or fo.get("packageList") or []
            if packages:
                exec_info.package_no_list = [
                    p.get("packageNo") or p.get("trackingNo") or str(p)
                    for p in packages if isinstance(p, dict)
                ]

            # 仓内状态
            status_info.warehouse_process_status = fo.get("status") or fo.get("fulfillmentStatus")

        # 从 shipment 数据补充时间节点
        if shipment_list:
            ship = shipment_list[0]
            status_info.warehouse_received_time = _ts(ship.get("warehouseReceivedTime"))
            status_info.warehouse_processing_start_time = _ts(ship.get("processingStartTime"))
            status_info.picked_time = _ts(ship.get("pickedTime"))
            status_info.packed_time = _ts(ship.get("packedTime"))
            status_info.loaded_time = _ts(ship.get("loadedTime"))
            status_info.shipped_time = _ts(ship.get("shippedTime"))

            # 补充仓内单号
            if not exec_info.warehouse_order_no:
                exec_info.warehouse_order_no = ship.get("warehouseOrderNo") or ship.get("wmsOrderNo")
            if not exec_info.shipment_no:
                exec_info.shipment_no = ship.get("shipmentNo")

        # 从订单详情补充仓内状态
        detail = context.order_detail or {}
        wps = detail.get("warehouseProcessStatus") or detail.get("status")
        if wps and not status_info.warehouse_process_status:
            status_info.warehouse_process_status = str(wps)

        # 状态描述
        status_desc_map = {
            "WAREHOUSE_PROCESSING": "仓库处理中",
            "WAREHOUSE_RECEIVED": "仓库已收货",
            "PICKED": "已拣货",
            "PACKED": "已打包",
            "LOADED": "已装车",
            "SHIPPED": "已发货",
            "PARTIALLY_SHIPPED": "部分发货",
        }
        if status_info.warehouse_process_status:
            status_info.warehouse_status_desc = status_desc_map.get(
                str(status_info.warehouse_process_status).upper(),
                str(status_info.warehouse_process_status),
            )

        result.success = fo_data is not None or shipment_data is not None
        result.data = {
            "warehouse_execution_info": exec_info,
            "warehouse_status_info": status_info,
        }
        return result
