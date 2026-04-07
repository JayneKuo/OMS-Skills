"""装箱计算引擎数据模型 - Pydantic v2 定义"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------

class TemperatureZone(str, Enum):
    """温区枚举"""
    NORMAL = "常温"
    CHILLED = "冷藏"
    FROZEN = "冷冻"


class HazmatType(str, Enum):
    """危险品类型枚举"""
    NONE = "无"
    FLAMMABLE = "易燃"
    EXPLOSIVE = "易爆"
    CORROSIVE = "腐蚀"


class CartonStatus(str, Enum):
    """装箱结果状态"""
    SUCCESS = "SUCCESS"
    FAILED = "CARTON_FAILED"


class SolutionStatus(str, Enum):
    """V2 装箱方案状态"""
    SUCCESS = "SUCCESS"
    ESTIMATED = "ESTIMATED"
    CARRIER_SWITCHED = "CARRIER_SWITCHED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    FAILED = "FAILED"


class InputCompletenessLevel(str, Enum):
    """输入完整度级别"""
    L1 = "L1"  # Only names/qty/natural language, missing dimensions/weight
    L2 = "L2"  # Partial SKU data, some carrier/packaging params missing
    L3 = "L3"  # Complete SKU data, box types, carrier limits, packaging prefs


class FallbackLevel(str, Enum):
    """回退级别"""
    F1_NON_STANDARD_BOX = "F1"
    F2_VIRTUAL_BOX = "F2"
    F3_OVERSIZE_CARRIER = "F3"
    F4_MANUAL_INTERVENTION = "F4"


class PackageFlag(str, Enum):
    """包裹标记"""
    LOW_FILL_RATE = "低填充率"
    DATA_DEGRADED = "数据降级"
    OVERSIZE_SPECIAL = "超大件专线"
    MANUAL_PACKING = "需人工包装"
    CARRIER_OVERSIZE = "承运商尺寸超限"
    RULE_CONFLICT = "规则冲突待人工介入"


# ---------------------------------------------------------------------------
# 基础输入模型
# ---------------------------------------------------------------------------

class Dimensions(BaseModel):
    """三维尺寸（cm）"""
    length: Decimal
    width: Decimal
    height: Decimal

    @property
    def volume(self) -> Decimal:
        return self.length * self.width * self.height


class SKUItem(BaseModel):
    """SKU 商品项"""
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
    fragile_level: Optional[int] = None  # 1-5 scale
    liquid_volume_ml: Optional[Decimal] = None


class BoxType(BaseModel):
    """箱型定义"""
    box_id: str
    inner_dimensions: Dimensions
    outer_dimensions: Dimensions
    max_weight: Decimal
    material_weight: Decimal
    packaging_cost: Decimal
    is_standard: bool = True
    supports_shock_proof: bool = False
    supports_leak_proof: bool = False
    tare_weight_kg: Decimal = Decimal("0")  # box self-weight (alias for material_weight)
    temperature_zone_supported: list[TemperatureZone] = Field(default_factory=lambda: [TemperatureZone.NORMAL])
    available_qty: Optional[int] = None  # warehouse stock of this box type


class CarrierLimits(BaseModel):
    """承运商限制"""
    carrier_id: str
    max_weight: Decimal
    max_dimension: Dimensions
    dim_factor: int
    max_girth: Optional[Decimal] = None  # max girth cm
    max_volume: Optional[Decimal] = None  # max volume cm3
    max_liquid_volume_ml: Optional[Decimal] = None  # max liquid per package


class OrderConfig(BaseModel):
    """订单业务配置"""
    max_package_count: int = 5
    gift_same_package_required: bool = True
    min_fill_rate: Decimal = Decimal("0.6")
    max_fill_rate: Decimal = Decimal("0.9")


# ---------------------------------------------------------------------------
# 包装参数模型
# ---------------------------------------------------------------------------

class PackagingParams(BaseModel):
    """包装参数"""
    cushion_weight_kg: Decimal = Decimal("0.3")
    cushion_volume_cm3: Decimal = Decimal("500")
    leakproof_weight_kg: Decimal = Decimal("0.1")
    leakproof_volume_cm3: Decimal = Decimal("200")
    gift_wrap_weight_kg: Decimal = Decimal("0.2")
    gift_wrap_volume_cm3: Decimal = Decimal("300")


class ProtectionCoefficients(BaseModel):
    """保护系数"""
    normal: Decimal = Decimal("1.00")
    fragile: Decimal = Decimal("1.15")
    liquid: Decimal = Decimal("1.10")
    gift_wrap: Decimal = Decimal("1.08")
    temperature_controlled: Decimal = Decimal("1.20")


# ---------------------------------------------------------------------------
# 输出模型
# ---------------------------------------------------------------------------

class PackageItem(BaseModel):
    """包裹内的 SKU 项"""
    sku_id: str
    sku_name: str
    quantity: int


class BillingWeight(BaseModel):
    """计费重量"""
    actual_weight: Decimal
    volumetric_weight: Decimal
    billing_weight: Decimal


class DecisionLog(BaseModel):
    """决策日志"""
    group_reason: str
    box_selection_reason: str
    split_reason: Optional[str] = None


class Package(BaseModel):
    """包裹"""
    package_id: str
    items: list[PackageItem]
    box_type: BoxType
    billing_weight: BillingWeight
    fill_rate: Decimal
    flags: list[PackageFlag] = Field(default_factory=list)
    decision_log: DecisionLog
    rule_validation_passed: bool = True
    physical_validation_passed: Optional[bool] = None  # None = not performed
    selection_reason: list[str] = Field(default_factory=list)
    split_merge_reason: Optional[str] = None
    special_flags: list[str] = Field(default_factory=list)  # FRAGILE, LIQUID, DG, LOW_FILL_RATE


class DegradationMark(BaseModel):
    """数据降级标记"""
    sku_id: str
    field: str
    original_value: Optional[Any] = None
    degraded_value: Any
    reason: str


class RuleViolation(BaseModel):
    """规则违反记录"""
    rule_name: str
    violated_skus: list[str]
    description: str


class CartonizationResult(BaseModel):
    """装箱计算结果"""
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


# ---------------------------------------------------------------------------
# 内部模型
# ---------------------------------------------------------------------------

class SKUGroup(BaseModel):
    """预分组结果，一组可以安全混装的 SKU"""
    group_id: str
    temperature_zone: TemperatureZone
    items: list[SKUItem]
    group_reason: str


class FallbackContext(BaseModel):
    """回退处理上下文"""
    non_standard_box_types: list[BoxType] = Field(default_factory=list)
    oversize_carriers: list[CarrierLimits] = Field(default_factory=list)


class FallbackResult(BaseModel):
    """回退处理结果"""
    success: bool
    level: FallbackLevel
    packages: list[Package] = Field(default_factory=list)
    message: str


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------

class CartonizationRequest(BaseModel):
    """装箱计算请求"""
    order_id: str
    items: list[SKUItem]
    box_types: list[BoxType]
    carrier_limits: CarrierLimits
    order_config: OrderConfig = Field(default_factory=OrderConfig)
    category_defaults: dict[str, dict] = Field(default_factory=dict)
    packaging_params: PackagingParams = Field(default_factory=PackagingParams)
    protection_coefficients: ProtectionCoefficients = Field(default_factory=ProtectionCoefficients)


# ---------------------------------------------------------------------------
# 验证结果模型
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    """输入验证结果"""
    success: bool
    items: list[SKUItem] = Field(default_factory=list)
    box_types: list[BoxType] = Field(default_factory=list)
    degradation_marks: list[DegradationMark] = Field(default_factory=list)
    input_level: Optional[InputCompletenessLevel] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# 异常类型
# ---------------------------------------------------------------------------

class RuleConflictError(Exception):
    """规则冲突异常"""

    def __init__(self, message: str, conflicting_skus: list[str] | None = None):
        super().__init__(message)
        self.conflicting_skus = conflicting_skus or []
