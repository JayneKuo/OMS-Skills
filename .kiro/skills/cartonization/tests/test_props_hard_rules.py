"""属性测试 - 硬规则校验器 Properties 17-20"""

from decimal import Decimal
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, CarrierLimits,
    TemperatureZone, HazmatType, RuleViolation,
)
from cartonization_engine.hard_rule_checker import HardRuleChecker


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def box_type_gen(draw):
    inner = Dimensions(
        length=draw(_pos_decimal("20", "80")),
        width=draw(_pos_decimal("15", "60")),
        height=draw(_pos_decimal("10", "50")),
    )
    outer = Dimensions(
        length=inner.length + Decimal("2"),
        width=inner.width + Decimal("2"),
        height=inner.height + Decimal("2"),
    )
    return BoxType(
        box_id=f"BOX{draw(st.integers(min_value=1, max_value=999)):03d}",
        inner_dimensions=inner, outer_dimensions=outer,
        max_weight=draw(_pos_decimal("10", "100")),
        material_weight=draw(_pos_decimal("0.1", "2")),
        packaging_cost=draw(_pos_decimal("0.5", "10")),
        supports_shock_proof=draw(st.booleans()),
        supports_leak_proof=draw(st.booleans()),
    )


@composite
def carrier_gen(draw):
    return CarrierLimits(
        carrier_id="CARRIER001",
        max_weight=draw(_pos_decimal("30", "100")),
        max_dimension=Dimensions(
            length=draw(_pos_decimal("80", "200")),
            width=draw(_pos_decimal("60", "150")),
            height=draw(_pos_decimal("50", "120")),
        ),
        dim_factor=draw(st.sampled_from([5000, 6000])),
    )


# ---------------------------------------------------------------------------
# Property 17: 温区不混装硬规则
# Feature: cartonization-engine, Property 17: 温区不混装硬规则
# **Validates: Requirements 7.1**
# ---------------------------------------------------------------------------

@composite
def mixed_zone_items(draw):
    """生成可能包含多温区的 SKU 列表。"""
    n = draw(st.integers(min_value=2, max_value=5))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=1,
        weight=draw(_pos_decimal("0.1", "5")),
        length=draw(_pos_decimal("1", "20")),
        width=draw(_pos_decimal("1", "15")),
        height=draw(_pos_decimal("1", "10")),
        temperature_zone=draw(st.sampled_from(list(TemperatureZone))),
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


@given(items=mixed_zone_items(), box=box_type_gen(), carrier=carrier_gen())
@settings(max_examples=100)
def test_property_17_temperature_zone_hard_rule(items, box, carrier):
    """Property 17: 同包裹内所有 SKU 温区相同时无违反，不同时有违反。"""
    checker = HardRuleChecker()
    violations = checker.check(items, box, carrier)

    zones = {it.temperature_zone for it in items}
    zone_violations = [v for v in violations if v.rule_name == "温区不混装"]

    if len(zones) > 1:
        assert len(zone_violations) == 1, "多温区应检测到温区不混装违反"
    else:
        assert len(zone_violations) == 0, "单温区不应有温区不混装违反"


# ---------------------------------------------------------------------------
# Property 18: 危险品隔离硬规则
# Feature: cartonization-engine, Property 18: 危险品隔离硬规则
# **Validates: Requirements 7.2**
# ---------------------------------------------------------------------------

@composite
def mixed_hazmat_items(draw):
    """生成可能包含危险品混装的 SKU 列表。"""
    n = draw(st.integers(min_value=2, max_value=5))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=1,
        weight=draw(_pos_decimal("0.1", "5")),
        length=draw(_pos_decimal("1", "20")),
        width=draw(_pos_decimal("1", "15")),
        height=draw(_pos_decimal("1", "10")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=draw(st.sampled_from(list(HazmatType))),
    ) for i in range(n)]


@given(items=mixed_hazmat_items(), box=box_type_gen(), carrier=carrier_gen())
@settings(max_examples=100)
def test_property_18_hazmat_isolation_hard_rule(items, box, carrier):
    """Property 18: 危险品不与普通品混装。"""
    checker = HardRuleChecker()
    violations = checker.check(items, box, carrier)

    hazmat = [it for it in items if it.hazmat_type and it.hazmat_type != HazmatType.NONE]
    normal = [it for it in items if not it.hazmat_type or it.hazmat_type == HazmatType.NONE]
    hazmat_violations = [v for v in violations if v.rule_name == "危险品隔离"]

    if hazmat and normal:
        assert len(hazmat_violations) == 1, "危险品与普通品混装应检测到违反"
    else:
        assert len(hazmat_violations) == 0, "纯危险品或纯普通品不应有违反"


# ---------------------------------------------------------------------------
# Property 19: 禁混品类隔离硬规则
# Feature: cartonization-engine, Property 19: 禁混品类隔离硬规则
# **Validates: Requirements 7.5**
# ---------------------------------------------------------------------------

@composite
def items_with_cannot_ship(draw):
    """生成含 cannot_ship_with 约束的 SKU 列表。"""
    n = draw(st.integers(min_value=2, max_value=4))
    items = []
    for i in range(n):
        # 随机选择一些其他 SKU 作为禁混对象
        other_ids = [f"SKU{j:03d}" for j in range(n) if j != i]
        forbidden = draw(st.lists(
            st.sampled_from(other_ids) if other_ids else st.nothing(),
            max_size=min(2, len(other_ids)),
            unique=True,
        ))
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
            quantity=1,
            weight=draw(_pos_decimal("0.1", "5")),
            length=draw(_pos_decimal("1", "20")),
            width=draw(_pos_decimal("1", "15")),
            height=draw(_pos_decimal("1", "10")),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            cannot_ship_with=forbidden,
        ))
    return items


@given(items=items_with_cannot_ship(), box=box_type_gen(), carrier=carrier_gen())
@settings(max_examples=100)
def test_property_19_cannot_ship_with_hard_rule(items, box, carrier):
    """Property 19: cannot_ship_with 中的 SKU 不在同一包裹。"""
    checker = HardRuleChecker()
    violations = checker.check(items, box, carrier)

    # 检查是否存在实际的禁混冲突
    sku_ids = {it.sku_id for it in items}
    has_conflict = False
    for it in items:
        for fid in it.cannot_ship_with:
            if fid in sku_ids and fid != it.sku_id:
                has_conflict = True
                break
        if has_conflict:
            break

    csw_violations = [v for v in violations if v.rule_name == "禁混品类隔离"]
    if has_conflict:
        assert len(csw_violations) >= 1, "存在禁混冲突但未检测到"
    else:
        assert len(csw_violations) == 0, "无禁混冲突但检测到违反"


# ---------------------------------------------------------------------------
# Property 20: 液体品防漏硬规则
# Feature: cartonization-engine, Property 20: 液体品防漏硬规则
# **Validates: Requirements 7.7**
# ---------------------------------------------------------------------------

@composite
def items_with_liquid(draw):
    """生成含液体品的 SKU 列表。"""
    n = draw(st.integers(min_value=1, max_value=4))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=1,
        weight=draw(_pos_decimal("0.1", "5")),
        length=draw(_pos_decimal("1", "20")),
        width=draw(_pos_decimal("1", "15")),
        height=draw(_pos_decimal("1", "10")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
        liquid_flag=draw(st.booleans()),
    ) for i in range(n)]


@given(items=items_with_liquid(), box=box_type_gen(), carrier=carrier_gen())
@settings(max_examples=100)
def test_property_20_liquid_leak_proof_hard_rule(items, box, carrier):
    """Property 20: 含液体品的包裹需防漏箱型。"""
    checker = HardRuleChecker()
    violations = checker.check(items, box, carrier)

    has_liquid = any(it.liquid_flag for it in items)
    liquid_violations = [v for v in violations if v.rule_name == "液体品防漏"]

    if has_liquid and not box.supports_leak_proof:
        assert len(liquid_violations) == 1, "含液体品但箱型不防漏应检测到违反"
    else:
        assert len(liquid_violations) == 0, "无液体品或箱型防漏不应有违反"
