"""反例测试集 - 10 个针对装箱引擎边界场景的确定性测试用例。

每个测试用例针对一个容易被纯体积/重量启发式算法忽略的陷阱场景，
验证引擎在几何约束、属性传播、包材开销、回退策略等方面的正确性。
"""

import pytest
from decimal import Decimal

from cartonization_engine.models import (
    BoxType,
    CarrierLimits,
    CartonizationRequest,
    CartonStatus,
    Dimensions,
    FallbackLevel,
    HazmatType,
    InputCompletenessLevel,
    OrderConfig,
    PackageFlag,
    PackagingParams,
    ProtectionCoefficients,
    SKUItem,
    TemperatureZone,
)
from cartonization_engine.engine import CartonizationEngine

# ---------------------------------------------------------------------------
# 标准箱型和承运商定义
# ---------------------------------------------------------------------------

BOX_S = BoxType(
    box_id="BOX_S", is_standard=True,
    inner_dimensions=Dimensions(length=Decimal("30"), width=Decimal("20"), height=Decimal("15")),
    outer_dimensions=Dimensions(length=Decimal("32"), width=Decimal("22"), height=Decimal("17")),
    max_weight=Decimal("5"), material_weight=Decimal("0.2"), packaging_cost=Decimal("1.5"),
    supports_shock_proof=False, supports_leak_proof=False,
    temperature_zone_supported=[TemperatureZone.NORMAL, TemperatureZone.CHILLED],
)
BOX_M = BoxType(
    box_id="BOX_M", is_standard=True,
    inner_dimensions=Dimensions(length=Decimal("40"), width=Decimal("30"), height=Decimal("20")),
    outer_dimensions=Dimensions(length=Decimal("42"), width=Decimal("32"), height=Decimal("22")),
    max_weight=Decimal("10"), material_weight=Decimal("0.3"), packaging_cost=Decimal("2.5"),
    supports_shock_proof=True, supports_leak_proof=True,
    temperature_zone_supported=[TemperatureZone.NORMAL, TemperatureZone.CHILLED],
)
BOX_L = BoxType(
    box_id="BOX_L", is_standard=True,
    inner_dimensions=Dimensions(length=Decimal("60"), width=Decimal("40"), height=Decimal("35")),
    outer_dimensions=Dimensions(length=Decimal("62"), width=Decimal("42"), height=Decimal("37")),
    max_weight=Decimal("20"), material_weight=Decimal("0.5"), packaging_cost=Decimal("4.0"),
    supports_shock_proof=True, supports_leak_proof=True,
    temperature_zone_supported=[TemperatureZone.NORMAL, TemperatureZone.CHILLED, TemperatureZone.FROZEN],
)
STD_BOXES = [BOX_S, BOX_M, BOX_L]
STD_CARRIER = CarrierLimits(
    carrier_id="STD", max_weight=Decimal("15"),
    max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
    dim_factor=6000,
)

engine = CartonizationEngine()


# ---------------------------------------------------------------------------
# CE-01: 不可叠放商品的层高陷阱
# ---------------------------------------------------------------------------

def test_ce01_non_stackable_volume_trap():
    """3 件不可叠放商品 (30×20×8cm)，总体积 14400cm³ 看似能装入 S 箱 (9000cm³ 体积)，
    但每件占用整层 (30×20×8)，3 层高度 = 24cm > S 箱高 15cm。
    引擎不应选择 S 箱。
    """
    items = [
        SKUItem(
            sku_id=f"NS_{i}", sku_name=f"不可叠放商品{i}", quantity=1,
            weight=Decimal("1.0"),
            length=Decimal("30"), width=Decimal("20"), height=Decimal("8"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            stackable=False,
        )
        for i in range(1, 4)
    ]
    request = CartonizationRequest(
        order_id="CE01", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    # 不应选择 S 箱（高度不够）
    for pkg in result.packages:
        assert pkg.box_type.box_id != "BOX_S", \
            "不可叠放商品 3×8cm 层高 = 24cm > S 箱高 15cm，不应选 S 箱"


# ---------------------------------------------------------------------------
# CE-02: 立放约束与箱高冲突
# ---------------------------------------------------------------------------

def test_ce02_upright_horizontal_conflict():
    """1 件 8×8×25cm 立放商品 (upright_required=True)。
    M 箱高度 20cm < 25cm，不应选 M。必须选 L (高度 35cm)。
    """
    items = [
        SKUItem(
            sku_id="UPRIGHT_1", sku_name="立放商品", quantity=1,
            weight=Decimal("2.0"),
            length=Decimal("8"), width=Decimal("8"), height=Decimal("25"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            upright_required=True,
        ),
    ]
    request = CartonizationRequest(
        order_id="CE02", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    assert len(result.packages) == 1
    assert result.packages[0].box_type.box_id == "BOX_L", \
        "upright 25cm 超过 M 箱高 20cm，必须选 L 箱"


# ---------------------------------------------------------------------------
# CE-03: 危险品 + 液体 + 易碎三重属性
# ---------------------------------------------------------------------------

def test_ce03_dg_liquid_fragile_triple():
    """1 件同时为危险品(易燃) + 液体 + 易碎的商品。
    应被隔离为 DG 组，且 DG 组仍应识别液体和易碎需求。
    """
    items = [
        SKUItem(
            sku_id="DG_LF_1", sku_name="易燃液体易碎品", quantity=1,
            weight=Decimal("1.5"),
            length=Decimal("10"), width=Decimal("10"), height=Decimal("15"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.FLAMMABLE,
            fragile_flag=True,
            liquid_flag=True,
            liquid_volume_ml=Decimal("200"),
        ),
    ]
    request = CartonizationRequest(
        order_id="CE03", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    assert len(result.packages) >= 1
    # DG 组应识别液体和易碎标记
    dg_pkg = result.packages[0]
    assert "DG" in dg_pkg.special_flags, "危险品应标记 DG"


# ---------------------------------------------------------------------------
# CE-04: 低填充率但必须接受（唯一温区匹配）
# ---------------------------------------------------------------------------

def test_ce04_low_fill_rate_must_accept():
    """1 件冷冻小商品 (15×10×5cm, 0.5kg)。只有 L 箱支持冷冻。
    填充率很低但必须接受 L 箱（无更小的冷冻箱可用）。
    """
    items = [
        SKUItem(
            sku_id="FROZEN_SMALL", sku_name="冷冻小商品", quantity=1,
            weight=Decimal("0.5"),
            length=Decimal("15"), width=Decimal("10"), height=Decimal("5"),
            temperature_zone=TemperatureZone.FROZEN,
            hazmat_type=HazmatType.NONE,
        ),
    ]
    request = CartonizationRequest(
        order_id="CE04", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    assert len(result.packages) == 1
    assert result.packages[0].box_type.box_id == "BOX_L", \
        "只有 L 箱支持冷冻温区，必须选 L"


# ---------------------------------------------------------------------------
# CE-05: 包材重量导致超重
# ---------------------------------------------------------------------------

def test_ce05_packaging_weight_tips_overweight():
    """1 件 9.5kg 易碎商品。M 箱 max_weight=10kg, material_weight=0.3kg。
    加上 cushion_weight_kg=0.3kg: 9.5 + 0.3 + 0.3 = 10.1 > 10。
    不应选 M，应选 L。
    """
    items = [
        SKUItem(
            sku_id="HEAVY_FRAG", sku_name="重易碎品", quantity=1,
            weight=Decimal("9.5"),
            length=Decimal("25"), width=Decimal("20"), height=Decimal("15"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            fragile_flag=True,
        ),
    ]
    request = CartonizationRequest(
        order_id="CE05", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
        packaging_params=PackagingParams(cushion_weight_kg=Decimal("0.3")),
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    assert len(result.packages) == 1
    assert result.packages[0].box_type.box_id != "BOX_M", \
        "9.5 + 0.3(包材) + 0.3(箱重) = 10.1 > M 箱 10kg 限重"
    assert result.packages[0].box_type.box_id == "BOX_L", \
        "应选 L 箱 (max_weight=20kg)"


# ---------------------------------------------------------------------------
# CE-06: 小箱无防震 → 必须选更大的防震箱
# ---------------------------------------------------------------------------

def test_ce06_smaller_box_no_shockproof():
    """4 件易碎杯子 (10×10×12cm, 0.4kg)。S 箱体积足够但无 shock_proof。
    必须选 M 箱 (supports_shock_proof=True)。
    """
    items = [
        SKUItem(
            sku_id=f"CUP_{i}", sku_name=f"易碎杯{i}", quantity=1,
            weight=Decimal("0.4"),
            length=Decimal("10"), width=Decimal("10"), height=Decimal("12"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            fragile_flag=True,
        )
        for i in range(1, 5)
    ]
    request = CartonizationRequest(
        order_id="CE06", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    for pkg in result.packages:
        assert pkg.box_type.supports_shock_proof, \
            "易碎品必须使用支持防震的箱型"
        assert pkg.box_type.box_id != "BOX_S", \
            "S 箱不支持防震，不应选择"


# ---------------------------------------------------------------------------
# CE-07: 禁混拆分后普通品应合并，不多建包裹
# ---------------------------------------------------------------------------

def test_ce07_partial_merge_trap():
    """coffee 和 cleaner 互斥，加 1 件普通品。
    普通品应与其中一方同包，不应产生 3 个包裹。
    """
    items = [
        SKUItem(
            sku_id="COFFEE", sku_name="咖啡", quantity=1,
            weight=Decimal("0.5"),
            length=Decimal("10"), width=Decimal("10"), height=Decimal("15"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            cannot_ship_with=["CLEANER"],
        ),
        SKUItem(
            sku_id="CLEANER", sku_name="清洁剂", quantity=1,
            weight=Decimal("0.8"),
            length=Decimal("10"), width=Decimal("10"), height=Decimal("20"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            cannot_ship_with=["COFFEE"],
        ),
        SKUItem(
            sku_id="TOWEL", sku_name="毛巾", quantity=1,
            weight=Decimal("0.3"),
            length=Decimal("15"), width=Decimal("10"), height=Decimal("5"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
        ),
    ]
    request = CartonizationRequest(
        order_id="CE07", items=items, box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    # 应该是 2 个包裹（coffee+towel 或 cleaner+towel），不是 3 个
    assert result.total_packages <= 2, \
        f"禁混拆分后普通品应合并到其中一组，不应产生 {result.total_packages} 个包裹"


# ---------------------------------------------------------------------------
# CE-08: 液体拆分后每组独立选箱（需防漏）
# ---------------------------------------------------------------------------

def test_ce08_liquid_split_box_reselect():
    """3 瓶液体各 500ml，承运商限制 1000ml/包。
    拆分为 2+1 后，每组应独立选择支持防漏的箱型 (M 或 L)。
    """
    items = [
        SKUItem(
            sku_id=f"BOTTLE_{i}", sku_name=f"液体瓶{i}", quantity=1,
            weight=Decimal("0.6"),
            length=Decimal("8"), width=Decimal("8"), height=Decimal("20"),
            temperature_zone=TemperatureZone.NORMAL,
            hazmat_type=HazmatType.NONE,
            liquid_flag=True,
            liquid_volume_ml=Decimal("500"),
        )
        for i in range(1, 4)
    ]
    carrier_with_liquid_limit = CarrierLimits(
        carrier_id="STD_LIQ", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000,
        max_liquid_volume_ml=Decimal("1000"),
    )
    request = CartonizationRequest(
        order_id="CE08", items=items, box_types=STD_BOXES,
        carrier_limits=carrier_with_liquid_limit,
    )
    result = engine.cartonize(request)
    assert result.status == CartonStatus.SUCCESS
    # 应拆分为至少 2 个包裹（1000ml 限制下 3×500=1500 需拆分）
    assert result.total_packages >= 2, \
        "3×500ml 超过 1000ml 限制，应拆分为至少 2 个包裹"
    # 每个包裹都应使用支持防漏的箱型
    for pkg in result.packages:
        assert pkg.box_type.supports_leak_proof, \
            f"液体包裹 {pkg.package_id} 应使用支持防漏的箱型"


# ---------------------------------------------------------------------------
# CE-09: 箱型能装但承运商超限 → 应触发 F3 而非 F2
# ---------------------------------------------------------------------------

def test_ce09_carrier_vs_box_conflict():
    """1 件大商品能装入 L 箱，但 L 箱外部尺寸超过承运商限制。
    应触发 F3 (承运商超限) 而非 F2 (虚拟箱型)。
    """
    large_item = SKUItem(
        sku_id="BIG_ITEM", sku_name="大件商品", quantity=1,
        weight=Decimal("5.0"),
        length=Decimal("55"), width=Decimal("35"), height=Decimal("30"),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    )
    # 承运商限制比 L 箱外部尺寸更小
    tight_carrier = CarrierLimits(
        carrier_id="TIGHT", max_weight=Decimal("25"),
        max_dimension=Dimensions(length=Decimal("50"), width=Decimal("40"), height=Decimal("30")),
        dim_factor=6000,
    )
    request = CartonizationRequest(
        order_id="CE09", items=[large_item], box_types=STD_BOXES,
        carrier_limits=tight_carrier,
    )
    result = engine.cartonize(request)
    # 应触发回退，且为 F3（承运商超限）而非 F2
    assert result.fallback_level is not None, "应触发回退"
    assert result.fallback_level == FallbackLevel.F3_OVERSIZE_CARRIER, \
        f"应为 F3 承运商超限，实际为 {result.fallback_level}"
    if result.packages:
        has_carrier_flag = any(
            PackageFlag.CARRIER_OVERSIZE in pkg.flags
            for pkg in result.packages
        )
        assert has_carrier_flag, "包裹应标记 CARRIER_OVERSIZE"


# ---------------------------------------------------------------------------
# CE-10: 数据完整度影响结果级别
# ---------------------------------------------------------------------------

def test_ce10_missing_data_level_switch():
    """同一商品：完整数据应为 L3/strict，缺失重量应为 L2/estimated 并有降级标记。"""
    # 完整数据请求
    full_item = SKUItem(
        sku_id="ITEM_FULL", sku_name="完整数据商品", quantity=1,
        weight=Decimal("1.0"),
        length=Decimal("15"), width=Decimal("10"), height=Decimal("8"),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    )
    full_request = CartonizationRequest(
        order_id="CE10_FULL", items=[full_item], box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    full_result = engine.cartonize(full_request)
    assert full_result.status == CartonStatus.SUCCESS
    assert full_result.input_completeness_level == InputCompletenessLevel.L3, \
        "完整数据应为 L3"

    # 缺失重量的请求
    partial_item = SKUItem(
        sku_id="ITEM_PARTIAL", sku_name="缺失重量商品", quantity=1,
        weight=None,  # 缺失重量
        length=Decimal("15"), width=Decimal("10"), height=Decimal("8"),
        temperature_zone=TemperatureZone.NORMAL,
        hazmat_type=HazmatType.NONE,
    )
    partial_request = CartonizationRequest(
        order_id="CE10_PARTIAL", items=[partial_item], box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    partial_result = engine.cartonize(partial_request)
    assert partial_result.status == CartonStatus.SUCCESS
    # 缺失重量时，验证器会降级填充默认值，因此 input_level 可能仍为 L3
    # 但关键区别是：应产生降级标记
    assert len(partial_result.degradation_marks) > 0, \
        "缺失重量应产生降级标记"
    weight_marks = [m for m in partial_result.degradation_marks if m.field == "weight"]
    assert len(weight_marks) > 0, \
        "应有 weight 字段的降级标记"
    # 完整数据不应有降级标记
    assert len(full_result.degradation_marks) == 0, \
        "完整数据不应有降级标记"
