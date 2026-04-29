"""oms_analysis 结果契约测试"""
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.enums import Confidence, DataCompleteness
from oms_analysis_engine.models.request import AnalysisRequest
from oms_analysis_engine.models.result import AnalysisResult, AnalysisResponse, ChartSpec, Recommendation
from oms_analysis_engine.result_aggregator import ResultAggregator


class TestAnalysisResultContract:
    def test_chart_spec_has_frontend_safe_defaults(self):
        chart = ChartSpec(chart_id="c1", title="Orders", chart_type="line")

        assert chart.data == []
        assert chart.series == []
        assert chart.y_keys == []
        assert chart.description is None

    def test_analysis_response_exposes_frontend_sections(self):
        response = AnalysisResponse()

        assert response.summary == ""
        assert response.metrics == {}
        assert response.charts == []
        assert response.recommendations == []


class TestResultAggregator:
    def test_aggregate_promotes_summary_metrics_charts_and_recommendations(self):
        result = AnalysisResult(
            analyzer_name="trend",
            analyzer_version="1.0",
            summary="近7天订单上升",
            metrics={"orders": 120},
            charts=[ChartSpec(chart_id="trend", title="Trend", chart_type="line")],
            recommendations=[Recommendation(action="继续观察", priority="medium")],
            confidence=Confidence.HIGH,
            data_completeness=DataCompleteness.PARTIAL,
        )

        context = AnalysisContext(request=AnalysisRequest())
        response = ResultAggregator().aggregate([result], context)

        assert response.summary == "近7天订单上升"
        assert response.metrics == {"orders": 120}
        assert len(response.charts) == 1
        assert response.recommendations[0].action == "继续观察"
