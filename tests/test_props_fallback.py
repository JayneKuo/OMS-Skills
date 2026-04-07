"""属性测试 - 回退处理器 Property 24"""

from decimal import Decimal
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, CarrierLimits,
    FallbackContext, FallbackLevel,
    TemperatureZone, HazmatType,
)
from cartonization_engine.fallback_handler import FallbackHandler


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def sku_items_gen(draw, min_size=1, max_size=3):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=3)),
        weight=draw(_pos_decimal("0.1", "10")),
        length=draw(_pos_decimal("1", "30")),
        width=draw(_pos_decimal("1", "20")),
        height=draw(_pos_decimal("1", "20")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


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


@composite
def fallback_context_gen(draw):
    """生成回退上下文，可能有或没有非标箱型。"""
    has_non_std = draw(st.booleans())
    non_std = []
    if has_non_std:
        inner = Dimensions(
            length=draw(_pos_decimal("50", "150")),
            width=draw(_pos_decimal("40", "100")),
            height=draw(_pos_decimal("30", "80")),
        )
        outer = Dimensions(
            length=inner.length + Decimal("2"),
            width=inner.width + Decimal("2"),
            height=inner.height + Decimal("2"),
        )
        non_std.append(BoxType(
            box_id="NONSTD001",
            inner_dimensions=inner, outer_dimensions=outer,
            max_weight=draw(_pos_decimal("30", "200")),
            material_weight=draw(_pos_decimal("0.1", "3")),
            packaging_cost=draw(_pos_decimal("1", "20")),
            is_standard=False,
        ))
    return FallbackContext(non_standard_box_types=non_std)


LEVEL_ORDER = [
    FallbackLevel.F1_NON_STANDARD_BOX,
    FallbackLevel.F2_VIRTUAL_BOX,
    FallbackLevel.F3_OVERSIZE_CARRIER,
    FallbackLevel.F4_MANUAL_INTERVENTION,
]


# ---------------------------------------------------------------------------
# Property 24: 回退顺序不变量
# Feature: cartonization-engine, Property 24: 回退顺序不变量
# **Validates: Requirements 10.5**
# ---------------------------------------------------------------------------

@given(
    items=sku_items_gen(),
    carrier=carrier_gen(),
    context=fallback_context_gen(),
)
@settings(max_examples=100)
def test_property_24_fallback_order_invariant(items, carrier, context):
    """Property 24: 回退按 F1→F2→F3→F4 顺序执行。"""
    handler = FallbackHandler()
    result = handler.handle(items, "测试回退", context, carrier)

    # 结果的 level 必须是有效的回退级别
    assert result.level in LEVEL_ORDER, f"无效的回退级别: {result.level}"

    # 如果有非标箱型且能装下，应该是 F1
    if context.non_standard_box_types:
        from cartonization_engine.box_selector import BoxSelector
        selector = BoxSelector()
        has_fragile = any(it.fragile_flag for it in items)
        selected = selector.select(
            items, context.non_standard_box_types, carrier,
            has_fragile=has_fragile,
        )
        if selected is not None:
            # F1 应该成功
            assert result.level == FallbackLevel.F1_NON_STANDARD_BOX, (
                f"有可用非标箱型但回退级别为 {result.level}"
            )
            assert result.success is True

    # 如果没有非标箱型，不应该是 F1
    if not context.non_standard_box_types:
        assert result.level != FallbackLevel.F1_NON_STANDARD_BOX, (
            "无非标箱型但回退级别为 F1"
        )

    # F2 总是成功的（虚拟箱型）
    if result.level == FallbackLevel.F2_VIRTUAL_BOX:
        assert result.success is True

    # F4 总是失败的
    if result.level == FallbackLevel.F4_MANUAL_INTERVENTION:
        assert result.success is False
