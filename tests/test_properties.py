"""属性测试 - 装箱计算引擎正确性属性验证"""

from decimal import Decimal

from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    BillingWeight,
    BoxType,
    CartonizationResult,
    CartonStatus,
    DecisionLog,
    DegradationMark,
    Dimensions,
    FallbackLevel,
    Package,
    PackageFlag,
    PackageItem,
    RuleViolation,
    TemperatureZone,
    HazmatType,
    SKUItem,
    CartonizationRequest,
    CarrierLimits,
    OrderConfig,
    ValidationResult,
)
from cartonization_engine.validator import InputValidator
from cartonization_engine.oversize_handler import OversizeHandler
from cartonization_engine.pre_grouper import PreGrouper


# ---------------------------------------------------------------------------
# Hypothesis 生成器
# ---------------------------------------------------------------------------

def _pos_decimal(min_val: str = "0.1", max_val: str = "200") -> st.SearchStrategy[Decimal]:
    """生成正 Decimal 值，限制小数位数避免 hypothesis 溢出"""
    return st.decimals(
        min_value=Decimal(min_val),
        max_value=Decimal(max_val),
        places=1,
        allow_nan=False,
        allow_infinity=False,
    )


@composite
def dimensions(draw: st.DrawFn) -> Dimensions:
    return Dimensions(
        length=draw(_pos_decimal("1", "150")),
        width=draw(_pos_decimal("1", "100")),
        height=draw(_pos_decimal("1", "100")),
    )


@composite
def package_items(draw: st.DrawFn, min_size: int = 1, max_size: int = 5) -> list[PackageItem]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [
        PackageItem(
            sku_id=f"SKU{i:03d}",
            sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=20)),
        )
        for i in range(n)
    ]


@composite
def box_types(draw: st.DrawFn) -> BoxType:
    inner = draw(dimensions())
    outer = Dimensions(
        length=inner.length + draw(_pos_decimal("0.5", "5")),
        width=inner.width + draw(_pos_decimal("0.5", "5")),
        height=inner.height + draw(_pos_decimal("0.5", "5")),
    )
    return BoxType(
        box_id=f"BOX{draw(st.integers(min_value=1, max_value=999)):03d}",
        inner_dimensions=inner,
        outer_dimensions=outer,
        max_weight=draw(_pos_decimal("5", "100")),
        material_weight=draw(_pos_decimal("0.1", "3")),
        packaging_cost=draw(_pos_decimal("0.5", "20")),
        is_standard=draw(st.booleans()),
        supports_shock_proof=draw(st.booleans()),
        supports_leak_proof=draw(st.booleans()),
    )


@composite
def billing_weights(draw: st.DrawFn) -> BillingWeight:
    actual = draw(_pos_decimal("0.1", "50"))
    volumetric = draw(_pos_decimal("0.1", "50"))
    billing = max(actual, volumetric)
    return BillingWeight(
        actual_weight=actual, volumetric_weight=volumetric, billing_weight=billing,
    )


@composite
def decision_logs(draw: st.DrawFn) -> DecisionLog:
    return DecisionLog(
        group_reason=draw(st.sampled_from(["温区分组", "危险品隔离", "禁混拆分"])),
        box_selection_reason=draw(st.sampled_from(["最小适配", "计费重最低", "包材最低"])),
        split_reason=draw(st.none() | st.sampled_from(["超重拆分", "超体积拆分"])),
    )


@composite
def packages(draw: st.DrawFn) -> Package:
    return Package(
        package_id=f"PKG{draw(st.integers(min_value=1, max_value=9999)):04d}",
        items=draw(package_items()),
        box_type=draw(box_types()),
        billing_weight=draw(billing_weights()),
        fill_rate=draw(_pos_decimal("10", "100")),
        flags=draw(st.lists(st.sampled_from(list(PackageFlag)), max_size=3, unique=True)),
        decision_log=draw(decision_logs()),
    )


@composite
def degradation_marks(draw: st.DrawFn) -> DegradationMark:
    return DegradationMark(
        sku_id=f"SKU{draw(st.integers(min_value=0, max_value=99)):03d}",
        field=draw(st.sampled_from(["weight", "length", "width", "height", "temperature_zone"])),
        original_value=None,
        degraded_value=str(draw(_pos_decimal("0.1", "50"))),
        reason="使用品类平均值替代缺失字段",
    )


@composite
def rule_violations(draw: st.DrawFn) -> RuleViolation:
    return RuleViolation(
        rule_name=draw(st.sampled_from(["温区不混装", "危险品隔离", "禁混品类"])),
        violated_skus=draw(st.lists(st.text(min_size=3, max_size=8, alphabet="ABCSKU0123456789"), min_size=1, max_size=3)),
        description="规则违反描述",
    )


@composite
def cartonization_results(draw: st.DrawFn) -> CartonizationResult:
    status = draw(st.sampled_from(list(CartonStatus)))
    pkgs = draw(st.lists(packages(), min_size=0, max_size=3))
    total_bw = sum((p.billing_weight.billing_weight for p in pkgs), Decimal("0"))
    return CartonizationResult(
        status=status,
        order_id=f"ORD{draw(st.integers(min_value=1, max_value=99999)):05d}",
        packages=pkgs, total_packages=len(pkgs), total_billing_weight=total_bw,
        degradation_marks=draw(st.lists(degradation_marks(), max_size=2)),
        violations=draw(st.lists(rule_violations(), max_size=2)),
        fallback_level=draw(st.none() | st.sampled_from(list(FallbackLevel))),
        error_code=draw(st.none() | st.sampled_from(["INVALID_INPUT", "CARTON_FAILED", "RULE_CONFLICT"])),
        error_message=draw(st.none() | st.text(min_size=1, max_size=30)),
        failed_skus=draw(st.lists(st.text(min_size=3, max_size=8, alphabet="SKU0123456789"), max_size=3)),
    )


@composite
def sku_items_with_missing_fields(draw: st.DrawFn, min_size: int = 1, max_size: int = 5) -> list[SKUItem]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    for i in range(n):
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=10)),
            weight=draw(st.one_of(st.none(), _pos_decimal("0.1", "50"))),
            length=draw(st.one_of(st.none(), _pos_decimal("1", "100"))),
            width=draw(st.one_of(st.none(), _pos_decimal("1", "100"))),
            height=draw(st.one_of(st.none(), _pos_decimal("1", "100"))),
            temperature_zone=draw(st.one_of(st.none(), st.sampled_from(list(TemperatureZone)))),
            hazmat_type=draw(st.one_of(st.none(), st.sampled_from(list(HazmatType)))),
            category_id=draw(st.one_of(st.none(), st.sampled_from(["CAT_A", "CAT_B"]))),
        ))
    return items


@composite
def valid_box_type_list(draw: st.DrawFn, min_size: int = 1, max_size: int = 3) -> list[BoxType]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(box_types()) for _ in range(n)]


@composite
def sample_carrier_limits(draw: st.DrawFn) -> CarrierLimits:
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


@composite
def invalid_box_type_lists(draw: st.DrawFn) -> list[BoxType]:
    strategy = draw(st.sampled_from(["empty", "invalid_dims"]))
    if strategy == "empty":
        return []
    inner = Dimensions(length=Decimal("0"), width=draw(_pos_decimal("1", "50")), height=draw(_pos_decimal("1", "50")))
    outer = Dimensions(length=inner.length + Decimal("2"), width=inner.width + Decimal("2"), height=inner.height + Decimal("2"))
    return [BoxType(box_id="BOX_INVALID", inner_dimensions=inner, outer_dimensions=outer,
                    max_weight=draw(_pos_decimal("5", "50")), material_weight=draw(_pos_decimal("0.1", "2")),
                    packaging_cost=draw(_pos_decimal("1", "10")))]


@composite
def sku_items_with_oversize(draw: st.DrawFn, min_size: int = 2, max_size: int = 8) -> list[SKUItem]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    for i in range(n):
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=5)),
            weight=draw(_pos_decimal("0.1", "50")),
            length=draw(_pos_decimal("1", "150")),
            width=draw(_pos_decimal("1", "100")),
            height=draw(_pos_decimal("1", "100")),
            temperature_zone=draw(st.sampled_from(list(TemperatureZone))),
            hazmat_type=draw(st.sampled_from(list(HazmatType))),
            oversize_flag=draw(st.booleans()),
        ))
    return items


@composite
def sku_items_multi_zone(draw: st.DrawFn, min_size: int = 2, max_size: int = 8) -> list[SKUItem]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    for i in range(n):
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=5)),
            weight=draw(_pos_decimal("0.1", "20")),
            length=draw(_pos_decimal("1", "50")),
            width=draw(_pos_decimal("1", "50")),
            height=draw(_pos_decimal("1", "50")),
            temperature_zone=draw(st.sampled_from(list(TemperatureZone))),
            hazmat_type=HazmatType.NONE,
        ))
    return items


@composite
def sku_items_with_hazmat_pg(draw: st.DrawFn, min_size: int = 2, max_size: int = 6) -> list[SKUItem]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    hazmat_types = [HazmatType.FLAMMABLE, HazmatType.EXPLOSIVE, HazmatType.CORROSIVE]
    for i in range(n):
        ht = draw(st.sampled_from(hazmat_types)) if i == 0 else draw(st.sampled_from(list(HazmatType)))
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
            quantity=draw(st.integers(min_value=1, max_value=5)),
            weight=draw(_pos_decimal("0.1", "20")),
            length=draw(_pos_decimal("1", "50")),
            width=draw(_pos_decimal("1", "50")),
            height=draw(_pos_decimal("1", "50")),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=ht,
        ))
    return items


@composite
def sku_items_cannot_ship_pg(draw: st.DrawFn) -> list[SKUItem]:
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
def sku_items_must_ship_pg(draw: st.DrawFn) -> list[SKUItem]:
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
def sku_items_with_gifts_pg(draw: st.DrawFn) -> list[SKUItem]:
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


# ---------------------------------------------------------------------------
# Property 26: 序列化往返一致性
# Feature: cartonization-engine, Property 26: 序列化往返一致性
# **Validates: Requirements 12.3**
# ---------------------------------------------------------------------------

@given(result=cartonization_results())
@settings(max_examples=100)
def test_property_26_serialization_round_trip(result: CartonizationResult):
    """Property 26: JSON 序列化再反序列化应产生等价结果。"""
    json_str = result.model_dump_json()
    restored = CartonizationResult.model_validate_json(json_str)
    assert restored == result


# ---------------------------------------------------------------------------
# Property 1: 数据降级正确性
# Feature: cartonization-engine, Property 1: 数据降级正确性
# **Validates: Requirements 1.2, 1.3, 1.4**
# ---------------------------------------------------------------------------

@given(items=sku_items_with_missing_fields(), bts=valid_box_type_list(), carrier=sample_carrier_limits())
@settings(max_examples=100)
def test_property_1_data_degradation_correctness(items, bts, carrier):
    """Property 1: 缺失字段应被降级替换并标记 DATA_DEGRADED。"""
    category_defaults = {
        "CAT_A": {"weight": "2.0", "length": "20", "width": "15", "height": "10"},
        "CAT_B": {"weight": "1.5", "length": "15", "width": "10", "height": "8"},
    }
    missing_fields: dict[str, list[str]] = {}
    for item in items:
        missing = []
        for f in ("weight", "length", "width", "height"):
            if getattr(item, f) is None:
                missing.append(f)
        if item.temperature_zone is None:
            missing.append("temperature_zone")
        if item.hazmat_type is None:
            missing.append("hazmat_type")
        if missing:
            missing_fields[item.sku_id] = missing
    request = CartonizationRequest(
        order_id="ORD_TEST", items=items, box_types=bts,
        carrier_limits=carrier, category_defaults=category_defaults,
    )
    validator = InputValidator()
    result = validator.validate(request)
    assert result.success is True
    for item in result.items:
        assert item.weight is not None
        assert item.length is not None
        assert item.width is not None
        assert item.height is not None
        assert item.temperature_zone is not None
        assert item.hazmat_type is not None
    mark_keys = {(m.sku_id, m.field) for m in result.degradation_marks}
    for sku_id, fields in missing_fields.items():
        for field in fields:
            assert (sku_id, field) in mark_keys


# ---------------------------------------------------------------------------
# Property 2: 箱型列表有效性
# Feature: cartonization-engine, Property 2: 箱型列表有效性
# **Validates: Requirements 1.5, 1.6**
# ---------------------------------------------------------------------------

@given(bts=invalid_box_type_lists(), carrier=sample_carrier_limits())
@settings(max_examples=100)
def test_property_2_box_type_list_validity(bts, carrier):
    """Property 2: 空或无效箱型列表应被拒绝。"""
    request = CartonizationRequest(
        order_id="ORD_TEST",
        items=[SKUItem(sku_id="SKU001", sku_name="测试商品", quantity=1,
                       weight=Decimal("1.0"), length=Decimal("10"),
                       width=Decimal("10"), height=Decimal("10"),
                       temperature_zone=TemperatureZone.NORMAL,
                       hazmat_type=HazmatType.NONE)],
        box_types=bts, carrier_limits=carrier,
    )
    validator = InputValidator()
    result = validator.validate(request)
    assert result.success is False
    assert result.error_code is not None


# ---------------------------------------------------------------------------
# Property 25: 超大件隔离
# Feature: cartonization-engine, Property 25: 超大件隔离
# **Validates: Requirements 11.1, 11.2, 11.3**
# ---------------------------------------------------------------------------

@given(items=sku_items_with_oversize())
@settings(max_examples=100)
def test_property_25_oversize_isolation(items: list[SKUItem]):
    """Property 25: 超大件 SKU 单独成包并标记 OVERSIZE_SPECIAL。"""
    handler = OversizeHandler()
    result = handler.separate(items)
    oversize_ids = {item.sku_id for item in items if item.oversize_flag}
    normal_ids = {item.sku_id for item in items if not item.oversize_flag}
    oversize_pkg_ids = {pkg.item.sku_id for pkg in result.oversize_packages}
    assert oversize_ids == oversize_pkg_ids
    for pkg in result.oversize_packages:
        assert PackageFlag.OVERSIZE_SPECIAL in pkg.flags
    normal_result_ids = {item.sku_id for item in result.normal_items}
    assert normal_ids == normal_result_ids
    for item in result.normal_items:
        assert not item.oversize_flag


# ---------------------------------------------------------------------------
# Property 3: 温区分组不变量
# Feature: cartonization-engine, Property 3: 温区分组不变量
# **Validates: Requirements 2.1**
# ---------------------------------------------------------------------------

@given(items=sku_items_multi_zone())
@settings(max_examples=100)
def test_property_3_temperature_zone_grouping(items: list[SKUItem]):
    """Property 3: 同组内所有 SKU 温区相同。"""
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    for group in groups:
        zones = {item.temperature_zone for item in group.items}
        assert len(zones) <= 1, f"组 {group.group_id} 内存在多个温区: {zones}"


# ---------------------------------------------------------------------------
# Property 4: 危险品隔离分组
# Feature: cartonization-engine, Property 4: 危险品隔离分组
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------

@given(items=sku_items_with_hazmat_pg())
@settings(max_examples=100)
def test_property_4_hazmat_isolation_grouping(items: list[SKUItem]):
    """Property 4: 危险品 SKU 单独成组。"""
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    hazmat_ids = {item.sku_id for item in items
                  if item.hazmat_type is not None and item.hazmat_type != HazmatType.NONE}
    for group in groups:
        group_ids = {item.sku_id for item in group.items}
        if group_ids & hazmat_ids:
            assert len(group.items) == 1, f"危险品组包含多个 SKU: {group_ids}"
            assert group.items[0].sku_id in hazmat_ids


# ---------------------------------------------------------------------------
# Property 5: 禁混互斥分组
# Feature: cartonization-engine, Property 5: 禁混互斥分组
# **Validates: Requirements 2.3**
# ---------------------------------------------------------------------------

@given(items=sku_items_cannot_ship_pg())
@settings(max_examples=100)
def test_property_5_cannot_ship_with_grouping(items: list[SKUItem]):
    """Property 5: 互斥 SKU 不在同组。"""
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    cannot_map = {item.sku_id: set(item.cannot_ship_with) for item in items}
    for group in groups:
        ids = [item.sku_id for item in group.items]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                assert b not in cannot_map.get(a, set()), f"互斥 {a} 和 {b} 同组"
                assert a not in cannot_map.get(b, set()), f"互斥 {b} 和 {a} 同组"


# ---------------------------------------------------------------------------
# Property 6: 同包绑定分组
# Feature: cartonization-engine, Property 6: 同包绑定分组
# **Validates: Requirements 2.4**
# ---------------------------------------------------------------------------

@given(items=sku_items_must_ship_pg())
@settings(max_examples=100)
def test_property_6_must_ship_with_grouping(items: list[SKUItem]):
    """Property 6: 绑定 SKU 在同组。"""
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig())
    sku_to_group: dict[str, str] = {}
    for group in groups:
        for item in group.items:
            sku_to_group[item.sku_id] = group.group_id
    for item in items:
        for target_id in item.must_ship_with:
            if target_id in sku_to_group:
                assert sku_to_group[item.sku_id] == sku_to_group[target_id]


# ---------------------------------------------------------------------------
# Property 7: 赠品同包分组
# Feature: cartonization-engine, Property 7: 赠品同包分组
# **Validates: Requirements 2.6**
# ---------------------------------------------------------------------------

@given(items=sku_items_with_gifts_pg())
@settings(max_examples=100)
def test_property_7_gift_same_package_grouping(items: list[SKUItem]):
    """Property 7: 赠品与主商品在同组。"""
    grouper = PreGrouper()
    groups = grouper.group(items, OrderConfig(gift_same_package_required=True))
    gift_ids = {item.sku_id for item in items if item.is_gift}
    non_gift_ids = {item.sku_id for item in items if not item.is_gift}
    if not gift_ids or not non_gift_ids:
        return
    groups_with_non_gifts = [g for g in groups if any(not it.is_gift for it in g.items)]
    for group in groups:
        g_gifts = {it.sku_id for it in group.items if it.is_gift}
        g_non = {it.sku_id for it in group.items if not it.is_gift}
        if g_gifts and not g_non:
            assert len(groups_with_non_gifts) == 0, f"赠品 {g_gifts} 单独成组"
