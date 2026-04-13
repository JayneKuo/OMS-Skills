"""回退处理器 - 4 级回退策略"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
import uuid

from cartonization_engine.models import (
    BillingWeight,
    BoxType,
    CarrierLimits,
    DecisionLog,
    Dimensions,
    FallbackContext,
    FallbackLevel,
    FallbackResult,
    Package,
    PackageFlag,
    PackageItem,
    SKUItem,
)
from cartonization_engine.box_selector import BoxSelector
from cartonization_engine.packer import FFDPacker


class FallbackHandler:
    """回退处理器。

    按 F1→F2→F3→F4 顺序逐级尝试回退。
    F1: 非标箱型
    F2: 虚拟箱型 + 人工包装标记
    F3: 超大件承运商切换标记
    F4: 规则冲突人工介入标记
    """

    def __init__(self):
        self._selector = BoxSelector()
        self._packer = FFDPacker()

    def handle(
        self,
        items: list[SKUItem],
        failure_reason: str,
        context: FallbackContext,
        carrier_limits: CarrierLimits,
        force_carrier_issue: bool = False,
    ) -> FallbackResult:
        """按 F1→F3→F2→F4 顺序逐级尝试回退。

        F3 在 F2 之前：如果是承运商尺寸/重量超限，应优先建议切换承运商，
        而不是直接使用虚拟箱型。
        """

        # F1: 尝试非标箱型
        f1 = self._try_f1(items, context, carrier_limits)
        if f1 is not None:
            return f1

        # F3: 承运商超限 → 建议切换大件承运商（优先于 F2）
        if force_carrier_issue or self._is_carrier_issue(items, carrier_limits):
            f3 = self._try_f3(items, carrier_limits)
            if f3 is not None:
                return f3

        # F2: 虚拟箱型 + 人工包装
        f2 = self._try_f2(items, carrier_limits)
        if f2 is not None:
            return f2

        # F4: 规则冲突人工介入
        return self._try_f4(items, failure_reason)

    def _is_carrier_issue(
        self,
        items: list[SKUItem],
        carrier_limits: CarrierLimits,
    ) -> bool:
        """判断失败是否因为承运商限制（尺寸或重量超限）。

        如果有箱型能装下商品但超过承运商尺寸限制，则判定为承运商问题。
        """
        limit = carrier_limits.max_dimension
        limit_dims = sorted([limit.length, limit.width, limit.height], reverse=True)
        # 检查单件是否超过承运商尺寸
        for it in items:
            l = it.length or Decimal(0)
            w = it.width or Decimal(0)
            h = it.height or Decimal(0)
            item_dims = sorted([l, w, h], reverse=True)
            if item_dims[0] > limit_dims[0] or item_dims[1] > limit_dims[1]:
                return True
        # 检查总重是否超过承运商限制
        total_wt = sum((it.weight or Decimal(0)) * it.quantity for it in items)
        if total_wt > carrier_limits.max_weight:
            return True
        # 检查总体积是否需要超过承运商尺寸的箱型
        total_vol = sum(
            (it.length or Decimal(0)) * (it.width or Decimal(0)) * (it.height or Decimal(0)) * it.quantity
            for it in items
        )
        # 如果最小能装下的箱型体积 > 承运商最大体积限制
        max_carrier_vol = limit.length * limit.width * limit.height
        if total_vol > max_carrier_vol * Decimal("0.9"):
            return True
        return False

    def _try_f1(
        self,
        items: list[SKUItem],
        context: FallbackContext,
        carrier_limits: CarrierLimits,
    ) -> Optional[FallbackResult]:
        """F1: 尝试非标箱型。"""
        non_std = context.non_standard_box_types
        if not non_std:
            return None

        has_fragile = any(it.fragile_flag for it in items)
        selected = self._selector.select(
            items, non_std, carrier_limits, has_fragile=has_fragile,
        )
        if selected is None:
            return None

        pack_result = self._packer.pack(items, selected)
        if not pack_result.bins:
            return None

        pkgs = self._bins_to_packages(pack_result.bins, selected, "F1非标箱型回退")
        return FallbackResult(
            success=True,
            level=FallbackLevel.F1_NON_STANDARD_BOX,
            packages=pkgs,
            message="使用非标箱型完成装箱",
        )

    def _try_f2(
        self,
        items: list[SKUItem],
        carrier_limits: CarrierLimits,
    ) -> Optional[FallbackResult]:
        """F2: 虚拟箱型 + 人工包装标记。"""
        total_vol = sum(
            (it.length or Decimal(0)) * (it.width or Decimal(0))
            * (it.height or Decimal(0)) * it.quantity
            for it in items
        )
        total_wt = sum(
            (it.weight or Decimal(0)) * it.quantity for it in items
        )

        # 创建虚拟箱型，尺寸按 SKU 总体积的立方根估算
        side = _cube_root(total_vol) + Decimal("5")
        virtual_box = BoxType(
            box_id="VIRTUAL_BOX",
            inner_dimensions=Dimensions(length=side, width=side, height=side),
            outer_dimensions=Dimensions(
                length=side + Decimal("2"),
                width=side + Decimal("2"),
                height=side + Decimal("2"),
            ),
            max_weight=total_wt + Decimal("10"),
            material_weight=Decimal("0"),
            packaging_cost=Decimal("0"),
            is_standard=False,
        )

        pkg_items = [
            PackageItem(sku_id=it.sku_id, sku_name=it.sku_name, quantity=it.quantity)
            for it in items
        ]
        pkg = Package(
            package_id=f"PKG-{uuid.uuid4().hex[:8]}",
            items=pkg_items,
            box_type=virtual_box,
            billing_weight=BillingWeight(
                actual_weight=total_wt,
                volumetric_weight=total_vol / Decimal(str(carrier_limits.dim_factor)),
                billing_weight=max(total_wt, total_vol / Decimal(str(carrier_limits.dim_factor))),
            ),
            fill_rate=Decimal("100"),
            flags=[PackageFlag.MANUAL_PACKING],
            decision_log=DecisionLog(
                group_reason="F2虚拟箱型回退",
                box_selection_reason="虚拟箱型",
            ),
        )
        return FallbackResult(
            success=True,
            level=FallbackLevel.F2_VIRTUAL_BOX,
            packages=[pkg],
            message="使用虚拟箱型，需人工包装",
        )

    def _try_f3(
        self,
        items: list[SKUItem],
        carrier_limits: CarrierLimits,
    ) -> Optional[FallbackResult]:
        """F3: 标记承运商尺寸超限，建议切换大件承运商。"""
        total_vol = sum(
            (it.length or Decimal(0)) * (it.width or Decimal(0))
            * (it.height or Decimal(0)) * it.quantity
            for it in items
        )
        total_wt = sum(
            (it.weight or Decimal(0)) * it.quantity for it in items
        )

        side = _cube_root(total_vol) + Decimal("5")
        virtual_box = BoxType(
            box_id="OVERSIZE_VIRTUAL",
            inner_dimensions=Dimensions(length=side, width=side, height=side),
            outer_dimensions=Dimensions(
                length=side + Decimal("2"),
                width=side + Decimal("2"),
                height=side + Decimal("2"),
            ),
            max_weight=total_wt + Decimal("10"),
            material_weight=Decimal("0"),
            packaging_cost=Decimal("0"),
            is_standard=False,
        )

        pkg_items = [
            PackageItem(sku_id=it.sku_id, sku_name=it.sku_name, quantity=it.quantity)
            for it in items
        ]
        pkg = Package(
            package_id=f"PKG-{uuid.uuid4().hex[:8]}",
            items=pkg_items,
            box_type=virtual_box,
            billing_weight=BillingWeight(
                actual_weight=total_wt,
                volumetric_weight=total_vol / Decimal(str(carrier_limits.dim_factor)),
                billing_weight=max(total_wt, total_vol / Decimal(str(carrier_limits.dim_factor))),
            ),
            fill_rate=Decimal("100"),
            flags=[PackageFlag.CARRIER_OVERSIZE],
            decision_log=DecisionLog(
                group_reason="F3承运商超限回退",
                box_selection_reason="超限虚拟箱型",
            ),
        )
        return FallbackResult(
            success=True,
            level=FallbackLevel.F3_OVERSIZE_CARRIER,
            packages=[pkg],
            message="承运商尺寸超限，建议切换大件承运商",
        )

    def _try_f4(
        self,
        items: list[SKUItem],
        failure_reason: str,
    ) -> FallbackResult:
        """F4: 规则冲突人工介入。"""
        return FallbackResult(
            success=False,
            level=FallbackLevel.F4_MANUAL_INTERVENTION,
            packages=[],
            message=f"规则冲突待人工介入: {failure_reason}",
        )

    def _bins_to_packages(
        self,
        bins: list,
        box_type: BoxType,
        reason: str,
    ) -> list[Package]:
        """将 OpenBin 列表转换为 Package 列表。"""
        packages: list[Package] = []
        for b in bins:
            # 合并同 SKU 的数量
            qty_map: dict[str, tuple[str, int]] = {}
            for item in b.items:
                if item.sku_id in qty_map:
                    name, q = qty_map[item.sku_id]
                    qty_map[item.sku_id] = (name, q + item.quantity)
                else:
                    qty_map[item.sku_id] = (item.sku_name, item.quantity)

            pkg_items = [
                PackageItem(sku_id=sid, sku_name=name, quantity=qty)
                for sid, (name, qty) in qty_map.items()
            ]
            packages.append(Package(
                package_id=f"PKG-{uuid.uuid4().hex[:8]}",
                items=pkg_items,
                box_type=box_type,
                billing_weight=BillingWeight(
                    actual_weight=b.used_weight + box_type.material_weight,
                    volumetric_weight=Decimal("0"),
                    billing_weight=b.used_weight + box_type.material_weight,
                ),
                fill_rate=Decimal("0"),
                flags=[],
                decision_log=DecisionLog(
                    group_reason=reason,
                    box_selection_reason="回退箱型选择",
                ),
            ))
        return packages


def _cube_root(val: Decimal) -> Decimal:
    """计算 Decimal 的立方根（近似）。"""
    if val <= 0:
        return Decimal("1")
    f = float(val)
    root = f ** (1.0 / 3.0)
    return Decimal(str(round(root, 1)))
