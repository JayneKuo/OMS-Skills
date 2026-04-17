"""Shipping Rate Engine — 运费计算数据模型

定义运费计算引擎的所有输入/输出 Pydantic 模型。
使用 Decimal 类型处理金额，避免浮点误差，所有金额保留 2 位小数。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── 枚举 ──────────────────────────────────────────────


class BillingMode(str, Enum):
    FIRST_WEIGHT_STEP = "first_weight_step"  # 首重+续重
    WEIGHT_TIER = "weight_tier"              # 阶梯重量
    VOLUME = "volume"                        # 体积计费
    FIXED = "fixed"                          # 固定费用


class SurchargeType(str, Enum):
    REMOTE = "remote"           # 偏远地区
    OVERWEIGHT = "overweight"   # 超重
    OVERSIZE = "oversize"       # 超尺寸
    FUEL = "fuel"               # 燃油
    HOLIDAY = "holiday"         # 节假日
    INSURANCE = "insurance"     # 保价
    COLD_CHAIN = "cold_chain"   # 冷链
    STAIR = "stair"             # 上楼


class SurchargeChargeMode(str, Enum):
    FIXED_AMOUNT = "fixed_amount"    # 固定金额
    PERCENTAGE = "percentage"        # 百分比


# ── 输入模型 ──────────────────────────────────────────


class Address(BaseModel):
    """地址模型"""
    province: str = ""
    city: str = ""
    district: str = ""
    country: str = "CN"


class PackageInput(BaseModel):
    """单包裹输入（来自装箱引擎输出）"""
    package_id: str
    billing_weight: Decimal          # 计费重量 kg
    actual_weight: Decimal           # 实际重量 kg
    volume_cm3: Decimal | None = None
    length_cm: Decimal | None = None
    width_cm: Decimal | None = None
    height_cm: Decimal | None = None
    items: list[dict] = Field(default_factory=list)
    has_cold_items: bool = False
    is_bulky: bool = False
    declared_value: Decimal = Decimal("0")


class ZoneMapping(BaseModel):
    """区域映射规则"""
    origin_province: str = ""
    origin_city: str = ""
    origin_district: str = ""
    dest_province: str = ""
    dest_city: str = ""
    dest_district: str = ""
    charge_zone: str


class WeightTier(BaseModel):
    """阶梯重量区间"""
    min_weight: Decimal            # 区间下限 kg（含）
    max_weight: Decimal | None     # 区间上限 kg（不含），None 表示无上限
    unit_price: Decimal            # 该区间单价 元/kg


class ZoneRate(BaseModel):
    """单个计费区域的费率配置"""
    charge_zone: str
    billing_mode: BillingMode
    # 首重+续重参数
    first_weight: Decimal = Decimal("1")
    first_weight_fee: Decimal = Decimal("0")
    step_weight: Decimal = Decimal("1")
    step_weight_fee: Decimal = Decimal("0")
    # 阶梯重量参数
    weight_tiers: list[WeightTier] = Field(default_factory=list)
    # 体积计费参数
    unit_price_per_m3: Decimal = Decimal("0")
    # 固定费用参数
    fixed_fee: Decimal = Decimal("0")


class PriceTable(BaseModel):
    """承运商价格表"""
    carrier: str
    zone_mappings: list[ZoneMapping] = Field(default_factory=list)
    zone_rates: list[ZoneRate] = Field(default_factory=list)


class SurchargeRule(BaseModel):
    """单条附加费规则"""
    surcharge_type: SurchargeType
    charge_mode: SurchargeChargeMode = SurchargeChargeMode.FIXED_AMOUNT
    fixed_amount: Decimal = Decimal("0")
    percentage: Decimal = Decimal("0")
    threshold: Decimal = Decimal("0")
    overweight_unit_price: Decimal = Decimal("0")
    per_floor_price: Decimal = Decimal("0")
    remote_areas: list[str] = Field(default_factory=list)
    holiday_periods: list[dict] = Field(default_factory=list)


class SurchargeRuleSet(BaseModel):
    """附加费规则集"""
    rules: list[SurchargeRule] = Field(default_factory=list)


class PromotionRule(BaseModel):
    """促销运费规则"""
    rule_name: str
    min_order_amount: Decimal = Decimal("0")
    discount_type: str = "full_free"  # full_free / fixed_discount / percentage_discount
    discount_amount: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")


class SurchargeContext(BaseModel):
    """附加费计算上下文"""
    ship_date: str | None = None
    estimated_delivery_date: str | None = None
    has_elevator: bool = True
    floor_number: int = 0
    destination: Address = Field(default_factory=Address)


class RateRequest(BaseModel):
    """运费计算请求"""
    packages: list[PackageInput] = Field(default_factory=list)
    origin: Address | None = None
    destination: Address | None = None
    carrier: str | None = None
    price_table: PriceTable | None = None
    surcharge_rules: SurchargeRuleSet = Field(default_factory=SurchargeRuleSet)
    promotion_rules: list[PromotionRule] = Field(default_factory=list)
    merchant_agreement: dict = Field(default_factory=dict)
    ship_date: str | None = None
    estimated_delivery_date: str | None = None
    has_elevator: bool = True
    floor_number: int = 0
    order_total_amount: Decimal | None = None
    recommend_source: str | None = None


# ── 输出模型 ──────────────────────────────────────────


class SurchargeDetail(BaseModel):
    """单项附加费明细"""
    surcharge_type: SurchargeType
    amount: Decimal = Decimal("0")
    triggered: bool = False
    reason: str = ""


class SurchargeBreakdown(BaseModel):
    """附加费汇总"""
    fuel: Decimal = Decimal("0")
    remote: Decimal = Decimal("0")
    overweight: Decimal = Decimal("0")
    oversize: Decimal = Decimal("0")
    cold_chain: Decimal = Decimal("0")
    insurance: Decimal = Decimal("0")
    stair: Decimal = Decimal("0")
    holiday: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    details: list[SurchargeDetail] = Field(default_factory=list)


class PackageRate(BaseModel):
    """单包裹运费明细"""
    package_id: str
    charge_zone: str = ""
    billing_mode: BillingMode | None = None
    freight_base: Decimal = Decimal("0")
    surcharge_breakdown: SurchargeBreakdown = Field(default_factory=SurchargeBreakdown)
    freight_total: Decimal = Decimal("0")


class PromotionApplied(BaseModel):
    """促销减免明细"""
    rule_name: str
    discount_amount: Decimal = Decimal("0")


class OrderRateSummary(BaseModel):
    """订单运费汇总"""
    freight_order: Decimal = Decimal("0")
    freight_order_before_promotion: Decimal = Decimal("0")
    package_rates: list[PackageRate] = Field(default_factory=list)
    promotions_applied: list[PromotionApplied] = Field(default_factory=list)
    total_promotion_discount: Decimal = Decimal("0")


class ProviderRateResult(BaseModel):
    """Provider 返回的单包裹运费结果"""
    success: bool = True
    package_rate: PackageRate | None = None
    error: str = ""


class RateResult(BaseModel):
    """运费计算结果"""
    success: bool = True
    freight_order: Decimal = Decimal("0")
    freight_order_before_promotion: Decimal = Decimal("0")
    package_rates: list[PackageRate] = Field(default_factory=list)
    promotions_applied: list[PromotionApplied] = Field(default_factory=list)
    total_promotion_discount: Decimal = Decimal("0")
    degraded: bool = False
    degraded_fields: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    carrier: str = ""
    recommend_source: str | None = None
    confidence: str = "high"
    calculation_explanation: str = ""
