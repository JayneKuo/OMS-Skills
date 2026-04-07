"""FFD 排序器 - 按体积降序、重量降序排列 SKU"""

from __future__ import annotations

from decimal import Decimal

from cartonization_engine.models import SKUItem


class FFDSorter:
    """FFD（First Fit Decreasing）排序器。

    按单件体积从大到小排序，体积相同时按单件重量从大到小排序。
    """

    @staticmethod
    def sort(items: list[SKUItem]) -> list[SKUItem]:
        """对 SKU 列表按 FFD 策略排序（不修改原列表）。"""
        def _sort_key(item: SKUItem) -> tuple[Decimal, Decimal]:
            vol = (item.length or Decimal(0)) * (item.width or Decimal(0)) * (item.height or Decimal(0))
            wt = item.weight or Decimal(0)
            # 负号实现降序
            return (-vol, -wt)

        return sorted(items, key=_sort_key)
