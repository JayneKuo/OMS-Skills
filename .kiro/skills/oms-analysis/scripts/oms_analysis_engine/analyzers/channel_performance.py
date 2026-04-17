"""渠道表现分析 — 含 GMV、客单价、取消率"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult
from oms_analysis_engine.models.enums import Confidence

MIN_SAMPLE = 5


class ChannelPerformanceAnalyzer(BaseAnalyzer):
    name = "渠道表现分析"
    version = "2.0.0"
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
                ch_stats[ch] = {"total": 0, "exception": 0, "completed": 0,
                                "cancelled": 0, "gmv": 0.0, "total_qty": 0}
            ch_stats[ch]["total"] += 1
            st = str(o.get("status", "")).upper()
            if st in ("EXCEPTION", "10"):
                ch_stats[ch]["exception"] += 1
            if st in ("SHIPPED", "CLOSED", "3", "4"):
                ch_stats[ch]["completed"] += 1
            if st in ("CANCELLED", "8", "CANCELLING", "12"):
                ch_stats[ch]["cancelled"] += 1
            amt = o.get("totalAmount") or o.get("total") or 0
            ch_stats[ch]["gmv"] += float(amt) if amt else 0
            qty = o.get("qty") or 0
            ch_stats[ch]["total_qty"] += int(qty) if qty else 0

        evidences = []
        channel_list = []
        total_gmv = sum(s["gmv"] for s in ch_stats.values())

        for ch, s in ch_stats.items():
            total = s["total"]
            exc_rate = (s["exception"] / total * 100) if total > 0 else 0
            comp_rate = (s["completed"] / total * 100) if total > 0 else 0
            cancel_rate = (s["cancelled"] / total * 100) if total > 0 else 0
            aov = (s["gmv"] / total) if total > 0 else 0
            gmv_share = (s["gmv"] / total_gmv * 100) if total_gmv > 0 else 0
            conf = Confidence.LOW if total < MIN_SAMPLE else Confidence.MEDIUM
            channel_list.append({
                "channel": ch,
                "total": total,
                "gmv": round(s["gmv"], 2),
                "gmv_share": round(gmv_share, 1),
                "avg_order_value": round(aov, 2),
                "exception_rate": round(exc_rate, 1),
                "completion_rate": round(comp_rate, 1),
                "cancel_rate": round(cancel_rate, 1),
                "total_qty": s["total_qty"],
                "confidence": conf.value,
            })
            if exc_rate > 15 and total >= MIN_SAMPLE:
                evidences.append(self._build_evidence(
                    "statistic",
                    f"渠道 {ch} 异常率 {exc_rate:.0f}%（{total} 单，GMV ${s['gmv']:,.2f}）",
                ))

        channel_list.sort(key=lambda x: x["gmv"], reverse=True)

        # 汇总
        top_ch = channel_list[0] if channel_list else None
        summary_parts = [f"共 {len(ch_stats)} 个渠道，总 GMV ${total_gmv:,.2f}"]
        if top_ch:
            summary_parts.append(f"最大渠道 {top_ch['channel']}（GMV ${top_ch['gmv']:,.2f}，占 {top_ch['gmv_share']:.0f}%）")

        return self._make_result(
            success=True,
            summary="，".join(summary_parts),
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            metrics={
                "channel_count": len(ch_stats),
                "total_gmv": round(total_gmv, 2),
                "total_orders": sum(s["total"] for s in ch_stats.values()),
            },
            details={"channels": channel_list},
        )
