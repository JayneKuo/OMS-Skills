"""Property 13, 14: Aggregator correctness

Property 13: Order aggregation sum
Property 14: Promotion discount with non-negative floor

Feature: shipping-rate-engine
Validates: Requirements 16.x, 17.x
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

from decimal import Decimal, ROUND_HALF_UP
from hypothesis import given, settings, strategies as st

from shipping_rate_engine.rate_models import (
    BillingMode, PackageRate, PromotionRule, SurchargeBreakdown,
)
from shipping_rate_engine.rate_aggregator import RateAggregator, _round2

pos_dec = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000"), places=2, allow_nan=False, allow_infinity=False)
short_str = st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnop")

pkg_rate_st = st.builds(
    PackageRate,
    package_id=short_str,
    charge_zone=st.just("Z1"),
    billing_mode=st.just(BillingMode.FIXED),
    freight_base=pos_dec,
    surcharge_breakdown=st.builds(SurchargeBreakdown),
    freight_total=pos_dec,
)


# ── Property 13: Order aggregation sum ────────────────

@given(rates=st.lists(pkg_rate_st, min_size=1, max_size=5))
@settings(max_examples=200)
def test_aggregation_sum(rates):
    """freight_order = sum(freight_total) when no promotions."""
    summary = RateAggregator.aggregate(rates, promotion_rules=None)
    expected = _round2(sum((r.freight_total for r in rates), Decimal("0")))
    assert summary.freight_order == expected
    assert summary.freight_order_before_promotion == expected
    assert len(summary.package_rates) == len(rates)


@given(rates=st.lists(pkg_rate_st, min_size=1, max_size=5))
@settings(max_examples=100)
def test_aggregation_preserves_all_packages(rates):
    """Output contains exactly one PackageRate per input package."""
    summary = RateAggregator.aggregate(rates)
    assert len(summary.package_rates) == len(rates)
    for i, r in enumerate(rates):
        assert summary.package_rates[i].package_id == r.package_id


# ── Property 14: Promotion non-negative floor ─────────

@given(
    freight=pos_dec,
    discount=st.decimals(min_value=Decimal("0"), max_value=Decimal("99999"), places=2, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_promotion_non_negative_floor(freight, discount):
    """freight_order >= 0 after promotion discount."""
    rates = [PackageRate(
        package_id="P1", freight_total=freight, freight_base=freight,
    )]
    promo = PromotionRule(
        rule_name="test",
        discount_type="fixed_discount",
        discount_amount=discount,
    )
    summary = RateAggregator.aggregate(rates, [promo])
    assert summary.freight_order >= 0
    assert summary.total_promotion_discount <= summary.freight_order_before_promotion


@given(freight=pos_dec, order_amount=pos_dec)
@settings(max_examples=100)
def test_full_free_promotion(freight, order_amount):
    """full_free promotion makes freight_order = 0."""
    rates = [PackageRate(package_id="P1", freight_total=freight, freight_base=freight)]
    promo = PromotionRule(
        rule_name="free_shipping",
        discount_type="full_free",
        min_order_amount=Decimal("0"),
    )
    summary = RateAggregator.aggregate(rates, [promo], order_amount)
    assert summary.freight_order == Decimal("0")
    assert summary.total_promotion_discount == summary.freight_order_before_promotion
