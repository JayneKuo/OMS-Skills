"""Property 15: Data model round-trip serialization

For any valid RateRequest, RateResult, or PriceTable object,
serializing to JSON and deserializing back SHALL produce an equal object.

Feature: shipping-rate-engine, Property 15: Data model round-trip serialization
Validates: Requirements 18.5, 18.6, 19.4
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

from decimal import Decimal
from hypothesis import given, settings, strategies as st

from shipping_rate_engine.rate_models import (
    Address, BillingMode, PackageInput, PackageRate, PriceTable,
    PromotionApplied, PromotionRule, RateRequest, RateResult,
    SurchargeBreakdown, SurchargeChargeMode, SurchargeDetail,
    SurchargeRule, SurchargeRuleSet, SurchargeType, WeightTier,
    ZoneMapping, ZoneRate,
)

# ── Strategies ────────────────────────────────────────

decimal_st = st.decimals(min_value=0, max_value=10000, places=2, allow_nan=False, allow_infinity=False)
pos_decimal_st = st.decimals(min_value=Decimal("0.01"), max_value=10000, places=2, allow_nan=False, allow_infinity=False)
short_str = st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz")

address_st = st.builds(
    Address,
    province=short_str, city=short_str, district=short_str, country=st.just("CN"),
)

weight_tier_st = st.builds(
    WeightTier,
    min_weight=decimal_st,
    max_weight=st.one_of(st.none(), pos_decimal_st),
    unit_price=pos_decimal_st,
)

zone_rate_st = st.builds(
    ZoneRate,
    charge_zone=short_str,
    billing_mode=st.sampled_from(BillingMode),
    first_weight=pos_decimal_st,
    first_weight_fee=decimal_st,
    step_weight=pos_decimal_st,
    step_weight_fee=decimal_st,
    weight_tiers=st.lists(weight_tier_st, max_size=3),
    unit_price_per_m3=decimal_st,
    fixed_fee=decimal_st,
)

zone_mapping_st = st.builds(
    ZoneMapping,
    origin_province=short_str, origin_city=short_str, origin_district=short_str,
    dest_province=short_str, dest_city=short_str, dest_district=short_str,
    charge_zone=short_str,
)

price_table_st = st.builds(
    PriceTable,
    carrier=short_str,
    zone_mappings=st.lists(zone_mapping_st, max_size=3),
    zone_rates=st.lists(zone_rate_st, max_size=3),
)

package_input_st = st.builds(
    PackageInput,
    package_id=short_str,
    billing_weight=pos_decimal_st,
    actual_weight=pos_decimal_st,
    volume_cm3=st.one_of(st.none(), pos_decimal_st),
    has_cold_items=st.booleans(),
    is_bulky=st.booleans(),
    declared_value=decimal_st,
)

surcharge_rule_st = st.builds(
    SurchargeRule,
    surcharge_type=st.sampled_from(SurchargeType),
    charge_mode=st.sampled_from(SurchargeChargeMode),
    fixed_amount=decimal_st,
    percentage=st.decimals(min_value=0, max_value=1, places=2, allow_nan=False, allow_infinity=False),
    threshold=decimal_st,
)

rate_request_st = st.builds(
    RateRequest,
    packages=st.lists(package_input_st, min_size=1, max_size=3),
    origin=st.one_of(st.none(), address_st),
    destination=st.one_of(st.none(), address_st),
    carrier=st.one_of(st.none(), short_str),
    price_table=st.one_of(st.none(), price_table_st),
    surcharge_rules=st.builds(SurchargeRuleSet, rules=st.lists(surcharge_rule_st, max_size=3)),
)


# ── Property Tests ────────────────────────────────────

@given(pt=price_table_st)
@settings(max_examples=100)
def test_price_table_roundtrip(pt: PriceTable):
    """PriceTable JSON round-trip"""
    json_str = pt.model_dump_json()
    restored = PriceTable.model_validate_json(json_str)
    assert restored == pt


@given(req=rate_request_st)
@settings(max_examples=100)
def test_rate_request_roundtrip(req: RateRequest):
    """RateRequest JSON round-trip"""
    json_str = req.model_dump_json()
    restored = RateRequest.model_validate_json(json_str)
    assert restored == req


@given(
    freight=decimal_st,
    carrier=short_str,
)
@settings(max_examples=100)
def test_rate_result_roundtrip(freight, carrier):
    """RateResult JSON round-trip"""
    result = RateResult(
        success=True,
        freight_order=freight,
        freight_order_before_promotion=freight,
        carrier=carrier,
    )
    json_str = result.model_dump_json()
    restored = RateResult.model_validate_json(json_str)
    assert restored == result
