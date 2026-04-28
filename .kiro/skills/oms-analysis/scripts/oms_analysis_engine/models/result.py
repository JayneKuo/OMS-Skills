"""分析结果模型"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from .enums import Confidence, DataCompleteness, Severity
from .context import SamplingInfo


class Evidence(BaseModel):
    source: str
    description: str
    data: dict | None = None


class Recommendation(BaseModel):
    action: str
    precondition: str | None = None
    risk: str | None = None
    priority: str = "medium"
    expected_effect: str | None = None


class ChartSeries(BaseModel):
    name: str
    data_key: str
    chart_type: str | None = None
    axis: str | None = None


class ChartSpec(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    data: list[dict[str, Any]] = Field(default_factory=list)
    x_key: str | None = None
    y_keys: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    category_key: str | None = None
    value_key: str | None = None
    unit: str | None = None
    description: str | None = None


class AnalysisResult(BaseModel):
    analyzer_name: str
    analyzer_version: str
    success: bool = True
    summary: str = ""
    reason: str = ""
    evidences: list[Evidence] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    data_completeness: DataCompleteness = DataCompleteness.INSUFFICIENT
    severity: Severity | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    charts: list[ChartSpec] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def error_result(cls, analyzer_name: str, analyzer_version: str,
                     error: str) -> AnalysisResult:
        return cls(
            analyzer_name=analyzer_name,
            analyzer_version=analyzer_version,
            success=False,
            summary=f"分析失败: {error}",
            errors=[error],
        )


class AnalysisResponse(BaseModel):
    results: list[AnalysisResult] = Field(default_factory=list)
    overall_severity: Severity | None = None
    overall_confidence: Confidence = Confidence.LOW
    overall_data_completeness: DataCompleteness = DataCompleteness.INSUFFICIENT
    all_recommendations: list[Recommendation] = Field(default_factory=list)
    sampling_info: SamplingInfo | None = None
