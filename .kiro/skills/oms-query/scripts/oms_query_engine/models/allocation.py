"""分仓域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class AllocationInfo(BaseModel):
    allocation_status: str | None = None
    allocation_reason: str | None = None
    candidate_warehouses: list[dict] | None = None
    dispatch_strategies: list[str] | None = None
    filter_strategies: list[str] | None = None
    backup_strategy: str | None = None


class WarehouseDecisionExplanation(BaseModel):
    final_warehouse_no: str | None = None
    final_warehouse_name: str | None = None
    decision_summary: str | None = None
    decision_factors: list[str] | None = None
    candidate_warehouses: list[dict] | None = None
    filtered_out_warehouses: list[dict] | None = None


class DeallocationDetailInfo(BaseModel):
    is_deallocated: bool | None = None
    deallocated_time: str | None = None
    deallocated_reason: str | None = None
    deallocated_operator: str | None = None
    previous_warehouse_no: str | None = None
    previous_warehouse_name: str | None = None
    current_allocation_status: str | None = None
    candidate_warehouses: list[dict] | None = None
    reallocation_hint: str | None = None
