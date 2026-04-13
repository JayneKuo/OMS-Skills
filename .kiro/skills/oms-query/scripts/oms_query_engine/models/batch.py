"""批量域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class BatchQueryResult(BaseModel):
    """批量查询结果。"""
    status_counts: dict[str, int] | None = None
    orders: list[dict] | None = None
    total: int = 0
    page_no: int = 1
    page_size: int = 20
