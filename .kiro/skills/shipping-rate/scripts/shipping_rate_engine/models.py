"""Shipping Rate Engine — 数据模型

通用映射规则引擎的数据模型。聚焦 OMS 三层映射体系：
  Layer 1: 一对一映射（OneToOneMapping）
  Layer 2: 条件映射（ConditionMapping）
  Layer 3: Shipping Mapping 多条件规则

引擎本身不绑定具体的比价/承运商 API，通过 recommend 的 provider 扩展点
对接外部数据源（Rate Shopping、第三方承运商 API 等）。
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ── 请求模型 ──────────────────────────────────────────


class MappingQueryRequest(BaseModel):
    """映射查询请求"""
    merchant_no: str
    mapping_types: list[str] | None = None  # CARRIER, SHIP_METHOD, DELIVERY_SERVICE, FREIGHT_TERM, SKU, UOM
    channel_no: str | None = None  # mappingKey 过滤
    include_condition_mappings: bool = True
    include_shipping_rules: bool = True


class MappingExecuteRequest(BaseModel):
    """映射执行请求"""
    merchant_no: str
    channel_no: str | None = None
    # 条件映射执行参数
    skus: list[str] | None = None
    carriers: list[str] | None = None
    ship_methods: list[str] | None = None
    delivery_services: list[str] | None = None
    freight_terms: list[str] | None = None
    mapping_key: str = "ALL"
    # Shipping Mapping 执行参数
    input_conditions: list[dict[str, str]] | None = None


class RecommendRequest(BaseModel):
    """承运商推荐请求

    推荐流程：
    1. 一对一映射解析（SKU→承运商/服务映射）
    2. 条件映射执行（多条件→输出）
    3. Shipping Mapping 规则匹配（渠道级多条件规则）
    4. [扩展点] 外部承运商 API / 比价服务
    """
    order_no: str | None = None
    merchant_no: str
    channel_no: str | None = None
    sku_list: list[dict[str, Any]] | None = None  # [{"sku": "ABC", "quantity": 2}]
    country: str = "US"
    state: str | None = None


# ── 映射规则模型 ──────────────────────────────────────


class OneToOneMapping(BaseModel):
    """Layer 1: 一对一映射"""
    id: int | None = None
    mapping_type: str | None = None
    mapped_type: str | None = None
    origin_value: str | None = None
    mapped_value: str | None = None
    mapping_key: str | None = None
    mapping_direction: int = 1
    status: int = 1


class ConditionMapping(BaseModel):
    """Layer 2: 条件映射"""
    id: int | None = None
    condition_in_list: list[dict] = Field(default_factory=list)
    condition_out: int | None = None
    condition_out_value: str | None = None
    mapping_key: str | None = None
    status: int = 1


class ShippingRule(BaseModel):
    """Layer 3: Shipping Mapping 规则"""
    id: int | str | None = None
    rule_name: str | None = None
    channel_no: str | None = None
    priority: int = 0
    conditions: list[dict] = Field(default_factory=list)
    outputs: list[dict] = Field(default_factory=list)
    mapping_key: str | None = None


# ── 执行结果模型 ──────────────────────────────────────


class ConditionMappingResult(BaseModel):
    """条件映射执行结果"""
    mapping_key: str
    delivery_service: str | None = None
    ship_method: str | None = None
    carrier: str | None = None
    freight_term: str | None = None
    shipment_type: str | None = None


class ShippingMappingResult(BaseModel):
    """Shipping Mapping 执行结果"""
    matched: bool = False
    outputs: dict[str, str] = Field(default_factory=dict)
    raw_response: dict[str, str] = Field(default_factory=dict)


# ── 查询/执行/推荐 结果 ──────────────────────────────


class MappingQueryResult(BaseModel):
    """映射查询结果"""
    success: bool = True
    one_to_one_mappings: list[OneToOneMapping] = Field(default_factory=list)
    condition_mappings: list[ConditionMapping] = Field(default_factory=list)
    shipping_rules: list[ShippingRule] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class MappingExecuteResult(BaseModel):
    """映射执行结果"""
    success: bool = True
    condition_mapping_results: list[ConditionMappingResult] = Field(default_factory=list)
    shipping_mapping_result: ShippingMappingResult | None = None
    explanation: str = ""
    errors: list[str] = Field(default_factory=list)


class CarrierRecommendation(BaseModel):
    """单条承运商推荐"""
    rank: int = 1
    carrier: str | None = None
    ship_method: str | None = None
    delivery_service: str | None = None
    freight_term: str | None = None
    shipment_type: str | None = None
    source: str = ""  # one_to_one / condition_mapping / shipping_mapping / [扩展: external_api]
    rule_name: str | None = None
    priority: int | None = None
    reason: str = ""


class RecommendResult(BaseModel):
    """承运商推荐结果"""
    success: bool = True
    recommendations: list[CarrierRecommendation] = Field(default_factory=list)
    mapping_context: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    confidence: str = "high"  # high / medium / low
    errors: list[str] = Field(default_factory=list)
