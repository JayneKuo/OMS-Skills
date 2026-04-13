"""发运域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class ShipmentInfo(BaseModel):
    shipment_no: str | None = None
    fulfillment_order_no: str | None = None
    warehouse_order_no: str | None = None
    carrier_name: str | None = None
    carrier_scac: str | None = None
    carrier_service_code: str | None = None
    carrier_service_name: str | None = None
    delivery_service: str | None = None
    tracking_no: str | None = None
    pro_no: str | None = None
    bol_no: str | None = None
    shipment_status: str | None = None
    shipment_status_desc: str | None = None
    shipped_time: str | None = None
    estimated_delivery_time: str | None = None
    actual_delivery_time: str | None = None
    signed_by: str | None = None
    package_count: int | None = None


class TrackingProgressInfo(BaseModel):
    current_tracking_status: str | None = None
    current_tracking_desc: str | None = None
    latest_tracking_event_time: str | None = None
    latest_tracking_location: str | None = None
    latest_tracking_event: str | None = None
    estimated_delivery_time: str | None = None
    delivery_attempt_count: int | None = None
    is_delivered: bool | None = None
    is_exception_in_transit: bool | None = None
    tracking_events: list[dict] | None = None
