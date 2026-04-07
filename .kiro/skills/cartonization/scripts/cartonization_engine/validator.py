"""输入验证器 - 验证装箱请求完整性并执行数据降级"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from cartonization_engine.models import (
    BoxType,
    CartonizationRequest,
    DegradationMark,
    HazmatType,
    InputCompletenessLevel,
    SKUItem,
    TemperatureZone,
    ValidationResult,
)


class InputValidator:
    """装箱请求输入验证器。

    职责：
    1. 验证 SKU 必填字段（sku_id, weight, length, width, height, temperature_zone）
    2. 验证箱型列表非空且尺寸/承重为正数
    3. 对缺失字段执行降级策略
    """

    def validate(self, request: CartonizationRequest) -> ValidationResult:
        """验证输入完整性，对缺失字段执行降级策略。"""
        # 1. 验证箱型列表
        if not request.box_types:
            return ValidationResult(
                success=False,
                error_code="NO_AVAILABLE_BOX",
                error_message="无可用箱型",
            )

        # 验证每个箱型的尺寸和承重为正数
        for bt in request.box_types:
            if not self._is_valid_box_type(bt):
                return ValidationResult(
                    success=False,
                    error_code="INVALID_INPUT",
                    error_message=f"箱型 {bt.box_id} 的尺寸或承重包含非正数值",
                )

        # 2. 验证并降级 SKU 列表
        degraded_items: list[SKUItem] = []
        all_marks: list[DegradationMark] = []

        for sku in request.items:
            marks = self._apply_degradation(sku, request.category_defaults)
            all_marks.extend(marks)
            degraded_items.append(sku)

        # 3. 分类输入完整度
        input_level = self.classify_input_level(request)

        return ValidationResult(
            success=True,
            items=degraded_items,
            box_types=request.box_types,
            degradation_marks=all_marks,
            input_level=input_level,
        )

    def classify_input_level(self, request: CartonizationRequest) -> InputCompletenessLevel:
        """Classify input completeness as L1/L2/L3."""
        items = request.items
        has_all_dimensions = all(
            it.length is not None and it.width is not None and it.height is not None and it.weight is not None
            for it in items
        )
        has_box_types = len(request.box_types) > 0
        has_carrier = request.carrier_limits is not None

        if has_all_dimensions and has_box_types and has_carrier:
            return InputCompletenessLevel.L3
        elif has_box_types or any(it.weight is not None for it in items):
            return InputCompletenessLevel.L2
        else:
            return InputCompletenessLevel.L1

    def _is_valid_box_type(self, bt: BoxType) -> bool:
        """检查箱型尺寸和承重是否为正数。"""
        dims = bt.inner_dimensions
        return (
            dims.length > 0
            and dims.width > 0
            and dims.height > 0
            and bt.max_weight > 0
        )

    def _apply_degradation(
        self, sku: SKUItem, category_defaults: dict[str, dict]
    ) -> list[DegradationMark]:
        """对缺失字段应用品类平均值或默认值。

        降级策略：
        - weight/length/width/height 缺失 → 使用品类平均值
        - temperature_zone 缺失 → 默认 "常温"
        - hazmat_type 缺失 → 默认 "无"
        """
        marks: list[DegradationMark] = []
        cat_defaults = category_defaults.get(sku.category_id or "", {})

        # 物理尺寸降级
        for field in ("weight", "length", "width", "height"):
            if getattr(sku, field) is None:
                default_val = cat_defaults.get(field)
                if default_val is not None:
                    degraded = Decimal(str(default_val))
                else:
                    degraded = Decimal("1.0")  # 无品类数据时的兜底值

                setattr(sku, field, degraded)
                marks.append(
                    DegradationMark(
                        sku_id=sku.sku_id,
                        field=field,
                        original_value=None,
                        degraded_value=degraded,
                        reason=f"使用品类平均值替代缺失的{field}字段",
                    )
                )

        # 温区降级
        if sku.temperature_zone is None:
            sku.temperature_zone = TemperatureZone.NORMAL
            marks.append(
                DegradationMark(
                    sku_id=sku.sku_id,
                    field="temperature_zone",
                    original_value=None,
                    degraded_value=TemperatureZone.NORMAL.value,
                    reason="缺失温区字段，默认设置为常温",
                )
            )

        # 危险品类型降级
        if sku.hazmat_type is None:
            sku.hazmat_type = HazmatType.NONE
            marks.append(
                DegradationMark(
                    sku_id=sku.sku_id,
                    field="hazmat_type",
                    original_value=None,
                    degraded_value=HazmatType.NONE.value,
                    reason="缺失危险品类型字段，默认设置为无",
                )
            )

        return marks
