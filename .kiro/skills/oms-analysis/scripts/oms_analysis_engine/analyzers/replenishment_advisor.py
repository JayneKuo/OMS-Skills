"""补货建议生成"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation, ChartSpec, ChartSeries
from oms_analysis_engine.models.enums import Urgency, Severity

DEFAULT_TARGET_DAYS = 14


class ReplenishmentAdvisor(BaseAnalyzer):
    name = "补货建议"
    version = "1.0.0"
    intent = "replenishment"
    required_data = ["inventory_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        items = context.inventory_data
        if not items:
            return self._make_result(summary="无库存数据")

        suggestions = []
        urgent_count = 0

        for item in items:
            sku = item.get("sku", "")
            available = item.get("availableQty") or item.get("available") or 0
            daily = item.get("dailyConsumption", 0)

            if daily <= 0:
                continue

            sellable_days = available / daily if daily > 0 else None
            suggested_qty = max(0, DEFAULT_TARGET_DAYS * daily - available)

            if sellable_days is not None and sellable_days < 3:
                urgency = Urgency.URGENT
                urgent_count += 1
            elif sellable_days is not None and sellable_days < 7:
                urgency = Urgency.SUGGESTED
            else:
                urgency = Urgency.OPTIONAL

            if urgency != Urgency.OPTIONAL:
                suggestions.append({
                    "sku": sku,
                    "current_stock": available,
                    "daily_consumption": round(daily, 1),
                    "sellable_days": round(sellable_days, 1) if sellable_days else None,
                    "suggested_qty": int(suggested_qty),
                    "urgency": urgency.value,
                })

        evidences = []
        if urgent_count:
            evidences.append(self._build_evidence("statistic", f"{urgent_count} 个 SKU 需要紧急补货"))

        recs = []
        for s in suggestions[:5]:
            if s["urgency"] == "urgent":
                recs.append(Recommendation(
                    action=f"紧急补货 {s['sku']}，建议补 {s['suggested_qty']} 件",
                    priority="high",
                ))

        return self._make_result(
            success=True,
            summary=f"共 {len(suggestions)} 个 SKU 需要补货，{urgent_count} 个紧急",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.CRITICAL if urgent_count > 3 else Severity.MAJOR if urgent_count > 0 else None,
            recommendations=recs,
            details={"replenishment_suggestions": suggestions},
            charts=[
                ChartSpec(
                    chart_id="replenishment_suggested_qty",
                    title="Suggested Replenishment Quantity",
                    chart_type="bar",
                    data=sorted(suggestions, key=lambda x: x["suggested_qty"], reverse=True)[:20],
                    x_key="sku",
                    y_keys=["suggested_qty"],
                    series=[ChartSeries(name="Suggested Quantity", data_key="suggested_qty")],
                ),
                ChartSpec(
                    chart_id="replenishment_urgency_distribution",
                    title="Replenishment Urgency Distribution",
                    chart_type="pie",
                    data=[
                        {"urgency": urgency, "count": sum(1 for s in suggestions if s["urgency"] == urgency)}
                        for urgency in sorted({s["urgency"] for s in suggestions})
                    ],
                    category_key="urgency",
                    value_key="count",
                ),
            ],
        )
