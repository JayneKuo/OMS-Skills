"""寻仓推荐引擎 — 结果构建 + 白盒解释 + 降级标记

构建 AllocationResult，生成可读的推荐解释文本，汇总降级标记并计算置信度。
"""

from __future__ import annotations

from .models import (
    Address,
    AllocationResult,
    EliminatedWarehouse,
    FulfillmentPlan,
    OrderItem,
    ScoredWarehouse,
)

# ── MVP 固定降级标记（距离估算模式下始终存在）──────────────

_MVP_DEGRADATION = [
    "cost_estimated=true",
    "eta_estimated=true",
    "weather_not_factored=true",
    "congestion_not_factored=true",
]


class ResultBuilder:
    """结果构建器。

    汇总降级标记、计算置信度、生成白盒解释文本。
    """

    def build(
        self,
        plan: FulfillmentPlan | None,
        alternatives: list[FulfillmentPlan],
        candidates: list[ScoredWarehouse],
        eliminated: list[EliminatedWarehouse],
        degradation: list[str],
        items: list[OrderItem],
        address: Address,
        matched_rules: list[str] | None = None,
    ) -> AllocationResult:
        """构建最终 AllocationResult。"""
        # 1. 追加 MVP 固定降级标记（去重）
        for marker in _MVP_DEGRADATION:
            if marker not in degradation:
                degradation.append(marker)

        # 2. 计算置信度
        confidence = self._compute_confidence(degradation)

        # 3. 生成解释文本
        explanation = self._build_explanation(
            plan, eliminated, items, address, degradation, matched_rules,
        )

        return AllocationResult(
            success=plan is not None,
            recommended_plan=plan,
            alternative_plans=alternatives,
            candidate_warehouses=candidates,
            eliminated_warehouses=eliminated,
            confidence=confidence,
            explanation=explanation,
            data_degradation=degradation,
        )

    # ── 置信度 ────────────────────────────────────────

    @staticmethod
    def _compute_confidence(degradation: list[str]) -> str:
        """根据降级标记数量计算置信度。"""
        count = len(degradation)
        if count == 0:
            return "high"
        elif count <= 3:
            return "medium"
        else:
            return "low"

    # ── 白盒解释 ──────────────────────────────────────

    def _build_explanation(
        self,
        plan: FulfillmentPlan | None,
        eliminated: list[EliminatedWarehouse],
        items: list[OrderItem],
        address: Address,
        degradation: list[str],
        matched_rules: list[str] | None = None,
    ) -> str:
        """根据方案类型生成可读解释文本。"""
        parts = []

        # 命中的规则
        if matched_rules:
            parts.append(f"命中规则：{'、'.join(matched_rules)}")

        if plan is None:
            parts.append(self._explain_failure(eliminated, items))
        elif plan.plan_type == "single_warehouse":
            parts.append(self._explain_single(plan, items, address, degradation))
        else:
            parts.append(self._explain_multi(plan, items, address, degradation))

        return "\n".join(parts)

    def _explain_single(
        self,
        plan: FulfillmentPlan,
        items: list[OrderItem],
        address: Address,
        degradation: list[str],
    ) -> str:
        """单仓直发解释模板。"""
        a = plan.assignments[0]
        sku_desc = "、".join(f"{item.sku} × {item.quantity}" for item in items)
        dest = address.state or address.country

        lines = [
            f"推荐从 {a.warehouse_name}（{a.accounting_code}）发货。",
            f"库存满足：{sku_desc} 均有货。",
            f"距离：距收货地 {dest} 约 {a.distance_km}km，"
            f"预估运费 ${a.estimated_cost}，预估 {a.estimated_days} 天送达。",
        ]

        bd = a.score_breakdown
        lines.append(
            f"综合评分 {a.score:.4f}"
            f"（成本 {bd.get('cost', 0):.2f} + 时效 {bd.get('eta', 0):.2f}"
            f" + 容量 {bd.get('capacity', 0):.2f}）。"
        )

        if degradation:
            lines.append(f"降级说明：{', '.join(degradation)}")

        return "\n".join(lines)

    def _explain_multi(
        self,
        plan: FulfillmentPlan,
        items: list[OrderItem],
        address: Address,
        degradation: list[str],
    ) -> str:
        """多仓拆发解释模板。"""
        n = len(plan.assignments)
        lines = [f"建议拆为 {n} 仓发货："]

        for a in plan.assignments:
            sku_desc = "、".join(f"{item.sku} × {item.quantity}" for item in a.items)
            lines.append(
                f"  {a.warehouse_name}（{a.accounting_code}）发 {sku_desc}，评分 {a.score:.4f}"
            )

        lines.append(f"拆单惩罚 -{plan.split_penalty:.4f}")
        lines.append(f"综合评分 {plan.total_score:.4f}")

        if degradation:
            lines.append(f"降级说明：{', '.join(degradation)}")

        return "\n".join(lines)

    @staticmethod
    def _explain_failure(
        eliminated: list[EliminatedWarehouse],
        items: list[OrderItem],
    ) -> str:
        """失败解释模板。"""
        lines = ["无法推荐发货仓。"]

        if eliminated:
            lines.append(f"{len(eliminated)} 个仓库被淘汰：")
            for ew in eliminated:
                reasons = "、".join(ew.reasons)
                lines.append(f"  - {ew.warehouse_name}：{reasons}")

        lines.append("建议：补充库存 或 调整拆单规则")
        return "\n".join(lines)
