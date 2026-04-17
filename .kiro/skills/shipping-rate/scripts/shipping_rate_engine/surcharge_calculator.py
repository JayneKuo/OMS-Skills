"""Shipping Rate Engine — 附加费计算器

纯函数实现，按 5 步顺序叠加 8 种附加费：
  Step 1: 基础运费（由 RateCalculator 计算，作为输入）
  Step 2: 燃油附加费
  Step 3: 偏远/超重/超尺寸附加费（独立计算后累加）
  Step 4: 冷链/保价/上楼附加费（独立计算后累加）
  Step 5: 节假日附加费（基于 基础运费+燃油 计算）
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from .rate_models import (
    PackageInput,
    SurchargeBreakdown,
    SurchargeChargeMode,
    SurchargeContext,
    SurchargeDetail,
    SurchargeRule,
    SurchargeRuleSet,
    SurchargeType,
)


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SurchargeCalculator:
    """附加费计算器（纯函数）"""

    @staticmethod
    def calculate_all(
        freight_base: Decimal,
        package: PackageInput,
        surcharge_rules: SurchargeRuleSet,
        context: SurchargeContext,
    ) -> SurchargeBreakdown:
        """按 5 步顺序叠加所有附加费"""
        details: list[SurchargeDetail] = []
        rules_by_type: dict[SurchargeType, SurchargeRule] = {}
        for rule in surcharge_rules.rules:
            rules_by_type[rule.surcharge_type] = rule

        # Step 2: 燃油附加费（始终计算）
        fuel_rule = rules_by_type.get(SurchargeType.FUEL)
        fuel = SurchargeCalculator.calc_fuel(
            freight_base,
            fuel_rule.percentage if fuel_rule else Decimal("0"),
        )
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.FUEL,
            amount=fuel,
            triggered=fuel > 0,
            reason=f"燃油附加费率 {fuel_rule.percentage if fuel_rule else 0}",
        ))

        # Step 3: 偏远/超重/超尺寸（独立计算）
        remote_rule = rules_by_type.get(SurchargeType.REMOTE)
        is_remote = SurchargeCalculator._is_remote(context.destination, remote_rule)
        remote = SurchargeCalculator.calc_remote(freight_base, remote_rule, is_remote) if remote_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.REMOTE,
            amount=remote,
            triggered=remote > 0,
            reason="收货地址在偏远地区列表中" if remote > 0 else "非偏远地区",
        ))

        ow_rule = rules_by_type.get(SurchargeType.OVERWEIGHT)
        overweight = SurchargeCalculator.calc_overweight(package.billing_weight, ow_rule) if ow_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.OVERWEIGHT,
            amount=overweight,
            triggered=overweight > 0,
            reason=f"计费重量 {package.billing_weight}kg" + (f" 超过阈值 {ow_rule.threshold}kg" if ow_rule and overweight > 0 else ""),
        ))

        os_rule = rules_by_type.get(SurchargeType.OVERSIZE)
        max_edge = SurchargeCalculator._max_edge(package)
        oversize = SurchargeCalculator.calc_oversize(max_edge, os_rule) if os_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.OVERSIZE,
            amount=oversize,
            triggered=oversize > 0,
            reason=f"最长边 {max_edge}cm" + (f" 超过阈值 {os_rule.threshold}cm" if os_rule and oversize > 0 else ""),
        ))

        # Step 4: 冷链/保价/上楼（独立计算）
        cc_rule = rules_by_type.get(SurchargeType.COLD_CHAIN)
        cold_chain = SurchargeCalculator.calc_cold_chain(package.has_cold_items, cc_rule) if cc_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.COLD_CHAIN,
            amount=cold_chain,
            triggered=cold_chain > 0,
            reason="包含冷藏/冷冻商品" if cold_chain > 0 else "无冷链商品",
        ))

        ins_rule = rules_by_type.get(SurchargeType.INSURANCE)
        insurance = SurchargeCalculator.calc_insurance(package.declared_value, ins_rule) if ins_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.INSURANCE,
            amount=insurance,
            triggered=insurance > 0,
            reason=f"声明价值 {package.declared_value}" + (f" 超过阈值 {ins_rule.threshold}" if ins_rule and insurance > 0 else ""),
        ))

        stair_rule = rules_by_type.get(SurchargeType.STAIR)
        stair = SurchargeCalculator.calc_stair(
            context.floor_number, package.is_bulky, context.has_elevator, stair_rule,
        ) if stair_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.STAIR,
            amount=stair,
            triggered=stair > 0,
            reason=f"楼层 {context.floor_number}" if stair > 0 else "无需上楼费",
        ))

        # Step 5: 节假日附加费（基于 基础运费+燃油 计算）
        hol_rule = rules_by_type.get(SurchargeType.HOLIDAY)
        is_holiday = SurchargeCalculator._is_holiday(context, hol_rule)
        base_plus_fuel = freight_base + fuel
        holiday = SurchargeCalculator.calc_holiday(base_plus_fuel, hol_rule, is_holiday) if hol_rule else Decimal("0")
        details.append(SurchargeDetail(
            surcharge_type=SurchargeType.HOLIDAY,
            amount=holiday,
            triggered=holiday > 0,
            reason="节假日期间" if holiday > 0 else "非节假日",
        ))

        total = fuel + remote + overweight + oversize + cold_chain + insurance + stair + holiday

        return SurchargeBreakdown(
            fuel=fuel,
            remote=remote,
            overweight=overweight,
            oversize=oversize,
            cold_chain=cold_chain,
            insurance=insurance,
            stair=stair,
            holiday=holiday,
            total=_round2(total),
            details=details,
        )

    # ── 8 种附加费独立计算方法 ────────────────────────

    @staticmethod
    def calc_fuel(freight_base: Decimal, fuel_rate: Decimal) -> Decimal:
        """燃油附加费 = freight_base × fuel_rate"""
        return _round2(freight_base * fuel_rate)

    @staticmethod
    def calc_remote(
        freight_base: Decimal,
        rule: SurchargeRule | None,
        is_remote: bool,
    ) -> Decimal:
        """偏远地区附加费"""
        if not is_remote or rule is None:
            return Decimal("0")
        if rule.charge_mode == SurchargeChargeMode.FIXED_AMOUNT:
            return _round2(rule.fixed_amount)
        else:  # percentage
            return _round2(freight_base * rule.percentage)

    @staticmethod
    def calc_overweight(billing_weight: Decimal, rule: SurchargeRule | None) -> Decimal:
        """超重附加费 = (billing_weight - threshold) × overweight_unit_price"""
        if rule is None or billing_weight <= rule.threshold:
            return Decimal("0")
        excess = billing_weight - rule.threshold
        return _round2(excess * rule.overweight_unit_price)

    @staticmethod
    def calc_oversize(max_edge: Decimal, rule: SurchargeRule | None) -> Decimal:
        """超尺寸附加费（固定金额）"""
        if rule is None or max_edge <= rule.threshold:
            return Decimal("0")
        return _round2(rule.fixed_amount)

    @staticmethod
    def calc_cold_chain(has_cold_items: bool, rule: SurchargeRule | None) -> Decimal:
        """冷链附加费（固定金额）"""
        if not has_cold_items or rule is None:
            return Decimal("0")
        return _round2(rule.fixed_amount)

    @staticmethod
    def calc_insurance(declared_value: Decimal, rule: SurchargeRule | None) -> Decimal:
        """保价费 = declared_value × insurance_rate"""
        if rule is None or declared_value <= rule.threshold:
            return Decimal("0")
        return _round2(declared_value * rule.percentage)

    @staticmethod
    def calc_stair(
        floor_number: int,
        is_bulky: bool,
        has_elevator: bool,
        rule: SurchargeRule | None,
    ) -> Decimal:
        """上楼费 = floor_number × per_floor_price"""
        if rule is None or not is_bulky or has_elevator or floor_number <= 0:
            return Decimal("0")
        return _round2(Decimal(str(floor_number)) * rule.per_floor_price)

    @staticmethod
    def calc_holiday(
        base_plus_fuel: Decimal,
        rule: SurchargeRule | None,
        is_holiday: bool,
    ) -> Decimal:
        """节假日附加费"""
        if not is_holiday or rule is None:
            return Decimal("0")
        if rule.charge_mode == SurchargeChargeMode.FIXED_AMOUNT:
            return _round2(rule.fixed_amount)
        else:  # percentage — 基于 (基础运费 + 燃油附加费)
            return _round2(base_plus_fuel * rule.percentage)

    # ── 辅助方法 ──────────────────────────────────────

    @staticmethod
    def _is_remote(destination, rule: SurchargeRule | None) -> bool:
        """判断收货地址是否在偏远地区列表中"""
        if rule is None or not rule.remote_areas:
            return False
        # 匹配省/市/区任一级
        addr_parts = [destination.province, destination.city, destination.district]
        return any(area in addr_parts for area in rule.remote_areas if area)

    @staticmethod
    def _max_edge(package: PackageInput) -> Decimal:
        """获取包裹最长边"""
        edges = [
            package.length_cm or Decimal("0"),
            package.width_cm or Decimal("0"),
            package.height_cm or Decimal("0"),
        ]
        return max(edges)

    @staticmethod
    def _is_holiday(context: SurchargeContext, rule: SurchargeRule | None) -> bool:
        """判断发货日或预计送达日是否在节假日期间"""
        if rule is None or not rule.holiday_periods:
            return False

        dates_to_check: list[str] = []
        if context.ship_date:
            dates_to_check.append(context.ship_date)
        if context.estimated_delivery_date:
            dates_to_check.append(context.estimated_delivery_date)

        if not dates_to_check:
            return False

        for period in rule.holiday_periods:
            start_str = period.get("start", "")
            end_str = period.get("end", "")
            if not start_str or not end_str:
                continue
            try:
                start = datetime.strptime(start_str, "%Y-%m-%d").date()
                end = datetime.strptime(end_str, "%Y-%m-%d").date()
                for d_str in dates_to_check:
                    d = datetime.strptime(d_str, "%Y-%m-%d").date()
                    if start <= d <= end:
                        return True
            except (ValueError, TypeError):
                continue

        return False
