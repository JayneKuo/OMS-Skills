"""装箱计算引擎数据模型 - Pydantic v2 定义"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TemperatureZone(str, Enum):
    NORMAL = "常温"
    CHILLED = "冷藏"
    FROZEN = "冷冻"

class HazmatType(str, Enum):
    NONE = "无"
    FLAMMABLE = "易燃"
    EXPLOSIVE = "易爆"
    CORROSIVE = "腐蚀"

class CartonStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "CARTON_FAILED"

class SolutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ESTIMATED = "ESTIMATED"
    CARRIER_SWITCHED = "CARRIER_SWITCHED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    FAILED = "FAILED"

class InputCompletenessLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

class FallbackLevel(str, Enum):
    F1_NON_STANDARD_BOX = "F1"
    F2_VIRTUAL_BOX = "F2"
    F3_OVERSIZE_CARRIER = "F3"
    F4_MANUAL_INTERVENTION = "F4"

class PackageFlag(str, Enum):
    LOW_FILL_RATE = "低填充率"
    DATA_DEGRADED = "数据降级"
    OVERSIZE_SPECIAL = "超大件专线"
    MANUAL_PACKING = "需人工包装"
    CARRIER_OVERSIZE = "承运商尺寸超限"
    RULE_CONFLICT = "规则冲突待人工介入"

class ResultLevel(str, Enum):
    STRICT = "strict"
    ESTIMATED = "estimated"
    MANUAL_REVIEW = "manual_review"

class ManualReasonType(str, Enum):
    CARRIER_LIMIT_EXCEEDED = "carrier_limit_exceeded"
    NO_STANDARD_BOX_FIT = "no_standard_box_fit"
    SPECIAL_HAZMAT_REQUIRED = "special_hazmat_required"
    LEAKPROOF_AND_DG_CONFLICT = "leakproof_and_dg_conflict"
    GEOMETRY_UNCERTAIN = "geometry_uncertain"
    MISSING_MASTER_DATA = "missing_master_data"
    NONSTANDARD_PACKAGING_NEEDED = "nonstandard_packaging_needed"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Dimensions(BaseModel):
    length: Decimal
    width: Decimal
    height: Decimal
    @property
    def volume(self) -> Decimal:
        return self.length * self.width * self.height

class SKUItem(BaseModel):
    sku_id: str
    sku_name: str
    quantity: int
    weight: Optional[Decimal] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    temperature_zone: Optional[TemperatureZone] = None
    hazmat_type: Optional[HazmatType] = None
    oversize_flag: bool = False
    must_ship_with: list[str] = Field(default_factory=list)
    cannot_ship_with: list[str] = Field(default_factory=list)
    is_gift: bool = False
    fragile_flag: bool = False
    liquid_flag: bool = False
    category_id: Optional[str] = None
    rotate_allowed: bool = True
    upright_required: bool = False
    stackable: bool = True
    compressible: bool = False
    max_stack_layers: Optional[int] = None
    fragile_level: Optional[int] = None
    liquid_volume_ml: Optional[Decimal] = None

class BoxType(BaseModel):
    box_id: str
    inner_dimensions: Dimensions
    outer_dimensions: Dimensions
    max_weight: Decimal
    material_weight: Decimal
    packaging_cost: Decimal
    is_standard: bool = True
    supports_shock_proof: bool = False
    supports_leak_proof: bool = False
    tare_weight_kg: Decimal = Decimal("0")
    temperature_zone_supported: list[TemperatureZone] = Field(default_factory=lambda: [TemperatureZone.NORMAL])
    available_qty: Optional[int] = None

class CarrierLimits(BaseModel):
    carrier_id: str
    max_weight: Decimal
    max_dimension: Dimensions
    dim_factor: int
    max_girth: Optional[Decimal] = None
    max_volume: Optional[Decimal] = None
    max_liquid_volume_ml: Optional[Decimal] = None

class OrderConfig(BaseModel):
    max_package_count: int = 5
    gift_same_package_required: bool = True
    min_fill_rate: Decimal = Decimal("0.6")
    max_fill_rate: Decimal = Decimal("0.9")

class PackagingParams(BaseModel):
    cushion_weight_kg: Decimal = Decimal("0.3")
    cushion_volume_cm3: Decimal = Decimal("500")
    leakproof_weight_kg: Decimal = Decimal("0.1")
    leakproof_volume_cm3: Decimal = Decimal("200")
    gift_wrap_weight_kg: Decimal = Decimal("0.2")
    gift_wrap_volume_cm3: Decimal = Decimal("300")

class ProtectionCoefficients(BaseModel):
    normal: Decimal = Decimal("1.00")
    fragile: Decimal = Decimal("1.15")
    liquid: Decimal = Decimal("1.10")
    gift_wrap: Decimal = Decimal("1.08")
    temperature_controlled: Decimal = Decimal("1.20")

class PackageItem(BaseModel):
    sku_id: str
    sku_name: str
    quantity: int

class BillingWeight(BaseModel):
    actual_weight: Decimal
    volumetric_weight: Decimal
    billing_weight: Decimal

class DecisionLog(BaseModel):
    group_reason: str
    box_selection_reason: str
    split_reason: Optional[str] = None

class Package(BaseModel):
    package_id: str
    items: list[PackageItem]
    box_type: BoxType
    billing_weight: BillingWeight
    fill_rate: Decimal
    flags: list[PackageFlag] = Field(default_factory=list)
    decision_log: DecisionLog
    rule_validation_passed: bool = True
    physical_validation_passed: Optional[bool] = None
    selection_reason: list[str] = Field(default_factory=list)
    split_merge_reason: Optional[str] = None
    special_flags: list[str] = Field(default_factory=list)
    geometry_passed: Optional[bool] = None
    geometry_reason: Optional[str] = None
    manual_reason_type: Optional[str] = None
    manual_action: Optional[str] = None

class DegradationMark(BaseModel):
    sku_id: str
    field: str
    original_value: Optional[Any] = None
    degraded_value: Any
    reason: str

class RuleViolation(BaseModel):
    rule_name: str
    violated_skus: list[str]
    description: str

class CartonizationResult(BaseModel):
    status: CartonStatus
    order_id: str
    packages: list[Package] = Field(default_factory=list)
    total_packages: int = 0
    total_billing_weight: Decimal = Decimal("0")
    total_actual_weight: Decimal = Decimal("0")
    input_completeness_level: Optional[InputCompletenessLevel] = None
    degradation_marks: list[DegradationMark] = Field(default_factory=list)
    violations: list[RuleViolation] = Field(default_factory=list)
    fallback_level: Optional[FallbackLevel] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failed_skus: list[str] = Field(default_factory=list)
    result_level: Optional[str] = None
    confidence: Optional[str] = None
    missing_data: list[str] = Field(default_factory=list)
    downgraded_fields: list[str] = Field(default_factory=list)
    manual_reason_types: list[str] = Field(default_factory=list)
    manual_actions: list[str] = Field(default_factory=list)
    validation_status: Optional[dict] = None

class SKUGroup(BaseModel):
    group_id: str
    temperature_zone: TemperatureZone
    items: list[SKUItem]
    group_reason: str

class FallbackContext(BaseModel):
    non_standard_box_types: list[BoxType] = Field(default_factory=list)
    oversize_carriers: list[CarrierLimits] = Field(default_factory=list)

class FallbackResult(BaseModel):
    success: bool
    level: FallbackLevel
    packages: list[Package] = Field(default_factory=list)
    message: str

class CartonizationRequest(BaseModel):
    order_id: str
    items: list[SKUItem]
    box_types: list[BoxType]
    carrier_limits: CarrierLimits
    order_config: OrderConfig = Field(default_factory=OrderConfig)
    category_defaults: dict[str, dict] = Field(default_factory=dict)
    packaging_params: PackagingParams = Field(default_factory=PackagingParams)
    protection_coefficients: ProtectionCoefficients = Field(default_factory=ProtectionCoefficients)

class ValidationResult(BaseModel):
    success: bool
    items: list[SKUItem] = Field(default_factory=list)
    box_types: list[BoxType] = Field(default_factory=list)
    degradation_marks: list[DegradationMark] = Field(default_factory=list)
    input_level: Optional[InputCompletenessLevel] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

class RuleConflictError(Exception):
    def __init__(self, message: str, conflicting_skus: list[str] | None = None):
        super().__init__(message)
        self.conflicting_skus = conflicting_skus or []
