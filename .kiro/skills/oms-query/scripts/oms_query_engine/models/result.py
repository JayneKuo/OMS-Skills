"""顶层输出模型"""
from __future__ import annotations
from pydantic import BaseModel, Field

from .resolve import QueryInput
from .order import (
    OrderIdentity, SourceInfo, OrderContext, CurrentStatus,
    ProductInfo, ShippingAddress,
)
from .inventory import InventoryInfo
from .warehouse import WarehouseInfo
from .allocation import AllocationInfo, WarehouseDecisionExplanation, DeallocationDetailInfo
from .rule import RuleInfo
from .fulfillment import WarehouseExecutionInfo, WarehouseStatusInfo
from .shipment import ShipmentInfo, TrackingProgressInfo
from .sync import ShipmentSyncInfo
from .event import EventInfo, MilestoneTimes, DurationMetrics
from .integration import IntegrationInfo
from .explanation import QueryExplanation, HoldDetailInfo, ExceptionDetailInfo


class DataCompleteness(BaseModel):
    completeness_level: str = "minimal"
    missing_fields: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


class OMSQueryResult(BaseModel):
    """OMS 全域查询标准化输出。"""
    query_input: QueryInput

    # 订单域
    order_identity: OrderIdentity | None = None
    source_info: SourceInfo | None = None
    order_context: OrderContext | None = None
    current_status: CurrentStatus | None = None
    product_info: ProductInfo | None = None
    shipping_address: ShippingAddress | None = None

    # 库存域
    inventory_info: InventoryInfo | None = None

    # 仓库域
    warehouse_info: WarehouseInfo | None = None

    # 履约域
    warehouse_execution_info: WarehouseExecutionInfo | None = None
    warehouse_status_info: WarehouseStatusInfo | None = None

    # 发运域
    shipment_info: ShipmentInfo | None = None
    tracking_progress_info: TrackingProgressInfo | None = None

    # 同步域
    shipment_sync_info: ShipmentSyncInfo | None = None

    # 分仓域
    allocation_info: AllocationInfo | None = None
    warehouse_decision_explanation: WarehouseDecisionExplanation | None = None

    # 状态专项
    hold_detail_info: HoldDetailInfo | None = None
    exception_detail_info: ExceptionDetailInfo | None = None
    deallocation_detail_info: DeallocationDetailInfo | None = None

    # 规则域
    rule_info: RuleInfo | None = None

    # 集成域
    integration_info: IntegrationInfo | None = None

    # 事件域
    event_info: EventInfo | None = None
    milestone_times: MilestoneTimes | None = None
    duration_metrics: DurationMetrics | None = None

    # 解释与完整度
    query_explanation: QueryExplanation | None = None
    data_completeness: DataCompleteness = Field(default_factory=DataCompleteness)

    # 错误
    error: dict | None = None
