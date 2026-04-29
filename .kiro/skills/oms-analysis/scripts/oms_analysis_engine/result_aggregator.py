"""结果聚合"""
from __future__ import annotations
from oms_analysis_engine.models.enums import Confidence, DataCompleteness, Severity
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, AnalysisResponse, Recommendation, ChartSpec

SEVERITY_ORDER = {Severity.CRITICAL: 3, Severity.MAJOR: 2, Severity.MINOR: 1}
CONFIDENCE_ORDER = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}
COMPLETENESS_ORDER = {DataCompleteness.COMPLETE: 3, DataCompleteness.PARTIAL: 2, DataCompleteness.INSUFFICIENT: 1}


class ResultAggregator:
    def aggregate(self, results: list[AnalysisResult],
                  context: AnalysisContext) -> AnalysisResponse:
        if not results:
            return AnalysisResponse()

        all_recs: list[Recommendation] = []
        merged_metrics: dict = {}
        merged_charts: list[ChartSpec] = []
        summaries: list[str] = []
        max_sev = None
        max_conf = Confidence.LOW
        min_comp = DataCompleteness.COMPLETE

        for r in results:
            all_recs.extend(r.recommendations)
            merged_metrics.update(r.metrics)
            merged_charts.extend(r.charts)
            if r.summary:
                summaries.append(r.summary)
            if r.severity and (max_sev is None or SEVERITY_ORDER.get(r.severity, 0) > SEVERITY_ORDER.get(max_sev, 0)):
                max_sev = r.severity
            if CONFIDENCE_ORDER.get(r.confidence, 0) > CONFIDENCE_ORDER.get(max_conf, 0):
                max_conf = r.confidence
            if COMPLETENESS_ORDER.get(r.data_completeness, 0) < COMPLETENESS_ORDER.get(min_comp, 0):
                min_comp = r.data_completeness

        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_recs.sort(key=lambda r: priority_order.get(r.priority, 9))

        return AnalysisResponse(
            results=results,
            summary="；".join(summaries),
            metrics=merged_metrics,
            charts=merged_charts,
            recommendations=all_recs,
            overall_severity=max_sev,
            overall_confidence=max_conf,
            overall_data_completeness=min_comp,
            all_recommendations=all_recs,
            sampling_info=context.sampling_info,
        )
