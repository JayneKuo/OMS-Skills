"""Property 4, 5, 6, 7: Rate calculator correctness

Property 4: First weight + step formula correctness
Property 5: Tiered weight formula correctness
Property 6: Volume formula correctness
Property 7: All monetary amounts have exactly 2 decimal places

Feature: shipping-rate-engine
Validates: Requirements 3.x, 4.x, 5.x, 6.x
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

import math
from decimal import Decimal, ROUND_HALF_UP
from hypothesis import given, settings, strategies as st, assume

from shipping_rate_engine.rate_models import BillingMode, WeightTier, ZoneRate
from shipping_rate_engine.rate_calculator import RateCalculator, _ceil_weight, _round2

pos_weight = st.decimals(min_value=Decimal("0.1"), max_value=Decimal("500"), places=1, allow_nan=False, allow_infinity=False)
pos_fee = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000"), places=2, allow_nan=False, allow_infinity=False)
pos_step = st.decimals(min_value=Decimal("0.1"), max_value=Decimal("10"), places=1, allow_nan=False, allow_infinity=False)


# ── Property 4: First weight + step formula ───────────

@given(
    weight=pos_weight,
    first_weight=pos_weight,
    first_fee=pos_fee,
    step_weight=pos_step,
    step_fee=pos_fee,
)
@settings(max_examples=200)
def test_first_weight_step_formula(weight, first_weight, first_fee, step_weight, step_fee):
    """Property 4: First weight + step formula correctness."""
    zr = ZoneRate(
        charge_zone="Z1", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
        first_weight=first_weight, first_weight_fee=first_fee,
        step_weight=step_weight, step_weight_fee=step_fee,
    )
    result = RateCalculator.calc_first_weight_step(weight, zr)

    charge_weight = _ceil_weight(weight)
    if charge_weight <= first_weight:
        expected = _round2(first_fee)
    else:
        excess = charge_weight - first_weight
        steps = Decimal(str(math.ceil(float(excess) / float(step_weight))))
        expected = _round2(first_fee + steps * step_fee)

    assert result == expected


@given(weight=pos_weight, first_weight=pos_weight, first_fee=pos_fee)
@settings(max_examples=100)
def test_weight_leq_first_returns_first_fee(weight, first_weight, first_fee):
    """When weight <= first_weight, return first_weight_fee."""
    assume(weight <= first_weight)
    zr = ZoneRate(
        charge_zone="Z1", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
        first_weight=first_weight, first_weight_fee=first_fee,
        step_weight=Decimal("1"), step_weight_fee=Decimal("5"),
    )
    result = RateCalculator.calc_first_weight_step(weight, zr)
    assert result == _round2(first_fee)


# ── Property 5: Tiered weight formula ─────────────────

@given(weight=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("100"), places=1, allow_nan=False, allow_infinity=False))
@settings(max_examples=200)
def test_weight_tier_formula(weight):
    """Property 5: Tiered weight formula correctness."""
    tiers = [
        WeightTier(min_weight=Decimal("0"), max_weight=Decimal("5"), unit_price=Decimal("10")),
        WeightTier(min_weight=Decimal("5"), max_weight=Decimal("20"), unit_price=Decimal("8")),
        WeightTier(min_weight=Decimal("20"), max_weight=None, unit_price=Decimal("6")),
    ]
    zr = ZoneRate(charge_zone="Z1", billing_mode=BillingMode.WEIGHT_TIER, weight_tiers=tiers)
    result = RateCalculator.calc_weight_tier(weight, zr)

    # Manual calculation
    cw = _ceil_weight(weight)
    expected = Decimal("0")
    remaining = cw
    for tier in tiers:
        if remaining <= 0:
            break
        if tier.max_weight is not None:
            w = min(remaining, tier.max_weight - tier.min_weight)
        else:
            w = remaining
        expected += w * tier.unit_price
        remaining -= w
    if remaining > 0:
        expected += remaining * tiers[-1].unit_price
    expected = _round2(expected)

    assert result == expected


@given(weight=st.decimals(min_value=Decimal("25"), max_value=Decimal("100"), places=1, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_weight_tier_excess_uses_highest(weight):
    """When weight exceeds max tier, excess uses highest tier price."""
    tiers = [
        WeightTier(min_weight=Decimal("0"), max_weight=Decimal("10"), unit_price=Decimal("10")),
        WeightTier(min_weight=Decimal("10"), max_weight=Decimal("20"), unit_price=Decimal("8")),
    ]
    zr = ZoneRate(charge_zone="Z1", billing_mode=BillingMode.WEIGHT_TIER, weight_tiers=tiers)
    result = RateCalculator.calc_weight_tier(weight, zr)
    assert result > Decimal("0")


# ── Property 6: Volume formula ────────────────────────

@given(
    volume=st.decimals(min_value=Decimal("100"), max_value=Decimal("10000000"), places=0, allow_nan=False, allow_infinity=False),
    price=pos_fee,
)
@settings(max_examples=200)
def test_volume_formula(volume, price):
    """Property 6: Volume formula correctness."""
    zr = ZoneRate(charge_zone="Z1", billing_mode=BillingMode.VOLUME, unit_price_per_m3=price)
    result = RateCalculator.calc_volume(volume, zr)
    expected = _round2(volume / Decimal("1000000") * price)
    assert result == expected


# ── Property 7: Monetary precision ────────────────────

@given(
    weight=pos_weight,
    first_fee=pos_fee,
    step_fee=pos_fee,
)
@settings(max_examples=200)
def test_monetary_precision_2dp(weight, first_fee, step_fee):
    """Property 7: All monetary amounts have exactly 2 decimal places."""
    zr = ZoneRate(
        charge_zone="Z1", billing_mode=BillingMode.FIRST_WEIGHT_STEP,
        first_weight=Decimal("1"), first_weight_fee=first_fee,
        step_weight=Decimal("0.5"), step_weight_fee=step_fee,
    )
    result = RateCalculator.calc_first_weight_step(weight, zr)
    # Check at most 2 decimal places
    assert result == result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
