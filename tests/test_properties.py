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
)


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
    # outer >= inner
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
        actual_weight=actual,
        volumetric_weight=volumetric,
        billing_weight=billing,
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
    """生成随机 CartonizationResult 对象"""
    status = draw(st.sampled_from(list(CartonStatus)))
    pkgs = draw(st.lists(packages(), min_size=0, max_size=3))
    total_bw = sum((p.billing_weight.billing_weight for p in pkgs), Decimal("0"))
    return CartonizationResult(
        status=status,
        order_id=f"ORD{draw(st.integers(min_value=1, max_value=99999)):05d}",
        packages=pkgs,
        total_packages=len(pkgs),
        total_billing_weight=total_bw,
        degradation_marks=draw(st.lists(degradation_marks(), max_size=2)),
        violations=draw(st.lists(rule_violations(), max_size=2)),
        fallback_level=draw(st.none() | st.sampled_from(list(FallbackLevel))),
        error_code=draw(st.none() | st.sampled_from(["INVALID_INPUT", "CARTON_FAILED", "RULE_CONFLICT"])),
        error_message=draw(st.none() | st.text(min_size=1, max_size=30)),
        failed_skus=draw(st.lists(st.text(min_size=3, max_size=8, alphabet="SKU0123456789"), max_size=3)),
    )


# ---------------------------------------------------------------------------
# Property 26: 序列化往返一致性
# Feature: cartonization-engine, Property 26: 序列化往返一致性
# **Validates: Requirements 12.3**
# ---------------------------------------------------------------------------

@given(result=cartonization_results())
@settings(max_examples=100)
def test_property_26_serialization_round_trip(result: CartonizationResult):
    """
    Property 26: 对于任意有效的 CartonizationResult 对象，
    将其序列化为 JSON 再反序列化回对象，应产生与原始对象等价的结果。
    """
    json_str = result.model_dump_json()
    restored = CartonizationResult.model_validate_json(json_str)
    assert restored == result, (
        f"Round-trip mismatch:\n"
        f"  original: {result}\n"
        f"  restored: {restored}"
    )


# ---------------------------------------------------------------------------
# 额外导入
# ---------------------------------------------------------------------------
from cartonization_engine.models import (
    SKUItem,
    CartonizationRequest,
    CarrierLimits,
    OrderConfig,
    ValidationResult,
)
from cartonization_engine.validator import InputValidator


# ---------------------------------------------------------------------------
# 辅助生成器
# ---------------------------------------------------------------------------

@composite
def sku_items_with_missing_fields(draw: st.DrawFn, min_size: int = 1, max_size: int = 5) -> list[SKUItem]:
    """生成部分字段为 None 的随机 SKU 列表"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    for i in range(n):
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}",
            sku_name=f"商品{i}",
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
    """生成有效的箱型列表"""
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


# ---------------------------------------------------------------------------
# Property 1: 数据降级正确性
# Feature: cartonization-engine, Property 1: 数据降级正确性
# **Validates: Requirements 1.2, 1.3, 1.4**
# ---------------------------------------------------------------------------

@given(
    items=sku_items_with_missing_fields(),
    bts=valid_box_type_list(),
    carrier=sample_carrier_limits(),
)
@settings(max_examples=100)
def test_property_1_data_degradation_correctness(
    items: list[SKUItem], bts: list[BoxType], carrier: CarrierLimits
):
    """
    Property 1: 对于任意 SKU 列表，如果某个 SKU 的 weight、length、width、height、
    temperature_zone 或 hazmat_type 字段缺失，验证后该字段应被替换为对应的降级值，
    且该 SKU 在输出中被标记为 DATA_DEGRADED。
    """
    category_defaults = {
        "CAT_A": {"weight": "2.0", "length": "20", "width": "15", "height": "10"},
        "CAT_B": {"weight": "1.5", "length": "15", "width": "10", "height": "8"},
    }

    # 记录哪些 SKU 的哪些字段原本为 None
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
        order_id="ORD_TEST",
        items=items,
        box_types=bts,
        carrier_limits=carrier,
        category_defaults=category_defaults,
    )

    validator = InputValidator()
    result = validator.validate(request)

    assert result.success is True

    # 验证所有缺失字段都被降级
    for item in result.items:
        assert item.weight is not None
        assert item.length is not None
        assert item.width is not None
        assert item.height is not None
        assert item.temperature_zone is not None
        assert item.hazmat_type is not None

    # 验证降级标记覆盖了所有缺失字段
    mark_keys = {(m.sku_id, m.field) for m in result.degradation_marks}
    for sku_id, fields in missing_fields.items():
        for field in fields:
            assert (sku_id, field) in mark_keys, (
                f"缺失字段 {sku_id}.{field} 未被标记为降级"
            )


# ---------------------------------------------------------------------------
# Property 2: 箱型列表有效性
# Feature: cartonization-engine, Property 2: 箱型列表有效性
# **Validates: Requirements 1.5, 1.6**
# ---------------------------------------------------------------------------

@composite
def invalid_box_type_lists(draw: st.DrawFn) -> list[BoxType]:
    """生成含空列表或无效值的箱型列表"""
    strategy = draw(st.sampled_from(["empty", "invalid_dims"]))
    if strategy == "empty":
        return []
    else:
        # 生成含非正数尺寸的箱型
        inner = Dimensions(
            length=Decimal("0"),  # 非正数
            width=draw(_pos_decimal("1", "50")),
            height=draw(_pos_decimal("1", "50")),
        )
        outer = Dimensions(
            length=inner.length + Decimal("2"),
            width=inner.width + Decimal("2"),
            height=inner.height + Decimal("2"),
        )
        return [BoxType(
            box_id="BOX_INVALID",
            inner_dimensions=inner,
            outer_dimensions=outer,
            max_weight=draw(_pos_decimal("5", "50")),
            material_weight=draw(_pos_decimal("0.1", "2")),
            packaging_cost=draw(_pos_decimal("1", "10")),
        )]


@given(
    bts=invalid_box_type_lists(),
    carrier=sample_carrier_limits(),
)
@settings(max_examples=100)
def test_property_2_box_type_list_validity(
    bts: list[BoxType], carrier: CarrierLimits
):
    """
    Property 2: 对于任意装箱请求，如果可用箱型列表为空或包含尺寸/承重为非正数的箱型，
    验证器应拒绝该请求并返回相应错误。
    """
    request = CartonizationRequest(
        order_id="ORD_TEST",
        items=[SKUItem(
            sku_id="SKU001",
            sku_name="测试商品",
            quantity=1,
            weight=Decimal("1.0"),
            length=Decimal("10"),
            width=Decimal("10"),
            height=Decimal("10"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
        )],
        box_types=bts,
        carrier_limits=carrier,
    )

    validator = InputValidator()
    result = validator.validate(request)

    assert result.success is False, (
        f"验证器应拒绝无效箱型列表，但返回了 success=True。箱型列表: {bts}"
    )
    assert result.error_code is not None


# ---------------------------------------------------------------------------
# 超大件处理器导入
# ---------------------------------------------------------------------------
from cartonization_engine.oversize_handler import OversizeHandler


# ---------------------------------------------------------------------------
# 辅助生成器 - 含超大件的 SKU 列表
# ---------------------------------------------------------------------------

@composite
def sku_items_with_oversize(draw: st.DrawFn, min_size: int = 2, max_size: int = 8) -> list[SKUItem]:
    """生成含超大件的随机 SKU 列表"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    for i in range(n):
        items.append(SKUItem(
            sku_id=f"SKU{i:03d}",
            sku_name=f"商品{i}",
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


# ---------------------------------------------------------------------------
# Property 25: 超大件隔离
# Feature: cartonization-engine, Property 25: 超大件隔离
# **Validates: Requirements 11.1, 11.2, 11.3**
# ---------------------------------------------------------------------------

@given(items=sku_items_with_oversize())
@settings(max_examples=100)
def test_property_25_oversize_isolation(items: list[SKUItem]):
    """
    Property 25: 对于任意 oversize_flag=True 的 SKU，该 SKU 单独成包，
    包裹标记为 OVERSIZE_SPECIAL，且该包裹不包含 oversize_flag=False 的 SKU。
    """
    handler = OversizeHandler()
    result = handler.separate(items)

    oversize_ids = {item.sku_id for item in items if item.oversize_flag}
    normal_ids = {item.sku_id for item in items if not item.oversize_flag}

    # 1. 每个超大件 SKU 单独成包
    oversize_pkg_ids = {pkg.item.sku_id for pkg in result.oversize_packages}
    assert oversize_ids == oversize_pkg_ids, (
        f"超大件 SKU 未全部单独成包: expected={oversize_ids}, got={oversize_pkg_ids}"
    )

    # 2. 每个超大件包裹标记为 OVERSIZE_SPECIAL
    from cartonization_engine.models import PackageFlag
    for pkg in result.oversize_packages:
        assert PackageFlag.OVERSIZE_SPECIAL in pkg.flags, (
            f"超大件包裹 {pkg.item.sku_id} 未标记 OVERSIZE_SPECIAL"
        )

    # 3. 普通件不出现在超大件包裹中
    normal_result_ids = {item.sku_id for item in result.normal_items}
    assert normal_ids == normal_result_ids, (
        f"普通件列表不匹配: expected={normal_ids}, got={normal_result_ids}"
    )

    # 4. 超大件不出现在普通件列表中
    for item in result.normal_items:
        assert not item.oversize_flag, (
            f"超大件 {item.sku_id} 出现在普通件列表中"
        )
