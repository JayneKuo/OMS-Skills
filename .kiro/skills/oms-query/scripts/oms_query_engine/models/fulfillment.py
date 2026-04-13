"""履约域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class WarehouseExecutionInfo(BaseModel):
    warehouse_no: str | None = None
    warehouse_name: str | None = None
    warehouse_order_no: str | None = None
    fulfillment_order_no: str | None = None
    shipment_no: str | None = None
    package_no_list: list[str] | None = None


class WarehouseStatusInfo(BaseModel):
    warehouse_process_status: str | None = None
    warehouse_status_desc: str | None = None
    warehouse_received_time: str | None = None
    warehouse_processing_start_time: str | None = None
    picked_time: str | None = None
    packed_time: str | None = None
    loaded_time: str | None = None
    shipped_time: str | None = None
