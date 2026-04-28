"""库存健康分析"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation, ChartSpec, ChartSeries
from oms_analysis_engine.models.enums import InventoryHealthLevel, Severity, Urgency

SAFETY_DAYS = 7
OVERSTOCK_DAYS = 60


class InventoryHealthAnalyzer(BaseAnalyzer):
    name = "库存健康分析"
    version = "1.0.0"
    intent = "inventory_health"
    required_data = ["inventory_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        items = context.inventory_data
        if not items:
            return self._make_result(summary="无库存数据")

        evidences = []
        sku_health = []
        out_of_stock = 0
        low_stock = 0

        for item in items:
            sku = item.get("sku", "")
            available = item.get("availableQty") or item.get("available") or 0
            on_hand = item.get("onHandQty") or item.get("onHand") or 0

            # 简化：无销量数据时用默认日均消耗
            daily_consumption = item.get("dailyConsumption", 0)
            if daily_consumption > 0:
                sellable_days = available / daily_consumption
            elif available == 0:
                sellable_days = 0
            else:
                sellable_days = None  # 无法计算

            if available == 0:
                level = InventoryHealthLevel.OUT_OF_STOCK
                out_of_stock += 1
            elif sellable_days is not None and sellable_days < SAFETY_DAYS:
                level = InventoryHealthLevel.LOW
                low_stock += 1
            elif sellable_days is not None and sellable_days > OVERSTOCK_DAYS:
                level = InventoryHealthLevel.OVERSTOCK
            else:
                level = InventoryHealthLevel.NORMAL

            sku_health.append({
                "sku": sku,
                "available": available,
                "on_hand": on_hand,
                "sellable_days": round(sellable_days, 1) if sellable_days is not None else "无法计算",
                "health_level": level.value,
            })

        if out_of_stock:
            evidences.append(self._build_evidence("statistic", f"{out_of_stock} 个 SKU 缺货"))
        if low_stock:
            evidences.append(self._build_evidence("statistic", f"{low_stock} 个 SKU 低库存"))

        recs = []
        if out_of_stock:
            recs.append(Recommendation(action=f"紧急补货 {out_of_stock} 个缺货 SKU", priority="high"))
        if low_stock:
            recs.append(Recommendation(action=f"建议补货 {low_stock} 个低库存 SKU", priority="medium"))

        return self._make_result(
            success=True,
            summary=f"共 {len(items)} 个 SKU，{out_of_stock} 个缺货，{low_stock} 个低库存",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.CRITICAL if out_of_stock > 5 else Severity.MAJOR if out_of_stock > 0 else Severity.MINOR,
            recommendations=recs,
            metrics={"total_skus": len(items), "out_of_stock": out_of_stock, "low_stock": low_stock},
            details={"sku_health": sku_health[:50]},
            charts=[
                ChartSpec(
                    chart_id="inventory_health_distribution",
                    title="Inventory Health Distribution",
                    chart_type="pie",
                    data=[
                        {"health_level": level, "count": sum(1 for s in sku_health if s["health_level"] == level)}
                        for level in sorted({s["health_level"] for s in sku_health})
                    ],
                    category_key="health_level",
                    value_key="count",
                ),
                ChartSpec(
                    chart_id="inventory_low_stock_top",
                    title="Low Stock SKU Top",
                    chart_type="bar",
                    data=sorted(
                        [s for s in sku_health if isinstance(s["sellable_days"], (int, float))],
                        key=lambda x: x["sellable_days"],
                    )[:20],
                    x_key="sku",
                    y_keys=["available", "sellable_days"],
                    series=[
                        ChartSeries(name="Available", data_key="available"),
                        ChartSeries(name="Sellable Days", data_key="sellable_days", axis="right"),
                    ],
                ),
            ],
        )
