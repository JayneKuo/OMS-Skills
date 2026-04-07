"""硬规则校验器 - 7 条硬规则全量检查"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    HazmatType,
    PackageItem,
    RuleViolation,
    SKUItem,
)


class HardRuleChecker:
    """硬规则校验器。

    对包裹执行 7 条独立硬规则校验，返回违反列表。
    空列表表示全部通过。
    """

    def check(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> list[RuleViolation]:
        """对一个包裹执行全部 7 条硬规则校验。"""
        violations: list[RuleViolation] = []
        for rule_fn in (
            self._check_temperature_zone,
            self._check_hazmat_isolation,
            self._check_weight_limit,
            self._check_dimension_limit,
            self._check_cannot_ship_with,
            self._check_fragile_protection,
            self._check_liquid_leak_proof,
        ):
            v = rule_fn(items, box_type, carrier_limits)
            if v is not None:
                violations.append(v)
        return violations

    def _check_temperature_zone(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 1: 同一包裹内所有 SKU 温区相同。"""
        if not items:
            return None
        zones = {item.temperature_zone for item in items}
        if len(zones) > 1:
            return RuleViolation(
                rule_name="温区不混装",
                violated_skus=[it.sku_id for it in items],
                description=f"包裹内存在多个温区: {', '.join(str(z) for z in zones)}",
            )
        return None

    def _check_hazmat_isolation(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 2: 危险品不与普通品混装。"""
        hazmat_items = [it for it in items if it.hazmat_type and it.hazmat_type != HazmatType.NONE]
        normal_items = [it for it in items if not it.hazmat_type or it.hazmat_type == HazmatType.NONE]
        if hazmat_items and normal_items:
            return RuleViolation(
                rule_name="危险品隔离",
                violated_skus=[it.sku_id for it in hazmat_items + normal_items],
                description="危险品与普通品混装",
            )
        return None

    def _check_weight_limit(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 3: 包裹重量 <= min(箱型承重, 承运商 max_weight)。"""
        total_weight = sum(
            (it.weight or Decimal(0)) * it.quantity for it in items
        )
        limit = min(box_type.max_weight, carrier_limits.max_weight)
        if total_weight > limit:
            return RuleViolation(
                rule_name="单包不超重",
                violated_skus=[it.sku_id for it in items],
                description=f"包裹重量 {total_weight}kg 超过限制 {limit}kg",
            )
        return None

    def _check_dimension_limit(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 4: 箱型外部尺寸 <= 承运商 max_dimension。"""
        outer = box_type.outer_dimensions
        limit = carrier_limits.max_dimension
        if (outer.length > limit.length
                or outer.width > limit.width
                or outer.height > limit.height):
            return RuleViolation(
                rule_name="单包不超尺寸",
                violated_skus=[it.sku_id for it in items],
                description=(
                    f"箱型外部尺寸 {outer.length}×{outer.width}×{outer.height} "
                    f"超过承运商限制 {limit.length}×{limit.width}×{limit.height}"
                ),
            )
        return None

    def _check_cannot_ship_with(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 5: cannot_ship_with 中的 SKU 不在同一包裹。"""
        sku_ids = {it.sku_id for it in items}
        for item in items:
            for forbidden_id in item.cannot_ship_with:
                if forbidden_id in sku_ids and forbidden_id != item.sku_id:
                    return RuleViolation(
                        rule_name="禁混品类隔离",
                        violated_skus=[item.sku_id, forbidden_id],
                        description=f"{item.sku_id} 禁止与 {forbidden_id} 同包",
                    )
        return None

    def _check_fragile_protection(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 6: 易碎品需防震箱型，且不含 >5kg 非易碎品。"""
        has_fragile = any(it.fragile_flag for it in items)
        if not has_fragile:
            return None

        if not box_type.supports_shock_proof:
            return RuleViolation(
                rule_name="易碎品保护",
                violated_skus=[it.sku_id for it in items if it.fragile_flag],
                description="包含易碎品但箱型不支持防震填充",
            )

        heavy_non_fragile = [
            it for it in items
            if not it.fragile_flag and (it.weight or Decimal(0)) > Decimal("3")
        ]
        if heavy_non_fragile:
            return RuleViolation(
                rule_name="易碎品保护",
                violated_skus=[it.sku_id for it in heavy_non_fragile],
                description="易碎品包裹内含有单件重量超过 3kg 的非易碎品",
            )
        return None

    def _check_liquid_leak_proof(
        self,
        items: list[SKUItem],
        box_type: BoxType,
        carrier_limits: CarrierLimits,
    ) -> Optional[RuleViolation]:
        """规则 7: 液体品需防漏箱型，且液体总量不超过承运商限制。"""
        liquid_items = [it for it in items if it.liquid_flag]
        if not liquid_items:
            return None
        if not box_type.supports_leak_proof:
            return RuleViolation(
                rule_name="液体品防漏",
                violated_skus=[it.sku_id for it in liquid_items],
                description="包含液体品但箱型不支持防漏",
            )
        # 检查液体总量是否超过承运商限制
        if carrier_limits.max_liquid_volume_ml is not None:
            total_liquid_ml = sum(
                (it.liquid_volume_ml or Decimal(0)) * it.quantity
                for it in liquid_items
            )
            if total_liquid_ml > carrier_limits.max_liquid_volume_ml:
                return RuleViolation(
                    rule_name="液体品防漏",
                    violated_skus=[it.sku_id for it in liquid_items],
                    description=(
                        f"液体总量 {total_liquid_ml}ml 超过承运商限制 "
                        f"{carrier_limits.max_liquid_volume_ml}ml"
                    ),
                )
        return None
