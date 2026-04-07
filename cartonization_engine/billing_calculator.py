"""计费重量计算器 - 计算包裹计费重量"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_CEILING

from cartonization_engine.models import (
    BillingWeight,
    BoxType,
    CarrierLimits,
    SKUItem,
)


class BillingWeightCalculator:
    """计费重量计算器。

    actual = Σ(sku.weight × qty) + box.material_weight
    volumetric = (outer_l × outer_w × outer_h) / dim_factor
    billing = ceil(max(actual, volumetric) × 10) / 10
    """

    def calculate(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> BillingWeight:
        """计算包裹计费重量。"""
        # 实际重量
        actual = sum(
            (it.weight or Decimal(0)) * it.quantity for it in items
        ) + box_type.material_weight

        # 体积重量
        outer = box_type.outer_dimensions
        volumetric = (
            outer.length * outer.width * outer.height
        ) / Decimal(str(carrier_limits.dim_factor))

        # 计费重量 = ceil(max(actual, volumetric) * 10) / 10
        raw = max(actual, volumetric)
        billing = (raw * Decimal("10")).to_integral_value(rounding=ROUND_CEILING) / Decimal("10")

        return BillingWeight(
            actual_weight=actual,
            volumetric_weight=volumetric,
            billing_weight=billing,
        )
