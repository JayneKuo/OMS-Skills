"""属性测试 - 填充率校验器 Properties 15-16"""

from decimal import Decimal
from hypothesis import given, settings, assume, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, CarrierLimits,
    PackageFlag, TemperatureZone, HazmatType,
)
from cartonization_engine.fill_rate_checker import FillRateChecker


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def small_sku_items(draw, min_size=1, max_size=3):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=2)),
        weight=draw(_pos_decimal("0.1", "3")),
        length=draw(_pos_decimal("1", "10")),
        width=draw(_pos_decimal("1", "8")),
        height=draw(_pos_decimal("1", "8")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


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
        max_weight=draw(_pos_decimal("10", "50")),
        material_weight=draw(_pos_decimal("0.1", "2")),
        packaging_cost=draw(_pos_decimal("0.5", "10")),
    )


@composite
def multiple_box_types_gen(draw, min_size=2, max_size=5):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(box_type_gen()) for _ in range(n)]


# Feature: cartonization-engine, Property 15: 填充率计算正确性
# **Validates: Requirements 6.1**
@given(items=small_sku_items(), box=box_type_gen())
@settings(max_examples=100)
def test_property_15_fill_rate_calculation(items, box):
    """Property 15: 填充率 = SKU 总体积 / 箱型内部体积 × 100%。"""
    checker = FillRateChecker()
    fill_rate = checker.calculate_fill_rate(items, box)

    # 手动计算期望值
    total_vol = sum(
        (it.length or Decimal(0)) * (it.width or Decimal(0))
        * (it.height or Decimal(0)) * it.quantity
        for it in items
    )
    box_vol = box.inner_dimensions.volume
    if box_vol == 0:
        expected = Decimal("0")
    else:
        expected = (total_vol / box_vol) * Decimal("100")

    assert fill_rate == expected, f"填充率不一致: {fill_rate} != {expected}"


# Feature: cartonization-engine, Property 16: 填充率优化
# **Validates: Requirements 6.2, 6.3**
@given(items=small_sku_items(), box=box_type_gen(), all_boxes=multiple_box_types_gen())
@settings(max_examples=100)
def test_property_16_fill_rate_optimization(items, box, all_boxes):
    """Property 16: 低填充率时应换用更小箱型或标记 LOW_FILL_RATE。"""
    checker = FillRateChecker()

    # 确保当前箱型在可用列表中
    all_boxes_with_current = [box] + all_boxes

    result_box, result_rate, flags = checker.check_and_optimize(
        items, box, all_boxes_with_current,
        min_rate=Decimal("60"), max_rate=Decimal("90"),
    )

    if result_rate < Decimal("60"):
        # 填充率仍低于阈值，应标记 LOW_FILL_RATE
        assert PackageFlag.LOW_FILL_RATE in flags, (
            f"填充率 {result_rate}% < 60% 但未标记 LOW_FILL_RATE"
        )

        # 验证确实没有更小的可用箱型能提高填充率到阈值以上
        total_vol = sum(
            (it.length or Decimal(0)) * (it.width or Decimal(0))
            * (it.height or Decimal(0)) * it.quantity
            for it in items
        )
        total_wt = sum((it.weight or Decimal(0)) * it.quantity for it in items)

        for bt in all_boxes_with_current:
            if bt.inner_dimensions.volume < total_vol:
                continue
            if bt.max_weight < total_wt:
                continue
            bv = bt.inner_dimensions.volume
            if bv > 0:
                rate = (total_vol / bv) * Decimal("100")
                # 如果存在能达到 60% 的箱型，它应该已被选中
                if rate >= Decimal("60"):
                    assert result_rate >= Decimal("60") or result_box.box_id == bt.box_id, (
                        f"存在可用箱型 {bt.box_id} 填充率 {rate}% >= 60%"
                    )
