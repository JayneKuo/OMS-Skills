"""寻仓推荐引擎 — 数据模型

定义 AllocationRequest（输入）、Warehouse（仓库）、AllocationResult（输出）等核心模型。
所有模型基于 pydantic BaseModel。
"""

from __future__ import annotations

from pydantic import BaseModel


# ── 输入模型 ──────────────────────────────────────────────


class OrderItem(BaseModel):
    """订单商品行"""
    sku: str
    quantity: int
    weight: float | None = None  # kg


class Address(BaseModel):
    """收货地址"""
    country: str
    state: str | None = None
    city: str | None = None
    zipcode: str | None = None


class ScoringWeights(BaseModel):
    """评分权重（三维，默认 cost=0.40, eta=0.35, capacity=0.25）"""
    cost: float = 0.40
    eta: float = 0.35
    capacity: float = 0.25


class AllocationRequest(BaseModel):
    """寻仓请求"""
    order_no: str | None = None
    merchant_no: str
    items: list[OrderItem] | None = None
    shipping_address: Address | None = None
    allow_split: bool = True
    max_split_warehouses: int = 3
    weights: ScoringWeights | None = None


# ── 仓库模型（从 API 映射）──────────────────────────────────


class Warehouse(BaseModel):
    """仓库信息（含库存快照）"""
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    country: str
    state: str | None = None
    city: str | None = None
    zipcode: str | None = None
    is_active: bool
    fulfillment_enabled: bool
    inventory_enabled: bool
    inventory: dict[str, int] = {}  # sku → onHandQty
    daily_capacity: int | None = None
    current_load: int | None = None


# ── 输出模型 ──────────────────────────────────────────────


class ScoredWarehouse(BaseModel):
    """通过 P0 并完成评分的候选仓"""
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    score: float
    score_breakdown: dict[str, float] = {}  # cost / eta / capacity
    can_fulfill_all: bool
    fulfillable_skus: list[str] = []
    missing_skus: list[str] = []


class EliminatedWarehouse(BaseModel):
    """未通过 P0 的淘汰仓"""
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    reasons: list[str]  # 可能有多条淘汰原因


class WarehouseAssignment(BaseModel):
    """方案中单个仓的分配详情"""
    warehouse_id: str
    warehouse_name: str
    accounting_code: str
    items: list[OrderItem]
    score: float
    score_breakdown: dict[str, float] = {}  # cost / eta / capacity
    estimated_cost: float | None = None
    estimated_days: float | None = None
    distance_km: float | None = None


class FulfillmentPlan(BaseModel):
    """履约方案（单仓直发 / 多仓拆发）"""
    plan_type: str  # single_warehouse / multi_warehouse
    assignments: list[WarehouseAssignment]
    total_score: float
    split_penalty: float = 0.0
    recommendation_reason: str = ""


class AllocationResult(BaseModel):
    """寻仓推荐结果（顶层输出）"""
    success: bool
    recommended_plan: FulfillmentPlan | None = None
    alternative_plans: list[FulfillmentPlan] = []
    candidate_warehouses: list[ScoredWarehouse] = []
    eliminated_warehouses: list[EliminatedWarehouse] = []
    confidence: str = "low"  # high / medium / low
    explanation: str = ""
    data_degradation: list[str] = []
    error: str | None = None
