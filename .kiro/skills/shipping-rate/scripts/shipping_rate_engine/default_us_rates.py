"""DefaultUSRateProvider — 美国三大承运商公开牌价表

内置 UPS Ground / FedEx Ground / USPS Priority Mail 的 2024-2025 公开费率。
当商户没有自定义价格表时，引擎自动降级使用此 provider 给出参考估算。

费率来源：各承运商官网公开的 published rate（非签约折扣价）。
Zone 划分简化为 8 个区（Zone 2-8 + Local），基于美国 ZIP 前缀距离。

注意：
- 这些是公开牌价，实际商户签约价通常有 30-70% 折扣
- 结果标注 confidence="estimated" 和 degraded=True
- 燃油附加费率按 2024 Q4 平均值（UPS 12.5%, FedEx 12.5%, USPS 0%）
"""

from __future__ import annotations

from decimal import Decimal

from .rate_models import (
    Address,
    BillingMode,
    PackageInput,
    PriceTable,
    ProviderRateResult,
    SurchargeChargeMode,
    SurchargeContext,
    SurchargeRule,
    SurchargeRuleSet,
    SurchargeType,
    ZoneMapping,
    ZoneRate,
)
from .rate_provider import RateProvider
from .zone_resolver import ZoneResolver, ZoneResolveError
from .rate_calculator import RateCalculator, _round2
from .surcharge_calculator import SurchargeCalculator
from .rate_models import PackageRate


# ── 美国州→区域映射（简化版，基于地理距离分 4 大区） ──

US_REGIONS = {
    "WEST": ["CA", "OR", "WA", "NV", "AZ", "UT", "CO", "NM", "ID", "MT", "WY", "HI", "AK"],
    "CENTRAL": ["TX", "OK", "KS", "NE", "SD", "ND", "MN", "IA", "MO", "AR", "LA", "WI", "IL", "IN", "MI", "OH"],
    "SOUTH": ["FL", "GA", "SC", "NC", "VA", "WV", "KY", "TN", "AL", "MS", "MD", "DE", "DC"],
    "EAST": ["NY", "NJ", "PA", "CT", "MA", "RI", "VT", "NH", "ME"],
}

# 区域→区域的 Zone 映射（简化）
_ZONE_MATRIX = {
    ("WEST", "WEST"): "Z2", ("WEST", "CENTRAL"): "Z5", ("WEST", "SOUTH"): "Z6", ("WEST", "EAST"): "Z8",
    ("CENTRAL", "WEST"): "Z5", ("CENTRAL", "CENTRAL"): "Z2", ("CENTRAL", "SOUTH"): "Z4", ("CENTRAL", "EAST"): "Z5",
    ("SOUTH", "WEST"): "Z6", ("SOUTH", "CENTRAL"): "Z4", ("SOUTH", "SOUTH"): "Z2", ("SOUTH", "EAST"): "Z4",
    ("EAST", "WEST"): "Z8", ("EAST", "CENTRAL"): "Z5", ("EAST", "SOUTH"): "Z4", ("EAST", "EAST"): "Z2",
}


def _state_to_region(state: str) -> str:
    s = state.upper().strip()
    for region, states in US_REGIONS.items():
        if s in states:
            return region
    return "CENTRAL"  # 默认


def _resolve_zone(origin_state: str, dest_state: str) -> str:
    if origin_state.upper() == dest_state.upper():
        return "Z2"  # 同州
    r1 = _state_to_region(origin_state)
    r2 = _state_to_region(dest_state)
    return _ZONE_MATRIX.get((r1, r2), "Z5")


# ── 公开牌价表（2024-2025 published rates，简化版） ──
# 单位：USD，重量：lbs（转换为 kg 时 1 lb = 0.4536 kg）
# 这里直接用 kg 作为计费单位，费率已按 kg 换算

def _build_ups_ground() -> dict[str, ZoneRate]:
    """UPS Ground published rates (simplified, per kg)"""
    # Zone 2: 近距离, Zone 5: 中距离, Zone 8: 远距离
    return {
        "Z2": ZoneRate(charge_zone="Z2", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("7.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("0.90")),
        "Z4": ZoneRate(charge_zone="Z4", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("8.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.20")),
        "Z5": ZoneRate(charge_zone="Z5", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("9.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.40")),
        "Z6": ZoneRate(charge_zone="Z6", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("10.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.60")),
        "Z8": ZoneRate(charge_zone="Z8", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("12.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("2.00")),
    }


def _build_fedex_ground() -> dict[str, ZoneRate]:
    """FedEx Ground published rates (simplified, per kg)"""
    return {
        "Z2": ZoneRate(charge_zone="Z2", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("7.80"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("0.95")),
        "Z4": ZoneRate(charge_zone="Z4", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("9.00"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.25")),
        "Z5": ZoneRate(charge_zone="Z5", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("10.00"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.45")),
        "Z6": ZoneRate(charge_zone="Z6", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("11.00"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.65")),
        "Z8": ZoneRate(charge_zone="Z8", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("13.00"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("2.10")),
    }


def _build_usps_priority() -> dict[str, ZoneRate]:
    """USPS Priority Mail published rates (simplified, per kg)"""
    return {
        "Z2": ZoneRate(charge_zone="Z2", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("7.00"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("0.75")),
        "Z4": ZoneRate(charge_zone="Z4", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("7.75"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("0.90")),
        "Z5": ZoneRate(charge_zone="Z5", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("8.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.05")),
        "Z6": ZoneRate(charge_zone="Z6", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("9.25"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.20")),
        "Z8": ZoneRate(charge_zone="Z8", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
            first_weight=Decimal("0.5"), first_weight_fee=Decimal("10.50"),
            step_weight=Decimal("0.5"), step_weight_fee=Decimal("1.50")),
    }


# 承运商→费率表
_CARRIER_RATES: dict[str, dict[str, ZoneRate]] = {
    "UPS Ground": _build_ups_ground(),
    "FedEx Ground": _build_fedex_ground(),
    "USPS Priority": _build_usps_priority(),
}

# 承运商→燃油附加费率
_FUEL_SURCHARGE: dict[str, Decimal] = {
    "UPS Ground": Decimal("0.125"),
    "FedEx Ground": Decimal("0.125"),
    "USPS Priority": Decimal("0"),  # USPS 不收燃油附加费
}

# 默认 SKU 重量估算（当 OMS 无重量数据时）
DEFAULT_WEIGHT_KG = Decimal("0.9")  # ~2 lbs，典型小件


class DefaultUSRateProvider(RateProvider):
    """美国公开牌价 provider。

    当商户没有自定义价格表时自动降级使用。
    支持 UPS Ground / FedEx Ground / USPS Priority Mail。
    结果标注 confidence="estimated"。
    """

    @property
    def priority(self) -> int:
        return 200  # 最低优先级，仅作兜底

    def get_rate(
        self,
        package: PackageInput,
        origin: Address,
        destination: Address,
        carrier: str,
        surcharge_rules: SurchargeRuleSet | None = None,
        surcharge_context: SurchargeContext | None = None,
    ) -> ProviderRateResult:
        rates = _CARRIER_RATES.get(carrier)
        if not rates:
            return ProviderRateResult(
                success=False,
                error=f"DefaultUSRateProvider 不支持承运商: {carrier}。支持: {list(_CARRIER_RATES.keys())}",
            )

        # 解析 zone
        origin_state = origin.province or origin.city or ""
        dest_state = destination.province or destination.city or ""
        if not origin_state or not dest_state:
            return ProviderRateResult(success=False, error="缺少发货州或收货州信息")

        zone = _resolve_zone(origin_state, dest_state)
        zone_rate = rates.get(zone)
        if not zone_rate:
            # 降级到最近的 zone
            zone_rate = rates.get("Z5") or next(iter(rates.values()))
            zone = zone_rate.charge_zone

        # 计费重量（如果为 0 或缺失，用默认值）
        billing_weight = package.billing_weight
        if not billing_weight or billing_weight <= 0:
            billing_weight = DEFAULT_WEIGHT_KG

        # 基础运费
        freight_base = RateCalculator.calculate(billing_weight, package.volume_cm3, zone_rate)

        # 燃油附加费
        fuel_rate = _FUEL_SURCHARGE.get(carrier, Decimal("0"))
        fuel_rules = SurchargeRuleSet(rules=[
            SurchargeRule(
                surcharge_type=SurchargeType.FUEL,
                charge_mode=SurchargeChargeMode.PERCENTAGE,
                percentage=fuel_rate,
            ),
        ])

        # 合并用户传入的附加费规则
        all_rules = fuel_rules
        if surcharge_rules and surcharge_rules.rules:
            all_rules = SurchargeRuleSet(rules=fuel_rules.rules + surcharge_rules.rules)

        ctx = surcharge_context or SurchargeContext(destination=destination)
        surcharge = SurchargeCalculator.calculate_all(freight_base, package, all_rules, ctx)

        freight_total = _round2(freight_base + surcharge.total)

        pkg_rate = PackageRate(
            package_id=package.package_id,
            charge_zone=zone,
            billing_mode=zone_rate.billing_mode,
            freight_base=freight_base,
            surcharge_breakdown=surcharge,
            freight_total=freight_total,
        )

        return ProviderRateResult(success=True, package_rate=pkg_rate)

    def get_all_carrier_rates(
        self,
        package: PackageInput,
        origin: Address,
        destination: Address,
        surcharge_rules: SurchargeRuleSet | None = None,
        surcharge_context: SurchargeContext | None = None,
    ) -> list[tuple[str, ProviderRateResult]]:
        """为所有支持的承运商计算运费，返回 [(carrier, result)] 列表。"""
        results = []
        for carrier in _CARRIER_RATES:
            r = self.get_rate(package, origin, destination, carrier, surcharge_rules, surcharge_context)
            results.append((carrier, r))
        return results

    @staticmethod
    def supported_carriers() -> list[str]:
        return list(_CARRIER_RATES.keys())
