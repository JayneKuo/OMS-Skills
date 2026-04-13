"""标识解析模型"""
from __future__ import annotations
from pydantic import BaseModel


class QueryInput(BaseModel):
    """记录标识解析过程。"""
    input_value: str
    identified_type: str | None = None
    primary_object_type: str | None = None  # order / sku / warehouse / connector / rule / batch
    resolved_primary_key: str | None = None
    candidate_matches: list[str] | None = None
    # 向后兼容
    resolved_order_no: str | None = None


class ResolveResult(BaseModel):
    """标识解析结果。"""
    success: bool
    query_input: QueryInput | None = None
    candidates: list[str] | None = None
    error: dict | None = None
