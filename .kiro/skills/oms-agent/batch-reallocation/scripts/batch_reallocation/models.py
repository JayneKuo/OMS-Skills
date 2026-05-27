from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Scenario = Literal["imported", "exception", "deallocated", "on_hold", "ineligible"]
ActionMode = Literal["whole_order", "partial_sku", "release_hold_then_recover"]


class OrderInput(BaseModel):
    raw_identifier: str
    order_no: str | None = None


class SkuCandidate(BaseModel):
    sku: str
    ordered_qty: int = 0
    fulfilled_qty: int = 0
    unfulfilled_qty: int = 0
    hold_qty: int = 0
    selected: bool = False
    eligible: bool = False
    reason: str | None = None


class OrderCandidate(BaseModel):
    order_no: str
    scenario: Scenario
    status: str
    eligible: bool
    reason: str | None = None
    exception_summary: str | None = None
    hold_reason: str | None = None
    skus: list[SkuCandidate] = Field(default_factory=list)


class FormGroup(BaseModel):
    scenario: Scenario
    title: str
    selection_mode: Literal["order", "sku"]
    orders: list[OrderCandidate] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    identifiers: list[str]
    merchant_no: str | None = None


class AnalyzeResponse(BaseModel):
    form_type: Literal["batch-reallocation-analysis"] = "batch-reallocation-analysis"
    groups: list[FormGroup] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    next_action: str = "collect_user_decision"


class OrderDecision(BaseModel):
    order_no: str
    action_mode: ActionMode
    selected_skus: list[str] = Field(default_factory=list)
    release_hold: bool = False


class ExecuteRequest(BaseModel):
    confirmed: bool = False
    decisions: list[OrderDecision]
    merchant_no: str | None = None


class ExecuteResponse(BaseModel):
    submitted_orders: int = 0
    succeeded_orders: list[str] = Field(default_factory=list)
    partial_succeeded_orders: list[str] = Field(default_factory=list)
    failed_orders: dict[str, str] = Field(default_factory=dict)
    skipped_orders: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
