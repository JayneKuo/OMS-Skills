"""请求模型"""
from __future__ import annotations
from pydantic import BaseModel


class QueryRequest(BaseModel):
    """单对象查询请求。"""
    identifier: str
    query_intent: str = "status"
    force_refresh: bool = False


class BatchQueryRequest(BaseModel):
    """批量查询请求。"""
    query_type: str
    status_filter: int | None = None
    page_no: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_order: str | None = None
