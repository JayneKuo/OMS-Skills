"""同步域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class SyncTarget(BaseModel):
    target_system: str | None = None
    target_store: str | None = None
    sync_object: str | None = None
    sync_status: str | None = None
    sync_time: str | None = None
    external_reference_no: str | None = None
    sync_result_message: str | None = None


class ShipmentSyncInfo(BaseModel):
    sync_targets: list[SyncTarget] | None = None
    all_sync_success: bool | None = None
    last_sync_time: str | None = None
    failed_sync_targets: list[str] | None = None
