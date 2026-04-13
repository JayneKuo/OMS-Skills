"""OMSAnalysisEngine — 顶层编排器"""
from __future__ import annotations

from oms_analysis_engine.analyzer_registry import AnalyzerRegistry
from oms_analysis_engine.intent_detector import IntentDetector
from oms_analysis_engine.data_fetcher import DataFetcher
from oms_analysis_engine.result_aggregator import ResultAggregator
from oms_analysis_engine.models.request import AnalysisRequest
from oms_analysis_engine.models.result import AnalysisResult, AnalysisResponse


class OMSAnalysisEngine:
    """OMS 运营分析引擎主入口。只负责编排。"""

    def __init__(self, data_fetcher: DataFetcher | None = None):
        self._registry = AnalyzerRegistry()
        self._intent_detector = IntentDetector()
        self._data_fetcher = data_fetcher or DataFetcher()
        self._aggregator = ResultAggregator()
        self._registry.auto_discover()

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        intents = self._intent_detector.detect(request)
        if not intents:
            return AnalysisResponse()

        analyzers = self._registry.resolve(intents)
        if not analyzers:
            return AnalysisResponse()

        context = self._data_fetcher.fetch(request, analyzers)

        results: list[AnalysisResult] = []
        for analyzer in analyzers:
            try:
                result = analyzer.analyze(context)
                results.append(result)
            except Exception as e:
                results.append(AnalysisResult.error_result(
                    analyzer_name=analyzer.name,
                    analyzer_version=analyzer.version,
                    error=str(e),
                ))

        return self._aggregator.aggregate(results, context)

    def list_capabilities(self) -> dict[str, str]:
        return self._registry.list_analyzers()
