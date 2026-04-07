"""属性测试 - 多包拆分器 Properties 13-14"""

from decimal import Decimal
from hypothesis import given, settings, assume, strategies as st
from hypothesis.strategies import composite

from cartonization_engine.models import (
    SKUItem, TemperatureZone, HazmatType,
)
from cartonization_engine.splitter import PackageSplitter


def _pos_decimal(min_val="0.1", max_val="200"):
    return st.decimals(min_value=Decimal(min_val), max_value=Decimal(max_val),
                       places=1, allow_nan=False, allow_infinity=False)


@composite
def sku_items_for_split(draw, min_size=2, max_size=8):
    """生成适合拆分测试的 SKU（单件不超过限制）"""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [SKUItem(
        sku_id=f"SKU{i:03d}", sku_name=f"商品{i}",
        quantity=draw(st.integers(min_value=1, max_value=3)),
        weight=draw(_pos_decimal("0.1", "5")),
        length=draw(_pos_decimal("1", "15")),
        width=draw(_pos_decimal("1", "10")),
        height=draw(_pos_decimal("1", "10")),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    ) for i in range(n)]


# Feature: cartonization-engine, Property 13: 拆分后单包不超限
# **Validates: Requirements 5.1, 5.2**
@given(items=sku_items_for_split())
@settings(max_examples=100)
def test_property_13_split_single_package_limit(items):
    """Property 13: 拆分后每包重量和体积不超限。"""
    max_weight = Decimal("15")
    max_volume = Decimal("5000")
    max_packages = 10  # 宽松限制以确保成功

    splitter = PackageSplitter()
    result = splitter.split(items, max_weight, max_volume, max_packages)

    if not result.success:
        return  # 包裹数超限时跳过

    for b in result.bins:
        assert b.total_weight <= max_weight, (
            f"单包超重: {b.total_weight} > {max_weight}"
        )
        assert b.total_volume <= max_volume, (
            f"单包超体积: {b.total_volume} > {max_volume}"
        )


# Feature: cartonization-engine, Property 14: 拆分后包裹数不超限
# **Validates: Requirements 5.4**
@given(
    items=sku_items_for_split(),
    max_pkg=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_property_14_split_package_count_limit(items, max_pkg):
    """Property 14: 成功状态下包裹数不超过 max_package_count。"""
    max_weight = Decimal("15")
    max_volume = Decimal("5000")

    splitter = PackageSplitter()
    result = splitter.split(items, max_weight, max_volume, max_pkg)

    if result.success:
        assert len(result.bins) <= max_pkg, (
            f"包裹数超限: {len(result.bins)} > {max_pkg}"
        )
