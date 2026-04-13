"""几何放置校验器 - 模拟逐层放置验证商品能否物理装入箱型"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from cartonization_engine.models import BoxType, Dimensions, SKUItem


@dataclass
class PlacementInfo:
    """单件商品的放置信息"""
    sku_id: str
    item_orientation: str  # "upright", "rotated", "fixed"
    occupy_full_layer: bool
    stacked_on_other: bool
    placement_mode: str  # "side_by_side", "layered", "single_layer", "single_item"
    layer_index: int
    geometry_valid: bool
    geometry_reason: str


@dataclass
class GeometryCheckResult:
    """几何校验结果"""
    passed: bool
    reason: str
    placements: list[PlacementInfo] = field(default_factory=list)
    total_height_used: Decimal = Decimal("0")
    box_height_available: Decimal = Decimal("0")


class GeometryChecker:
    """几何放置校验器。

    模拟逐层放置，验证商品在箱型内的物理可行性。
    排序优先级：non-stackable > upright_required > 按高度降序。
    """

    def check(self, items: list[SKUItem], box: BoxType) -> GeometryCheckResult:
        """对一组 SKU 执行几何放置校验。"""
        box_length = box.inner_dimensions.length
        box_width = box.inner_dimensions.width
        box_height = box.inner_dimensions.height
        box_footprint = box_length * box_width

        # 展开为单件
        expanded: list[SKUItem] = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item)

        # 排序：non-stackable 优先，然后 upright_required，然后按高度降序
        expanded.sort(key=lambda it: (
            0 if not it.stackable else 1,
            0 if it.upright_required else 1,
            -(it.height or Decimal(0)),
        ))

        placements: list[PlacementInfo] = []
        current_layer_index = 0
        total_height_used = Decimal("0")
        current_layer_height = Decimal("0")
        current_layer_footprint_used = Decimal("0")
        all_valid = True
        fail_reason = ""

        for item in expanded:
            item_l = item.length or Decimal(0)
            item_w = item.width or Decimal(0)
            item_h = item.height or Decimal(0)

            if not item.stackable:
                # Non-stackable: 每件占用整层
                if current_layer_footprint_used > 0:
                    # 当前层已有物品，开新层
                    total_height_used += current_layer_height
                    current_layer_index += 1
                    current_layer_height = Decimal("0")
                    current_layer_footprint_used = Decimal("0")

                layer_height = item_h
                remaining = box_height - total_height_used
                valid = layer_height <= remaining
                reason = "OK" if valid else f"non-stackable 层高 {layer_height} 超过剩余高度 {remaining}"
                if not valid and all_valid:
                    all_valid = False
                    fail_reason = reason

                placements.append(PlacementInfo(
                    sku_id=item.sku_id,
                    item_orientation="fixed",
                    occupy_full_layer=True,
                    stacked_on_other=current_layer_index > 0,
                    placement_mode="single_layer",
                    layer_index=current_layer_index,
                    geometry_valid=valid,
                    geometry_reason=reason,
                ))
                total_height_used += layer_height
                current_layer_index += 1
                current_layer_height = Decimal("0")
                current_layer_footprint_used = Decimal("0")

            elif item.upright_required:
                # Upright: 高度必须沿箱高方向
                remaining = box_height - total_height_used - current_layer_height
                # 如果当前层高度不够，尝试开新层
                if current_layer_height > 0 and item_h > (box_height - total_height_used - current_layer_height):
                    total_height_used += current_layer_height
                    current_layer_index += 1
                    current_layer_height = Decimal("0")
                    current_layer_footprint_used = Decimal("0")

                remaining = box_height - total_height_used
                valid = item_h <= remaining
                reason = "OK" if valid else f"upright 高度 {item_h} 超过剩余高度 {remaining}"
                if not valid and all_valid:
                    all_valid = False
                    fail_reason = reason

                # 并排放置
                item_footprint = item_l * item_w
                if current_layer_footprint_used + item_footprint > box_footprint:
                    # 当前层底面积不够，开新层
                    total_height_used += current_layer_height
                    current_layer_index += 1
                    current_layer_height = Decimal("0")
                    current_layer_footprint_used = Decimal("0")

                current_layer_height = max(current_layer_height, item_h)
                current_layer_footprint_used += item_footprint

                placements.append(PlacementInfo(
                    sku_id=item.sku_id,
                    item_orientation="upright",
                    occupy_full_layer=False,
                    stacked_on_other=current_layer_index > 0,
                    placement_mode="side_by_side",
                    layer_index=current_layer_index,
                    geometry_valid=valid,
                    geometry_reason=reason,
                ))

            else:
                # Normal stackable: 放入剩余空间
                item_footprint = item_l * item_w
                if current_layer_footprint_used + item_footprint > box_footprint:
                    # 开新层
                    total_height_used += current_layer_height
                    current_layer_index += 1
                    current_layer_height = Decimal("0")
                    current_layer_footprint_used = Decimal("0")

                current_layer_height = max(current_layer_height, item_h)
                current_layer_footprint_used += item_footprint

                remaining = box_height - total_height_used
                valid = current_layer_height <= remaining
                reason = "OK" if valid else f"层高 {current_layer_height} 超过剩余高度 {remaining}"
                if not valid and all_valid:
                    all_valid = False
                    fail_reason = reason

                is_single = len(expanded) == 1
                placements.append(PlacementInfo(
                    sku_id=item.sku_id,
                    item_orientation="rotated" if item.rotate_allowed else "fixed",
                    occupy_full_layer=False,
                    stacked_on_other=current_layer_index > 0,
                    placement_mode="single_item" if is_single else "layered",
                    layer_index=current_layer_index,
                    geometry_valid=valid,
                    geometry_reason=reason,
                ))

        # 加上最后一层的高度
        total_height_used += current_layer_height

        if total_height_used > box_height:
            all_valid = False
            if not fail_reason:
                fail_reason = f"总高度 {total_height_used} 超过箱高 {box_height}"

        return GeometryCheckResult(
            passed=all_valid,
            reason="OK" if all_valid else fail_reason,
            placements=placements,
            total_height_used=total_height_used,
            box_height_available=box_height,
        )
