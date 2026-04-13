#!/usr/bin/env python3
"""批量装箱测试用例 - 从自然语言描述生成并执行"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cartonization_engine.models import *
from cartonization_engine.engine import CartonizationEngine

engine = CartonizationEngine()

# ── 公共箱型定义 ──
BOX_S = BoxType(
    box_id="BOX_S", is_standard=True,
    inner_dimensions=Dimensions(length=Decimal("30"), width=Decimal("20"), height=Decimal("15")),
    outer_dimensions=Dimensions(length=Decimal("32"), width=Decimal("22"), height=Decimal("17")),
    max_weight=Decimal("5"), material_weight=Decimal("0.2"),
    packaging_cost=Decimal("1.5"),
    supports_shock_proof=False, supports_leak_proof=False,
    temperature_zone_supported=[TemperatureZone.NORMAL, TemperatureZone.CHILLED],
)
BOX_M = BoxType(
    box_id="BOX_M", is_standard=True,
    inner_dimensions=Dimensions(length=Decimal("40"), width=Decimal("30"), height=Decimal("20")),
    outer_dimensions=Dimensions(length=Decimal("42"), width=Decimal("32"), height=Decimal("22")),
    max_weight=Decimal("10"), material_weight=Decimal("0.3"),
    packaging_cost=Decimal("2.5"),
    supports_shock_proof=True, supports_leak_proof=True,
    temperature_zone_supported=[TemperatureZone.NORMAL, TemperatureZone.CHILLED],
)
BOX_L = BoxType(
    box_id="BOX_L", is_standard=True,
    inner_dimensions=Dimensions(length=Decimal("60"), width=Decimal("40"), height=Decimal("35")),
    outer_dimensions=Dimensions(length=Decimal("62"), width=Decimal("42"), height=Decimal("37")),
    max_weight=Decimal("20"), material_weight=Decimal("0.5"),
    packaging_cost=Decimal("4.0"),
    supports_shock_proof=True, supports_leak_proof=True,
    temperature_zone_supported=[TemperatureZone.NORMAL, TemperatureZone.CHILLED, TemperatureZone.FROZEN],
)
STD_BOXES = [BOX_S, BOX_M, BOX_L]

STD_CARRIER = CarrierLimits(
    carrier_id="STD", max_weight=Decimal("15"),
    max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
    dim_factor=6000,
)

def fmt(result: CartonizationResult, title: str) -> str:
    """格式化输出装箱结果。"""
    lines = [f"\n{'='*60}", f"【{title}】", f"{'='*60}"]
    lines.append(f"状态: {result.status.value}")
    if result.error_message:
        lines.append(f"错误: {result.error_code} - {result.error_message}")
        if result.failed_skus:
            lines.append(f"失败SKU: {result.failed_skus}")
        return "\n".join(lines)

    lines.append(f"输入完整度: {result.input_completeness_level.value if result.input_completeness_level else 'N/A'}")
    lines.append(f"包裹数: {result.total_packages}")
    lines.append(f"总实际重量: {result.total_actual_weight}kg")
    lines.append(f"总计费重量: {result.total_billing_weight}kg")
    if result.fallback_level:
        lines.append(f"回退级别: {result.fallback_level.value}")
    if result.degradation_marks:
        lines.append(f"数据降级: {len(result.degradation_marks)} 项")
        for dm in result.degradation_marks:
            lines.append(f"  - {dm.sku_id}.{dm.field}: {dm.reason}")
    if result.violations:
        lines.append(f"规则违反: {len(result.violations)} 项")
        for v in result.violations:
            lines.append(f"  - {v.rule_name}: {v.description}")

    for pkg in result.packages:
        lines.append(f"\n  📦 {pkg.package_id}")
        lines.append(f"     箱型: {pkg.box_type.box_id} ({pkg.box_type.inner_dimensions.length}×{pkg.box_type.inner_dimensions.width}×{pkg.box_type.inner_dimensions.height})")
        lines.append(f"     商品: {', '.join(f'{i.sku_name}×{i.quantity}' for i in pkg.items)}")
        lines.append(f"     实际重: {pkg.billing_weight.actual_weight}kg | 体积重: {pkg.billing_weight.volumetric_weight}kg | 计费重: {pkg.billing_weight.billing_weight}kg")
        lines.append(f"     填充率: {pkg.fill_rate}%")
        lines.append(f"     分组原因: {pkg.decision_log.group_reason}")
        lines.append(f"     选箱原因: {pkg.decision_log.box_selection_reason}")
        if pkg.selection_reason:
            lines.append(f"     详细原因: {'; '.join(pkg.selection_reason)}")
        if pkg.special_flags:
            lines.append(f"     特殊标记: {', '.join(pkg.special_flags)}")
        if pkg.flags:
            lines.append(f"     包裹标记: {', '.join(f.value for f in pkg.flags)}")

    return "\n".join(lines)

# ══════════════════════════════════════════════════════════
# 用例 1: 2件T恤，常温普通商品
# ══════════════════════════════════════════════════════════
def case1():
    req = CartonizationRequest(
        order_id="CASE-001",
        items=[SKUItem(
            sku_id="TSHIRT-001", sku_name="T恤", quantity=2,
            weight=Decimal("0.3"), length=Decimal("25"), width=Decimal("20"), height=Decimal("2"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            stackable=True, compressible=True,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例1: 2件T恤常温普通商品")

# ══════════════════════════════════════════════════════════
# 用例 2: 4个充电宝(危险品) + 2件T恤(普通)
# ══════════════════════════════════════════════════════════
def case2():
    req = CartonizationRequest(
        order_id="CASE-002",
        items=[
            SKUItem(
                sku_id="POWERBANK-001", sku_name="充电宝", quantity=4,
                weight=Decimal("0.32"), length=Decimal("14"), width=Decimal("7"), height=Decimal("2"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.FLAMMABLE,
            ),
            SKUItem(
                sku_id="TSHIRT-001", sku_name="T恤", quantity=2,
                weight=Decimal("0.3"), length=Decimal("25"), width=Decimal("20"), height=Decimal("2"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                stackable=True, compressible=True,
            ),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例2: 4充电宝(危险品)+2T恤")

# ══════════════════════════════════════════════════════════
# 用例 3: 1件冷藏饮料 + 3包常温零食
# ══════════════════════════════════════════════════════════
def case3():
    req = CartonizationRequest(
        order_id="CASE-003",
        items=[
            SKUItem(
                sku_id="DRINK-001", sku_name="冷藏饮料", quantity=1,
                weight=Decimal("1.2"), length=Decimal("20"), width=Decimal("10"), height=Decimal("10"),
                temperature_zone=TemperatureZone.CHILLED, hazmat_type=HazmatType.NONE,
            ),
            SKUItem(
                sku_id="SNACK-001", sku_name="常温零食", quantity=3,
                weight=Decimal("0.2"), length=Decimal("15"), width=Decimal("10"), height=Decimal("5"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            ),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例3: 冷藏饮料+常温零食(温区隔离)")

# ══════════════════════════════════════════════════════════
# 用例 4: 6个陶瓷杯(易碎) + 1个机器配件(3.1kg重物)
# ══════════════════════════════════════════════════════════
def case4():
    req = CartonizationRequest(
        order_id="CASE-004",
        items=[
            SKUItem(
                sku_id="CUP-001", sku_name="陶瓷杯", quantity=6,
                weight=Decimal("0.4"), length=Decimal("10"), width=Decimal("10"), height=Decimal("12"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                fragile_flag=True,
            ),
            SKUItem(
                sku_id="PART-001", sku_name="机器配件", quantity=1,
                weight=Decimal("3.1"), length=Decimal("30"), width=Decimal("20"), height=Decimal("10"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            ),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例4: 6陶瓷杯(易碎)+1重物配件(3.1kg)")

# ══════════════════════════════════════════════════════════
# 用例 5: 4个陶瓷杯(易碎) + 1个普通配件(2.9kg)
# ══════════════════════════════════════════════════════════
def case5():
    req = CartonizationRequest(
        order_id="CASE-005",
        items=[
            SKUItem(
                sku_id="CUP-001", sku_name="陶瓷杯", quantity=4,
                weight=Decimal("0.4"), length=Decimal("10"), width=Decimal("10"), height=Decimal("12"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                fragile_flag=True,
            ),
            SKUItem(
                sku_id="PART-002", sku_name="普通配件", quantity=1,
                weight=Decimal("2.9"), length=Decimal("25"), width=Decimal("18"), height=Decimal("8"),
                temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            ),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例5: 4陶瓷杯(易碎)+1配件(2.9kg)")

# ══════════════════════════════════════════════════════════
# 用例 6: 2瓶洗发水(液体500ml) 承运商限1000ml
# ══════════════════════════════════════════════════════════
def case6():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
    )
    req = CartonizationRequest(
        order_id="CASE-006",
        items=[SKUItem(
            sku_id="SHAMPOO-001", sku_name="洗发水", quantity=2,
            weight=Decimal("0.55"), length=Decimal("7"), width=Decimal("7"), height=Decimal("20"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            liquid_flag=True, liquid_volume_ml=Decimal("500"),
        )],
        box_types=STD_BOXES,
        carrier_limits=carrier,
    )
    return fmt(engine.cartonize(req), "用例6: 2瓶洗发水(液体,1000ml内)")

# ══════════════════════════════════════════════════════════
# 用例 7: 3瓶洗发水(液体1500ml) 承运商限1000ml → 需拆包
# ══════════════════════════════════════════════════════════
def case7():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
    )
    req = CartonizationRequest(
        order_id="CASE-007",
        items=[SKUItem(
            sku_id="SHAMPOO-001", sku_name="洗发水", quantity=3,
            weight=Decimal("0.55"), length=Decimal("7"), width=Decimal("7"), height=Decimal("20"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            liquid_flag=True, liquid_volume_ml=Decimal("500"),
        )],
        box_types=STD_BOXES,
        carrier_limits=carrier,
    )
    return fmt(engine.cartonize(req), "用例7: 3瓶洗发水(液体1500ml,超限)")

# ══════════════════════════════════════════════════════════
# 用例 8: 8件同商品(每件2.5kg) 承运商限15kg → 需拆包
# ══════════════════════════════════════════════════════════
def case8():
    req = CartonizationRequest(
        order_id="CASE-008",
        items=[SKUItem(
            sku_id="ITEM-001", sku_name="普通商品", quantity=8,
            weight=Decimal("2.5"), length=Decimal("20"), width=Decimal("20"), height=Decimal("10"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例8: 8件×2.5kg(超重拆包)")

# ══════════════════════════════════════════════════════════
# 用例 9: 2台台灯(易碎,不可叠放)
# ══════════════════════════════════════════════════════════
def case9():
    req = CartonizationRequest(
        order_id="CASE-009",
        items=[SKUItem(
            sku_id="LAMP-001", sku_name="台灯", quantity=2,
            weight=Decimal("0.95"), length=Decimal("36"), width=Decimal("15"), height=Decimal("8"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            fragile_flag=True, stackable=False,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例9: 2台台灯(易碎,不可叠放)")

# ══════════════════════════════════════════════════════════
# 用例 10: 大混合订单(12T恤+6杯子+4充电宝+8洗发水+2台灯)
# ══════════════════════════════════════════════════════════
def case10():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
    )
    req = CartonizationRequest(
        order_id="CASE-010",
        items=[
            SKUItem(sku_id="TSHIRT-001", sku_name="T恤", quantity=12,
                    weight=Decimal("0.3"), length=Decimal("25"), width=Decimal("20"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    stackable=True, compressible=True),
            SKUItem(sku_id="CUP-001", sku_name="杯子", quantity=6,
                    weight=Decimal("0.4"), length=Decimal("10"), width=Decimal("10"), height=Decimal("12"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    fragile_flag=True),
            SKUItem(sku_id="POWERBANK-001", sku_name="充电宝", quantity=4,
                    weight=Decimal("0.32"), length=Decimal("14"), width=Decimal("7"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.FLAMMABLE),
            SKUItem(sku_id="SHAMPOO-001", sku_name="洗发水", quantity=8,
                    weight=Decimal("0.55"), length=Decimal("7"), width=Decimal("7"), height=Decimal("20"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    liquid_flag=True, liquid_volume_ml=Decimal("500")),
            SKUItem(sku_id="LAMP-001", sku_name="台灯", quantity=2,
                    weight=Decimal("0.95"), length=Decimal("36"), width=Decimal("15"), height=Decimal("8"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    fragile_flag=True, stackable=False),
        ],
        box_types=STD_BOXES,
        carrier_limits=carrier,
        order_config=OrderConfig(max_package_count=10),
    )
    return fmt(engine.cartonize(req), "用例10: 大混合订单(T恤+杯子+充电宝+洗发水+台灯)")

# ══════════════════════════════════════════════════════════
# 用例 11: 4杯子+2洗发水 缺重量数据 → 数据降级
# ══════════════════════════════════════════════════════════
def case11():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
    )
    req = CartonizationRequest(
        order_id="CASE-011",
        items=[
            SKUItem(sku_id="CUP-001", sku_name="杯子", quantity=4,
                    length=Decimal("10"), width=Decimal("10"), height=Decimal("12"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    fragile_flag=True),
            SKUItem(sku_id="SHAMPOO-001", sku_name="洗发水", quantity=2,
                    length=Decimal("7"), width=Decimal("7"), height=Decimal("20"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    liquid_flag=True, liquid_volume_ml=Decimal("500")),
        ],
        box_types=STD_BOXES,
        carrier_limits=carrier,
    )
    return fmt(engine.cartonize(req), "用例11: 4杯子+2洗发水(缺重量,数据降级)")

# ══════════════════════════════════════════════════════════
# 用例 12: 1个充电宝(危险品) 单独包装
# ══════════════════════════════════════════════════════════
def case12():
    req = CartonizationRequest(
        order_id="CASE-012",
        items=[SKUItem(
            sku_id="POWERBANK-001", sku_name="充电宝", quantity=1,
            weight=Decimal("0.32"), length=Decimal("14"), width=Decimal("7"), height=Decimal("2"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.FLAMMABLE,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例12: 1充电宝(危险品单独包装)")

# ══════════════════════════════════════════════════════════
# 用例 13: 2包咖啡豆(食品) + 1瓶清洁剂(化学品) 禁混
# ══════════════════════════════════════════════════════════
def case13():
    req = CartonizationRequest(
        order_id="CASE-013",
        items=[
            SKUItem(sku_id="COFFEE-001", sku_name="咖啡豆", quantity=2,
                    weight=Decimal("0.5"), length=Decimal("20"), width=Decimal("12"), height=Decimal("8"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    cannot_ship_with=["CLEANER-001"]),
            SKUItem(sku_id="CLEANER-001", sku_name="清洁剂", quantity=1,
                    weight=Decimal("0.8"), length=Decimal("20"), width=Decimal("8"), height=Decimal("8"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    cannot_ship_with=["COFFEE-001"]),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例13: 咖啡豆+清洁剂(禁混)")

# ══════════════════════════════════════════════════════════
# 用例 14: 2瓶洗发水(液体) + 2个充电宝(危险品) 不能混装
# ══════════════════════════════════════════════════════════
def case14():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
    )
    req = CartonizationRequest(
        order_id="CASE-014",
        items=[
            SKUItem(sku_id="SHAMPOO-001", sku_name="洗发水", quantity=2,
                    weight=Decimal("0.55"), length=Decimal("7"), width=Decimal("7"), height=Decimal("20"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    liquid_flag=True, liquid_volume_ml=Decimal("500")),
            SKUItem(sku_id="POWERBANK-001", sku_name="充电宝", quantity=2,
                    weight=Decimal("0.32"), length=Decimal("14"), width=Decimal("7"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.FLAMMABLE),
        ],
        box_types=STD_BOXES,
        carrier_limits=carrier,
    )
    return fmt(engine.cartonize(req), "用例14: 洗发水(液体)+充电宝(危险品)")

# ══════════════════════════════════════════════════════════
# 用例 15: 1件超长灯管(120cm) S/M/L最长60cm → 装不下
# ══════════════════════════════════════════════════════════
def case15():
    req = CartonizationRequest(
        order_id="CASE-015",
        items=[SKUItem(
            sku_id="TUBE-001", sku_name="灯管", quantity=1,
            weight=Decimal("2"), length=Decimal("120"), width=Decimal("10"), height=Decimal("10"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例15: 超长灯管120cm(所有箱型装不下)")

# ══════════════════════════════════════════════════════════
# 用例 16: 1件大件 外箱110cm 承运商限100cm → 承运商超限
# ══════════════════════════════════════════════════════════
def case16():
    big_box = BoxType(
        box_id="BOX_XL", is_standard=True,
        inner_dimensions=Dimensions(length=Decimal("108"), width=Decimal("50"), height=Decimal("40")),
        outer_dimensions=Dimensions(length=Decimal("110"), width=Decimal("52"), height=Decimal("42")),
        max_weight=Decimal("30"), material_weight=Decimal("1"),
        packaging_cost=Decimal("8"),
        supports_shock_proof=True, supports_leak_proof=True,
    )
    carrier_small = CarrierLimits(
        carrier_id="SMALL", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000,
    )
    req = CartonizationRequest(
        order_id="CASE-016",
        items=[SKUItem(
            sku_id="BIGITEM-001", sku_name="大件商品", quantity=1,
            weight=Decimal("8"), length=Decimal("100"), width=Decimal("40"), height=Decimal("30"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES + [big_box],
        carrier_limits=carrier_small,
    )
    return fmt(engine.cartonize(req), "用例16: 大件商品(承运商尺寸超限)")

# ══════════════════════════════════════════════════════════
# 用例 17: 2件T恤 S箱无库存 → 跳过S选M
# ══════════════════════════════════════════════════════════
def case17():
    box_s_no_stock = BOX_S.model_copy(update={"available_qty": 0})
    box_m_stock = BOX_M.model_copy(update={"available_qty": 50})
    box_l_stock = BOX_L.model_copy(update={"available_qty": 20})
    req = CartonizationRequest(
        order_id="CASE-017",
        items=[SKUItem(
            sku_id="TSHIRT-001", sku_name="T恤", quantity=2,
            weight=Decimal("0.3"), length=Decimal("25"), width=Decimal("20"), height=Decimal("2"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=[box_s_no_stock, box_m_stock, box_l_stock],
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例17: 2T恤(S箱无库存→选M)")

# ══════════════════════════════════════════════════════════
# 用例 18: 2件冷冻食品 S/M只支持常温冷藏 L支持冷冻
# ══════════════════════════════════════════════════════════
def case18():
    req = CartonizationRequest(
        order_id="CASE-018",
        items=[SKUItem(
            sku_id="FROZEN-001", sku_name="冷冻食品", quantity=2,
            weight=Decimal("1.5"), length=Decimal("20"), width=Decimal("15"), height=Decimal("8"),
            temperature_zone=TemperatureZone.FROZEN, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例18: 2冷冻食品(只有L箱支持冷冻)")

# ══════════════════════════════════════════════════════════
# 用例 19: 6个陶瓷杯(易碎) S不支持防震 M/L支持
# ══════════════════════════════════════════════════════════
def case19():
    req = CartonizationRequest(
        order_id="CASE-019",
        items=[SKUItem(
            sku_id="CUP-001", sku_name="陶瓷杯", quantity=6,
            weight=Decimal("0.4"), length=Decimal("10"), width=Decimal("10"), height=Decimal("12"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            fragile_flag=True,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例19: 6陶瓷杯(易碎,S不防震→选M/L)")

# ══════════════════════════════════════════════════════════
# 用例 20: 2瓶洗发水(液体) S不支持防漏 M/L支持
# ══════════════════════════════════════════════════════════
def case20():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
    )
    req = CartonizationRequest(
        order_id="CASE-020",
        items=[SKUItem(
            sku_id="SHAMPOO-001", sku_name="洗发水", quantity=2,
            weight=Decimal("0.55"), length=Decimal("7"), width=Decimal("7"), height=Decimal("20"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            liquid_flag=True, liquid_volume_ml=Decimal("500"),
        )],
        box_types=STD_BOXES,
        carrier_limits=carrier,
    )
    return fmt(engine.cartonize(req), "用例20: 2洗发水(液体,S不防漏→选M)")

# ══════════════════════════════════════════════════════════
# 用例 21: 1件9.7kg商品 M箱自重0.3kg 总重正好10kg
# ══════════════════════════════════════════════════════════
def case21():
    req = CartonizationRequest(
        order_id="CASE-021",
        items=[SKUItem(
            sku_id="HEAVY-001", sku_name="重物", quantity=1,
            weight=Decimal("9.7"), length=Decimal("35"), width=Decimal("25"), height=Decimal("15"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例21: 9.7kg商品+M箱0.3kg=10kg(刚好不超)")

# ══════════════════════════════════════════════════════════
# 用例 22: 1件9.8kg商品 M箱自重0.3kg 总重10.1kg → 超M箱限重
# ══════════════════════════════════════════════════════════
def case22():
    req = CartonizationRequest(
        order_id="CASE-022",
        items=[SKUItem(
            sku_id="HEAVY-002", sku_name="重物", quantity=1,
            weight=Decimal("9.8"), length=Decimal("35"), width=Decimal("25"), height=Decimal("15"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例22: 9.8kg商品(M箱超重→选L)")

# ══════════════════════════════════════════════════════════
# 用例 23: 1个抱枕(轻但大) 60×40×35 1kg → 体积重大于实际重
# ══════════════════════════════════════════════════════════
def case23():
    req = CartonizationRequest(
        order_id="CASE-023",
        items=[SKUItem(
            sku_id="PILLOW-001", sku_name="抱枕", quantity=1,
            weight=Decimal("1"), length=Decimal("60"), width=Decimal("40"), height=Decimal("35"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=CarrierLimits(
            carrier_id="STD", max_weight=Decimal("15"),
            max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
            dim_factor=6000,
        ),
    )
    return fmt(engine.cartonize(req), "用例23: 抱枕(轻但大,体积重>实际重)")

# ══════════════════════════════════════════════════════════
# 用例 24: 1块金属配件(重但小) 10×10×10 6kg → 实际重>体积重
# ══════════════════════════════════════════════════════════
def case24():
    req = CartonizationRequest(
        order_id="CASE-024",
        items=[SKUItem(
            sku_id="METAL-001", sku_name="金属配件", quantity=1,
            weight=Decimal("6"), length=Decimal("10"), width=Decimal("10"), height=Decimal("10"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
        )],
        box_types=STD_BOXES,
        carrier_limits=CarrierLimits(
            carrier_id="STD", max_weight=Decimal("15"),
            max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
            dim_factor=6000,
        ),
    )
    return fmt(engine.cartonize(req), "用例24: 金属配件(重但小,实际重>体积重)")

# ══════════════════════════════════════════════════════════
# 用例 25: 2T恤+2短裤 尽量少拆包
# ══════════════════════════════════════════════════════════
def case25():
    req = CartonizationRequest(
        order_id="CASE-025",
        items=[
            SKUItem(sku_id="TSHIRT-001", sku_name="T恤", quantity=2,
                    weight=Decimal("0.3"), length=Decimal("25"), width=Decimal("20"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    stackable=True, compressible=True),
            SKUItem(sku_id="SHORTS-001", sku_name="短裤", quantity=2,
                    weight=Decimal("0.25"), length=Decimal("20"), width=Decimal("18"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    stackable=True),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例25: 2T恤+2短裤(尽量少拆包)")

# ══════════════════════════════════════════════════════════
# 用例 26: 2瓶玻璃饮料(必须立放) M箱高20不够 L箱高35够
# ══════════════════════════════════════════════════════════
def case26():
    req = CartonizationRequest(
        order_id="CASE-026",
        items=[SKUItem(
            sku_id="GLASS-001", sku_name="玻璃饮料", quantity=2,
            weight=Decimal("1"), length=Decimal("8"), width=Decimal("8"), height=Decimal("25"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            upright_required=True, liquid_flag=True, liquid_volume_ml=Decimal("330"),
        )],
        box_types=STD_BOXES,
        carrier_limits=CarrierLimits(
            carrier_id="STD", max_weight=Decimal("15"),
            max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
            dim_factor=6000, max_liquid_volume_ml=Decimal("1000"),
        ),
    )
    return fmt(engine.cartonize(req), "用例26: 2玻璃饮料(必须立放,M箱高度不够)")

# ══════════════════════════════════════════════════════════
# 用例 27: 2个礼盒蛋糕(不可叠放) 30×20×10 S箱高15不够
# ══════════════════════════════════════════════════════════
def case27():
    req = CartonizationRequest(
        order_id="CASE-027",
        items=[SKUItem(
            sku_id="CAKE-001", sku_name="礼盒蛋糕", quantity=2,
            weight=Decimal("1"), length=Decimal("30"), width=Decimal("20"), height=Decimal("10"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
            stackable=False,
        )],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例27: 2礼盒蛋糕(不可叠放)")

# ══════════════════════════════════════════════════════════
# 用例 28: 4充电宝(危险品)+2T恤 输出总重/选箱原因/特殊标记
# ══════════════════════════════════════════════════════════
def case28():
    req = CartonizationRequest(
        order_id="CASE-028",
        items=[
            SKUItem(sku_id="POWERBANK-001", sku_name="充电宝", quantity=4,
                    weight=Decimal("0.32"), length=Decimal("14"), width=Decimal("7"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.FLAMMABLE),
            SKUItem(sku_id="TSHIRT-001", sku_name="T恤", quantity=2,
                    weight=Decimal("0.3"), length=Decimal("25"), width=Decimal("20"), height=Decimal("2"),
                    temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.NONE,
                    stackable=True, compressible=True),
        ],
        box_types=STD_BOXES,
        carrier_limits=STD_CARRIER,
    )
    return fmt(engine.cartonize(req), "用例28: 4充电宝+2T恤(详细输出)")

# ══════════════════════════════════════════════════════════
# 用例 29: 1件危险化学液体 无箱型支持 → F4人工介入
# ══════════════════════════════════════════════════════════
def case29():
    carrier = CarrierLimits(
        carrier_id="STD", max_weight=Decimal("15"),
        max_dimension=Dimensions(length=Decimal("100"), width=Decimal("80"), height=Decimal("60")),
        dim_factor=6000, max_liquid_volume_ml=Decimal("500"),
    )
    req = CartonizationRequest(
        order_id="CASE-029",
        items=[SKUItem(
            sku_id="HAZLIQ-001", sku_name="危险化学液体", quantity=1,
            weight=Decimal("2"), length=Decimal("15"), width=Decimal("10"), height=Decimal("10"),
            temperature_zone=TemperatureZone.NORMAL, hazmat_type=HazmatType.CORROSIVE,
            liquid_flag=True, liquid_volume_ml=Decimal("800"),
        )],
        box_types=STD_BOXES,
        carrier_limits=carrier,
    )
    return fmt(engine.cartonize(req), "用例29: 危险化学液体(无箱型支持→回退)")


# ══════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    cases = [
        case1, case2, case3, case4, case5, case6, case7, case8, case9, case10,
        case11, case12, case13, case14, case15, case16, case17, case18, case19, case20,
        case21, case22, case23, case24, case25, case26, case27, case28, case29,
    ]
    for fn in cases:
        print(fn())
    print(f"\n{'='*60}")
    print(f"共执行 {len(cases)} 个测试用例")
    print(f"{'='*60}")
