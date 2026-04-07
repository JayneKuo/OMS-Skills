"""属性测试 - 箱型选择器 Properties 10-12"""

from decimal import Decimal
from hypothesis import given, settings, assume, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, CarrierLimits, TemperatureZone, HazmatType,
)
from cartonization_engine.box_selector import BoxSelector


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def small_sku_items(draw, min_size=1, max_size=4):
    """生成小尺寸 SKU 以确保能被箱型容纳"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=2)),
        weight=draw(_pos_decimal("0.1", "3")),
        length=draw(_pos_decimal("1", "15")),
        width=draw(_pos_decimal("1", "10")),
        height=draw(_pos_decimal("1", "10")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


@composite
def carrier_limits_gen(draw):
    return CarrierLimits(
        carrier_id="CARRIER001",
        max_weight=draw(_pos_decimal("50", "100")),
        max_dimension=Dimensions(
            length=draw(_pos_decimal("100", "200")),
            width=draw(_pos_decimal("80", "150")),
            height=draw(_pos_decimal("60", "120")),
        ),
        dim_factor=draw(st.sampled_from([5000, 6000])),
    )


@composite
def multiple_box_types(draw, min_size=2, max_size=5):
    """生成多个不同大小的箱型"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    bts = []
    for i in range(n):
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
        bts.append(BoxType(
            box_id=f"BOX{i:03d}",
            inner_dimensions=inner, outer_dimensions=outer,
            max_weight=draw(_pos_decimal("10", "50")),
            material_weight=draw(_pos_decimal("0.1", "2")),
            packaging_cost=draw(_pos_decimal("0.5", "15")),
            supports_shock_proof=draw(st.booleans()),
            supports_leak_proof=draw(st.booleans()),
        ))
    return bts


# Feature: cartonization-engine, Property 10: 箱型选择优先级
# **Validates: Requirements 4.1, 4.2, 4.3**
@given(items=small_sku_items(), bts=multiple_box_types(), carrier=carrier_limits_gen())
@settings(max_examples=100)
def test_property_10_box_selection_priority(items, bts, carrier):
    """Property 10: 选中箱型的计费重量和包材成本最优。"""
    selector = BoxSelector()
    selected = selector.select(items, bts, carrier)
    if selected is None:
        return  # 无可用箱型

    # 计算 SKU 总体积和总重量
    total_vol = sum(
        (it.length or Decimal(0)) * (it.width or Decimal(0)) * (it.height or Decimal(0)) * it.quantity
        for it in items
    )
    total_wt = sum((it.weight or Decimal(0)) * it.quantity for it in items)

    def billing_weight(bt):
        actual = total_wt + bt.material_weight
        volumetric = bt.outer_dimensions.volume / Decimal(str(carrier.dim_factor))
        return max(actual, volumetric)

    selected_bw = billing_weight(selected)

    # 验证不存在更优的可用箱型
    for bt in bts:
        if bt.box_id == selected.box_id:
            continue
        # 检查是否满足物理容纳
        if bt.inner_dimensions.volume < total_vol or bt.max_weight < total_wt:
            continue
        if not BoxSelector._carrier_compliant(bt, carrier):
            continue
        bt_bw = billing_weight(bt)
        if bt_bw < selected_bw:
            assert False, f"存在更优箱型 {bt.box_id}: bw={bt_bw} < selected bw={selected_bw}"
        elif bt_bw == selected_bw:
            assert bt.packaging_cost >= selected.packaging_cost, (
                f"存在同计费重但更低成本的箱型 {bt.box_id}"
            )


# Feature: cartonization-engine, Property 11: 箱型承运商尺寸合规
# **Validates: Requirements 4.5, 7.4**
@given(items=small_sku_items(), bts=multiple_box_types(), carrier=carrier_limits_gen())
@settings(max_examples=100)
def test_property_11_carrier_dimension_compliance(items, bts, carrier):
    """Property 11: 所选箱型外部尺寸不超过承运商限制。"""
    selector = BoxSelector()
    selected = selector.select(items, bts, carrier)
    if selected is None:
        return
    outer = selected.outer_dimensions
    limit = carrier.max_dimension
    assert outer.length <= limit.length, f"长度超限: {outer.length} > {limit.length}"
    assert outer.width <= limit.width, f"宽度超限: {outer.width} > {limit.width}"
    assert outer.height <= limit.height, f"高度超限: {outer.height} > {limit.height}"


# Feature: cartonization-engine, Property 12: 易碎品防震保护
# **Validates: Requirements 4.6, 7.6**
@given(items=small_sku_items(), bts=multiple_box_types(), carrier=carrier_limits_gen())
@settings(max_examples=100)
def test_property_12_fragile_shock_proof(items, bts, carrier):
    """Property 12: 含易碎品时箱型支持防震。"""
    # 标记第一个 SKU 为易碎品
    if not items:
        return
    fragile_items = [it.model_copy(update={"fragile_flag": True}) for it in items]
    has_fragile = True

    selector = BoxSelector()
    selected = selector.select(fragile_items, bts, carrier, has_fragile=has_fragile)
    if selected is None:
        return  # 无防震箱型可用
    assert selected.supports_shock_proof, "易碎品包裹未选择防震箱型"
