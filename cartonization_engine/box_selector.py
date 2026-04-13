"""箱型选择器 - 为包裹选择最优箱型"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    PackagingParams,
    ProtectionCoefficients,
    SKUItem,
    TemperatureZone,
)


class BoxSelector:
    """箱型选择器。

    选择优先级：
    1. 箱型库存可用（available_qty > 0 或 None）
    2. 箱型温区支持
    3. 物理容纳（内部体积 >= SKU 总体积 × 保护系数，最大承重 >= SKU 总重量 + 包材重量）
    4. 承运商尺寸/围长/体积合规
    5. 易碎品需 supports_shock_proof=True
    6. 液体品需 supports_leak_proof=True
    7. 计费重量最低
    8. 包材成本最低
    """

    def select(
        self,
        items: list[SKUItem],
        box_types: list[BoxType],
        carrier_limits: CarrierLimits,
        has_fragile: bool = False,
        has_liquid: bool = False,
        temperature_zone: Optional[TemperatureZone] = None,
        packaging_params: Optional[PackagingParams] = None,
        protection_coefficients: Optional[ProtectionCoefficients] = None,
    ) -> Optional[BoxType]:
        """为一组 SKU 选择最优箱型。"""
        pkg_params = packaging_params or PackagingParams()
        prot_coeff = protection_coefficients or ProtectionCoefficients()

        # 应用保护系数到体积
        volume_coeff = self._get_volume_coefficient(items, prot_coeff)

        # 加上包材占用的体积和重量
        extra_weight, extra_volume = self._calc_packaging_overhead(items, pkg_params)

        # 总重量（不含箱体自重，箱体自重在候选过滤时加）
        total_weight = Decimal("0")
        for item in items:
            item_wt = item.weight or Decimal(0)
            total_weight += item_wt * item.quantity
        effective_weight = total_weight + extra_weight

        candidates: list[BoxType] = []
        for bt in box_types:
            # 0. 库存过滤
            if bt.available_qty is not None and bt.available_qty <= 0:
                continue

            # 0.5 温区支持
            if temperature_zone and temperature_zone not in bt.temperature_zone_supported:
                continue

            # 1. 单件尺寸校验
            if not self._all_items_fit(items, bt):
                continue

            # 2. 计算有效体积（含 non-stackable 整层占用）
            effective_volume = self._calc_effective_volume(items, bt, volume_coeff) + extra_volume
            if bt.inner_dimensions.volume < effective_volume:
                continue

            # 承重校验：商品重量 + 包材重量 + 箱体自重 <= max_weight
            if bt.max_weight < effective_weight + bt.material_weight:
                continue

            # 3. 承运商尺寸合规（含围长和体积）
            if not self._carrier_compliant(bt, carrier_limits):
                continue

            # 4. 易碎品需防震
            if has_fragile and not bt.supports_shock_proof:
                continue

            # 5. 液体品需防漏
            if has_liquid and not bt.supports_leak_proof:
                continue

            candidates.append(bt)

        if not candidates:
            return None

        def _sort_key(bt: BoxType):
            actual_wt = effective_weight + bt.material_weight
            outer_vol = bt.outer_dimensions.volume
            volumetric_wt = outer_vol / Decimal(str(carrier_limits.dim_factor))
            billing_wt = max(actual_wt, volumetric_wt)
            return (billing_wt, bt.packaging_cost)

        candidates.sort(key=_sort_key)
        return candidates[0]

    @staticmethod
    def _calc_effective_volume(
        items: list[SKUItem],
        bt: BoxType,
        volume_coeff: Decimal,
    ) -> Decimal:
        """计算有效体积，non-stackable 商品按整层计算。"""
        total = Decimal("0")
        box_footprint = bt.inner_dimensions.length * bt.inner_dimensions.width
        for item in items:
            if not item.stackable:
                ih = item.height or Decimal(0)
                item_vol = box_footprint * ih
            else:
                item_vol = (item.length or Decimal(0)) * (item.width or Decimal(0)) * (item.height or Decimal(0))
            total += item_vol * item.quantity
        return total * volume_coeff

    @staticmethod
    def _get_volume_coefficient(
        items: list[SKUItem],
        prot: ProtectionCoefficients,
    ) -> Decimal:
        """根据商品属性返回最大保护系数。"""
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
        items: list[SKUItem],
        params: PackagingParams,
    ) -> tuple[Decimal, Decimal]:
        """计算包材额外重量和体积。"""
        extra_wt = Decimal("0")
        extra_vol = Decimal("0")
        has_fragile = any(it.fragile_flag for it in items)
        has_liquid = any(it.liquid_flag for it in items)
        has_gift = any(it.is_gift for it in items)
        if has_fragile:
            extra_wt += params.cushion_weight_kg
            extra_vol += params.cushion_volume_cm3
        if has_liquid:
            extra_wt += params.leakproof_weight_kg
            extra_vol += params.leakproof_volume_cm3
        if has_gift:
            extra_wt += params.gift_wrap_weight_kg
            extra_vol += params.gift_wrap_volume_cm3
        return extra_wt, extra_vol

    @staticmethod
    def _all_items_fit(items: list[SKUItem], bt: BoxType) -> bool:
        """检查每个 SKU 是否能物理放入箱型（考虑旋转和立放约束）。

        upright_required=True 时，商品的 height 必须沿箱型高度方向放置，
        即 item.height <= box.height，且 item.length/width 在箱型 length/width 内。
        """
        box_dims = sorted([bt.inner_dimensions.length, bt.inner_dimensions.width, bt.inner_dimensions.height], reverse=True)
        box_height = bt.inner_dimensions.height
        box_lw = sorted([bt.inner_dimensions.length, bt.inner_dimensions.width], reverse=True)
        for item in items:
            l = item.length or Decimal(0)
            w = item.width or Decimal(0)
            h = item.height or Decimal(0)
            if l == 0 and w == 0 and h == 0:
                continue
            if item.upright_required:
                # 立放：height 必须沿箱型高度方向
                if h > box_height:
                    return False
                item_lw = sorted([l, w], reverse=True)
                if item_lw[0] > box_lw[0] or item_lw[1] > box_lw[1]:
                    return False
            elif item.rotate_allowed:
                # 可旋转：排序后逐维比较
                item_dims = sorted([l, w, h], reverse=True)
                if item_dims[0] > box_dims[0] or item_dims[1] > box_dims[1] or item_dims[2] > box_dims[2]:
                    return False
            else:
                # 不可旋转：固定方向放入
                if l > bt.inner_dimensions.length or w > bt.inner_dimensions.width or h > bt.inner_dimensions.height:
                    return False
        return True

    @staticmethod
    def _carrier_compliant(bt: BoxType, carrier: CarrierLimits) -> bool:
        """检查箱型外部尺寸是否符合承运商限制（含围长和体积）。"""
        outer = bt.outer_dimensions
        limit = carrier.max_dimension
        dims = sorted([outer.length, outer.width, outer.height], reverse=True)
        limit_dims = sorted([limit.length, limit.width, limit.height], reverse=True)
        if dims[0] > limit_dims[0] or dims[1] > limit_dims[1] or dims[2] > limit_dims[2]:
            return False
        # 围长校验: girth = longest + 2*(second + third)
        if carrier.max_girth is not None:
            girth = dims[0] + Decimal("2") * (dims[1] + dims[2])
            if girth > carrier.max_girth:
                return False
        # 体积校验
        if carrier.max_volume is not None:
            if outer.volume > carrier.max_volume:
                return False
        return True
