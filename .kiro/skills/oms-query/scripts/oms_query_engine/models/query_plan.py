"""查询计划模型"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    """查询计划。"""
    primary_object_type: str          # order / sku / warehouse / connector / rule / batch
    primary_key: str | None = None
    core_providers: list[str]         # 必须执行的 Provider 名称列表
    extended_providers: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class QueryContext(BaseModel):
    """传递给 Provider 的查询上下文。"""
    primary_key: str | None = None
    merchant_no: str | None = None
    order_no: str | None = None
    order_detail: dict | None = None
    event_ids: list[str] = Field(default_factory=list)
    skus: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
