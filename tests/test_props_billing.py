"""属性测试 - 计费重量计算器 Property 21"""

from decimal import Decimal, ROUND_CEILING
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, CarrierLimits,
    TemperatureZone, HazmatType,
)
from cartonization_engine.billing_calculator import BillingWeightCalculator


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def sku_items_gen(draw, min_size=1, max_size=3):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=5)),
        weight=draw(_pos_decimal("0.1", "10")),
        length=draw(_pos_decimal("1", "30")),
        width=draw(_pos_decimal("1", "20")),
        height=draw(_pos_decimal("1", "20")),
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
        box_id="BOX001",
        inner_dimensions=inner, outer_dimensions=outer,
        max_weight=draw(_pos_decimal("10", "100")),
        material_weight=draw(_pos_decimal("0.1", "3")),
        packaging_cost=draw(_pos_decimal("0.5", "10")),
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
# Property 21: 计费重量计算正确性
# Feature: cartonization-engine, Property 21: 计费重量计算正确性
# **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
# ---------------------------------------------------------------------------

@given(items=sku_items_gen(), box=box_type_gen(), carrier=carrier_gen())
@settings(max_examples=100)
def test_property_21_billing_weight_correctness(items, box, carrier):
    """Property 21: 计费重量公式正确且 billing >= actual 且 billing >= volumetric。"""
    calc = BillingWeightCalculator()
    result = calc.calculate(items, box, carrier)

    # 手动计算
    expected_actual = sum(
        (it.weight or Decimal(0)) * it.quantity for it in items
    ) + box.material_weight

    outer = box.outer_dimensions
    expected_volumetric = (
        outer.length * outer.width * outer.height
    ) / Decimal(str(carrier.dim_factor))

    raw = max(expected_actual, expected_volumetric)
    expected_billing = (raw * Decimal("10")).to_integral_value(
        rounding=ROUND_CEILING
    ) / Decimal("10")

    assert result.actual_weight == expected_actual, (
        f"实际重量不一致: {result.actual_weight} != {expected_actual}"
    )
    assert result.volumetric_weight == expected_volumetric, (
        f"体积重量不一致: {result.volumetric_weight} != {expected_volumetric}"
    )
    assert result.billing_weight == expected_billing, (
        f"计费重量不一致: {result.billing_weight} != {expected_billing}"
    )

    # 不变量: billing >= actual 且 billing >= volumetric
    assert result.billing_weight >= result.actual_weight, (
        f"计费重量 {result.billing_weight} < 实际重量 {result.actual_weight}"
    )
    assert result.billing_weight >= result.volumetric_weight, (
        f"计费重量 {result.billing_weight} < 体积重量 {result.volumetric_weight}"
    )
