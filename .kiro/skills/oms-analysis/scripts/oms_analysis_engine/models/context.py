"""分析上下文"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from .request import AnalysisRequest


class SamplingInfo(BaseModel):
    total_count: int
    sample_count: int
    sample_ratio: float
    method: str = "random"


class AnalysisContext(BaseModel):
    request: AnalysisRequest
    order_data: dict | None = None
    inventory_data: list[dict] = Field(default_factory=list)
    warehouse_data: list[dict] = Field(default_factory=list)
    rule_data: list[dict] = Field(default_factory=list)
    event_data: list[dict] = Field(default_factory=list)
    shipment_data: dict | None = None
    batch_orders: list[dict] = Field(default_factory=list)
    channel_data: list[dict] = Field(default_factory=list)
    status_counts: dict = Field(default_factory=dict)
    sampling_info: SamplingInfo | None = None

    def has_data(self, field: str) -> bool:
        val = getattr(self, field, None)
        if val is None:
            return False
        if isinstance(val, list):
            return len(val) > 0
        return True
