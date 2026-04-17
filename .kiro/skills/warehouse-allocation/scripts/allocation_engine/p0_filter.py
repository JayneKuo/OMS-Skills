"""寻仓推荐引擎 — P0 硬约束过滤

对每个仓库执行 5 条硬约束检查，输出通过的候选仓和被淘汰的仓。
"""

from __future__ import annotations

from .models import (
    Address,
    EliminatedWarehouse,
    OrderItem,
    ScoredWarehouse,
    Warehouse,
)

# 国家名标准化映射
_COUNTRY_ALIASES: dict[str, str] = {
    "US": "US", "USA": "US", "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US",
    "CN": "CN", "CHINA": "CN",
    "UK": "GB", "UNITED KINGDOM": "GB", "GB": "GB",
    "CA": "CA", "CANADA": "CA",
}


def _normalize_country(country: str) -> str:
    """标准化国家名（US/USA → US，大小写不敏感）。"""
    upper = (country or "").strip().upper()
    return _COUNTRY_ALIASES.get(upper, upper)


class P0Filter:
    """P0 硬约束过滤器。

    依次检查仓状态、SKU 库存、配送国家、温区匹配，
    记录所有淘汰原因后输出候选仓和淘汰仓。
    """

    def filter(
        self,
        warehouses: list[Warehouse],
        items: list[OrderItem],
        address: Address,
        degradation: list[str],
        skip_inventory_check: bool = False,
    ) -> tuple[list[ScoredWarehouse], list[EliminatedWarehouse]]:
        """执行 P0 过滤。

        Parameters
        ----------
        skip_inventory_check : bool
            为 True 时跳过库存硬约束（当商户配置了 ONE_WAREHOUSE_BACKUP 规则时）。
            库存信息仍会记录到 fulfillable_skus/missing_skus，但不作为淘汰条件。

        Returns
        -------
        candidates : list[ScoredWarehouse]
            通过硬约束的候选仓（score=0，待 P2 评分）。
        eliminated : list[EliminatedWarehouse]
            未通过硬约束的淘汰仓（含原因列表）。
        """
        candidates: list[ScoredWarehouse] = []
        eliminated: list[EliminatedWarehouse] = []

        required_skus = {item.sku for item in items}

        for wh in warehouses:
            reasons: list[str] = []

            # P0-1: 仓状态检查
            self._check_status(wh, reasons)

            # P0-2: SKU 库存检查（记录但可能不淘汰）
            fulfillable_skus, missing_skus = self._check_inventory(
                wh, items, reasons, skip_inventory_check,
            )

            # P0-3: 配送国家匹配
            self._check_country(wh, address, reasons)

            # P0-4: 温区匹配（可选，无数据时跳过）
            self._check_temp_zone(wh, items, degradation, reasons)

            # P0-5: 淘汰原因记录
            if reasons:
                eliminated.append(EliminatedWarehouse(
                    warehouse_id=wh.warehouse_id,
                    warehouse_name=wh.warehouse_name,
                    accounting_code=wh.accounting_code,
                    reasons=reasons,
                ))
            else:
                can_fulfill_all = len(missing_skus) == 0 and len(fulfillable_skus) == len(required_skus)
                candidates.append(ScoredWarehouse(
                    warehouse_id=wh.warehouse_id,
                    warehouse_name=wh.warehouse_name,
                    accounting_code=wh.accounting_code,
                    score=0.0,
                    can_fulfill_all=can_fulfill_all,
                    fulfillable_skus=fulfillable_skus,
                    missing_skus=missing_skus,
                ))

        return candidates, eliminated

    # ── 各项检查 ──────────────────────────────────────

    @staticmethod
    def _check_status(wh: Warehouse, reasons: list[str]) -> None:
        """P0-1: 仓库必须 is_active 且 fulfillment_enabled。"""
        if not wh.is_active or not wh.fulfillment_enabled:
            reasons.append("仓库未启用")

    @staticmethod
    def _check_inventory(
        wh: Warehouse,
        items: list[OrderItem],
        reasons: list[str],
        skip_as_hard_constraint: bool = False,
    ) -> tuple[list[str], list[str]]:
        """P0-2: 检查每个 SKU 的库存是否满足需求。

        Parameters
        ----------
        skip_as_hard_constraint : bool
            为 True 时不因库存不足淘汰仓库（ONE_WAREHOUSE_BACKUP 模式）。

        Returns fulfillable_skus, missing_skus.
        """
        fulfillable: list[str] = []
        missing: list[str] = []

        for item in items:
            on_hand = wh.inventory.get(item.sku, 0)
            if on_hand >= item.quantity:
                fulfillable.append(item.sku)
            else:
                missing.append(item.sku)

        # 全部缺货 → 淘汰（除非 skip 模式）
        if not skip_as_hard_constraint:
            if len(missing) == len(items) and len(items) > 0:
                reasons.append("所有 SKU 均无库存")

        return fulfillable, missing

    @staticmethod
    def _check_country(wh: Warehouse, address: Address, reasons: list[str]) -> None:
        """P0-3: 仓库国家必须与收货地址国家匹配（大小写不敏感，US/USA 标准化）。"""
        wh_country = _normalize_country(wh.country)
        addr_country = _normalize_country(address.country)
        if wh_country != addr_country:
            reasons.append("不在配送范围（国家不匹配）")

    @staticmethod
    def _check_temp_zone(
        wh: Warehouse,
        items: list[OrderItem],
        degradation: list[str],
        reasons: list[str],
    ) -> None:
        """P0-4: 温区匹配（可选）。

        当前 MVP 无温区数据，跳过检查并标记降级。
        """
        # MVP 阶段：无温区数据，跳过并标记降级
        if "temp_zone_defaulted" not in degradation:
            degradation.append("temp_zone_defaulted")
