"""Property 1, 2, 16, 17: Rate engine level properties

Property 1: Input validation correctness
Property 2: Graceful degradation on missing optional rules
Property 16: Multi-recommendation rate calculation
Property 17: Provider chain with priority fallback

Feature: shipping-rate-engine
Validates: Requirements 1.x, 20.x, 21.x
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

from decimal import Decimal
from hypothesis import given, settings, strategies as st

from shipping_rate_engine.rate_models import (
    Address, BillingMode, PackageInput, PriceTable, RateRequest,
    SurchargeRuleSet, ZoneMapping, ZoneRate,
)
from shipping_rate_engine.rate_engine import RateEngine
from shipping_rate_engine.rate_provider import (
    LocalRateProvider, RateProvider, ProviderRateResult,
)
from shipping_rate_engine.rate_models import PackageRate, ProviderRateResult as PResult

short_str = st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnop")

# Fixtures
_ORIGIN = Address(province="广东", city="深圳")
_DEST = Address(province="浙江", city="杭州")
_MAPPINGS = [ZoneMapping(origin_province="广东", dest_province="浙江", charge_zone="Z1")]
_ZONE_RATES = [ZoneRate(charge_zone="Z1", billing_mode=BillingMode.FIXED, fixed_fee=Decimal("15"))]
_PT = PriceTable(carrier="SF", zone_mappings=_MAPPINGS, zone_rates=_ZONE_RATES)
_PKG = PackageInput(package_id="P1", billing_weight=Decimal("2"), actual_weight=Decimal("2"))


# ── Property 1: Input validation ──────────────────────

def test_missing_packages():
    """Empty packages → MISSING_PACKAGE_INFO error."""
    req = RateRequest(packages=[], origin=_ORIGIN, destination=_DEST, carrier="SF", price_table=_PT)
    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert not result.success
    codes = [e["code"] for e in result.errors]
    assert "MISSING_PACKAGE_INFO" in codes


def test_missing_origin():
    """Missing origin → MISSING_ADDRESS error."""
    req = RateRequest(packages=[_PKG], origin=None, destination=_DEST, carrier="SF", price_table=_PT)
    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert not result.success
    codes = [e["code"] for e in result.errors]
    assert "MISSING_ADDRESS" in codes


def test_missing_destination():
    """Missing destination → MISSING_ADDRESS error."""
    req = RateRequest(packages=[_PKG], origin=_ORIGIN, destination=None, carrier="SF", price_table=_PT)
    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert not result.success
    codes = [e["code"] for e in result.errors]
    assert "MISSING_ADDRESS" in codes


def test_missing_carrier():
    """Missing carrier → error."""
    req = RateRequest(packages=[_PKG], origin=_ORIGIN, destination=_DEST, carrier=None, price_table=_PT)
    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert not result.success


def test_missing_price_table():
    """Missing price_table and no providers → PRICE_TABLE_NOT_FOUND."""
    req = RateRequest(packages=[_PKG], origin=_ORIGIN, destination=_DEST, carrier="SF", price_table=None)
    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert not result.success
    codes = [e["code"] for e in result.errors]
    assert "PRICE_TABLE_NOT_FOUND" in codes


# ── Property 2: Graceful degradation ──────────────────

def test_degraded_on_missing_optional():
    """Missing surcharge_rules/promotion_rules → degraded=True."""
    req = RateRequest(
        packages=[_PKG], origin=_ORIGIN, destination=_DEST,
        carrier="SF", price_table=_PT,
        surcharge_rules=SurchargeRuleSet(),  # empty
        promotion_rules=[],                   # empty
        merchant_agreement={},                # empty
    )
    engine = RateEngine()
    result = engine.calculate_rate(req)
    assert result.success
    assert result.degraded is True
    assert "surcharge_rules" in result.degraded_fields
    assert "promotion_rules" in result.degraded_fields
    assert "merchant_agreement" in result.degraded_fields


# ── Property 16: Multi-recommendation ─────────────────

def test_multi_recommendation():
    """calculate_rate_multi returns N results for N recommendations."""
    class FakeRec:
        def __init__(self, carrier, source):
            self.carrier = carrier
            self.source = source

    recs = [FakeRec("SF", "one_to_one"), FakeRec("YTO", "condition_mapping")]
    req = RateRequest(
        packages=[_PKG], origin=_ORIGIN, destination=_DEST,
        carrier="SF", price_table=_PT,
    )
    engine = RateEngine()
    results = engine.calculate_rate_multi(req, recs)
    assert len(results) == len(recs)
    assert results[0].recommend_source == "one_to_one"
    assert results[1].recommend_source == "condition_mapping"


# ── Property 17: Provider chain fallback ──────────────

class FailingProvider(RateProvider):
    @property
    def priority(self) -> int:
        return 1

    def get_rate(self, package, origin, destination, carrier, **kwargs):
        raise RuntimeError("Provider failed")


class SuccessProvider(RateProvider):
    @property
    def priority(self) -> int:
        return 50

    def get_rate(self, package, origin, destination, carrier, **kwargs):
        return PResult(
            success=True,
            package_rate=PackageRate(
                package_id=package.package_id,
                freight_base=Decimal("20"),
                freight_total=Decimal("20"),
            ),
        )


def test_provider_fallback():
    """If first provider fails, falls back to next."""
    engine = RateEngine(providers=[FailingProvider(), SuccessProvider()])
    req = RateRequest(
        packages=[_PKG], origin=_ORIGIN, destination=_DEST, carrier="SF",
    )
    result = engine.calculate_rate(req)
    assert result.success
    assert result.freight_order == Decimal("20")


def test_all_providers_fail():
    """If all providers fail, returns error."""
    engine = RateEngine(providers=[FailingProvider()])
    req = RateRequest(
        packages=[_PKG], origin=_ORIGIN, destination=_DEST, carrier="SF",
    )
    result = engine.calculate_rate(req)
    assert not result.success
