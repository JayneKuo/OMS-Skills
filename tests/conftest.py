"""Shared fixtures for cartonization engine tests."""

import pytest
from decimal import Decimal

from cartonization_engine.models import (
    Dimensions,
    SKUItem,
    BoxType,
    CarrierLimits,
    OrderConfig,
    TemperatureZone,
    HazmatType,
)


@pytest.fixture
def sample_dimensions():
    return Dimensions(length=Decimal("30"), width=Decimal("20"), height=Decimal("15"))


@pytest.fixture
def sample_sku():
    return SKUItem(
        sku_id="SKU001",
        sku_name="测试商品",
        quantity=1,
        weight=Decimal("1.5"),
        length=Decimal("20"),
        width=Decimal("15"),
        height=Decimal("10"),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    )


@pytest.fixture
def sample_box_type():
    return BoxType(
        box_id="BOX001",
        inner_dimensions=Dimensions(
            length=Decimal("40"), width=Decimal("30"), height=Decimal("25")
        ),
        outer_dimensions=Dimensions(
            length=Decimal("42"), width=Decimal("32"), height=Decimal("27")
        ),
        max_weight=Decimal("20"),
        material_weight=Decimal("0.5"),
        packaging_cost=Decimal("3.0"),
    )


@pytest.fixture
def sample_carrier_limits():
    return CarrierLimits(
        carrier_id="CARRIER001",
        max_weight=Decimal("30"),
        max_dimension=Dimensions(
            length=Decimal("100"), width=Decimal("80"), height=Decimal("60")
        ),
        dim_factor=6000,
    )
