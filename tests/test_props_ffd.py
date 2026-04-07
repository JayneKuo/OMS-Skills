"""属性测试 - FFD 排序器与装箱器 Properties 8-9"""

from decimal import Decimal
from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, BoxType, Dimensions, TemperatureZone, HazmatType,
)
from cartonization_engine.sorter import FFDSorter
from cartonization_engine.packer import FFDPacker


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def sku_items_for_sort(draw, min_size=2, max_size=10):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=5)),
        weight=draw(_pos_decimal("0.1", "30")),
        length=draw(_pos_decimal("1", "80")),
        width=draw(_pos_decimal("1", "60")),
        height=draw(_pos_decimal("1", "60")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


@composite
def sku_items_for_pack(draw, min_size=1, max_size=6):
    """生成适合装箱的 SKU（尺寸较小以确保能装入箱型）"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=3)),
        weight=draw(_pos_decimal("0.1", "5")),
        length=draw(_pos_decimal("1", "20")),
        width=draw(_pos_decimal("1", "15")),
        height=draw(_pos_decimal("1", "15")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


@composite
def large_box_type(draw):
    """生成足够大的箱型"""
    inner = Dimensions(
        length=draw(_pos_decimal("40", "100")),
        width=draw(_pos_decimal("30", "80")),
        height=draw(_pos_decimal("25", "60")),
    )
    outer = Dimensions(
        length=inner.length + Decimal("2"),
        width=inner.width + Decimal("2"),
        height=inner.height + Decimal("2"),
    )
    return BoxType(
        box_id="BOX_LARGE",
        inner_dimensions=inner,
        outer_dimensions=outer,
        max_weight=draw(_pos_decimal("20", "100")),
        material_weight=Decimal("0.5"),
        packaging_cost=Decimal("3.0"),
    )


# Feature: cartonization-engine, Property 8: FFD 排序正确性
# **Validates: Requirements 3.1, 3.2**
@given(items=sku_items_for_sort())
@settings(max_examples=100)
def test_property_8_ffd_sort_correctness(items):
    """Property 8: 排序后体积从大到小，体积相同时重量从大到小。"""
    sorter = FFDSorter()
    sorted_items = sorter.sort(items)

    for i in range(len(sorted_items) - 1):
        a, b = sorted_items[i], sorted_items[i + 1]
        vol_a = a.length * a.width * a.height
        vol_b = b.length * b.width * b.height
        wt_a = a.weight or Decimal(0)
        wt_b = b.weight or Decimal(0)
        assert vol_a > vol_b or (vol_a == vol_b and wt_a >= wt_b), (
            f"排序错误: SKU[{i}] vol={vol_a} wt={wt_a}, SKU[{i+1}] vol={vol_b} wt={wt_b}"
        )


# Feature: cartonization-engine, Property 9: 装箱容量不变量
# **Validates: Requirements 3.4, 7.3**
@given(items=sku_items_for_pack(), box=large_box_type())
@settings(max_examples=100)
def test_property_9_packing_capacity_invariant(items, box):
    """Property 9: 每个包裹内 SKU 总体积不超过箱型内部体积，总重量不超过最大承重。"""
    packer = FFDPacker()
    result = packer.pack(items, box)

    box_volume = box.inner_dimensions.volume
    box_max_weight = box.max_weight

    for b in result.bins:
        assert b.used_volume <= box_volume, (
            f"体积超限: used={b.used_volume}, max={box_volume}"
        )
        assert b.used_weight <= box_max_weight, (
            f"重量超限: used={b.used_weight}, max={box_max_weight}"
        )
