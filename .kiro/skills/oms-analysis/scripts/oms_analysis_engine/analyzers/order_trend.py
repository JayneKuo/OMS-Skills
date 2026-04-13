"""订单趋势分析"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import Severity


class OrderTrendAnalyzer(BaseAnalyzer):
    name = "订单趋势分析"
    version = "1.0.0"
    intent = "order_trend"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无订单数据")

        daily: dict[str, dict] = defaultdict(lambda: {"total": 0, "exception": 0})
        for o in orders:
            ts = o.get("orderDate") or o.get("createTime")
            if not ts:
                continue
            if isinstance(ts, (int, float)) and ts > 1e12:
                day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            else:
                day = str(ts)[:10]
            daily[day]["total"] += 1
            if str(o.get("status", "")).upper() in ("EXCEPTION", "10"):
                daily[day]["exception"] += 1

        sorted_days = sorted(daily.keys())
        trend = []
        for d in sorted_days:
            total = daily[d]["total"]
            exc = daily[d]["exception"]
            rate = (exc / total * 100) if total > 0 else 0
            trend.append({"date": d, "total": total, "exception": exc, "exception_rate": round(rate, 1)})

        # 连续上升预警
        rates = [t["exception_rate"] for t in trend]
        warning = False
        for i in range(len(rates) - 2):
            if rates[i] < rates[i + 1] < rates[i + 2]:
                warning = True
                break

        evidences = []
        if warning:
            evidences.append(self._build_evidence("statistic", "异常率连续 3 天上升"))

        recs = []
        if warning:
            recs.append(Recommendation(action="排查异常率上升原因", priority="high"))

        return self._make_result(
            success=True,
            summary=f"共 {len(sorted_days)} 天数据，{'⚠️ 异常率连续上升' if warning else '趋势正常'}",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.MAJOR if warning else None,
            recommendations=recs,
            details={"daily_trend": trend, "consecutive_rise_warning": warning},
        )
