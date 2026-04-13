"""填充率校验器 - 校验并优化包裹填充率"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    PackageFlag,
    PackagingParams,
    ProtectionCoefficients,
    SKUItem,
    TemperatureZone,
)


class FillRateChecker:
    """填充率校验器。

    计算填充率 = (SKU 总体积 × 保护系数 + 包材体积) / 箱型内部体积 × 100%。
    填充率低于阈值时尝试换更小箱型，无更小箱型则标记 LOW_FILL_RATE。
    """

    def calculate_fill_rate(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        protection_coefficients: Optional[ProtectionCoefficients] = None,
        packaging_params: Optional[PackagingParams] = None,
    ) -> Decimal:
        """计算填充率百分比（含保护系数和包材体积）。"""
        prot = protection_coefficients or ProtectionCoefficients()
        pkg = packaging_params or PackagingParams()

        total_vol = sum(
            ((it.length or Decimal(0)) * (it.width or Decimal(0))
             * (it.height or Decimal(0))) * it.quantity
            for it in items
        )
        coeff = self._get_volume_coefficient(items, prot)
        effective_vol = total_vol * coeff
        _, extra_vol = self._calc_packaging_overhead(items, pkg)
        effective_vol += extra_vol

        box_vol = box_type.inner_dimensions.volume
        if box_vol == 0:
            return Decimal("0")
        return (effective_vol / box_vol) * Decimal("100")

    def check_and_optimize(
        self,
        items: list[SKUItem],
        current_box: BoxType,
        available_boxes: list[BoxType],
        carrier_limits: Optional[CarrierLimits] = None,
        min_rate: Decimal = Decimal("60"),
        max_rate: Decimal = Decimal("90"),
        has_fragile: bool = False,
        has_liquid: bool = False,
        temperature_zone: Optional[TemperatureZone] = None,
        protection_coefficients: Optional[ProtectionCoefficients] = None,
        packaging_params: Optional[PackagingParams] = None,
    ) -> tuple[BoxType, Decimal, list[PackageFlag]]:
        """校验填充率并尝试优化。"""
        prot = protection_coefficients or ProtectionCoefficients()
        pkg = packaging_params or PackagingParams()

        total_vol = sum(
            ((it.length or Decimal(0)) * (it.width or Decimal(0))
             * (it.height or Decimal(0))) * it.quantity
            for it in items
        )
        total_wt = sum(
            (it.weight or Decimal(0)) * it.quantity
            for it in items
        )
        coeff = self._get_volume_coefficient(items, prot)
        effective_vol = total_vol * coeff
        extra_wt, extra_vol = self._calc_packaging_overhead(items, pkg)
        effective_vol += extra_vol
        effective_wt = total_wt + extra_wt

        fill_rate = self._calc_rate(effective_vol, current_box)
        flags: list[PackageFlag] = []

        if fill_rate >= min_rate:
            return current_box, fill_rate, flags

        # 尝试换更小箱型
        smaller_boxes = self._find_smaller_boxes(
            current_box, available_boxes, effective_vol, effective_wt,
            carrier_limits, has_fragile, has_liquid, temperature_zone, items,
        )

        best_box = current_box
        best_rate = fill_rate

        for sb in smaller_boxes:
            rate = self._calc_rate(effective_vol, sb)
            if min_rate <= rate <= max_rate:
                best_box = sb
                best_rate = rate
                break
            elif rate > best_rate:
                best_box = sb
                best_rate = rate

        if best_rate < min_rate:
            flags.append(PackageFlag.LOW_FILL_RATE)

        return best_box, best_rate, flags

    def _find_smaller_boxes(
        self,
        current: BoxType,
        available: list[BoxType],
        effective_vol: Decimal,
        effective_wt: Decimal,
        carrier_limits: Optional[CarrierLimits],
        has_fragile: bool,
        has_liquid: bool = False,
        temperature_zone: Optional[TemperatureZone] = None,
        items: Optional[list[SKUItem]] = None,
    ) -> list[BoxType]:
        """找到比当前箱型更小但仍能容纳的箱型，按体积升序排列。"""
        from cartonization_engine.box_selector import BoxSelector
        candidates = []
        current_vol = current.inner_dimensions.volume

        for bt in available:
            if bt.box_id == current.box_id:
                continue
            # 库存过滤
            if bt.available_qty is not None and bt.available_qty <= 0:
                continue
            # 温区过滤
            if temperature_zone and temperature_zone not in bt.temperature_zone_supported:
                continue
            bv = bt.inner_dimensions.volume
            if bv >= current_vol:
                continue
            if bv < effective_vol:
                continue
            # 承重校验：含箱体自重
            if bt.max_weight < effective_wt + bt.material_weight:
                continue
            if has_fragile and not bt.supports_shock_proof:
                continue
            if has_liquid and not bt.supports_leak_proof:
                continue
            # 单件尺寸校验（含 upright_required / non-stackable）
            if items and not BoxSelector._all_items_fit(items, bt):
                continue
            if carrier_limits and not BoxSelector._carrier_compliant(bt, carrier_limits):
                continue
            candidates.append(bt)

        candidates.sort(key=lambda b: b.inner_dimensions.volume)
        return candidates

    @staticmethod
    def _get_volume_coefficient(
        items: list[SKUItem], prot: ProtectionCoefficients,
    ) -> Decimal:
        coeff = prot.normal
        for it in items:
            if it.fragile_flag:
                coeff = max(coeff, prot.fragile)
            if it.liquid_flag:
                coeff = max(coeff, prot.liquid)
            if it.is_gift:
                coeff = max(coeff, prot.gift_wrap)
            tz = it.temperature_zone or TemperatureZone.NORMAL
            if tz in (TemperatureZone.CHILLED, TemperatureZone.FROZEN):
                coeff = max(coeff, prot.temperature_controlled)
        return coeff

    @staticmethod
    def _calc_packaging_overhead(
        items: list[SKUItem], params: PackagingParams,
    ) -> tuple[Decimal, Decimal]:
        extra_wt = Decimal("0")
        extra_vol = Decimal("0")
        if any(it.fragile_flag for it in items):
            extra_wt += params.cushion_weight_kg
            extra_vol += params.cushion_volume_cm3
        if any(it.liquid_flag for it in items):
            extra_wt += params.leakproof_weight_kg
            extra_vol += params.leakproof_volume_cm3
        if any(it.is_gift for it in items):
            extra_wt += params.gift_wrap_weight_kg
            extra_vol += params.gift_wrap_volume_cm3
        return extra_wt, extra_vol

    @staticmethod
    def _calc_rate(effective_vol: Decimal, box: BoxType) -> Decimal:
        bv = box.inner_dimensions.volume
        if bv == 0:
            return Decimal("0")
        return (effective_vol / bv) * Decimal("100")
