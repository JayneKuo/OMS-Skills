"""多包拆分器 - 超重/超体积时拆分为多包"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from cartonization_engine.models import SKUItem


@dataclass
class SplitBin:
    """拆分后的单个包裹容器"""
    items: list[SKUItem] = field(default_factory=list)
    total_weight: Decimal = Decimal("0")
    total_volume: Decimal = Decimal("0")

    def add(self, item: SKUItem) -> None:
        wt = (item.weight or Decimal(0)) * item.quantity
        vol = ((item.length or Decimal(0)) * (item.width or Decimal(0))
               * (item.height or Decimal(0))) * item.quantity
        self.items.append(item)
        self.total_weight += wt
        self.total_volume += vol


@dataclass
class SplitResult:
    """拆分结果"""
    success: bool
    bins: list[SplitBin] = field(default_factory=list)
    error_message: Optional[str] = None


class PackageSplitter:
    """多包拆分器。

    当单箱无法容纳时拆分为多包。
    优先均匀分配重量，确保不超过 max_package_count。
    """

    def split(
        self,
        items: list[SKUItem],
        max_weight: Decimal,
        max_volume: Decimal,
        max_packages: int = 5,
    ) -> SplitResult:
        """将 SKU 列表拆分为多个包裹。

        Args:
            items: 待拆分的 SKU 列表
            max_weight: 单包最大重量
            max_volume: 单包最大体积
            max_packages: 最大包裹数

        Returns:
            SplitResult
        """
        if not items:
            return SplitResult(success=True)

        # 展开为单件
        expanded: list[SKUItem] = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item.model_copy(update={"quantity": 1}))

        # 按重量降序排列以实现更均匀分配
        expanded.sort(
            key=lambda it: (it.weight or Decimal(0)),
            reverse=True,
        )

        # 贪心分配：逐件放入当前最轻的包裹
        bins: list[SplitBin] = [SplitBin()]

        for single in expanded:
            wt = single.weight or Decimal(0)
            vol = ((single.length or Decimal(0)) * (single.width or Decimal(0))
                   * (single.height or Decimal(0)))

            # 尝试放入已有包裹（选最轻的）
            placed = False
            candidates = sorted(bins, key=lambda b: b.total_weight)
            for b in candidates:
                if b.total_weight + wt <= max_weight and b.total_volume + vol <= max_volume:
                    b.add(single)
                    placed = True
                    break

            if not placed:
                if len(bins) >= max_packages:
                    return SplitResult(
                        success=False,
                        bins=bins,
                        error_message=f"包裹数超限: 需要 >{max_packages} 个包裹",
                    )
                new_bin = SplitBin()
                new_bin.add(single)
                bins.append(new_bin)

        return SplitResult(success=True, bins=bins)
