"""Shipping Rate Engine — 顶层编排器

运费计算主入口，编排 ZoneResolver → RateCalculator → SurchargeCalculator → RateAggregator。
支持输入验证、降级策略、多承运商计算和 Provider 链式回退。
"""

from __future__ import annotations

from decimal import Decimal

from .rate_models import (
    PackageRate,
    RateRequest,
    RateResult,
    SurchargeContext,
)
from .rate_provider import LocalRateProvider, RateProvider
from .rate_aggregator import RateAggregator
from .rate_calculator import _round2


class RateEngine:
    """运费计算引擎"""

    def __init__(self, providers: list[RateProvider] | None = None, use_default_us_rates: bool = True):
        self._providers: list[RateProvider] = sorted(
            providers or [],
            key=lambda p: p.priority,
        )
        # 自动注册美国公开牌价 provider 作为兜底
        if use_default_us_rates:
            from .default_us_rates import DefaultUSRateProvider
            has_default = any(isinstance(p, DefaultUSRateProvider) for p in self._providers)
            if not has_default:
                self._providers.append(DefaultUSRateProvider())
                self._providers.sort(key=lambda p: p.priority)

    def add_provider(self, provider: RateProvider) -> None:
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)

    def calculate_rate(self, request: RateRequest) -> RateResult:
        """运费计算主入口。

        当 carrier 未指定且有 DefaultUSRateProvider 时，
        自动为所有支持的承运商计算运费，返回最低价方案。
        """
        # 如果没指定承运商但有默认 provider，做多承运商比价
        if not request.carrier and self._has_default_provider():
            return self._estimate_all_carriers(request)

        # 1. 输入验证
        errors = self._validate_input(request)
        if errors:
            return RateResult(
                success=False,
                errors=errors,
                carrier=request.carrier or "",
                recommend_source=request.recommend_source,
            )

        # 2. 检查降级
        degraded = False
        degraded_fields: list[str] = []
        if not request.surcharge_rules.rules:
            degraded = True
            degraded_fields.append("surcharge_rules")
        if not request.promotion_rules:
            degraded = True
            degraded_fields.append("promotion_rules")
        if not request.merchant_agreement:
            degraded = True
            degraded_fields.append("merchant_agreement")

        # 3. 构建附加费上下文
        ctx = SurchargeContext(
            ship_date=request.ship_date,
            estimated_delivery_date=request.estimated_delivery_date,
            has_elevator=request.has_elevator,
            floor_number=request.floor_number,
            destination=request.destination,
        )

        # 4. 遍历每个包裹计算运费
        package_rates: list[PackageRate] = []
        pkg_errors: list[dict] = []

        for pkg in request.packages:
            rate_result = self._calculate_package_rate(
                pkg, request, ctx,
            )
            if rate_result is not None:
                package_rates.append(rate_result)
            else:
                pkg_errors.append({
                    "code": "PACKAGE_CALC_FAILED",
                    "message": f"包裹 {pkg.package_id} 运费计算失败（所有 Provider 均失败）",
                })

        if not package_rates and pkg_errors:
            return RateResult(
                success=False,
                errors=pkg_errors,
                carrier=request.carrier or "",
                recommend_source=request.recommend_source,
                degraded=degraded,
                degraded_fields=degraded_fields,
            )

        # 5. 订单级汇总 + 促销减免
        summary = RateAggregator.aggregate(
            package_rates,
            request.promotion_rules if request.promotion_rules else None,
            request.order_total_amount,
        )

        # 6. 构建说明
        explanation_parts = [f"承运商: {request.carrier}"]
        explanation_parts.append(f"包裹数: {len(package_rates)}")
        if degraded:
            explanation_parts.append(f"降级字段: {degraded_fields}")
            if "merchant_agreement" in degraded_fields:
                explanation_parts.append("注意：无商户签约价格表，使用公开牌价估算，实际签约价通常有 30-70% 折扣，仅供参考")
        if summary.total_promotion_discount > 0:
            explanation_parts.append(f"促销减免: {summary.total_promotion_discount}")

        confidence = "high"
        if degraded:
            if "merchant_agreement" in degraded_fields:
                confidence = "estimated"
            else:
                confidence = "medium"

        return RateResult(
            success=True,
            freight_order=summary.freight_order,
            freight_order_before_promotion=summary.freight_order_before_promotion,
            package_rates=summary.package_rates,
            promotions_applied=summary.promotions_applied,
            total_promotion_discount=summary.total_promotion_discount,
            degraded=degraded,
            degraded_fields=degraded_fields,
            errors=pkg_errors,
            carrier=request.carrier or "",
            recommend_source=request.recommend_source,
            confidence=confidence,
            calculation_explanation="；".join(explanation_parts),
        )

    def calculate_rate_multi(
        self,
        request: RateRequest,
        recommendations: list,
    ) -> list[RateResult]:
        """为多个承运商推荐分别计算运费"""
        results: list[RateResult] = []
        for rec in recommendations:
            # 构建每个承运商的请求
            carrier = getattr(rec, "carrier", None) or ""
            source = getattr(rec, "source", None)
            req = request.model_copy(update={
                "carrier": carrier,
                "recommend_source": source,
            })
            result = self.calculate_rate(req)
            result.recommend_source = source
            results.append(result)
        return results

    def _calculate_package_rate(
        self,
        package,
        request: RateRequest,
        ctx: SurchargeContext,
    ) -> PackageRate | None:
        """使用 Provider 链计算单包裹运费，按优先级回退。
        Provider 全部失败后，回退到内置价格表计算。
        """
        # 先尝试 Provider 链
        if self._providers:
            for provider in self._providers:
                try:
                    result = provider.get_rate(
                        package=package,
                        origin=request.origin,
                        destination=request.destination,
                        carrier=request.carrier or "",
                        surcharge_rules=request.surcharge_rules,
                        surcharge_context=ctx,
                    )
                    if result.success and result.package_rate:
                        return result.package_rate
                except Exception:
                    continue

        # Provider 全部失败或无 Provider，回退到内置价格表计算
        if request.price_table is not None:
            return self._calculate_with_price_table(package, request, ctx)

        return None

    def _calculate_with_price_table(
        self,
        package,
        request: RateRequest,
        ctx: SurchargeContext,
    ) -> PackageRate | None:
        """使用请求中的 price_table 直接计算。"""
        from .zone_resolver import ZoneResolver, ZoneResolveError
        from .rate_calculator import RateCalculator
        from .surcharge_calculator import SurchargeCalculator

        try:
            charge_zone = ZoneResolver.resolve(
                request.origin, request.destination, request.price_table.zone_mappings,
            )
        except ZoneResolveError:
            return None

        zone_rate = None
        for zr in request.price_table.zone_rates:
            if zr.charge_zone == charge_zone:
                zone_rate = zr
                break

        if zone_rate is None:
            return None

        try:
            freight_base = RateCalculator.calculate(
                package.billing_weight, package.volume_cm3, zone_rate,
            )
        except Exception:
            return None

        surcharge = SurchargeCalculator.calculate_all(
            freight_base, package, request.surcharge_rules, ctx,
        )

        freight_total = _round2(freight_base + surcharge.total)

        return PackageRate(
            package_id=package.package_id,
            charge_zone=charge_zone,
            billing_mode=zone_rate.billing_mode,
            freight_base=freight_base,
            surcharge_breakdown=surcharge,
            freight_total=freight_total,
        )

    def _validate_input(self, request: RateRequest) -> list[dict]:
        """验证输入，返回错误列表"""
        errors: list[dict] = []

        if not request.packages:
            errors.append({
                "code": "MISSING_PACKAGE_INFO",
                "message": "包裹列表为空",
            })
        else:
            for pkg in request.packages:
                if pkg.billing_weight is None or pkg.billing_weight <= 0:
                    errors.append({
                        "code": "MISSING_PACKAGE_INFO",
                        "message": f"包裹 {pkg.package_id} 计费重量缺失或无效",
                    })

        if request.origin is None:
            errors.append({
                "code": "MISSING_ADDRESS",
                "message": "发货仓地址缺失",
            })

        if request.destination is None:
            errors.append({
                "code": "MISSING_ADDRESS",
                "message": "收货地址缺失",
            })

        if not request.carrier:
            # 如果有 DefaultUSRateProvider，允许不指定承运商（会用所有支持的承运商）
            if not self._has_default_provider():
                errors.append({
                    "code": "MISSING_PACKAGE_INFO",
                    "message": "承运商缺失",
                })

        if request.price_table is None and not self._providers:
            errors.append({
                "code": "PRICE_TABLE_NOT_FOUND",
                "message": "承运商价格表未找到且无可用 Provider",
            })

        return errors

    def _has_default_provider(self) -> bool:
        from .default_us_rates import DefaultUSRateProvider
        return any(isinstance(p, DefaultUSRateProvider) for p in self._providers)

    def _estimate_all_carriers(self, request: RateRequest) -> RateResult:
        """为所有默认承运商计算运费，返回最低价方案（含所有方案对比）。"""
        from .default_us_rates import DefaultUSRateProvider

        all_results: list[RateResult] = []
        for carrier in DefaultUSRateProvider.supported_carriers():
            req = request.model_copy(update={"carrier": carrier})
            r = self.calculate_rate(req)
            if r.success:
                all_results.append(r)

        if not all_results:
            return RateResult(
                success=False,
                errors=[{"code": "NO_CARRIER_MATCH", "message": "所有承运商计算均失败"}],
                degraded=True,
                confidence="low",
            )

        # 按运费排序，取最低
        all_results.sort(key=lambda r: r.freight_order)
        best = all_results[0]

        # 在说明中附带所有方案对比
        comparison = []
        for r in all_results:
            comparison.append(f"{r.carrier}: ${r.freight_order}")

        best.calculation_explanation = (
            f"多承运商比价（公开牌价估算）：{' | '.join(comparison)}。"
            f"推荐 {best.carrier}（最低价 ${best.freight_order}）。"
            f"注意：实际签约价通常有 30-70% 折扣。"
        )
        best.confidence = "estimated"
        best.degraded = True
        if "default_us_rates" not in best.degraded_fields:
            best.degraded_fields.append("default_us_rates")

        return best
