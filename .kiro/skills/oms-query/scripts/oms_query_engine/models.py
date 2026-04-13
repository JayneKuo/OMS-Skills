"""订单全景查询引擎 - 所有 Pydantic v2 数据模型"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── 请求模型 ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    """单订单查询请求。"""
    identifier: str
    query_intent: str = "status"
    force_refresh: bool = False


class BatchQueryRequest(BaseModel):
    """批量查询请求。"""
    query_type: str
    status_filter: int | None = None
    page_no: int = 1
    page_size: int = 20


# ── 标识解析模型 ──────────────────────────────────────────

class QueryInput(BaseModel):
    """记录标识解析过程。"""
    input_value: str
    identified_type: str | None = None
    resolved_order_no: str | None = None


class ResolveResult(BaseModel):
    """标识解析结果。"""
    success: bool
    query_input: QueryInput | None = None
    candidates: list[str] | None = None
    error: dict | None = None


# ── 状态模型 ──────────────────────────────────────────────

class StatusMapping(BaseModel):
    """状态码映射条目。"""
    main_status: str
    category: str
    is_exception: bool = False
    is_hold: bool = False


class NormalizedStatus(BaseModel):
    """归一化后的状态。"""
    status_code: int | str
    main_status: str
    category: str
    is_exception: bool
    is_hold: bool


# ── 查询中间模型 ──────────────────────────────────────────

class CoreQueryResult(BaseModel):
    """核心查询结果（3 个 API 的原始返回）。"""
    search_result: dict | None = None
    order_detail: dict | None = None
    order_logs: dict | None = None
    success: bool = False
    errors: list[str] = Field(default_factory=list)


class ExtendedQueryResult(BaseModel):
    """扩展查询结果。"""
    tracking_detail: dict | None = None
    fulfillment_orders: dict | None = None
    tracking_status: dict | None = None
    warehouse_list: dict | None = None
    deallocate_info: dict | None = None
    routing_rules: dict | None = None
    custom_rules: dict | None = None
    sku_warehouse_rules: dict | None = None
    inventory: dict | None = None
    hold_rules: dict | None = None
    timeline: dict | None = None
    failed_apis: list[str] = Field(default_factory=list)
    called_apis: list[str] = Field(default_factory=list)


# ── 输出子模型 ────────────────────────────────────────────

class OrderIdentity(BaseModel):
    order_no: str | None = None
    customer_order_no: str | None = None
    external_order_no: str | None = None
    merchant_no: str | None = None
    channel_no: str | None = None
    channel_name: str | None = None


class OrderContext(BaseModel):
    order_type: str | None = None
    order_type_tags: list[str] | None = None
    related_order_no: str | None = None
    order_source: str | None = None


class CurrentStatus(BaseModel):
    main_status: str | None = None
    fulfillment_status: str | None = None
    shipment_status: str | None = None
    is_exception: bool | None = None
    is_hold: bool | None = None
    hold_reason: str | None = None
    exception_reason: str | None = None


class OrderItem(BaseModel):
    sku: str
    quantity: int
    description: str | None = None
    weight: float | None = None
    dimensions: str | None = None


class ShippingAddress(BaseModel):
    country: str | None = None
    state: str | None = None
    city: str | None = None
    zipcode: str | None = None
    address1: str | None = None


class ShipmentInfo(BaseModel):
    shipment_no: str | None = None
    carrier_name: str | None = None
    carrier_scac: str | None = None
    delivery_service: str | None = None
    tracking_no: str | None = None
    shipment_status: str | None = None


class InventoryInfo(BaseModel):
    sku_inventory: list[dict] | None = None
    inventory_summary: str | None = None


class WarehouseInfo(BaseModel):
    allocated_warehouse: str | None = None
    warehouse_name: str | None = None
    warehouse_accounting_code: str | None = None


class AllocationInfo(BaseModel):
    allocation_reason: str | None = None
    dispatch_strategies: list[str] | None = None
    filter_strategies: list[str] | None = None
    backup_strategy: str | None = None


class RuleInfo(BaseModel):
    routing_rules: list[dict] | None = None
    custom_rules: list[dict] | None = None
    hold_rules: list[dict] | None = None
    sku_warehouse_rules: list[dict] | None = None


class EventInfo(BaseModel):
    timeline: list[dict] | None = None
    latest_event_type: str | None = None
    latest_event_time: str | None = None
    order_logs: list[dict] | None = None


class QueryExplanation(BaseModel):
    current_step: str | None = None
    why_hold: str | None = None
    why_exception: str | None = None
    why_this_warehouse: str | None = None


class DataCompleteness(BaseModel):
    completeness_level: str = "minimal"
    missing_fields: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


class OrderQueryResult(BaseModel):
    """订单全景查询标准化输出。"""
    query_input: QueryInput
    order_identity: OrderIdentity | None = None
    order_context: OrderContext | None = None
    current_status: CurrentStatus | None = None
    order_items: list[OrderItem] | None = None
    shipping_address: ShippingAddress | None = None
    shipment_info: ShipmentInfo | None = None
    inventory_info: InventoryInfo | None = None
    warehouse_info: WarehouseInfo | None = None
    allocation_info: AllocationInfo | None = None
    rule_info: RuleInfo | None = None
    event_info: EventInfo | None = None
    query_explanation: QueryExplanation | None = None
    data_completeness: DataCompleteness = Field(default_factory=DataCompleteness)
    error: dict | None = None


class BatchQueryResult(BaseModel):
    """批量查询结果。"""
    status_counts: dict[str, dict] | None = None
    orders: list[dict] | None = None
    total: int = 0
    page_no: int = 1
    page_size: int = 20
