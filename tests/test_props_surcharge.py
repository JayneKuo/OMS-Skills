"""Property 8, 9, 10, 11, 12: Surcharge calculator correctness

Property 8: Conditional surcharge trigger correctness
Property 9: Fuel surcharge formula
Property 10: Service surcharge trigger correctness
Property 11: Holiday surcharge uses correct base
Property 12: Surcharge pipeline ordering

Feature: shipping-rate-engine
Validates: Requirements 7-15
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

from decimal import Decimal, ROUND_HALF_UP
from hypothesis import given, settings, strategies as st, assume

from shipping_rate_engine.rate_models import (
    Address, PackageInput, SurchargeChargeMode, SurchargeContext,
    SurchargeRule, SurchargeRuleSet, SurchargeType,
)
from shipping_rate_engine.surcharge_calculator import SurchargeCalculator, _round2

pos_dec = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000"), places=2, allow_nan=False, allow_infinity=False)
rate_dec = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=2, allow_nan=False, allow_infinity=False)
weight_dec = st.decimals(min_value=Decimal("0.1"), max_value=Decimal("500"), places=1, allow_nan=False, allow_infinity=False)


# ── Property 8: Conditional surcharge triggers ────────

@given(
    billing_weight=weight_dec,
    threshold=weight_dec,
    unit_price=pos_dec,
)
@settings(max_examples=200)
def test_overweight_trigger(billing_weight, threshold, unit_price):
    """Overweight surcharge > 0 iff billing_weight > threshold."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.OVERWEIGHT,
        threshold=threshold,
        overweight_unit_price=unit_price,
    )
    result = SurchargeCalculator.calc_overweight(billing_weight, rule)
    if billing_weight > threshold:
        assert result > 0
    else:
        assert result == 0


@given(
    max_edge=st.decimals(min_value=Decimal("1"), max_value=Decimal("300"), places=0, allow_nan=False, allow_infinity=False),
    threshold=st.decimals(min_value=Decimal("1"), max_value=Decimal("300"), places=0, allow_nan=False, allow_infinity=False),
    fixed=pos_dec,
)
@settings(max_examples=200)
def test_oversize_trigger(max_edge, threshold, fixed):
    """Oversize surcharge > 0 iff max_edge > threshold."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.OVERSIZE,
        threshold=threshold,
        fixed_amount=fixed,
    )
    result = SurchargeCalculator.calc_oversize(max_edge, rule)
    if max_edge > threshold:
        assert result > 0
    else:
        assert result == 0


@given(is_remote=st.booleans(), fixed=pos_dec)
@settings(max_examples=100)
def test_remote_trigger(is_remote, fixed):
    """Remote surcharge > 0 iff is_remote is True."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.REMOTE,
        charge_mode=SurchargeChargeMode.FIXED_AMOUNT,
        fixed_amount=fixed,
        remote_areas=["偏远市"],
    )
    result = SurchargeCalculator.calc_remote(Decimal("100"), rule, is_remote)
    if is_remote:
        assert result > 0
    else:
        assert result == 0


# ── Property 9: Fuel surcharge formula ────────────────

@given(freight_base=pos_dec, fuel_rate=rate_dec)
@settings(max_examples=200)
def test_fuel_surcharge_formula(freight_base, fuel_rate):
    """Fuel surcharge = round(freight_base * fuel_rate, 2)."""
    result = SurchargeCalculator.calc_fuel(freight_base, fuel_rate)
    expected = _round2(freight_base * fuel_rate)
    assert result == expected


@given(freight_base=pos_dec)
@settings(max_examples=100)
def test_fuel_always_computed(freight_base):
    """Fuel surcharge is always computed (never skipped) when rate > 0."""
    result = SurchargeCalculator.calc_fuel(freight_base, Decimal("0.10"))
    assert result > 0


# ── Property 10: Service surcharge triggers ───────────

@given(declared_value=pos_dec, threshold=pos_dec, rate=rate_dec)
@settings(max_examples=200)
def test_insurance_trigger(declared_value, threshold, rate):
    """Insurance > 0 iff declared_value > threshold."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.INSURANCE,
        threshold=threshold,
        percentage=rate,
    )
    result = SurchargeCalculator.calc_insurance(declared_value, rule)
    if declared_value > threshold:
        assert result > 0
    else:
        assert result == 0


@given(has_cold=st.booleans(), fixed=pos_dec)
@settings(max_examples=100)
def test_cold_chain_trigger(has_cold, fixed):
    """Cold chain > 0 iff has_cold_items is True."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.COLD_CHAIN,
        fixed_amount=fixed,
    )
    result = SurchargeCalculator.calc_cold_chain(has_cold, rule)
    if has_cold:
        assert result > 0
    else:
        assert result == 0


@given(
    floor=st.integers(min_value=0, max_value=30),
    is_bulky=st.booleans(),
    has_elevator=st.booleans(),
    per_floor=pos_dec,
)
@settings(max_examples=200)
def test_stair_trigger(floor, is_bulky, has_elevator, per_floor):
    """Stair fee > 0 iff is_bulky AND NOT has_elevator AND floor > 0."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.STAIR,
        per_floor_price=per_floor,
    )
    result = SurchargeCalculator.calc_stair(floor, is_bulky, has_elevator, rule)
    should_trigger = is_bulky and not has_elevator and floor > 0
    if should_trigger:
        assert result > 0
    else:
        assert result == 0


# ── Property 11: Holiday surcharge uses correct base ──

@given(freight_base=pos_dec, fuel=pos_dec, pct=rate_dec)
@settings(max_examples=200)
def test_holiday_uses_base_plus_fuel(freight_base, fuel, pct):
    """Holiday surcharge percentage is based on (base + fuel), not just base."""
    rule = SurchargeRule(
        surcharge_type=SurchargeType.HOLIDAY,
        charge_mode=SurchargeChargeMode.PERCENTAGE,
        percentage=pct,
        holiday_periods=[{"start": "2025-01-01", "end": "2025-12-31"}],
    )
    base_plus_fuel = freight_base + fuel
    result = SurchargeCalculator.calc_holiday(base_plus_fuel, rule, True)
    expected = _round2(base_plus_fuel * pct)
    assert result == expected

    # Verify it's NOT just freight_base * pct (unless fuel == 0)
    wrong = _round2(freight_base * pct)
    if fuel > 0 and pct > 0:
        assert result != wrong or freight_base == Decimal("0")


# ── Property 12: Surcharge pipeline ordering ──────────

@given(freight_base=pos_dec, fuel_rate=rate_dec)
@settings(max_examples=100)
def test_surcharge_pipeline_order(freight_base, fuel_rate):
    """Property 12: Surcharges computed in 5-step order.
    Steps 3 and 4 are independent of each other."""
    pkg = PackageInput(
        package_id="P1",
        billing_weight=Decimal("50"),  # trigger overweight
        actual_weight=Decimal("50"),
        length_cm=Decimal("200"),      # trigger oversize
        width_cm=Decimal("50"),
        height_cm=Decimal("50"),
        has_cold_items=True,           # trigger cold chain
        is_bulky=True,                 # trigger stair
        declared_value=Decimal("5000"),  # trigger insurance
    )
    rules = SurchargeRuleSet(rules=[
        SurchargeRule(surcharge_type=SurchargeType.FUEL, percentage=fuel_rate),
        SurchargeRule(surcharge_type=SurchargeType.REMOTE, charge_mode=SurchargeChargeMode.FIXED_AMOUNT, fixed_amount=Decimal("20"), remote_areas=["偏远市"]),
        SurchargeRule(surcharge_type=SurchargeType.OVERWEIGHT, threshold=Decimal("30"), overweight_unit_price=Decimal("2")),
        SurchargeRule(surcharge_type=SurchargeType.OVERSIZE, threshold=Decimal("150"), fixed_amount=Decimal("50")),
        SurchargeRule(surcharge_type=SurchargeType.COLD_CHAIN, fixed_amount=Decimal("30")),
        SurchargeRule(surcharge_type=SurchargeType.INSURANCE, threshold=Decimal("1000"), percentage=Decimal("0.01")),
        SurchargeRule(surcharge_type=SurchargeType.STAIR, per_floor_price=Decimal("10")),
        SurchargeRule(surcharge_type=SurchargeType.HOLIDAY, charge_mode=SurchargeChargeMode.PERCENTAGE, percentage=Decimal("0.10"), holiday_periods=[{"start": "2025-01-01", "end": "2025-12-31"}]),
    ])
    ctx = SurchargeContext(
        destination=Address(province="偏远省", city="偏远市"),
        has_elevator=False,
        floor_number=5,
        ship_date="2025-06-15",
    )

    breakdown = SurchargeCalculator.calculate_all(freight_base, pkg, rules, ctx)

    # Step 2: fuel
    assert breakdown.fuel == _round2(freight_base * fuel_rate)
    # Step 3: independent
    assert breakdown.remote == Decimal("20")
    assert breakdown.overweight == _round2(Decimal("20") * Decimal("2"))  # 50-30=20
    assert breakdown.oversize == Decimal("50")
    # Step 4: independent
    assert breakdown.cold_chain == Decimal("30")
    assert breakdown.insurance == _round2(Decimal("5000") * Decimal("0.01"))
    assert breakdown.stair == _round2(Decimal("5") * Decimal("10"))
    # Step 5: holiday based on base+fuel
    base_plus_fuel = freight_base + breakdown.fuel
    assert breakdown.holiday == _round2(base_plus_fuel * Decimal("0.10"))
