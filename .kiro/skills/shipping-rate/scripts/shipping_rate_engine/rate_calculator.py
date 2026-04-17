"""Shipping Rate Engine — 基础运费计算器

纯函数实现，支持 4 种计费模式：
1. 首重+续重 (first_weight_step)
2. 阶梯重量 (weight_tier)
3. 体积计费 (volume)
4. 固定费用 (fixed)

所有金额使用 Decimal，保留 2 位小数。
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

from .rate_models import BillingMode, ZoneRate


def _round2(value: Decimal) -> Decimal:
    """保留 2 位小数，四舍五入"""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ceil_weight(weight: Decimal) -> Decimal:
    """计费重量向上取整到 0.1kg"""
    w = float(weight)
    return Decimal(str(math.ceil(w * 10) / 10))


class RateCalculator:
    """基础运费计算器（纯函数）"""

    @staticmethod
    def calculate(
        billing_weight: Decimal,
        volume_cm3: Decimal | None,
        zone_rate: ZoneRate,
    ) -> Decimal:
        """根据 zone_rate.billing_mode 分派到对应计费函数"""
        mode = zone_rate.billing_mode
        if mode == BillingMode.FIRST_WEIGHT_STEP:
            return RateCalculator.calc_first_weight_step(billing_weight, zone_rate)
        elif mode == BillingMode.WEIGHT_TIER:
            return RateCalculator.calc_weight_tier(billing_weight, zone_rate)
        elif mode == BillingMode.VOLUME:
            return RateCalculator.calc_volume(volume_cm3 or Decimal("0"), zone_rate)
        elif mode == BillingMode.FIXED:
            return RateCalculator.calc_fixed(zone_rate)
        else:
            raise ValueError(f"INVALID_BILLING_MODE: {mode}")

    @staticmethod
    def calc_first_weight_step(billing_weight: Decimal, zone_rate: ZoneRate) -> Decimal:
        """首重+续重模式

        公式: freight_base = first_weight_fee + ceil((charge_weight - first_weight) / step_weight) * step_weight_fee
        当 weight <= first_weight 时，返回 first_weight_fee
        """
        charge_weight = _ceil_weight(billing_weight)

        if charge_weight <= zone_rate.first_weight:
            return _round2(zone_rate.first_weight_fee)

        excess = charge_weight - zone_rate.first_weight
        if zone_rate.step_weight <= 0:
            return _round2(zone_rate.first_weight_fee)

        steps = Decimal(str(math.ceil(float(excess) / float(zone_rate.step_weight))))
        freight = zone_rate.first_weight_fee + steps * zone_rate.step_weight_fee
        return _round2(freight)

    @staticmethod
    def calc_weight_tier(billing_weight: Decimal, zone_rate: ZoneRate) -> Decimal:
        """阶梯重量模式

        按重量区间分段计费，每个区间使用对应单价。
        超过最高区间用最高区间单价。
        """
        if not zone_rate.weight_tiers:
            return Decimal("0")

        charge_weight = _ceil_weight(billing_weight)
        total = Decimal("0")
        remaining = charge_weight

        # 按 min_weight 排序
        sorted_tiers = sorted(zone_rate.weight_tiers, key=lambda t: t.min_weight)

        for i, tier in enumerate(sorted_tiers):
            if remaining <= 0:
                break

            if tier.max_weight is not None:
                tier_range = tier.max_weight - tier.min_weight
                weight_in_tier = min(remaining, tier_range)
            else:
                # 无上限区间，剩余全部在此区间
                weight_in_tier = remaining

            total += weight_in_tier * tier.unit_price
            remaining -= weight_in_tier

        # 如果还有剩余（超过所有区间），用最高区间单价
        if remaining > 0:
            total += remaining * sorted_tiers[-1].unit_price

        return _round2(total)

    @staticmethod
    def calc_volume(volume_cm3: Decimal, zone_rate: ZoneRate) -> Decimal:
        """体积计费模式

        公式: freight_base = volume_m3 * unit_price_per_m3
        volume_m3 = volume_cm3 / 1_000_000
        """
        volume_m3 = volume_cm3 / Decimal("1000000")
        freight = volume_m3 * zone_rate.unit_price_per_m3
        return _round2(freight)

    @staticmethod
    def calc_fixed(zone_rate: ZoneRate) -> Decimal:
        """固定费用模式"""
        return _round2(zone_rate.fixed_fee)
