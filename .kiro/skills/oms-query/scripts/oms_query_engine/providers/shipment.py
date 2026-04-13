"""ShipmentProvider - 发运追踪域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.shipment import ShipmentInfo, TrackingProgressInfo
from .base import BaseProvider

TRACKING_DETAIL = "/api/linker-oms/opc/app-api/tracking-assistant/{orderNo}"
TRACKING_STATUS = "/api/linker-oms/opc/app-api/tracking-assistant/tracking-status/{orderNo}"


class ShipmentProvider(BaseProvider):
    """发运、追踪、ETA、签收。"""

    name = "shipment"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        order_no = context.order_no or context.primary_key
        if not order_no:
            result.errors.append("缺少 orderNo")
            return result

        td = ts = None

        # tracking detail
        try:
            path = TRACKING_DETAIL.format(orderNo=order_no)
            resp = self._fetch_get(path, f"tracking:{order_no}", QueryCache.TTL_ORDER)
            td = self._get_data(resp)
            result.called_apis.append(path)
        except Exception as e:
            result.failed_apis.append("tracking_detail")
            result.errors.append(f"tracking detail: {e}")

        # tracking status
        try:
            path = TRACKING_STATUS.format(orderNo=order_no)
            resp = self._fetch_get(path, f"track_status:{order_no}", 30)
            ts = self._get_data(resp)
            result.called_apis.append(path)
        except Exception as e:
            result.failed_apis.append("tracking_status")
            result.errors.append(f"tracking status: {e}")

        shipment_info = ShipmentInfo()
        tracking_info = TrackingProgressInfo()

        # 先从订单详情中提取承运商信息（兜底）
        od = context.order_detail
        if od:
            shipment_info.carrier_name = od.get("carrierName")
            shipment_info.carrier_scac = od.get("carrierScac") or od.get("carrier")
            shipment_info.delivery_service = od.get("deliveryService") or od.get("shippingService")

        # tracking detail 覆盖（更准确）
        if isinstance(td, dict):
            shipment_info.shipment_no = td.get("shipmentNo")
            shipment_info.carrier_name = td.get("carrierName")
            shipment_info.carrier_scac = td.get("carrierScac")
            shipment_info.delivery_service = td.get("deliveryService")
            shipment_info.tracking_no = td.get("trackingNo")
            shipment_info.shipment_status = td.get("shipmentStatus")
            shipment_info.shipped_time = td.get("shippedTime")
            shipment_info.estimated_delivery_time = td.get("estimatedDeliveryTime")

        if isinstance(ts, dict):
            tracking_info.current_tracking_status = ts.get("status")
            tracking_info.current_tracking_desc = ts.get("statusDesc")
            tracking_info.is_delivered = ts.get("isDelivered")
            events = ts.get("events") or ts.get("trackingEvents") or []
            tracking_info.tracking_events = events or None
            if events:
                latest = events[0]
                tracking_info.latest_tracking_event = latest.get("description")
                tracking_info.latest_tracking_event_time = latest.get("eventTime")
                tracking_info.latest_tracking_location = latest.get("location")

        result.success = td is not None or ts is not None
        result.data = {
            "shipment_info": shipment_info,
            "tracking_progress_info": tracking_info,
        }
        return result
