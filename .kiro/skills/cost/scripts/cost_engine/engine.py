"""Cost Engine — 综合成本计算引擎

实现 Cost_total 公式、Score 公式、容量惩罚、拆单惩罚、归一化、多方案排序。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import (
    CostBreakdown,
    CostRequest,
    CostResult,
    NormalizedScores,
    PlanInput,
    PlanResult,
    ScoreBreakdown,
)


def _round2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_capacity_penalty(utilization: Decimal) -> Decimal:
    """容量惩罚函数（4 个梯度）

    Tier 1: 0%~70%   → 0
    Tier 2: 70%~85%  → (u - 0.70) × 10
    Tier 3: 85%~95%  → 1.5 + (u - 0.85) × 30
    Tier 4: 95%~100% → 4.5 + (u - 0.95) × 100
    """
    u = min(max(utilization, Decimal("0")), Decimal("1"))
    if u <= Decimal("0.70"):
        return Decimal("0")
    elif u <= Decimal("0.85"):
        return _round2((u - Decimal("0.70")) * Decimal("10"))
    elif u <= Decimal("0.95"):
        return _round2(Decimal("1.50") + (u - Decimal("0.85")) * Decimal("30"))
    else:
        return _round2(Decimal("4.50") + (u - Decimal("0.95")) * Decimal("100"))


def calc_split_penalty(n_warehouses: int, unit: Decimal) -> Decimal:
    """拆单惩罚 = (N_warehouses - 1) × split_penalty_unit"""
    if n_warehouses <= 1:
        return Decimal("0")
    return _round2(Decimal(str(n_warehouses - 1)) * unit)


def normalize_min_max_inverse(value: Decimal, min_val: Decimal, max_val: Decimal) -> Decimal:
    """Min-Max 反向归一化（越低越好 → 越高分）

    Normalize(x) = 1 - (x - min) / (max - min)
    当 max == min 时返回 1.0（所有方案相同）
    """
    if max_val == min_val:
        return Decimal("1")
    return _round2(Decimal("1") - (value - min_val) / (max_val - min_val))


def normalize_reference_inverse(value: Decimal, ref_max: Decimal) -> Decimal:
    """参考值反向归一化（越低越好 → 越高分）

    Normalize(x) = 1 - x / ref_max
    用于 PRD 案例中的绝对归一化（成本/100, 时效/max_hours）
    """
    if ref_max <= 0:
        return Decimal("1")
    result = Decimal("1") - value / ref_max
    return _round2(max(result, Decimal("0")))


class CostEngine:
    """综合成本计算引擎"""

    def calculate(self, request: CostRequest) -> CostResult:
        """执行综合成本计算和评分"""
        if not request.plans:
            return CostResult(
                success=False,
                errors=["至少需要一个方案"],
            )

        errors: list[str] = []
        degraded_fields: list[str] = []
        weights = request.weights

        # ── 1. 计算每个方案的 Cost_total ──
        plan_costs: list[tuple[PlanInput, CostBreakdown]] = []
        for plan in request.plans:
            penalty_split = calc_split_penalty(plan.n_warehouses, request.split_penalty_unit)
            penalty_capacity = calc_capacity_penalty(plan.capacity_utilization)

            cost_total = _round2(
                plan.freight_order
                + plan.cost_warehouse
                + plan.cost_transfer
                + penalty_split
                + penalty_capacity
                + plan.cost_risk
            )

            breakdown = CostBreakdown(
                freight_order=_round2(plan.freight_order),
                cost_warehouse=_round2(plan.cost_warehouse),
                cost_transfer=_round2(plan.cost_transfer),
                penalty_split=penalty_split,
                penalty_capacity=penalty_capacity,
                cost_risk=_round2(plan.cost_risk),
                cost_total=cost_total,
            )
            plan_costs.append((plan, breakdown))

        # ── 2. 归一化 ──
        costs = [cb.cost_total for _, cb in plan_costs]
        etas = [p.eta_hours for p, _ in plan_costs]

        # 支持两种归一化模式：
        # 1. 参考值归一化（cost_ref_max / eta_ref_max 指定时）
        # 2. 方案集内 Min-Max 归一化（默认）
        use_ref_cost = request.cost_ref_max is not None
        use_ref_eta = request.eta_ref_max is not None

        cost_min, cost_max = min(costs), max(costs)
        eta_min, eta_max = min(etas), max(etas)

        # ── 3. 计算 Score ──
        plan_results: list[PlanResult] = []
        for plan, cb in plan_costs:
            # 归一化
            if use_ref_cost:
                cost_score = normalize_reference_inverse(cb.cost_total, request.cost_ref_max)
            else:
                cost_score = normalize_min_max_inverse(cb.cost_total, cost_min, cost_max)

            if use_ref_eta:
                eta_score = normalize_reference_inverse(plan.eta_hours, request.eta_ref_max)
            else:
                eta_score = normalize_min_max_inverse(plan.eta_hours, eta_min, eta_max)
            ontime_score = plan.on_time_probability

            # 剩余容量
            if plan.remain_capacity_pct is not None:
                cap_score = plan.remain_capacity_pct
            else:
                cap_score = _round2(Decimal("1") - plan.capacity_utilization)

            normalized = NormalizedScores(
                cost_score=cost_score,
                eta_score=eta_score,
                ontime_score=ontime_score,
                capacity_score=cap_score,
            )

            # 加权
            w_cost = _round2(weights.w_cost * cost_score)
            w_eta = _round2(weights.w_eta * eta_score)
            w_ontime = _round2(weights.w_ontime * ontime_score)
            w_cap = _round2(weights.w_cap * cap_score)
            score = _round2(w_cost + w_eta + w_eta * Decimal("0") + w_ontime + w_cap)
            # 重新精确计算 score 避免上面的冗余
            score = _round2(w_cost + w_eta + w_ontime + w_cap)

            score_bd = ScoreBreakdown(
                normalized=normalized,
                weighted_cost=w_cost,
                weighted_eta=w_eta,
                weighted_ontime=w_ontime,
                weighted_cap=w_cap,
                score=score,
            )

            on_time_risk = plan.on_time_probability < Decimal("0.85")

            plan_results.append(PlanResult(
                plan_id=plan.plan_id,
                plan_name=plan.plan_name,
                cost_breakdown=cb,
                score_breakdown=score_bd,
                score=score,
                eta_hours=plan.eta_hours,
                on_time_probability=plan.on_time_probability,
                on_time_risk=on_time_risk,
            ))

        # ── 4. 排序（Score 降序） ──
        plan_results.sort(key=lambda r: r.score, reverse=True)
        for i, pr in enumerate(plan_results):
            pr.rank = i + 1
            pr.recommended = (i == 0)
            pr.explanation = (
                f"排名 #{pr.rank} | Score={pr.score} | "
                f"Cost={pr.cost_breakdown.cost_total}元 | "
                f"ETA={pr.eta_hours}h | "
                f"OnTimeProb={pr.on_time_probability}"
            )

        recommended_id = plan_results[0].plan_id if plan_results else ""

        explanation_parts = [
            f"共 {len(plan_results)} 个方案",
            f"推荐: {recommended_id}（Score={plan_results[0].score}）" if plan_results else "",
            f"权重: cost={weights.w_cost} eta={weights.w_eta} ontime={weights.w_ontime} cap={weights.w_cap}",
        ]

        return CostResult(
            success=True,
            plans=plan_results,
            recommended_plan_id=recommended_id,
            weights_used=weights,
            degraded=len(degraded_fields) > 0,
            degraded_fields=degraded_fields,
            confidence="high",
            explanation=" | ".join(explanation_parts),
            errors=errors,
        )
