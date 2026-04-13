"""几何摆放校验器 - 验证商品在箱型内的物理摆放合法性"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    ItemGeometry,
    PlacementMode,
    SKUItem,
)


@dataclass
class GeometryResult:
    """几何校验结果"""
    passed: bool
    reason: str
    item_geometries: list[ItemGeometry]
    total_height_used: Decimal = Decimal("0")


class GeometryValidator:
    """几何摆放校验器。

    对包裹内的商品执行分层摆放模拟：
    1. 不可叠放商品独占整层（箱底面积×商品高度）
    2. 必须立放商品高度沿箱型高度方向
    3. 易碎品不可被压在其他商品下方
    4. 液体品尽量立放
    5. 所有层高度之和 ≤ 箱型内高
    """

    def validate(
        self,
        items: list[SKUItem],
        box_type: BoxType,
    ) -> GeometryResult:
        """执行几何摆放校验。"""
        box_l = box_type.inner_dimensions.length
        box_w = box_type.inner_dimensions.width
        box_h = box_type.inner_dimensions.height
        box_footprint = box_l * box_w

        # 展开为单件
        expanded: list[SKUItem] = []
        for it in items:
            for _ in range(it.quantity):
                expanded.append(it.model_copy(update={"quantity": 1}))

        # 分类
        full_layer_items = [it for it in expanded if not it.stackable]
        upright_items = [it for it in expanded if it.upright_required and it.stackable]
        fragile_items = [it for it in expanded if it.fragile_flag and it.stackable and not it.upright_required]
        normal_items = [it for it in expanded
                        if it.stackable and not it.upright_required and not it.fragile_flag]

        geometries: list[ItemGeometry] = []
        total_height = Decimal("0")

        # Layer 1: 不可叠放商品，每件独占一层
        for it in full_layer_items:
            h = it.height or Decimal(0)
            l = it.length or Decimal(0)
            w = it.width or Decimal(0)
            # 检查底面是否放得下
            item_lw = sorted([l, w], reverse=True)
            box_lw = sorted([box_l, box_w], reverse=True)
            if item_lw[0] > box_lw[0] or item_lw[1] > box_lw[1]:
                return GeometryResult(
                    passed=False,
                    reason=f"{it.sku_id} 底面 {l}×{w} 超过箱型底面 {box_l}×{box_w}",
                    item_geometries=geometries,
                )
            total_height += h
            geometries.append(ItemGeometry(
                sku_id=it.sku_id,
                item_orientation="横放",
                occupy_full_layer=True,
                stacked_on_other_item=len(geometries) > 0,
                placement_mode=PlacementMode.FULL_LAYER.value,
                layer_height_used=h,
            ))

        # Layer 2: 必须立放商品
        for it in upright_items:
            h = it.height or Decimal(0)
            total_height += h
            geometries.append(ItemGeometry(
                sku_id=it.sku_id,
                item_orientation="立放",
                occupy_full_layer=False,
                stacked_on_other_item=False,
                placement_mode=PlacementMode.UPRIGHT.value,
                layer_height_used=h,
            ))

        # Layer 3: 普通品（可叠放）- 估算层高
        if normal_items:
            normal_vol = sum(
                (it.length or Decimal(0)) * (it.width or Decimal(0)) * (it.height or Decimal(0))
                for it in normal_items
            )
            if box_footprint > 0:
                est_height = normal_vol / box_footprint
            else:
                est