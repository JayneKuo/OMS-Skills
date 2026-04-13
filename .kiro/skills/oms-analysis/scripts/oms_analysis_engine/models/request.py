"""请求模型"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start: datetime
    end: datetime


class AnalysisIntent(BaseModel):
    intent_type: str
    confidence: float = 1.0
    parameters: dict = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    identifier: str | None = None
    merchant_no: str | None = None
    intent: str | None = None
    query: str | None = None
    time_range: TimeRange | None = None
    filters: dict = Field(default_factory=dict)
