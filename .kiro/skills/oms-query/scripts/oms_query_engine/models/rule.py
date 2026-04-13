"""规则域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class RuleInfo(BaseModel):
    routing_rules: list[dict] | None = None
    custom_rules: list[dict] | None = None
    hold_rules: list[dict] | None = None
    sku_warehouse_rules: list[dict] | None = None
    mapping_rules: list[dict] | None = None
