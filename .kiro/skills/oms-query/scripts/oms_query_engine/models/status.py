"""状态模型"""
from __future__ import annotations
from pydantic import BaseModel


class StatusMapping(BaseModel):
    """状态码映射条目。"""
    main_status: str
    category: str
    is_exception: bool = False
    is_hold: bool = False
    is_deallocated: bool = False


class NormalizedStatus(BaseModel):
    """归一化后的状态。"""
    status_code: int | str
    main_status: str
    category: str
    is_exception: bool
    is_hold: bool
    is_deallocated: bool = False
