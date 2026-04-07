"""装箱计算引擎 - 流水线编排入口"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from cartonization_engine.models import (
    BillingWeight,
    CartonizationRequest,
    CartonizationResult,
    CartonStatus,
    DecisionLog,
    DegradationMark,
    FallbackContext,
    FallbackLevel,
    HazmatType,
    InputCompletenessLevel,
    Package,
    PackageFlag,
    PackageItem,
    RuleConflictError,
    RuleViolation,
    SKUGroup,
    SKUItem,
    TemperatureZone,
)
from cartonization_engine.validator import InputValidator
from cartonization_engine.oversize_handler import OversizeHandler
from cartonization_engine.pre_grouper import PreGrouper
from cartonization_engine.sorter import FFDSorter
from cartonization_engine.packer import FFDPacker
from cartonization_engine.box_selector import BoxSelector
from cartonization_engine.fill_rate_checker import FillRateChecker
from cartonization_engine.hard_rule_checker import HardRuleChecker
from cartonization_engine.billing_calculator import BillingWeightCalculator
from cartonization_engine.fallback_handler import FallbackHandler


class CartonizationEngine:
    """装箱计算引擎主入口。

    按流水线顺序编排：
    输入验证 → 超大件分离 → 预分组 → FFD排序 → FFD装箱
    → 箱型选择 → 填充率校验 → 硬规则校验 → 回退处理
    → 计费重计算 → 组装输出
    """

    def __init__(self):
        self._validator = InputValidator()
        self._oversize = OversizeHandler()
        self._grouper = PreGrouper()
        self._sorter = FFDSorter()
        self._packer = FFDPacker()
        self._selector = BoxSelector()
        self._fill_checker = FillRateChecker()
        self._rule_checker = HardRuleChecker()
        self._billing = BillingWeightCalculator()
        self._fallback = FallbackHandler()

    def cartonize(self, request: CartonizationRequest) -> CartonizationResult:
        """装箱计算主入口。"""
        try:
            return self._do_cartonize(request)
        except RuleConflictError as e:
            return CartonizationResult(
                status=CartonStatus.FAILED,
                order_id=request.order_id,
                error_code="RULE_CONFLICT",
                error_message=str(e),
                failed_skus=e.conflicting_skus,
            )
        except Exception as e:
            return CartonizationResult(
                status=CartonStatus.FAILED,
                order_id=request.order_id,
                error_code="CARTON_FAILED",
                error_message=str(e),
            )

    def _do_cartonize(self, request: CartonizationRequest) -> CartonizationResult:
        # 1. 输入验证
        val_result = self._validator.validate(request)
        if not val_result.success:
            return CartonizationResult(
                status=CartonStatus.FAILED,
                order_id=request.order_id,
                error_code=val_result.error_code or "INVALID_INPUT",
                error_message=val_result.error_message,
                failed_skus=[it.sku_id for it in request.items],
            )

        items = val_result.items
        box_types = val_result.box_types
        degradation_marks = val_result.degradation_marks
        input_level = val_result.input_level
        carrier = request.carrier_limits
        config = request.order_config

        if not items:
            return CartonizationResult(
                status=CartonStatus.FAILED,
                order_id=request.order_id,
                error_code="INVALID_INPUT",
                error_message="SKU 列表为空",
            )

        # 2. 超大件分离
        oversize_result = self._oversize.separate(items)
        normal_items = oversize_result.normal_items

        # 构建超大件包裹
        oversize_packages: list[Package] = []
        for opkg in oversize_result.oversize_packages:
            oi = opkg.item
            # 为超大件选箱型或使用虚拟箱型
            os_box = self._selector.select([oi], box_types, carrier)
            if os_box is None:
                # 使用虚拟箱型
                from cartonization_engine.models import BoxType, Dimensions
                side = Decimal("200")
                os_box = BoxType(
                    box_id="OVERSIZE_VIRTUAL",
                    inner_dimensions=Dimensions(length=side, width=side, height=side),
                    outer_dimensions=Dimensions(
                        length=side + Decimal("2"),
                        width=side + Decimal("2"),
                        height=side + Decimal("2"),
                    ),
                    max_weight=Decimal("999"),
                    material_weight=Decimal("0"),
                    packaging_cost=Decimal("0"),
                    is_standard=False,
                )
            bw = self._billing.calculate([oi], os_box, carrier)
            oversize_packages.append(Package(
                package_id=f"PKG-{uuid.uuid4().hex[:8]}",
                items=[PackageItem(
                    sku_id=oi.sku_id, sku_name=oi.sku_name, quantity=oi.quantity,
                )],
                box_type=os_box,
                billing_weight=bw,
                fill_rate=Decimal("100"),
                flags=[PackageFlag.OVERSIZE_SPECIAL],
                decision_log=DecisionLog(
                    group_reason="超大件分离",
                    box_selection_reason="超大件专线",
                ),
            ))

        # 如果没有普通件，直接返回超大件结果
        if not normal_items:
            total_bw = sum(p.billing_weight.billing_weight for p in oversize_packages)
            total_aw = sum(p.billing_weight.actual_weight for p in oversize_packages)
            return CartonizationResult(
                status=CartonStatus.SUCCESS,
                order_id=request.order_id,
                packages=oversize_packages,
                total_packages=len(oversize_packages),
                total_billing_weight=total_bw,
                total_actual_weight=total_aw,
                input_completeness_level=input_level,
                degradation_marks=degradation_marks,
            )

        # 3. 预分组
        groups = self._grouper.group(normal_items, config)

        # 4-9. 对每个组执行装箱流水线
        all_packages: list[Package] = list(oversize_packages)
        all_violations: list[RuleViolation] = []
        fallback_level: Optional[FallbackLevel] = None

        for group in groups:
            grp_packages, grp_violations, grp_fallback = self._process_group(
                group, box_types, carrier, config,
            )
            all_packages.extend(grp_packages)
            all_violations.extend(grp_violations)
            if grp_fallback is not None:
                if fallback_level is None or grp_fallback.value > fallback_level.value:
                    fallback_level = grp_fallback

        # 检查包裹数限制
        if len(all_packages) > config.max_package_count:
            return CartonizationResult(
                status=CartonStatus.FAILED,
                order_id=request.order_id,
                error_code="PACKAGE_LIMIT_EXCEEDED",
                error_message=f"包裹数 {len(all_packages)} 超过限制 {config.max_package_count}",
                failed_skus=[it.sku_id for it in request.items],
            )

        total_bw = sum(p.billing_weight.billing_weight for p in all_packages)
        total_aw = sum(p.billing_weight.actual_weight for p in all_packages)

        return CartonizationResult(
            status=CartonStatus.SUCCESS,
            order_id=request.order_id,
            packages=all_packages,
            total_packages=len(all_packages),
            total_billing_weight=total_bw,
            total_actual_weight=total_aw,
            input_completeness_level=input_level,
            degradation_marks=degradation_marks,
            violations=all_violations,
            fallback_level=fallback_level,
        )

    def _process_group(
        self,
        group: SKUGroup,
        box_types: list,
        carrier,
        config,
    ) -> tuple[list[Package], list[RuleViolation], Optional[FallbackLevel]]:
        """对单个预分组执行装箱流水线。"""
        items = group.items
        fallback_level: Optional[FallbackLevel] = None

        # FFD 排序
        sorted_items = self._sorter.sort(items)

        # 检查是否有易碎品/液体品
        has_fragile = any(it.fragile_flag for it in items)
        has_liquid = any(it.liquid_flag for it in items)

        # 箱型选择
        selected_box = self._selector.select(
            sorted_items, box_types, carrier, has_fragile=has_fragile,
        )

        if selected_box is None:
            # 无可用箱型，进入回退
            fb_context = FallbackContext(
                non_standard_box_types=[b for b in box_types if not b.is_standard],
            )
            fb_result = self._fallback.handle(
                items, "无可用箱型", fb_context, carrier,
            )
            fallback_level = fb_result.level
            if fb_result.success:
                return fb_result.packages, [], fallback_level
            else:
                return [], [], fallback_level

        # FFD 装箱
        pack_result = self._packer.pack(sorted_items, selected_box)

        # 对每个 bin 构建包裹
        packages: list[Package] = []
        violations: list[RuleViolation] = []

        for b in pack_result.bins:
            bin_items = b.items  # list[SKUItem] with qty=1

            # 合并同 SKU 数量
            qty_map: dict[str, tuple[str, int, SKUItem]] = {}
            for si in bin_items:
                if si.sku_id in qty_map:
                    name, q, ref = qty_map[si.sku_id]
                    qty_map[si.sku_id] = (name, q + si.quantity, ref)
                else:
                    qty_map[si.sku_id] = (si.sku_name, si.quantity, si)

            pkg_items = [
                PackageItem(sku_id=sid, sku_name=name, quantity=qty)
                for sid, (name, qty, _) in qty_map.items()
            ]

            # 重建 SKUItem 列表（合并后）用于后续校验
            merged_sku_items = []
            for sid, (name, qty, ref) in qty_map.items():
                merged_sku_items.append(ref.model_copy(update={"quantity": qty}))

            # 箱型选择（为每个 bin 单独选最优箱型）
            bin_box = self._selector.select(
                merged_sku_items, box_types, carrier, has_fragile=has_fragile,
            )
            if bin_box is None:
                bin_box = selected_box

            # 填充率校验
            final_box, fill_rate, fill_flags = self._fill_checker.check_and_optimize(
                merged_sku_items, bin_box, box_types,
                carrier_limits=carrier,
                min_rate=Decimal("60"),
                max_rate=Decimal("90"),
                has_fragile=has_fragile,
            )

            # 硬规则校验
            rule_violations = self._rule_checker.check(
                merged_sku_items, final_box, carrier,
            )

            if rule_violations:
                # 尝试回退
                fb_context = FallbackContext(
                    non_standard_box_types=[bt for bt in box_types if not bt.is_standard],
                )
                fb_result = self._fallback.handle(
                    merged_sku_items,
                    "; ".join(v.description for v in rule_violations),
                    fb_context,
                    carrier,
                )
                fallback_level = fb_result.level
                if fb_result.success:
                    packages.extend(fb_result.packages)
                else:
                    violations.extend(rule_violations)
                continue

            # 计费重计算
            bw = self._billing.calculate(merged_sku_items, final_box, carrier)

            flags = list(fill_flags)

            # Build special_flags based on item properties
            special_flags: list[str] = []
            if has_fragile:
                special_flags.append("FRAGILE")
            if has_liquid:
                special_flags.append("LIQUID")
            if PackageFlag.LOW_FILL_RATE in flags:
                special_flags.append("LOW_FILL_RATE")

            pkg = Package(
                package_id=f"PKG-{uuid.uuid4().hex[:8]}",
                items=pkg_items,
                box_type=final_box,
                billing_weight=bw,
                fill_rate=fill_rate,
                flags=flags,
                decision_log=DecisionLog(
                    group_reason=group.group_reason,
                    box_selection_reason=f"最优箱型: {final_box.box_id}",
                ),
                rule_validation_passed=True,
                physical_validation_passed=True,
                selection_reason=[f"最优箱型: {final_box.box_id}", f"填充率: {fill_rate}%"],
                special_flags=special_flags,
            )
            packages.append(pkg)

        return packages, violations, fallback_level
