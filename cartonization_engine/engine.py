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
    PackagingParams,
    ProtectionCoefficients,
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
from cartonization_engine.splitter import PackageSplitter
from cartonization_engine.fill_rate_checker import FillRateChecker
from cartonization_engine.hard_rule_checker import HardRuleChecker
from cartonization_engine.billing_calculator import BillingWeightCalculator
from cartonization_engine.fallback_handler import FallbackHandler
from cartonization_engine.geometry_checker import GeometryChecker


class CartonizationEngine:
    """装箱计算引擎主入口。

    流水线：输入验证 → 超大件分离 → 预分组 → FFD排序
    → 拆分(超重/超体积/液体超限) → FFD装箱 → 箱型选择
    → 填充率校验 → 硬规则校验 → 回退处理
    → 计费重计算 → 组装输出
    """

    def __init__(self):
        self._validator = InputValidator()
        self._oversize = OversizeHandler()
        self._grouper = PreGrouper()
        self._sorter = FFDSorter()
        self._packer = FFDPacker()
        self._selector = BoxSelector()
        self._splitter = PackageSplitter()
        self._fill_checker = FillRateChecker()
        self._rule_checker = HardRuleChecker()
        self._billing = BillingWeightCalculator()
        self._fallback = FallbackHandler()
        self._geometry = GeometryChecker()

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
        pkg_params = request.packaging_params
        prot_coeff = request.protection_coefficients

        if not items:
            return CartonizationResult(
                status=CartonStatus.FAILED,
                order_id=request.order_id,
                error_code="INVALID_INPUT",
                error_message="SKU 列表为空",
            )

        # 超大件分离
        oversize_result = self._oversize.separate(items)
        normal_items = oversize_result.normal_items

        oversize_packages: list[Package] = []
        for opkg in oversize_result.oversize_packages:
            oi = opkg.item
            os_box = self._selector.select([oi], box_types, carrier)
            if os_box is None:
                from cartonization_engine.models import BoxType, Dimensions
                side = Decimal("200")
                os_box = BoxType(
                    box_id="OVERSIZE_VIRTUAL",
                    inner_dimensions=Dimensions(length=side, width=side, height=side),
                    outer_dimensions=Dimensions(
                        length=side + Decimal("2"), width=side + Decimal("2"),
                        height=side + Decimal("2"),
                    ),
                    max_weight=Decimal("999"), material_weight=Decimal("0"),
                    packaging_cost=Decimal("0"), is_standard=False,
                )
            bw = self._billing.calculate([oi], os_box, carrier, pkg_params)
            oversize_packages.append(Package(
                package_id=f"PKG-{uuid.uuid4().hex[:8]}",
                items=[PackageItem(sku_id=oi.sku_id, sku_name=oi.sku_name, quantity=oi.quantity)],
                box_type=os_box, billing_weight=bw, fill_rate=Decimal("100"),
                flags=[PackageFlag.OVERSIZE_SPECIAL],
                decision_log=DecisionLog(group_reason="超大件分离", box_selection_reason="超大件专线"),
            ))

        if not normal_items:
            total_bw = sum(p.billing_weight.billing_weight for p in oversize_packages)
            total_aw = sum(p.billing_weight.actual_weight for p in oversize_packages)
            return CartonizationResult(
                status=CartonStatus.SUCCESS, order_id=request.order_id,
                packages=oversize_packages, total_packages=len(oversize_packages),
                total_billing_weight=total_bw, total_actual_weight=total_aw,
                input_completeness_level=input_level, degradation_marks=degradation_marks,
            )

        groups = self._grouper.group(normal_items, config)

        all_packages: list[Package] = list(oversize_packages)
        all_violations: list[RuleViolation] = []
        fallback_level: Optional[FallbackLevel] = None

        for group in groups:
            grp_packages, grp_violations, grp_fallback = self._process_group(
                group, box_types, carrier, config, pkg_params, prot_coeff,
            )
            all_packages.extend(grp_packages)
            all_violations.extend(grp_violations)
            if grp_fallback is not None:
                if fallback_level is None or grp_fallback.value > fallback_level.value:
                    fallback_level = grp_fallback

        if len(all_packages) > config.max_package_count:
            return CartonizationResult(
                status=CartonStatus.FAILED, order_id=request.order_id,
                error_code="PACKAGE_LIMIT_EXCEEDED",
                error_message=f"包裹数 {len(all_packages)} 超过限制 {config.max_package_count}",
                failed_skus=[it.sku_id for it in request.items],
            )

        total_bw = sum(p.billing_weight.billing_weight for p in all_packages)
        total_aw = sum(p.billing_weight.actual_weight for p in all_packages)

        # 计算结果级别和可信度
        has_fallback = fallback_level is not None
        has_degradation = len(degradation_marks) > 0
        has_manual = any(
            PackageFlag.MANUAL_PACKING in p.flags or PackageFlag.CARRIER_OVERSIZE in p.flags
            for p in all_packages
        )

        if has_manual:
            result_level = "manual_review"
            confidence = "low"
        elif has_degradation:
            result_level = "estimated"
            confidence = "medium"
        else:
            result_level = "strict"
            confidence = "high"

        # 收集人工介入原因
        manual_reason_types: list[str] = []
        manual_actions: list[str] = []
        for p in all_packages:
            if PackageFlag.CARRIER_OVERSIZE in p.flags:
                manual_reason_types.append("carrier_limit_exceeded")
                manual_actions.append("建议切换大件承运商")
            if PackageFlag.MANUAL_PACKING in p.flags:
                manual_reason_types.append("no_standard_box_fit")
                manual_actions.append("需仓库人工选择包装方案")

        # 校验状态汇总
        rules_passed = len(all_violations) == 0
        physical_passed = all(p.geometry_passed is not False for p in all_packages)
        billing_passed = all(
            p.billing_weight.billing_weight >= p.billing_weight.actual_weight
            and p.billing_weight.billing_weight >= p.billing_weight.volumetric_weight
            for p in all_packages
        )

        return CartonizationResult(
            status=CartonStatus.SUCCESS, order_id=request.order_id,
            packages=all_packages, total_packages=len(all_packages),
            total_billing_weight=total_bw, total_actual_weight=total_aw,
            input_completeness_level=input_level, degradation_marks=degradation_marks,
            violations=all_violations, fallback_level=fallback_level,
            result_level=result_level,
            confidence=confidence,
            downgraded_fields=[m.field for m in degradation_marks],
            manual_reason_types=list(set(manual_reason_types)),
            manual_actions=list(set(manual_actions)),
            validation_status={
                "rules_passed": rules_passed,
                "physical_passed": physical_passed,
                "billing_passed": billing_passed,
            },
        )

    def _process_group(
        self,
        group: SKUGroup,
        box_types: list,
        carrier,
        config,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
    ) -> tuple[list[Package], list[RuleViolation], Optional[FallbackLevel]]:
        """对单个预分组执行装箱流水线。"""
        items = group.items
        fallback_level: Optional[FallbackLevel] = None
        zone = group.temperature_zone

        # 从实际商品属性推断标记（修复 Issue 5: DG 组液体标记丢失）
        has_fragile = any(it.fragile_flag for it in items)
        has_liquid = any(it.liquid_flag for it in items)

        # ── Step 1: 液体超限预拆分 ──
        # 如果液体总量超过承运商限制，先按液体量拆分
        if has_liquid and carrier.max_liquid_volume_ml is not None:
            total_liquid_ml = sum(
                (it.liquid_volume_ml or Decimal(0)) * it.quantity
                for it in items if it.liquid_flag
            )
            if total_liquid_ml > carrier.max_liquid_volume_ml:
                return self._split_by_liquid_limit(
                    items, group, box_types, carrier, config, pkg_params, prot_coeff,
                )

        # ── Step 2: 选箱 ──
        sorted_items = self._sorter.sort(items)
        selected_box = self._selector.select(
            sorted_items, box_types, carrier,
            has_fragile=has_fragile, has_liquid=has_liquid,
            temperature_zone=zone,
            packaging_params=pkg_params, protection_coefficients=prot_coeff,
        )

        if selected_box is None:
            # 无可用箱型 → 判断原因
            # 检查是否有箱型能装下但超承运商限制 → F3
            carrier_blocked = self._has_carrier_blocked_box(
                sorted_items, box_types, carrier, has_fragile, has_liquid, zone,
                pkg_params, prot_coeff,
            )

            # 尝试 splitter 拆分后重试
            split_pkgs = self._try_split_and_pack(
                items, group, box_types, carrier, config, pkg_params, prot_coeff,
            )
            if split_pkgs is not None:
                return split_pkgs, [], None

            fb_context = FallbackContext(
                non_standard_box_types=[b for b in box_types if not b.is_standard],
            )
            fb_result = self._fallback.handle(
                items, "无可用箱型" + (" (承运商超限)" if carrier_blocked else ""),
                fb_context, carrier,
                force_carrier_issue=carrier_blocked,
            )
            return (
                fb_result.packages if fb_result.success else [],
                [],
                fb_result.level,
            )

        # ── Step 3: FFD 装箱 ──
        pack_result = self._packer.pack(sorted_items, selected_box)

        packages: list[Package] = []
        violations: list[RuleViolation] = []

        for b in pack_result.bins:
            pkg = self._build_package_from_bin(
                b, group, box_types, carrier, pkg_params, prot_coeff,
                has_fragile, has_liquid, zone,
            )
            if pkg is not None:
                packages.append(pkg)
                continue

            # bin 构建失败（硬规则违反）→ 回退
            merged = self._merge_bin_items(b)
            fb_context = FallbackContext(
                non_standard_box_types=[bt for bt in box_types if not bt.is_standard],
            )
            rule_violations = self._rule_checker.check(merged, selected_box, carrier)
            fb_result = self._fallback.handle(
                merged,
                "; ".join(v.description for v in rule_violations) if rule_violations else "装箱失败",
                fb_context, carrier,
            )
            fallback_level = fb_result.level
            if fb_result.success:
                packages.extend(fb_result.packages)
            else:
                violations.extend(rule_violations)

        return packages, violations, fallback_level

    def _split_by_liquid_limit(
        self,
        items: list[SKUItem],
        group: SKUGroup,
        box_types: list,
        carrier,
        config,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
    ) -> tuple[list[Package], list[RuleViolation], Optional[FallbackLevel]]:
        """按液体量限制拆分为多个子组，每组液体量不超限。"""
        max_ml = carrier.max_liquid_volume_ml
        zone = group.temperature_zone
        has_fragile = any(it.fragile_flag for it in items)
        has_liquid = True

        # 分离液体和非液体
        liquid_items: list[SKUItem] = []
        non_liquid_items: list[SKUItem] = []
        for it in items:
            if it.liquid_flag:
                # 展开为单件
                for _ in range(it.quantity):
                    liquid_items.append(it.model_copy(update={"quantity": 1}))
            else:
                non_liquid_items.append(it)

        # 按液体量贪心分组
        liquid_bins: list[list[SKUItem]] = [[]]
        bin_ml: list[Decimal] = [Decimal("0")]
        for li in liquid_items:
            ml = li.liquid_volume_ml or Decimal(0)
            placed = False
            for i in range(len(liquid_bins)):
                if bin_ml[i] + ml <= max_ml:
                    liquid_bins[i].append(li)
                    bin_ml[i] += ml
                    placed = True
                    break
            if not placed:
                liquid_bins.append([li])
                bin_ml.append(ml)

        # 非液体品放入第一个液体组（如果有空间）或单独成组
        packages: list[Package] = []
        fallback_level: Optional[FallbackLevel] = None

        for i, lbin in enumerate(liquid_bins):
            bin_items = list(lbin)
            if i == 0 and non_liquid_items:
                bin_items.extend(non_liquid_items)

            if not bin_items:
                continue

            # 合并同 SKU
            merged = self._merge_item_list(bin_items)
            pkg = self._pack_item_list(
                merged, group, box_types, carrier, config, pkg_params, prot_coeff,
                has_fragile, True, zone,
            )
            if pkg:
                packages.extend(pkg)
            else:
                # 回退
                fb_context = FallbackContext(
                    non_standard_box_types=[b for b in box_types if not b.is_standard],
                )
                fb_result = self._fallback.handle(merged, "液体拆分后仍无法装箱", fb_context, carrier)
                fallback_level = fb_result.level
                if fb_result.success:
                    packages.extend(fb_result.packages)

        return packages, [], fallback_level

    def _try_split_and_pack(
        self,
        items: list[SKUItem],
        group: SKUGroup,
        box_types: list,
        carrier,
        config,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
    ) -> Optional[list[Package]]:
        """尝试用 splitter 拆分后重新装箱。"""
        zone = group.temperature_zone
        has_fragile = any(it.fragile_flag for it in items)
        has_liquid = any(it.liquid_flag for it in items)

        # 找到最大可用箱型
        best_box = None
        for bt in sorted(box_types, key=lambda b: b.inner_dimensions.volume, reverse=True):
            if bt.available_qty is not None and bt.available_qty <= 0:
                continue
            if zone and zone not in bt.temperature_zone_supported:
                continue
            if has_fragile and not bt.supports_shock_proof:
                continue
            if has_liquid and not bt.supports_leak_proof:
                continue
            if not self._selector._carrier_compliant(bt, carrier):
                continue
            best_box = bt
            break

        if best_box is None:
            return None

        # 计算有效承重（扣除包材）
        extra_wt, _ = self._selector._calc_packaging_overhead(items, pkg_params)
        effective_max_weight = min(
            best_box.max_weight - best_box.material_weight - extra_wt,
            carrier.max_weight - best_box.material_weight - extra_wt,
        )
        if effective_max_weight <= 0:
            return None

        split_result = self._splitter.split(
            items,
            max_weight=effective_max_weight,
            max_volume=best_box.inner_dimensions.volume,
            max_packages=config.max_package_count,
        )

        if not split_result.success:
            return None

        packages: list[Package] = []
        for sbin in split_result.bins:
            if not sbin.items:
                continue
            merged = self._merge_item_list(sbin.items)
            pkgs = self._pack_item_list(
                merged, group, box_types, carrier, config, pkg_params, prot_coeff,
                has_fragile, has_liquid, zone,
            )
            if pkgs:
                packages.extend(pkgs)
            else:
                return None  # 拆分后仍无法装箱

        return packages if packages else None

    def _pack_item_list(
        self,
        items: list[SKUItem],
        group: SKUGroup,
        box_types: list,
        carrier,
        config,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
        has_fragile: bool,
        has_liquid: bool,
        zone: TemperatureZone,
    ) -> Optional[list[Package]]:
        """对一组 items 执行选箱→装箱→校验→计费，返回包裹列表。"""
        sorted_items = self._sorter.sort(items)
        box = self._selector.select(
            sorted_items, box_types, carrier,
            has_fragile=has_fragile, has_liquid=has_liquid,
            temperature_zone=zone,
            packaging_params=pkg_params, protection_coefficients=prot_coeff,
        )
        if box is None:
            return None

        pack_result = self._packer.pack(sorted_items, box)
        packages: list[Package] = []
        for b in pack_result.bins:
            pkg = self._build_package_from_bin(
                b, group, box_types, carrier, pkg_params, prot_coeff,
                has_fragile, has_liquid, zone,
            )
            if pkg:
                packages.append(pkg)
            else:
                return None
        return packages if packages else None

    def _build_package_from_bin(
        self,
        b,
        group: SKUGroup,
        box_types: list,
        carrier,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
        has_fragile: bool,
        has_liquid: bool,
        zone: TemperatureZone,
    ) -> Optional[Package]:
        """从一个 OpenBin 构建 Package，校验硬规则，失败返回 None。"""
        merged_sku_items = self._merge_bin_items(b)
        pkg_items = [
            PackageItem(sku_id=it.sku_id, sku_name=it.sku_name, quantity=it.quantity)
            for it in merged_sku_items
        ]

        # 为 bin 单独选最优箱型
        bin_box = self._selector.select(
            merged_sku_items, box_types, carrier,
            has_fragile=has_fragile, has_liquid=has_liquid,
            temperature_zone=zone,
            packaging_params=pkg_params, protection_coefficients=prot_coeff,
        )
        if bin_box is None:
            return None

        # 填充率校验
        final_box, fill_rate, fill_flags = self._fill_checker.check_and_optimize(
            merged_sku_items, bin_box, box_types,
            carrier_limits=carrier, min_rate=Decimal("60"), max_rate=Decimal("90"),
            has_fragile=has_fragile, has_liquid=has_liquid,
            temperature_zone=zone,
            protection_coefficients=prot_coeff, packaging_params=pkg_params,
        )

        # 硬规则校验
        rule_violations = self._rule_checker.check(merged_sku_items, final_box, carrier)
        if rule_violations:
            return None

        # 几何校验
        geo_result = self._geometry.check(merged_sku_items, final_box)

        # 计费重
        bw = self._billing.calculate(merged_sku_items, final_box, carrier, pkg_params)

        flags = list(fill_flags)
        special_flags: list[str] = []
        if has_fragile:
            special_flags.append("FRAGILE")
        if has_liquid:
            special_flags.append("LIQUID")
        if any(it.hazmat_type and it.hazmat_type != HazmatType.NONE for it in merged_sku_items):
            special_flags.append("DG")
        if PackageFlag.LOW_FILL_RATE in flags:
            special_flags.append("LOW_FILL_RATE")

        why_not_smaller = self._explain_why_not_smaller(
            merged_sku_items, final_box, box_types, carrier,
            has_fragile, has_liquid, zone, pkg_params, prot_coeff,
        )

        return Package(
            package_id=f"PKG-{uuid.uuid4().hex[:8]}",
            items=pkg_items, box_type=final_box, billing_weight=bw,
            fill_rate=fill_rate, flags=flags,
            decision_log=DecisionLog(
                group_reason=group.group_reason,
                box_selection_reason=f"最优箱型: {final_box.box_id}",
            ),
            rule_validation_passed=True,
            physical_validation_passed=geo_result.passed,
            geometry_passed=geo_result.passed,
            geometry_reason=geo_result.reason,
            selection_reason=[
                f"最优箱型: {final_box.box_id}",
                f"填充率: {fill_rate}%",
                why_not_smaller,
            ],
            special_flags=special_flags,
        )

    @staticmethod
    def _merge_bin_items(b) -> list[SKUItem]:
        """合并 bin 中同 SKU 的数量。"""
        qty_map: dict[str, tuple[str, int, SKUItem]] = {}
        for si in b.items:
            if si.sku_id in qty_map:
                name, q, ref = qty_map[si.sku_id]
                qty_map[si.sku_id] = (name, q + si.quantity, ref)
            else:
                qty_map[si.sku_id] = (si.sku_name, si.quantity, si)
        return [
            ref.model_copy(update={"quantity": qty})
            for _, (_, qty, ref) in qty_map.items()
        ]

    @staticmethod
    def _merge_item_list(items: list[SKUItem]) -> list[SKUItem]:
        """合并 item 列表中同 SKU 的数量。"""
        qty_map: dict[str, tuple[int, SKUItem]] = {}
        for it in items:
            if it.sku_id in qty_map:
                q, ref = qty_map[it.sku_id]
                qty_map[it.sku_id] = (q + it.quantity, ref)
            else:
                qty_map[it.sku_id] = (it.quantity, it)
        return [
            ref.model_copy(update={"quantity": qty})
            for _, (qty, ref) in qty_map.items()
        ]

    def _has_carrier_blocked_box(
        self,
        items: list[SKUItem],
        box_types: list,
        carrier,
        has_fragile: bool,
        has_liquid: bool,
        zone: TemperatureZone,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
    ) -> bool:
        """检查是否存在箱型能装下商品但因承运商限制被过滤。"""
        volume_coeff = self._selector._get_volume_coefficient(items, prot_coeff)
        extra_wt, extra_vol = self._selector._calc_packaging_overhead(items, pkg_params)
        total_wt = sum((it.weight or Decimal(0)) * it.quantity for it in items) + extra_wt

        for bt in box_types:
            if bt.available_qty is not None and bt.available_qty <= 0:
                continue
            if zone and zone not in bt.temperature_zone_supported:
                continue
            if not self._selector._all_items_fit(items, bt):
                continue
            eff_vol = self._selector._calc_effective_volume(items, bt, volume_coeff) + extra_vol
            if bt.inner_dimensions.volume < eff_vol:
                continue
            if bt.max_weight < total_wt + bt.material_weight:
                continue
            if has_fragile and not bt.supports_shock_proof:
                continue
            if has_liquid and not bt.supports_leak_proof:
                continue
            # 箱型能装下，但承运商不合规 → carrier issue
            if not self._selector._carrier_compliant(bt, carrier):
                return True
        return False

    def _explain_why_not_smaller(
        self,
        items: list[SKUItem],
        current_box,
        box_types: list,
        carrier,
        has_fragile: bool,
        has_liquid: bool,
        zone: TemperatureZone,
        pkg_params: PackagingParams,
        prot_coeff: ProtectionCoefficients,
    ) -> str:
        """解释为什么没有选更小的箱型。"""
        smaller = [
            bt for bt in box_types
            if bt.inner_dimensions.volume < current_box.inner_dimensions.volume
            and bt.box_id != current_box.box_id
        ]
        if not smaller:
            return "已是最小可用箱型"
        reasons = []
        for bt in sorted(smaller, key=lambda b: b.inner_dimensions.volume, reverse=True):
            if bt.available_qty is not None and bt.available_qty <= 0:
                reasons.append(f"{bt.box_id}: 无库存")
                continue
            if zone and zone not in bt.temperature_zone_supported:
                reasons.append(f"{bt.box_id}: 不支持{zone.value}温区")
                continue
            if has_fragile and not bt.supports_shock_proof:
                reasons.append(f"{bt.box_id}: 不支持防震")
                continue
            if has_liquid and not bt.supports_leak_proof:
                reasons.append(f"{bt.box_id}: 不支持防漏")
                continue
            result = self._selector.select(
                items, [bt], carrier,
                has_fragile=has_fragile, has_liquid=has_liquid,
                temperature_zone=zone,
                packaging_params=pkg_params, protection_coefficients=prot_coeff,
            )
            if result is None:
                reasons.append(f"{bt.box_id}: 容量/重量/尺寸不足")
        if reasons:
            return "更小箱型不可用: " + "; ".join(reasons[:3])
        return "已是最优箱型"
