"""属性测试 - 流水线引擎 Properties 22-23"""

from decimal import Decimal
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, CarrierLimits,
    OrderConfig, CartonizationRequest, CartonStatus,
    TemperatureZone, HazmatType,
)
from cartonization_engine.engine import CartonizationEngine


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def simple_sku_items(draw, min_size=1, max_size=4):
    """生成简单的 SKU 列表（同温区、无危险品、无禁混）以确保装箱成功。"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=3)),
        weight=draw(_pos_decimal("0.1", "3")),
        length=draw(_pos_decimal("1", "10")),
        width=draw(_pos_decimal("1", "8")),
        height=draw(_pos_decimal("1", "8")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


@composite
def large_box_types(draw, min_size=1, max_size=3):
    """生成足够大的箱型以确保能装下 SKU。"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    boxes = []
    for i in range(n):
        inner = Dimensions(
            length=draw(_pos_decimal("40", "80")),
            width=draw(_pos_decimal("30", "60")),
            height=draw(_pos_decimal("25", "50")),
        )
        outer = Dimensions(
            length=inner.length + Decimal("2"),
            width=inner.width + Decimal("2"),
            height=inner.height + Decimal("2"),
        )
        boxes.append(BoxType(
            box_id=f"BOX{i:03d}",
            inner_dimensions=inner, outer_dimensions=outer,
            max_weight=draw(_pos_decimal("30", "100")),
            material_weight=draw(_pos_decimal("0.1", "2")),
            packaging_cost=draw(_pos_decimal("0.5", "10")),
            supports_shock_proof=True,
            supports_leak_proof=True,
        ))
    return boxes


@composite
def large_carrier_gen(draw):
    return CarrierLimits(
        carrier_id="CARRIER001",
        max_weight=draw(_pos_decimal("50", "200")),
        max_dimension=Dimensions(
            length=draw(_pos_decimal("100", "300")),
            width=draw(_pos_decimal("80", "200")),
            height=draw(_pos_decimal("60", "150")),
        ),
        dim_factor=draw(st.sampled_from([5000, 6000])),
    )


@composite
def cartonization_request_gen(draw):
    items = draw(simple_sku_items())
    boxes = draw(large_box_types())
    carrier = draw(large_carrier_gen())
    return CartonizationRequest(
        order_id=f"ORD{draw(st.integers(min_value=1, max_value=9999)):04d}",
        items=items,
        box_types=boxes,
        carrier_limits=carrier,
        order_config=OrderConfig(max_package_count=10),
    )


# ---------------------------------------------------------------------------
# Property 22: SKU 数量守恒
# Feature: cartonization-engine, Property 22: SKU 数量守恒
# **Validates: Requirements 9.3**
# ---------------------------------------------------------------------------

@given(request=cartonization_request_gen())
@settings(max_examples=100)
def test_property_22_sku_quantity_conservation(request):
    """Property 22: 成功结果中所有包裹的 SKU 数量之和等于输入。"""
    engine = CartonizationEngine()
    result = engine.cartonize(request)

    if result.status != CartonStatus.SUCCESS:
        return  # 只验证成功的结果

    # 统计输入 SKU 数量
    input_qty: dict[str, int] = {}
    for item in request.items:
        input_qty[item.sku_id] = input_qty.get(item.sku_id, 0) + item.quantity

    # 统计输出 SKU 数量
    output_qty: dict[str, int] = {}
    for pkg in result.packages:
        for pi in pkg.items:
            output_qty[pi.sku_id] = output_qty.get(pi.sku_id, 0) + pi.quantity

    assert input_qty == output_qty, (
        f"SKU 数量不守恒:\n  输入: {input_qty}\n  输出: {output_qty}"
    )


# ---------------------------------------------------------------------------
# Property 23: 输出完整性
# Feature: cartonization-engine, Property 23: 输出完整性
# **Validates: Requirements 9.1, 9.2, 9.4**
# ---------------------------------------------------------------------------

@given(request=cartonization_request_gen())
@settings(max_examples=100)
def test_property_23_output_completeness(request):
    """Property 23: 成功结果中每个包裹包含非空 SKU、有效箱型、计费重量、决策日志。"""
    engine = CartonizationEngine()
    result = engine.cartonize(request)

    if result.status != CartonStatus.SUCCESS:
        return

    # total_packages 等于包裹列表长度
    assert result.total_packages == len(result.packages), (
        f"total_packages {result.total_packages} != len(packages) {len(result.packages)}"
    )

    for pkg in result.packages:
        # 非空 SKU 列表
        assert len(pkg.items) > 0, f"包裹 {pkg.package_id} 的 SKU 列表为空"

        # 有效箱型
        assert pkg.box_type is not None
        assert pkg.box_type.box_id

        # 计费重量
        assert pkg.billing_weight is not None
        assert pkg.billing_weight.billing_weight >= Decimal("0")

        # 决策日志
        assert pkg.decision_log is not None
        assert pkg.decision_log.group_reason
        assert pkg.decision_log.box_selection_reason
