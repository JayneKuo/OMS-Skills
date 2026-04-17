"""寻仓推荐引擎（allocation_engine）

根据订单目的地、SKU 库存、仓库能力和业务规则，输出最优发货仓推荐。
"""

from .models import (
    Address,
    AllocationRequest,
    AllocationResult,
    EliminatedWarehouse,
    FulfillmentPlan,
    OrderItem,
    ScoredWarehouse,
    ScoringWeights,
    Warehouse,
    WarehouseAssignment,
)
from .distance import (
    get_distance,
    estimate_cost,
    estimate_days,
    haversine,
)
from .data_loader import DataLoader
from .p0_filter import P0Filter
from .p2_scorer import P2Scorer, normalize
from .plan_generator import PlanGenerator
from .result_builder import ResultBuilder
from .engine import WarehouseAllocationEngine

__all__ = [
    # models
    "Address",
    "AllocationRequest",
    "AllocationResult",
    "EliminatedWarehouse",
    "FulfillmentPlan",
    "OrderItem",
    "ScoredWarehouse",
    "ScoringWeights",
    "Warehouse",
    "WarehouseAssignment",
    # distance
    "get_distance",
    "estimate_cost",
    "estimate_days",
    "haversine",
    # data loader
    "DataLoader",
    # P0 filter
    "P0Filter",
    # P2 scorer
    "P2Scorer",
    "normalize",
    # plan generator
    "PlanGenerator",
    # result builder
    "ResultBuilder",
    # engine
    "WarehouseAllocationEngine",
]
