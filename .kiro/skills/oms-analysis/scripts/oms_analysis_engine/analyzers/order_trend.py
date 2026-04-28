"""订单趋势分析 — 含 GMV、客单价、取消率、件单比"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation, ChartSpec, ChartSeries
from oms_analysis_engine.models.enums import Severity


class OrderTrendAnalyzer(BaseAnalyzer):
    name = "订单趋势分析"
    version = "2.0.0"
    intent = "order_trend"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无订单数据")

        daily: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "exception": 0, "cancelled": 0,
            "gmv": 0.0, "total_qty": 0,
        })
        for o in orders:
            ts = o.get("orderDate") or o.get("createTime")
            if not ts:
                continue
            if isinstance(ts, (int, float)) and ts > 1e12:
                day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            else:
                day = str(ts)[:10]
            daily[day]["total"] += 1
            st = str(o.get("status", "")).upper()
            if st in ("EXCEPTION", "10"):
                daily[day]["exception"] += 1
            if st in ("CANCELLED", "8", "CANCELLING", "12"):
                daily[day]["cancelled"] += 1
            amt = o.get("totalAmount") or o.get("total") or 0
            daily[day]["gmv"] += float(amt) if amt else 0
            qty = o.get("qty") or 0
            daily[day]["total_qty"] += int(qty) if qty else 0

        sorted_days = sorted(daily.keys())
        trend = []
        for d in sorted_days:
            s = daily[d]
            total = s["total"]
            exc_rate = (s["exception"] / total * 100) if total > 0 else 0
            cancel_rate = (s["cancelled"] / total * 100) if total > 0 else 0
            avg_order_value = (s["gmv"] / total) if total > 0 else 0
            items_per_order = (s["total_qty"] / total) if total > 0 else 0
            trend.append({
                "date": d,
                "total": total,
                "exception": s["exception"],
                "exception_rate": round(exc_rate, 1),
                "cancelled": s["cancelled"],
                "cancel_rate": round(cancel_rate, 1),
                "gmv": round(s["gmv"], 2),
                "avg_order_value": round(avg_order_value, 2),
                "total_qty": s["total_qty"],
                "items_per_order": round(items_per_order, 1),
            })

        # 汇总指标
        total_orders = sum(d["total"] for d in trend)
        total_gmv = sum(d["gmv"] for d in trend)
        total_exc = sum(d["exception"] for d in trend)
        total_cancel = sum(d["cancelled"] for d in trend)
        overall_aov = (total_gmv / total_orders) if total_orders > 0 else 0

        # 连续上升预警
        rates = [t["exception_rate"] for t in trend]
        warning = False
        for i in range(len(rates) - 2):
            if rates[i] < rates[i + 1] < rates[i + 2]:
                warning = True
                break

        evidences = []
        evidences.append(self._build_evidence(
            "statistic",
            f"期间总订单 {total_orders} 单，GMV ${total_gmv:,.2f}，客单价 ${overall_aov:,.2f}",
        ))
        if total_exc > 0:
            evidences.append(self._build_evidence(
                "statistic",
                f"异常 {total_exc} 单（{total_exc/total_orders*100:.1f}%），取消 {total_cancel} 单（{total_cancel/total_orders*100:.1f}%）",
            ))
        if warning:
            evidences.append(self._build_evidence("statistic", "异常率连续 3 天上升"))

        recs = []
        if warning:
            recs.append(Recommendation(action="排查异常率上升原因", priority="high"))

        return self._make_result(
            success=True,
            summary=f"共 {len(sorted_days)} 天，{total_orders} 单，GMV ${total_gmv:,.2f}{'，⚠️ 异常率连续上升' if warning else ''}",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.MAJOR if warning else None,
            recommendations=recs,
            metrics={
                "total_orders": total_orders,
                "total_gmv": round(total_gmv, 2),
                "avg_order_value": round(overall_aov, 2),
                "total_exception": total_exc,
                "total_cancelled": total_cancel,
                "days_count": len(sorted_days),
            },
            details={"daily_trend": trend, "consecutive_rise_warning": warning},
            charts=[
                ChartSpec(
                    chart_id="order_daily_trend",
                    title="Daily Order Trend",
                    chart_type="line",
                    data=trend,
                    x_key="date",
                    series=[
                        ChartSeries(name="Orders", data_key="total"),
                        ChartSeries(name="GMV", data_key="gmv", axis="right"),
                    ],
                    description="Daily order count and GMV trend",
                ),
                ChartSpec(
                    chart_id="order_exception_cancel_rate",
                    title="Exception and Cancel Rate",
                    chart_type="line",
                    data=trend,
                    x_key="date",
                    series=[
                        ChartSeries(name="Exception Rate", data_key="exception_rate"),
                        ChartSeries(name="Cancel Rate", data_key="cancel_rate"),
                    ],
                    unit="%",
                    description="Daily exception and cancel rate",
                ),
            ],
        )
