"""ShippingPlanWorkflow — 全链路物流方案推荐

流水线：
1. oms_query     → 查订单（SKU、数量、地址、仓库）
2. 构建包裹信息  → 无 SKU 物理数据时用默认重量 0.9kg 估算
3. shipping_rate → 多承运商运费比价（UPS/FedEx/USPS）
4. eta           → 每个承运商方案的 ETA
5. cost          → 综合评分排序
6. 输出          → Top-3 推荐方案 + 白盒解释

每一步失败不阻断后续步骤，降级继续。
"""

from __future__ import annotations

import time
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    OrderSummary,
    PackageSummary,
    PipelineStep,
    PlanSummary,
    ShippingPlanRequest,
    ShippingPlanResult,
)

DEFAULT_WEIGHT_KG = Decimal("0.9")  # 无 SKU 物理数据时的默认重量


def _round2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ms_since(start: float) -> int:
    return int((time.time() - start) * 1000)


class ShippingPlanWorkflow:
    """全链路物流方案推荐 workflow"""

    def run(self, order_no: str, merchant_no: str = "LAN0000002",
            risk_level: str = "P75", carriers: list[str] | None = None) -> ShippingPlanResult:
        req = ShippingPlanRequest(
            order_no=order_no,
            merchant_no=merchant_no,
            risk_level=risk_level,
            carriers=carriers or ["UPS Ground", "FedEx Ground", "USPS Priority"],
        )

        result = ShippingPlanResult()
        steps: list[PipelineStep] = []
        degraded_reasons: list[str] = []

        # ── Step 1: 查订单 ──
        order_summary, step1 = self._step_query_order(req)
        steps.append(step1)
        result.order_summary = order_summary
        if step1.degraded:
            degraded_reasons.append(f"Step1-oms_query: {step1.error or 'degraded'}")

        # ── Step 2: 构建包裹信息 ──
        pkg_summary, step2 = self._step_build_packages(order_summary)
        steps.append(step2)
        result.package_summary = pkg_summary
        if step2.degraded:
            degraded_reasons.append("Step2-packages: 使用默认重量 0.9kg 估算")

        # ── Step 3: 多承运商运费比价 ──
        carrier_rates, step3 = self._step_rate_compare(
            pkg_summary, order_summary, req.carriers,
        )
        steps.append(step3)
        if step3.degraded:
            degraded_reasons.append(f"Step3-shipping_rate: {step3.error or 'degraded'}")

        # ── Step 4: ETA 计算 ──
        carrier_etas, step4 = self._step_eta(
            order_summary, carrier_rates, req.risk_level,
        )
        steps.append(step4)
        if step4.degraded:
            degraded_reasons.append(f"Step4-eta: {step4.error or 'degraded'}")

        # ── Step 5: 综合评分 ──
        plans, step5 = self._step_cost_score(carrier_rates, carrier_etas)
        steps.append(step5)
        if step5.degraded:
            degraded_reasons.append(f"Step5-cost: {step5.error or 'degraded'}")

        # ── Step 6: 构建最终结果 ──
        result.plans = plans[:3]  # Top-3
        result.recommended_plan = plans[0] if plans else None
        result.pipeline_steps = steps
        result.degraded = len(degraded_reasons) > 0
        result.degraded_reasons = degraded_reasons
        result.success = any(s.success for s in steps)
        result.explanation = self._build_explanation(result)

        return result

    # ── Step 1 ──────────────────────────────────────────

    def _step_query_order(self, req: ShippingPlanRequest) -> tuple[OrderSummary, PipelineStep]:
        t0 = time.time()
        summary = OrderSummary(order_no=req.order_no)
        step = PipelineStep(step_name="oms_query")

        try:
            from oms_query_engine.engine_v2 import OMSQueryEngine
            from oms_query_engine.models.request import QueryRequest

            engine = OMSQueryEngine()
            qr = engine.query(QueryRequest(
                identifier=req.order_no,
                query_intent="panorama",
            ))

            # 提取 SKU 信息
            if qr.product_info and qr.product_info.items:
                summary.sku_count = len(qr.product_info.items)
                summary.item_count = sum(i.quantity for i in qr.product_info.items)
                summary.skus = [
                    {"sku": i.sku, "quantity": i.quantity,
                     "weight": i.weight, "name": i.product_name}
                    for i in qr.product_info.items
                ]

            # 提取地址
            if qr.shipping_address:
                summary.dest_country = qr.shipping_address.country or ""
                summary.dest_state = qr.shipping_address.state or ""
                summary.dest_city = qr.shipping_address.city or ""

            # 提取仓库
            if qr.warehouse_info:
                summary.warehouse = qr.warehouse_info.allocated_warehouse or ""

            # 提取状态
            if qr.current_status:
                summary.status = qr.current_status.status_name or ""

            # 尝试从仓库地址推断 origin_state
            origin_state = self._infer_origin_state(qr)
            summary.origin_state = origin_state

            step.success = True
            step.output_summary = (
                f"订单 {req.order_no}: {summary.sku_count} SKU, "
                f"{summary.item_count} 件, 目的地 {summary.dest_state or '未知'}"
            )
        except Exception as e:
            step.success = False
            step.degraded = True
            step.error = str(e)[:200]
            step.output_summary = f"订单查询失败: {step.error}"

        step.duration_ms = _ms_since(t0)
        return summary, step

    def _infer_origin_state(self, qr) -> str:
        """从查询结果推断发货仓所在州"""
        # 尝试从 warehouse_info 获取
        if qr.warehouse_info and qr.warehouse_info.warehouse_address:
            addr = qr.warehouse_info.warehouse_address
            # 地址中可能包含州缩写
            for state in ["CA", "NJ", "TX", "IL", "WA", "GA", "OH", "PA", "NY", "FL"]:
                if state in addr.upper():
                    return state
        # 默认 NJ（美国东部常见仓库位置）
        return "NJ"

    # ── Step 2 ──────────────────────────────────────────

    def _step_build_packages(self, order: OrderSummary) -> tuple[PackageSummary, PipelineStep]:
        t0 = time.time()
        step = PipelineStep(step_name="build_packages")
        pkg = PackageSummary()

        try:
            total_weight = Decimal("0")
            has_real_weight = False

            for sku_info in order.skus:
                w = sku_info.get("weight")
                qty = sku_info.get("quantity", 1)
                if w and float(w) > 0:
                    total_weight += Decimal(str(w)) * Decimal(str(qty))
                    has_real_weight = True
                else:
                    total_weight += DEFAULT_WEIGHT_KG * Decimal(str(qty))

            if total_weight <= 0:
                total_weight = DEFAULT_WEIGHT_KG * max(Decimal(str(order.item_count)), Decimal("1"))

            pkg.package_count = 1
            pkg.total_weight_kg = _round2(total_weight)
            pkg.billing_weight_kg = _round2(total_weight)
            pkg.packages = [{
                "package_id": "PKG-1",
                "billing_weight": str(_round2(total_weight)),
                "actual_weight": str(_round2(total_weight)),
                "item_count": order.item_count,
            }]

            step.success = True
            if not has_real_weight:
                step.degraded = True
                step.output_summary = f"1 包裹, 估算重量 {pkg.billing_weight_kg}kg (默认 {DEFAULT_WEIGHT_KG}kg/件)"
            else:
                step.output_summary = f"1 包裹, 重量 {pkg.billing_weight_kg}kg"
        except Exception as e:
            step.success = False
            step.degraded = True
            step.error = str(e)[:200]
            # 降级：用默认值
            pkg.package_count = 1
            pkg.total_weight_kg = DEFAULT_WEIGHT_KG
            pkg.billing_weight_kg = DEFAULT_WEIGHT_KG
            pkg.packages = [{
                "package_id": "PKG-1",
                "billing_weight": str(DEFAULT_WEIGHT_KG),
                "actual_weight": str(DEFAULT_WEIGHT_KG),
            }]
            step.output_summary = f"包裹构建异常，降级使用默认重量 {DEFAULT_WEIGHT_KG}kg"

        step.duration_ms = _ms_since(t0)
        return pkg, step

    # ── Step 3 ──────────────────────────────────────────

    def _step_rate_compare(
        self,
        pkg: PackageSummary,
        order: OrderSummary,
        carriers: list[str],
    ) -> tuple[dict[str, Decimal], PipelineStep]:
        """多承运商运费比价，返回 {carrier: freight_total}"""
        t0 = time.time()
        step = PipelineStep(step_name="shipping_rate")
        rates: dict[str, Decimal] = {}

        try:
            from shipping_rate_engine.default_us_rates import DefaultUSRateProvider
            from shipping_rate_engine.rate_models import Address, PackageInput

            provider = DefaultUSRateProvider()

            origin = Address(
                province=order.origin_state,
                country="US",
            )
            dest = Address(
                province=order.dest_state,
                city=order.dest_city,
                country=order.dest_country or "US",
            )

            # 取第一个包裹
            p_data = pkg.packages[0] if pkg.packages else {}
            package = PackageInput(
                package_id=p_data.get("package_id", "PKG-1"),
                billing_weight=Decimal(str(p_data.get("billing_weight", "0.9"))),
                actual_weight=Decimal(str(p_data.get("actual_weight", "0.9"))),
            )

            for carrier in carriers:
                r = provider.get_rate(package, origin, dest, carrier)
                if r.success and r.package_rate:
                    rates[carrier] = r.package_rate.freight_total
                else:
                    step.degraded = True

            step.success = len(rates) > 0
            summaries = [f"{c}: ${v}" for c, v in sorted(rates.items(), key=lambda x: x[1])]
            step.output_summary = f"{len(rates)} 承运商报价: " + ", ".join(summaries)
        except Exception as e:
            step.success = False
            step.degraded = True
            step.error = str(e)[:200]
            step.output_summary = f"运费计算失败: {step.error}"

        step.duration_ms = _ms_since(t0)
        return rates, step

    # ── Step 4 ──────────────────────────────────────────

    def _step_eta(
        self,
        order: OrderSummary,
        carrier_rates: dict[str, Decimal],
        risk_level: str,
    ) -> tuple[dict[str, dict], PipelineStep]:
        """为每个承运商计算 ETA，返回 {carrier: {eta_hours, eta_days, on_time_prob}}"""
        t0 = time.time()
        step = PipelineStep(step_name="eta")
        etas: dict[str, dict] = {}

        try:
            from eta_engine.engine import ETAEngine
            from eta_engine.models import ETARequest

            engine = ETAEngine()
            origin = order.origin_state or "NJ"
            dest = order.dest_state or "CA"

            # 承运商名称 → 服务级别映射
            svc_map = {
                "UPS Ground": "Ground",
                "FedEx Ground": "Ground",
                "USPS Priority": "Priority",
            }

            carriers_to_calc = list(carrier_rates.keys()) if carrier_rates else ["UPS Ground", "FedEx Ground", "USPS Priority"]

            for carrier in carriers_to_calc:
                svc = svc_map.get(carrier, "Ground")
                req = ETARequest(
                    origin_state=origin,
                    dest_state=dest,
                    carrier=carrier,
                    service_level=svc,
                    risk_level=risk_level,
                )
                r = engine.calculate(req)
                if r.success:
                    etas[carrier] = {
                        "eta_hours": r.eta_hours,
                        "eta_days": r.eta_days,
                        "on_time_prob": r.on_time_probability,
                        "service_level": svc,
                    }

            step.success = len(etas) > 0
            summaries = [f"{c}: {v['eta_hours']}h" for c, v in etas.items()]
            step.output_summary = f"{len(etas)} 承运商 ETA: " + ", ".join(summaries)
        except Exception as e:
            step.success = False
            step.degraded = True
            step.error = str(e)[:200]
            step.output_summary = f"ETA 计算失败: {step.error}"

        step.duration_ms = _ms_since(t0)
        return etas, step

    # ── Step 5 ──────────────────────────────────────────

    def _step_cost_score(
        self,
        carrier_rates: dict[str, Decimal],
        carrier_etas: dict[str, dict],
    ) -> tuple[list[PlanSummary], PipelineStep]:
        """综合评分排序"""
        t0 = time.time()
        step = PipelineStep(step_name="cost_score")
        plans: list[PlanSummary] = []

        try:
            from cost_engine.engine import CostEngine
            from cost_engine.models import CostRequest, PlanInput

            cost_plans: list[PlanInput] = []
            # 合并 rate + eta 数据
            all_carriers = set(list(carrier_rates.keys()) + list(carrier_etas.keys()))

            for carrier in all_carriers:
                freight = carrier_rates.get(carrier, Decimal("0"))
                eta_info = carrier_etas.get(carrier, {})
                eta_hours = eta_info.get("eta_hours", Decimal("72"))
                on_time_prob = eta_info.get("on_time_prob", Decimal("0.85"))

                cost_plans.append(PlanInput(
                    plan_id=carrier,
                    plan_name=carrier,
                    freight_order=freight,
                    eta_hours=eta_hours,
                    on_time_probability=on_time_prob,
                ))

            if not cost_plans:
                step.success = False
                step.degraded = True
                step.output_summary = "无可评分方案"
                step.duration_ms = _ms_since(t0)
                return plans, step

            engine = CostEngine()
            result = engine.calculate(CostRequest(plans=cost_plans))

            if result.success:
                for pr in result.plans:
                    eta_info = carrier_etas.get(pr.plan_id, {})
                    plans.append(PlanSummary(
                        carrier=pr.plan_id,
                        service_level=eta_info.get("service_level", "Ground"),
                        freight=pr.cost_breakdown.cost_total,
                        eta_hours=pr.eta_hours,
                        eta_days=_round2(pr.eta_hours / Decimal("24")),
                        on_time_prob=pr.on_time_probability,
                        score=pr.score,
                        rank=pr.rank,
                        explanation=pr.explanation,
                    ))

            step.success = len(plans) > 0
            if plans:
                best = plans[0]
                step.output_summary = (
                    f"推荐: {best.carrier} (Score={best.score}, "
                    f"${best.freight}, {best.eta_hours}h)"
                )
        except Exception as e:
            step.success = False
            step.degraded = True
            step.error = str(e)[:200]
            step.output_summary = f"综合评分失败: {step.error}"
            # 降级：仅按运费排序
            plans = self._fallback_sort(carrier_rates, carrier_etas)

        step.duration_ms = _ms_since(t0)
        return plans, step

    def _fallback_sort(
        self,
        carrier_rates: dict[str, Decimal],
        carrier_etas: dict[str, dict],
    ) -> list[PlanSummary]:
        """降级排序：仅按运费从低到高"""
        plans = []
        for i, (carrier, freight) in enumerate(
            sorted(carrier_rates.items(), key=lambda x: x[1]), 1
        ):
            eta_info = carrier_etas.get(carrier, {})
            plans.append(PlanSummary(
                carrier=carrier,
                service_level=eta_info.get("service_level", "Ground"),
                freight=freight,
                eta_hours=eta_info.get("eta_hours", Decimal("0")),
                eta_days=_round2(eta_info.get("eta_hours", Decimal("0")) / Decimal("24")) if eta_info.get("eta_hours") else Decimal("0"),
                on_time_prob=eta_info.get("on_time_prob", Decimal("0")),
                score=Decimal("0"),
                rank=i,
                explanation=f"降级排序（仅按运费）: ${freight}",
            ))
        return plans

    # ── 白盒解释 ────────────────────────────────────────

    def _build_explanation(self, result: ShippingPlanResult) -> str:
        parts = [f"订单 {result.order_summary.order_no} 物流方案推荐"]

        # 流水线状态
        ok = sum(1 for s in result.pipeline_steps if s.success)
        total = len(result.pipeline_steps)
        parts.append(f"流水线: {ok}/{total} 步成功")

        if result.degraded:
            parts.append(f"降级: {', '.join(result.degraded_reasons)}")

        # 推荐方案
        if result.recommended_plan:
            p = result.recommended_plan
            parts.append(
                f"推荐: {p.carrier} | 运费 ${p.freight} | "
                f"ETA {p.eta_hours}h ≈ {p.eta_days}天 | "
                f"准时率 {p.on_time_prob} | Score {p.score}"
            )

        # 备选
        for p in result.plans[1:]:
            parts.append(
                f"备选#{p.rank}: {p.carrier} | ${p.freight} | "
                f"{p.eta_hours}h | Score {p.score}"
            )

        return " | ".join(parts)
