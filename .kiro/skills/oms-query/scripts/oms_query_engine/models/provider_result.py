"""Provider 统一返回结构"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class ProviderResult(BaseModel):
    """Provider 统一返回结构。"""
    provider_name: str
    success: bool = False
    data: Any = None
    called_apis: list[str] = Field(default_factory=list)
    failed_apis: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
