"""Shipping Rate Engine — 运费汇总器

纯函数实现，汇总包裹运费并应用促销减免。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .rate_models import (
    OrderRateSummary,
    PackageRate,
    PromotionApplied,
    PromotionRule,
)


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class RateAggregator:
    """运费汇总器（纯函数）"""

    @staticmethod
    def aggregate(
        package_rates: list[PackageRate],
        promotion_rules: list[PromotionRule] | None = None,
        order_total_amount: Decimal | None = None,
    ) -> OrderRateSummary:
        """汇总订单运费，应用促销减免。

        公式: Freight_order = Σ(freight_total) - promotion_discount
        确保减免后运费 >= 0
        """
        # 汇总包裹运费
        freight_before = sum(
            (pkg.freight_total for pkg in package_rates),
            Decimal("0"),
        )
        freight_before = _round2(freight_before)

        # 应用促销减免
        promotions_applied: list[PromotionApplied] = []
        total_discount = Decimal("0")

        for rule in (promotion_rules or []):
            discount = RateAggregator._calc_promotion_discount(
                rule, freight_before, order_total_amount,
            )
            if discount > 0:
                promotions_applied.append(PromotionApplied(
                    rule_name=rule.rule_name,
                    discount_amount=discount,
                ))
                total_discount += discount

        # 确保减免不超过运费
        total_discount = min(total_discount, freight_before)
        total_discount = _round2(total_discount)

        freight_order = _round2(freight_before - total_discount)
        # 确保非负
        if freight_order < 0:
            freight_order = Decimal("0")

        return OrderRateSummary(
            freight_order=freight_order,
            freight_order_before_promotion=freight_before,
            package_rates=package_rates,
            promotions_applied=promotions_applied,
            total_promotion_discount=total_discount,
        )

    @staticmethod
    def _calc_promotion_discount(
        rule: PromotionRule,
        freight_before: Decimal,
        order_total_amount: Decimal | None,
    ) -> Decimal:
        """计算单条促销规则的减免金额"""
        # 检查最低订单金额条件
        if rule.min_order_amount > 0:
            if order_total_amount is None or order_total_amount < rule.min_order_amount:
                return Decimal("0")

        if rule.discount_type == "full_free":
            return _round2(freight_before)
        elif rule.discount_type == "fixed_discount":
            return _round2(min(rule.discount_amount, freight_before))
        elif rule.discount_type == "percentage_discount":
            return _round2(freight_before * rule.discount_percentage)
        else:
            return Decimal("0")
