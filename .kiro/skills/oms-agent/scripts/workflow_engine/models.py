"""Shipping Plan Workflow — 数据模型

定义物流方案推荐 workflow 的所有输入/输出 Pydantic 模型。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ShippingPlanRequest(BaseModel):
    """物流方案推荐请求"""
    order_no: str
    merchant_no: str
    carriers: list[str] = Field(default_factory=lambda: ["UPS Ground", "FedEx Ground", "USPS Priority"])
    risk_level: str = "P75"


class PipelineStep(BaseModel):
    """流水线单步执行状态"""
    step_name: str
    success: bool = False
    duration_ms: int = 0
    degraded: bool = False
    output_summary: str = ""
    error: str = ""


class PlanSummary(BaseModel):
    """单个物流方案摘要"""
    carrier: str = ""
    service_level: str = "Ground"
    freight: Decimal = Decimal("0")
    eta_hours: Decimal = Decimal("0")
    eta_days: Decimal = Decimal("0")
    on_time_prob: Decimal = Decimal("0")
    score: Decimal = Decimal("0")
    rank: int = 0
    explanation: str = ""


class OrderSummary(BaseModel):
    """订单摘要"""
    order_no: str = ""
    status: str = ""
    sku_count: int = 0
    item_count: int = 0
    skus: list[dict] = Field(default_factory=list)
    dest_country: str = ""
    dest_state: str = ""
    dest_city: str = ""
    origin_state: str = ""
    warehouse: str = ""


class PackageSummary(BaseModel):
    """包裹摘要"""
    package_count: int = 1
    total_weight_kg: Decimal = Decimal("0")
    billing_weight_kg: Decimal = Decimal("0")
    packages: list[dict] = Field(default_factory=list)


class ShippingPlanResult(BaseModel):
    """物流方案推荐结果"""
    success: bool = True
    order_summary: OrderSummary = Field(default_factory=OrderSummary)
    package_summary: PackageSummary = Field(default_factory=PackageSummary)
    plans: list[PlanSummary] = Field(default_factory=list)
    recommended_plan: PlanSummary | None = None
    pipeline_steps: list[PipelineStep] = Field(default_factory=list)
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    explanation: str = ""
    errors: list[str] = Field(default_factory=list)
