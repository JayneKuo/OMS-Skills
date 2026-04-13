"""事件域输出模型"""
from __future__ import annotations
from pydantic import BaseModel, Field


class EventInfo(BaseModel):
    timeline: list[dict] | None = None
    latest_event_type: str | None = None
    latest_event_time: str | None = None
    latest_exception_event: str | None = None
    latest_hold_event: str | None = None
    order_logs: list[dict] | None = None


class MilestoneTimes(BaseModel):
    order_created_time: str | None = None
    order_imported_time: str | None = None
    allocated_time: str | None = None
    warehouse_received_time: str | None = None
    warehouse_processing_start_time: str | None = None
    picked_time: str | None = None
    packed_time: str | None = None
    loaded_time: str | None = None
    shipped_time: str | None = None
    actual_delivery_time: str | None = None
    latest_update_time: str | None = None


class DurationMetrics(BaseModel):
    order_age_minutes: int | None = None
    warehouse_processing_minutes: int | None = None
    hold_duration_minutes: int | None = None
    exception_duration_minutes: int | None = None
    time_to_allocate_minutes: int | None = None
    time_to_release_to_warehouse_minutes: int | None = None
    time_to_ship_minutes: int | None = None
    time_in_transit_minutes: int | None = None
