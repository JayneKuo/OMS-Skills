"""Example-based tests for Shipping Rate Engine

Tests based on PRD cases: different carriers, billing modes, multi-package orders.

Feature: shipping-rate-engine
Validates: Requirements 3.1, 4.1, 5.1, 6.1, 16.1
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

from decimal import Decimal

from shipping_rate_engine.rate_models import (
    Address, BillingMode, PackageInput, PriceTable, PromotionRule,
    RateRequest, SurchargeRule, SurchargeRuleSet, SurchargeType,
    WeightTier, ZoneMapping, ZoneRate,
)
from shipping_rate_engine.rate_engine import RateEngine


# ── Fixtures ──────────────────────────────────────────

ORIGIN = Address(province="广东", city="深圳", district="南山")
DEST_SAME_CITY = Address(province="广东", city="深圳", district="福田")
DEST_CROSS_PROVINCE = Address(province="浙江", city="杭州", district="西湖")
DEST_REMOTE = Address(province="新疆", city="乌鲁木齐", district="天山")

ZONE_MAPPINGS = [
    ZoneMapping(origin_province="广东", origin_city="深圳", dest_province="广东", dest_city="深圳", charge_zone="SAME_CITY"),
    ZoneMapping(origin_province="广东", dest_province="浙江", charge_zone="CROSS_PROVINCE"),
    ZoneMapping(origin_province="广东", dest_province="新疆", charge_zone="REMOTE"),
]


def _make_price_table(carrier: str, zone_rates: list[ZoneRate]) -> PriceTable:
    return PriceTable(carrier=carrier, zone_mappings=ZONE_MAPPINGS, zone_rates=zone_rates)


# ── Case 1: 首重+续重 — 顺丰快递 ─────────────────────

def test_case1_first_weight_step_sf():
    """顺丰快递：首重1kg=12元，续重每0.5kg=5元，跨省3.5kg"""
    zone_rates = [ZoneRate(
        charge_zone="CROSS_PROVINCE",
        billing_mode=BillingMode.FIRST_WEIGHT_STEP,
        first_weight=Decimal("1"),
        first_weight_fee=Decimal("12"),
        step_weight=Decimal("0.5"),
        step_weight_fee=Decimal("5"),
    )]
    pt = _make_price_table("SF", zone_rates)
    pkg = PackageInput(package_id="P1", billing_weight=Decimal("3.5"), actual_weight=Decimal("3.5"))
    req = RateRequest(packages=[pkg], origin=ORIGIN, destination=DEST_CROSS_PROVINCE, carrier="SF", price_table=pt)

    engine = RateEngine()
    result = engine.calculate_rate(req)

    assert result.success
    # 12 + ceil((3.5-1)/0.5)*5 = 12 + 5*5 = 37
    assert result.freight_order == Decimal("37.00")


def test_case1b_weight_leq_first():
    """计费重量 <= 首重，只收首重费"""
    zone_rates = [ZoneRate(
        charge_zone="CROSS_PROVINCE",
        billing_mode=BillingMode.FIRST_WEIGHT_STEP,
        first_weight=Decimal("1"),
        first_weight_fee=Decimal("12"),
        step_weight=Decimal("0.5"),
        step_weight_fee=Decimal("5"),
    )]
    pt = _make_price_table("SF", zone_rates)
    pkg = PackageInput(package_id="P1", billing_weight=Decimal("0.8"), actual_weight=Decimal("0.8"))
    req = RateRequest(packages=[pkg], origin=ORIGIN, destination=DEST_CROSS_PROVINCE, carrier="SF", price_table=pt)

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    assert result.freight_order == Decimal("12.00")


# ── Case 2: 阶梯重量 — 零担物流 ──────────────────────

def test_case2_weight_tier():
    """零担物流：0-5kg@10元/kg, 5-20kg@8元/kg, 20+@6元/kg，计费重量25kg"""
    zone_rates = [ZoneRate(
        charge_zone="CROSS_PROVINCE",
        billing_mode=BillingMode.WEIGHT_TIER,
        weight_tiers=[
            WeightTier(min_weight=Decimal("0"), max_weight=Decimal("5"), unit_price=Decimal("10")),
            WeightTier(min_weight=Decimal("5"), max_weight=Decimal("20"), unit_price=Decimal("8")),
            WeightTier(min_weight=Decimal("20"), max_weight=None, unit_price=Decimal("6")),
        ],
    )]
    pt = _make_price_table("ZTO", zone_rates)
    pkg = PackageInput(package_id="P1", billing_weight=Decimal("25"), actual_weight=Decimal("25"))
    req = RateRequest(packages=[pkg], origin=ORIGIN, destination=DEST_CROSS_PROVINCE, carrier="ZTO", price_table=pt)

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    # 5*10 + 15*8 + 5*6 = 50 + 120 + 30 = 200
    assert result.freight_order == Decimal("200.00")


# ── Case 3: 体积计费 ─────────────────────────────────

def test_case3_volume():
    """体积计费：500元/m³，包裹 50x40x30cm = 60000cm³"""
    zone_rates = [ZoneRate(
        charge_zone="CROSS_PROVINCE",
        billing_mode=BillingMode.VOLUME,
        unit_price_per_m3=Decimal("500"),
    )]
    pt = _make_price_table("YTO", zone_rates)
    pkg = PackageInput(
        package_id="P1", billing_weight=Decimal("5"), actual_weight=Decimal("5"),
        volume_cm3=Decimal("60000"),
        length_cm=Decimal("50"), width_cm=Decimal("40"), height_cm=Decimal("30"),
    )
    req = RateRequest(packages=[pkg], origin=ORIGIN, destination=DEST_CROSS_PROVINCE, carrier="YTO", price_table=pt)

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    # 60000/1000000 * 500 = 0.06 * 500 = 30
    assert result.freight_order == Decimal("30.00")


# ── Case 4: 固定费用 — 同城配送 ──────────────────────

def test_case4_fixed():
    """同城配送：固定费用 15 元"""
    zone_rates = [ZoneRate(
        charge_zone="SAME_CITY",
        billing_mode=BillingMode.FIXED,
        fixed_fee=Decimal("15"),
    )]
    pt = _make_price_table("LOCAL", zone_rates)
    pkg = PackageInput(package_id="P1", billing_weight=Decimal("2"), actual_weight=Decimal("2"))
    req = RateRequest(packages=[pkg], origin=ORIGIN, destination=DEST_SAME_CITY, carrier="LOCAL", price_table=pt)

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    assert result.freight_order == Decimal("15.00")


# ── Case 5: 多包裹订单 ───────────────────────────────

def test_case5_multi_package():
    """多包裹订单：2个包裹，固定费用各15元，总计30元"""
    zone_rates = [ZoneRate(
        charge_zone="SAME_CITY",
        billing_mode=BillingMode.FIXED,
        fixed_fee=Decimal("15"),
    )]
    pt = _make_price_table("LOCAL", zone_rates)
    pkgs = [
        PackageInput(package_id="P1", billing_weight=Decimal("2"), actual_weight=Decimal("2")),
        PackageInput(package_id="P2", billing_weight=Decimal("3"), actual_weight=Decimal("3")),
    ]
    req = RateRequest(packages=pkgs, origin=ORIGIN, destination=DEST_SAME_CITY, carrier="LOCAL", price_table=pt)

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    assert result.freight_order == Decimal("30.00")
    assert len(result.package_rates) == 2


# ── Case 6: 附加费叠加 ───────────────────────────────

def test_case6_surcharges():
    """基础运费 + 燃油 + 超重附加费"""
    zone_rates = [ZoneRate(
        charge_zone="CROSS_PROVINCE",
        billing_mode=BillingMode.FIRST_WEIGHT_STEP,
        first_weight=Decimal("1"), first_weight_fee=Decimal("12"),
        step_weight=Decimal("1"), step_weight_fee=Decimal("5"),
    )]
    pt = _make_price_table("SF", zone_rates)
    pkg = PackageInput(
        package_id="P1", billing_weight=Decimal("35"), actual_weight=Decimal("35"),
    )
    surcharge_rules = SurchargeRuleSet(rules=[
        SurchargeRule(surcharge_type=SurchargeType.FUEL, percentage=Decimal("0.10")),
        SurchargeRule(surcharge_type=SurchargeType.OVERWEIGHT, threshold=Decimal("30"), overweight_unit_price=Decimal("3")),
    ])
    req = RateRequest(
        packages=[pkg], origin=ORIGIN, destination=DEST_CROSS_PROVINCE,
        carrier="SF", price_table=pt, surcharge_rules=surcharge_rules,
    )

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    # base: 12 + ceil((35-1)/1)*5 = 12 + 34*5 = 182
    # fuel: 182 * 0.10 = 18.20
    # overweight: (35-30)*3 = 15
    # total: 182 + 18.20 + 15 = 215.20
    assert result.freight_order == Decimal("215.20")


# ── Case 7: 促销减免 ─────────────────────────────────

def test_case7_promotion():
    """满 100 免运费"""
    zone_rates = [ZoneRate(
        charge_zone="SAME_CITY",
        billing_mode=BillingMode.FIXED,
        fixed_fee=Decimal("15"),
    )]
    pt = _make_price_table("LOCAL", zone_rates)
    pkg = PackageInput(package_id="P1", billing_weight=Decimal("1"), actual_weight=Decimal("1"))
    promo = PromotionRule(
        rule_name="满100免运费",
        min_order_amount=Decimal("100"),
        discount_type="full_free",
    )
    req = RateRequest(
        packages=[pkg], origin=ORIGIN, destination=DEST_SAME_CITY,
        carrier="LOCAL", price_table=pt,
        promotion_rules=[promo],
        order_total_amount=Decimal("200"),
    )

    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    assert result.freight_order == Decimal("0")
    assert result.total_promotion_discount == Decimal("15.00")
