"""属性测试 - 预分组器 Properties 3-7"""

from decimal import Decimal
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, OrderConfig, TemperatureZone, HazmatType,
)
from cartonization_engine.pre_grouper import PreGrouper


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def sku_items_multi_zone(draw, min_size=2, max_size=8):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=5)),
        weight=draw(_pos_decimal("0.1", "20")),
        length=draw(_pos_decimal("1", "50")),
        width=draw(_pos_decimal("1", "50")),
        height=draw(_pos_decimal("1", "50")),
        temperature_zone=draw(st.sampled_from(list(TemperatureZone))),
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


@composite
def sku_items_with_hazmat_pg(draw, min_size=2, max_size=6):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    hazmat_types = [HazmatType.FLAMMABLE, HazmatType.EXPLOSIVE, HazmatType.CORROSIVE]
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=5)),
        weight=draw(_pos_decimal("0.1", "20")),
        length=draw(_pos_decimal("1", "50")),
        width=draw(_pos_decimal("1", "50")),
        height=draw(_pos_decimal("1", "50")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=draw(st.sampled_from(hazmat_types)) if i == 0 else draw(st.sampled_from(list(HazmatType))),
    ) for i in range(n)]


@composite
def sku_items_cannot_ship_pg(draw):
    n = draw(st.integers(min_value=3, max_value=6))
    sku_ids = [f"SKU{i:03d}" for i in range(n)]
    items = []
    for i in range(n):
        other_ids = [sid for sid in sku_ids if sid != sku_ids[i]]
        cannot = draw(st.lists(st.sampled_from(other_ids), max_size=min(2, len(other_ids)), unique=True))
        items.append(SKUItem(
            sku_id=sku_ids[i], sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=5)),
            weight=draw(_pos_decimal("0.1", "20")),
            length=draw(_pos_decimal("1", "50")),
            width=draw(_pos_decimal("1", "50")),
            height=draw(_pos_decimal("1", "50")),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            cannot_ship_with=cannot,
        ))
    return items


@composite
def sku_items_must_ship_pg(draw):
    n = draw(st.integers(min_value=3, max_value=6))
    sku_ids = [f"SKU{i:03d}" for i in range(n)]
    zone = draw(st.sampled_from(list(TemperatureZone)))
    pair_idx = draw(st.integers(min_value=0, max_value=n - 2))
    bind_a, bind_b = sku_ids[pair_idx], sku_ids[pair_idx + 1]
    items = []
    for i in range(n):
        must = [bind_b] if sku_ids[i] == bind_a else ([bind_a] if sku_ids[i] == bind_b else [])
        items.append(SKUItem(
            sku_id=sku_ids[i], sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=5)),
            weight=draw(_pos_decimal("0.1", "20")),
            length=draw(_pos_decimal("1", "50")),
            width=draw(_pos_decimal("1", "50")),
            height=draw(_pos_decimal("1", "50")),
            temperature_zone=zone, hazmat_type=HazmatType.NONE,
            must_ship_with=must,
        ))
    return items


@composite
def sku_items_with_gifts_pg(draw):
    n = draw(st.integers(min_value=2, max_value=6))
    zone = draw(st.sampled_from(list(TemperatureZone)))
    items = []
    for i in range(n):
        is_gift = (i == n - 1) if i > 0 else False
        if 0 < i < n - 1:
            is_gift = draw(st.booleans())
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=5)),
            weight=draw(_pos_decimal("0.1", "20")),
            length=draw(_pos_decimal("1", "50")),
            width=draw(_pos_decimal("1", "50")),
            height=draw(_pos_decimal("1", "50")),
            temperature_zone=zone, hazmat_type=HazmatType.NONE,
            is_gift=is_gift,
        ))
    return items


# Feature: cartonization-engine, Property 3: 温区分组不变量
# **Validates: Requirements 2.1**
@given(items=sku_items_multi_zone())
@settings(max_examples=100)
def test_property_3_temperature_zone_grouping(items):
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    for group in groups:
        zones = {item.temperature_zone for item in group.items}
        assert len(zones) <= 1, f"组内存在多个温区: {zones}"


# Feature: cartonization-engine, Property 4: 危险品隔离分组
# **Validates: Requirements 2.2**
@given(items=sku_items_with_hazmat_pg())
@settings(max_examples=100)
def test_property_4_hazmat_isolation_grouping(items):
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    hazmat_ids = {it.sku_id for it in items if it.hazmat_type and it.hazmat_type != HazmatType.NONE}
    for group in groups:
        gids = {it.sku_id for it in group.items}
        if gids & hazmat_ids:
            assert len(group.items) == 1
            assert group.items[0].sku_id in hazmat_ids


# Feature: cartonization-engine, Property 5: 禁混互斥分组
# **Validates: Requirements 2.3**
@given(items=sku_items_cannot_ship_pg())
@settings(max_examples=100)
def test_property_5_cannot_ship_with_grouping(items):
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    cannot_map = {it.sku_id: set(it.cannot_ship_with) for it in items}
    for group in groups:
        ids = [it.sku_id for it in group.items]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                assert b not in cannot_map.get(a, set())
                assert a not in cannot_map.get(b, set())


# Feature: cartonization-engine, Property 6: 同包绑定分组
# **Validates: Requirements 2.4**
@given(items=sku_items_must_ship_pg())
@settings(max_examples=100)
def test_property_6_must_ship_with_grouping(items):
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    sku_to_group = {}
    for group in groups:
        for item in group.items:
            sku_to_group[item.sku_id] = group.group_id
    for item in items:
        for tid in item.must_ship_with:
            if tid in sku_to_group:
                assert sku_to_group[item.sku_id] == sku_to_group[tid]


# Feature: cartonization-engine, Property 7: 赠品同包分组
# **Validates: Requirements 2.6**
@given(items=sku_items_with_gifts_pg())
@settings(max_examples=100)
def test_property_7_gift_same_package_grouping(items):
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig(gift_same_package_required=True))
    gift_ids = {it.sku_id for it in items if it.is_gift}
    non_gift_ids = {it.sku_id for it in items if not it.is_gift}
    if not gift_ids or not non_gift_ids:
        return
    groups_with_non = [g for g in groups if any(not it.is_gift for it in g.items)]
    for group in groups:
        g_gifts = {it.sku_id for it in group.items if it.is_gift}
        g_non = {it.sku_id for it in group.items if not it.is_gift}
        if g_gifts and not g_non:
            assert len(groups_with_non) == 0
