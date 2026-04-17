"""Property 3: Zone resolution with hierarchical priority

For any set of ZoneMapping entries with overlapping coverage,
the ZoneResolver SHALL select the most specific match (district > city > province).
For same-city origin/destination, SHALL return same-city zone.

Feature: shipping-rate-engine, Property 3: Zone resolution with hierarchical priority
Validates: Requirements 2.1, 2.2, 2.4
"""

import sys
sys.path.insert(0, ".kiro/skills/shipping-rate/scripts")

from hypothesis import given, settings, strategies as st, assume

from shipping_rate_engine.rate_models import Address, ZoneMapping
from shipping_rate_engine.zone_resolver import ZoneResolver, ZoneResolveError

short_str = st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnop")


@given(
    province=short_str,
    city=short_str,
    district_o=short_str,
    district_d=short_str,
)
@settings(max_examples=100)
def test_district_beats_city_beats_province(province, city, district_o, district_d):
    """District-level match has higher priority than city-level and province-level."""
    origin = Address(province=province, city=city, district=district_o)
    dest = Address(province=province, city=city, district=district_d)

    mappings = [
        ZoneMapping(origin_province=province, dest_province=province, charge_zone="PROVINCE"),
        ZoneMapping(origin_province=province, origin_city=city, dest_province=province, dest_city=city, charge_zone="CITY"),
        ZoneMapping(
            origin_province=province, origin_city=city, origin_district=district_o,
            dest_province=province, dest_city=city, dest_district=district_d,
            charge_zone="DISTRICT",
        ),
    ]

    zone = ZoneResolver.resolve(origin, dest, mappings)
    assert zone == "DISTRICT"


@given(
    province=short_str,
    city=short_str,
    district_o=short_str,
    district_d=short_str,
)
@settings(max_examples=100)
def test_same_city_returns_city_zone(province, city, district_o, district_d):
    """Same-city origin and destination should match city-level zone."""
    origin = Address(province=province, city=city, district=district_o)
    dest = Address(province=province, city=city, district=district_d)

    mappings = [
        ZoneMapping(origin_province=province, dest_province=province, charge_zone="PROVINCE"),
        ZoneMapping(origin_province=province, origin_city=city, dest_province=province, dest_city=city, charge_zone="SAME_CITY"),
    ]

    zone = ZoneResolver.resolve(origin, dest, mappings)
    assert zone == "SAME_CITY"


@given(province=short_str, city=short_str)
@settings(max_examples=100)
def test_is_same_city(province, city):
    """is_same_city returns True when province and city match."""
    o = Address(province=province, city=city, district="a")
    d = Address(province=province, city=city, district="b")
    assert ZoneResolver.is_same_city(o, d) is True


@given(
    p1=short_str, c1=short_str,
    p2=short_str, c2=short_str,
)
@settings(max_examples=100)
def test_no_match_raises(p1, c1, p2, c2):
    """When no mapping matches, ZONE_NOT_FOUND is raised."""
    assume(p1 != p2)  # ensure different provinces
    origin = Address(province=p1, city=c1)
    dest = Address(province=p2, city=c2)

    # Only a mapping for p1→p1 (same province), won't match p1→p2
    mappings = [
        ZoneMapping(origin_province=p1, dest_province=p1, charge_zone="SAME"),
    ]

    try:
        ZoneResolver.resolve(origin, dest, mappings)
        assert False, "Should have raised ZoneResolveError"
    except ZoneResolveError as e:
        assert "ZONE_NOT_FOUND" in str(e)
