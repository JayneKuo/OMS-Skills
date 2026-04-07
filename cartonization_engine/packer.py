"""FFD 装箱器 - First Fit Decreasing 装箱核心算法"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    SKUGroup,
    SKUItem,
)
from cartonization_engine.sorter import FFDSorter


@dataclass
class OpenBin:
    """已开箱（装箱过程中的临时容器）"""
    box_type: BoxType
    items: list[SKUItem] = field(default_factory=list)
    used_volume: Decimal = Decimal("0")
    used_weight: Decimal = Decimal("0")

    @property
    def remaining_volume(self) -> Decimal:
        return self.box_type.inner_dimensions.volume - self.used_volume

    @property
    def remaining_weight(self) -> Decimal:
        return self.box_type.max_weight - self.used_weight

    def can_fit(self, item: SKUItem) -> bool:
        """检查箱型能否容纳该 SKU（体积 + 重量）"""
        item_vol = (item.length or Decimal(0)) * (item.width or Decimal(0)) * (item.height or Decimal(0))
        item_wt = item.weight or Decimal(0)
        return item_vol <= self.remaining_volume and item_wt <= self.remaining_weight

    def add(self, item: SKUItem) -> None:
        item_vol = (item.length or Decimal(0)) * (item.width or Decimal(0)) * (item.height or Decimal(0))
        item_wt = item.weight or Decimal(0)
        self.items.append(item)
        self.used_volume += item_vol
        self.used_weight += item_wt


@dataclass
class PackResult:
    """装箱结果"""
    bins: list[OpenBin] = field(default_factory=list)


class FFDPacker:
    """FFD 装箱器。

    对排序后的 SKU 逐件尝试放入第一个可容纳的已开箱，
    无法放入则开新箱。每个 SKU 的 quantity 会被展开为单件处理。
    """

    def __init__(self):
        self._sorter = FFDSorter()

    def pack(
        self,
        items: list[SKUItem],
        box_type: BoxType,
    ) -> PackResult:
        """对 SKU 列表执行 FFD 装箱。

        Args:
            items: 待装箱的 SKU 列表
            box_type: 使用的箱型

        Returns:
            PackResult 包含所有已开箱列表
        """
        if not items:
            return PackResult()

        # 1. FFD 排序
        sorted_items = self._sorter.sort(items)

        # 2. 展开 quantity 为单件
        expanded: list[SKUItem] = []
        for item in sorted_items:
            for _ in range(item.quantity):
                single = item.model_copy(update={"quantity": 1})
                expanded.append(single)

        # 3. 逐件 First Fit
        bins: list[OpenBin] = []
        for single_item in expanded:
            placed = False
            for b in bins:
                if b.can_fit(single_item):
                    b.add(single_item)
                    placed = True
                    break
            if not placed:
                new_bin = OpenBin(box_type=box_type)
                new_bin.add(single_item)
                bins.append(new_bin)

        return PackResult(bins=bins)
