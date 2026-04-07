"""箱型选择器 - 为包裹选择最优箱型"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    SKUItem,
)


class BoxSelector:
    """箱型选择器。

    选择优先级：
    1. 物理容纳（内部体积 >= SKU 总体积，最大承重 >= SKU 总重量）
    2. 承运商尺寸合规（外部尺寸不超过 carrier max_dimension）
    3. 易碎品需 supports_shock_proof=True
    4. 计费重量最低
    5. 包材成本最低
    """

    def select(
        self,
        items: list[SKUItem],
        box_types: list[BoxType],
        carrier_limits: CarrierLimits,
        has_fragile: bool = False,
        has_heavy_non_fragile: bool = False,
    ) -> Optional[BoxType]:
        """为一组 SKU 选择最优箱型。

        Args:
            items: 包裹内的 SKU 列表
            box_types: 可用箱型列表
            carrier_limits: 承运商限制
            has_fragile: 是否包含易碎品
            has_heavy_non_fragile: 是否包含超3kg非易碎品

        Returns:
            最优箱型，无可用箱型时返回 None
        """
        total_volume = Decimal("0")
        total_weight = Decimal("0")
        for item in items:
            item_vol = (item.length or Decimal(0)) * (item.width or Decimal(0)) * (item.height or Decimal(0))
            item_wt = item.weight or Decimal(0)
            total_volume += item_vol * item.quantity
            total_weight += item_wt * item.quantity

        candidates: list[BoxType] = []
        for bt in box_types:
            # 0. 单件尺寸校验：每个 SKU 的最长边必须 ≤ 箱型最长内边
            if not self._all_items_fit(items, bt):
                continue

            # 1. 物理容纳
            if bt.inner_dimensions.volume < total_volume:
                continue
            if bt.max_weight < total_weight:
                continue

            # 2. 承运商尺寸合规
            if not self._carrier_compliant(bt, carrier_limits):
                continue

            # 3. 易碎品需防震
            if has_fragile and not bt.supports_shock_proof:
                continue

            candidates.append(bt)

        if not candidates:
            return None

        # 4. 按计费重量排序（计费重 = max(实际重, 体积重)）
        # 5. 计费重相同按包材成本排序
        def _sort_key(bt: BoxType):
            actual_wt = total_weight + bt.material_weight
            outer_vol = bt.outer_dimensions.volume
            volumetric_wt = outer_vol / Decimal(str(carrier_limits.dim_factor))
            billing_wt = max(actual_wt, volumetric_wt)
            return (billing_wt, bt.packaging_cost)

        candidates.sort(key=_sort_key)
        return candidates[0]

    @staticmethod
    def _all_items_fit(items: list[SKUItem], bt: BoxType) -> bool:
        """检查每个 SKU 是否能物理放入箱型（考虑旋转）。"""
        box_dims = sorted([bt.inner_dimensions.length, bt.inner_dimensions.width, bt.inner_dimensions.height], reverse=True)
        for item in items:
            l = item.length or Decimal(0)
            w = item.width or Decimal(0)
            h = item.height or Decimal(0)
            if l == 0 and w == 0 and h == 0:
                continue  # 无尺寸数据，跳过
            item_dims = sorted([l, w, h], reverse=True)
            # 允许旋转：排序后逐维比较
            if item.rotate_allowed and not item.upright_required:
                if item_dims[0] > box_dims[0] or item_dims[1] > box_dims[1] or item_dims[2] > box_dims[2]:
                    return False
            else:
                # 不允许旋转或必须立放：高度必须 ≤ 箱高，长宽排序后比较
                if h > bt.inner_dimensions.height:
                    return False
                lw = sorted([l, w], reverse=True)
                box_lw = sorted([bt.inner_dimensions.length, bt.inner_dimensions.width], reverse=True)
                if lw[0] > box_lw[0] or lw[1] > box_lw[1]:
                    return False
        return True

    @staticmethod
    def _carrier_compliant(bt: BoxType, carrier: CarrierLimits) -> bool:
        """检查箱型外部尺寸是否符合承运商限制。"""
        outer = bt.outer_dimensions
        limit = carrier.max_dimension
        return (
            outer.length <= limit.length
            and outer.width <= limit.width
            and outer.height <= limit.height
        )
