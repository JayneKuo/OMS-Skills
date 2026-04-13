"""BaseAnalyzer 接口"""
from __future__ import annotations
from abc import ABC, abstractmethod

from oms_analysis_engine.models.enums import Confidence, DataCompleteness
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Evidence


class BaseAnalyzer(ABC):
    """所有 Analyzer 的基类。"""

    name: str = "base"
    version: str = "1.0.0"
    intent: str = ""
    required_data: list[str] = []

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        ...

    def _build_evidence(self, source: str, description: str,
                        data: dict | None = None) -> Evidence:
        return Evidence(source=source, description=description, data=data)

    def _assess_confidence(self, evidences: list[Evidence]) -> Confidence:
        if not evidences:
            return Confidence.LOW
        high_sources = {"status", "rule", "business_field"}
        high_count = sum(1 for e in evidences if e.source in high_sources)
        if high_count >= 2:
            return Confidence.HIGH
        if high_count >= 1 or len(evidences) >= 2:
            return Confidence.MEDIUM
        return Confidence.LOW

    def _assess_data_completeness(self, context: AnalysisContext,
                                  required_fields: list[str]) -> DataCompleteness:
        if not required_fields:
            return DataCompleteness.COMPLETE
        present = sum(1 for f in required_fields if context.has_data(f))
        ratio = present / len(required_fields)
        if ratio >= 0.9:
            return DataCompleteness.COMPLETE
        if ratio >= 0.5:
            return DataCompleteness.PARTIAL
        return DataCompleteness.INSUFFICIENT

    def _make_result(self, **kwargs) -> AnalysisResult:
        kwargs.setdefault("analyzer_name", self.name)
        kwargs.setdefault("analyzer_version", self.version)
        return AnalysisResult(**kwargs)
