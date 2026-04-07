"""超大件处理器 - 分离超大件 SKU 并单独成包"""

from __future__ import annotations

from dataclasses import dataclass, field

from cartonization_engine.models import (
    PackageFlag,
    SKUItem,
)


@dataclass
class OversizeSeparationResult:
    """超大件分离结果"""
    normal_items: list[SKUItem] = field(default_factory=list)
    oversize_packages: list[OversizePackage] = field(default_factory=list)


@dataclass
class OversizePackage:
    """超大件独立包裹"""
    item: SKUItem
    flags: list[PackageFlag] = field(default_factory=lambda: [PackageFlag.OVERSIZE_SPECIAL])


class OversizeHandler:
    """超大件处理器。

    职责：
    - 从 SKU 列表中分离 oversize_flag=True 的 SKU
    - 每个超大件 SKU 单独成包并标记 OVERSIZE_SPECIAL
    - 确保超大件不与普通 SKU 混装
    """

    def separate(self, items: list[SKUItem]) -> OversizeSeparationResult:
        """将 SKU 列表分为超大件和普通件。

        每个超大件 SKU 单独成为一个 OversizePackage，
        普通件保留在 normal_items 中继续后续装箱流程。
        """
        result = OversizeSeparationResult()

        for item in items:
            if item.oversize_flag:
                result.oversize_packages.append(OversizePackage(item=item))
            else:
                result.normal_items.append(item)

        return result
