"""填充率校验器 - 校验并优化包裹填充率"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    PackageFlag,
    SKUItem,
)


class FillRateChecker:
    """填充率校验器。

    计算填充率 = SKU 总体积 / 箱型内部体积 × 100%。
    填充率低于阈值时尝试换更小箱型，无更小箱型则标记 LOW_FILL_RATE。
    """

    def calculate_fill_rate(
        self,
        items: list[SKUItem],
        box_type: BoxType,
    ) -> Decimal:
        """计算填充率百分比。"""
        total_vol = sum(
            ((it.length or Decimal(0)) * (it.width or Decimal(0))
             * (it.height or Decimal(0))) * it.quantity
            for it in items
        )
        box_vol = box_type.inner_dimensions.volume
        if box_vol == 0:
            return Decimal("0")
        return (total_vol / box_vol) * Decimal("100")

    def check_and_optimize(
        self,
        items: list[SKUItem],
        current_box: BoxType,
        available_boxes: list[BoxType],
        carrier_limits: Optional[CarrierLimits] = None,
        min_rate: Decimal = Decimal("60"),
        max_rate: Decimal = Decimal("90"),
        has_fragile: bool = False,
    ) -> tuple[BoxType, Decimal, list[PackageFlag]]:
        """校验填充率并尝试优化。

        Returns:
            (最终箱型, 填充率, 标记列表)
        """
        total_vol = sum(
            ((it.length or Decimal(0)) * (it.width or Decimal(0))
             * (it.height or Decimal(0))) * it.quantity
            for it in items
        )
        total_wt = sum(
            (it.weight or Decimal(0)) * it.quantity
            for it in items
        )

        fill_rate = self.calculate_fill_rate(items, current_box)
        flags: list[PackageFlag] = []

        if fill_rate >= min_rate:
            return current_box, fill_rate, flags

        # 尝试换更小箱型
        smaller_boxes = self._find_smaller_boxes(
            current_box, available_boxes, total_vol, total_wt,
            carrier_limits, has_fragile,
        )

        best_box = current_box
        best_rate = fill_rate

        for sb in smaller_boxes:
            rate = self._calc_rate(total_vol, sb)
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
        total_vol: Decimal,
        total_wt: Decimal,
        carrier_limits: Optional[CarrierLimits],
        has_fragile: bool,
    ) -> list[BoxType]:
        """找到比当前箱型更小但仍能容纳的箱型，按体积升序排列。"""
        candidates = []
        current_vol = current.inner_dimensions.volume

        for bt in available:
            if bt.box_id == current.box_id:
                continue
            bv = bt.inner_dimensions.volume
            if bv >= current_vol:
                continue  # 不比当前小
            if bv < total_vol:
                continue  # 装不下
            if bt.max_weight < total_wt:
                continue
            if has_fragile and not bt.supports_shock_proof:
                continue
            if carrier_limits:
                outer = bt.outer_dimensions
                limit = carrier_limits.max_dimension
                if (outer.length > limit.length or outer.width > limit.width
                        or outer.height > limit.height):
                    continue
            candidates.append(bt)

        # 按体积升序（最小的先尝试）
        candidates.sort(key=lambda b: b.inner_dimensions.volume)
        return candidates

    @staticmethod
    def _calc_rate(total_vol: Decimal, box: BoxType) -> Decimal:
        bv = box.inner_dimensions.volume
        if bv == 0:
            return Decimal("0")
        return (total_vol / bv) * Decimal("100")
