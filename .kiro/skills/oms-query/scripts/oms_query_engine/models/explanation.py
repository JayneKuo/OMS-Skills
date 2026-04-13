"""查询级解释模型"""
from __future__ import annotations
from pydantic import BaseModel


class QueryExplanation(BaseModel):
    current_step: str | None = None
    why_hold: str | None = None
    why_exception: str | None = None
    why_deallocated: str | None = None
    why_this_warehouse: str | None = None
    hold_impact: str | None = None
    release_hint: str | None = None
    shipment_summary: str | None = None
    sync_summary: str | None = None
    integration_summary: str | None = None


class HoldDetailInfo(BaseModel):
    is_on_hold: bool | None = None
    hold_status: str | None = None
    hold_reason_code: str | None = None
    hold_reason_name: str | None = None
    hold_reason_desc: str | None = None
    hold_source: str | None = None
    hold_rule_id: str | None = None
    hold_rule_name: str | None = None
    hold_rule_type: str | None = None
    hold_start_time: str | None = None
    hold_duration_minutes: int | None = None
    hold_operator: str | None = None
    hold_scope: str | None = None
    release_condition: str | None = None
    release_hint: str | None = None


class ExceptionDetailInfo(BaseModel):
    is_in_exception: bool | None = None
    exception_stage: str | None = None
    exception_code: str | None = None
    exception_type: str | None = None
    exception_reason: str | None = None
    exception_event_id: str | None = None
    exception_start_time: str | None = None
    exception_duration_minutes: int | None = None
    latest_failed_step: str | None = None
    latest_failed_action: str | None = None
    latest_error_message: str | None = None
    recoverable_hint: str | None = None
