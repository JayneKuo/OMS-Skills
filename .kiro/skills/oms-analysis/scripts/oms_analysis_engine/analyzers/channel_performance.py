"""渠道表现分析"""
from __future__ import annotations
from collections import Counter
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult
from oms_analysis_engine.models.enums import Confidence

MIN_SAMPLE = 5


class ChannelPerformanceAnalyzer(BaseAnalyzer):
    name = "渠道表现分析"
    version = "1.0.0"
    intent = "channel_performance"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无订单数据")

        ch_stats: dict[str, dict] = {}
        for o in orders:
            ch = o.get("channelName") or o.get("dataChannel") or "未知"
            if ch not in ch_stats:
                ch_stats[ch] = {"total": 0, "exception": 0, "completed": 0}
            ch_stats[ch]["total"] += 1
            st = str(o.get("status", "")).upper()
            if st in ("EXCEPTION", "10"):
                ch_stats[ch]["exception"] += 1
            if st in ("SHIPPED", "CLOSED", "3", "4"):
                ch_stats[ch]["completed"] += 1

        evidences = []
        channel_list = []
        for ch, stats in ch_stats.items():
            total = stats["total"]
            exc_rate = (stats["exception"] / total * 100) if total > 0 else 0
            comp_rate = (stats["completed"] / total * 100) if total > 0 else 0
            conf = Confidence.LOW if total < MIN_SAMPLE else Confidence.MEDIUM
            channel_list.append({
                "channel": ch, "total": total,
                "exception_rate": round(exc_rate, 1),
                "completion_rate": round(comp_rate, 1),
                "confidence": conf.value,
            })
            if exc_rate > 15 and total >= MIN_SAMPLE:
                evidences.append(self._build_evidence("statistic", f"渠道 {ch} 异常率 {exc_rate:.0f}%（{total} 单）"))

        channel_list.sort(key=lambda x: x["total"], reverse=True)

        return self._make_result(
            success=True,
            summary=f"共 {len(ch_stats)} 个渠道",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            details={"channels": channel_list},
        )
