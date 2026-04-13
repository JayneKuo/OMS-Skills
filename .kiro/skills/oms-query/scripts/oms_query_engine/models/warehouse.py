"""仓库域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class WarehouseInfo(BaseModel):
    allocated_warehouse: str | None = None
    warehouse_no: str | None = None
    warehouse_name: str | None = None
    warehouse_type: str | None = None
    warehouse_accounting_code: str | None = None
    warehouse_address: str | None = None
    warehouse_capabilities: list[str] | None = None
    warehouse_constraints: list[str] | None = None
    warehouse_status_desc: str | None = None
