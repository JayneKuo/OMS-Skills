"""跨维度关联分析"""
from __future__ import annotations
from collections import defaultdict
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, ChartSpec


class CrossDimensionAnalyzer(BaseAnalyzer):
    name = "跨维度关联分析"
    version = "1.0.0"
    intent = "cross_dimension"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无批量数据")

        # 按 仓库×渠道 交叉统计异常率
        cross: dict[tuple, dict] = defaultdict(lambda: {"total": 0, "exception": 0})
        for o in orders:
            wh = o.get("accountingCode") or o.get("warehouseCode") or "unknown"
            ch = o.get("channelName") or o.get("dataChannel") or "unknown"
            key = (wh, ch)
            cross[key]["total"] += 1
            if str(o.get("status", "")).upper() in ("EXCEPTION", "10"):
                cross[key]["exception"] += 1

        resonances = []
        evidences = []
        for (wh, ch), stats in cross.items():
            if stats["total"] < 3:
                continue
            rate = stats["exception"] / stats["total"] * 100
            if rate > 30:
                resonances.append({
                    "warehouse": wh, "channel": ch,
                    "total": stats["total"], "exception": stats["exception"],
                    "cross_exception_rate": round(rate, 1),
                })
                evidences.append(self._build_evidence(
                    "statistic",
                    f"仓库 {wh} + 渠道 {ch} 交叉异常率 {rate:.0f}%（{stats['exception']}/{stats['total']}）",
                ))

        return self._make_result(
            success=True,
            summary=f"发现 {len(resonances)} 个维度共振" if resonances else "未发现显著维度共振",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            details={"resonances": resonances},
            charts=[
                ChartSpec(
                    chart_id="warehouse_channel_exception_heatmap",
                    title="Warehouse × Channel Exception Heatmap",
                    chart_type="heatmap",
                    data=resonances,
                    x_key="warehouse",
                    y_keys=["cross_exception_rate"],
                    category_key="channel",
                    value_key="cross_exception_rate",
                    unit="%",
                ),
            ],
        )
