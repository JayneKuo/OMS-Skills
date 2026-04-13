"""发运异常分析"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import Severity

RETRYABLE_ERRORS = {"timeout", "internal_error", "rate_limit", "temporary"}
PERMANENT_ERRORS = {"invalid_address", "carrier_rejected", "auth_expired", "format_error"}


class ShipmentExceptionAnalyzer(BaseAnalyzer):
    name = "发运异常分析"
    version = "1.0.0"
    intent = "shipment_exception"
    required_data = ["order_data", "event_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        order = context.order_data or {}
        evidences = []
        retryable = None

        for evt in context.event_data:
            etype = str(evt.get("eventType", "")).lower()
            if any(w in etype for w in ["ship", "label", "sync", "tracking"]):
                desc = evt.get("description", "")
                evidences.append(self._build_evidence("event", desc or etype))
                retryable = self._check_retryable(desc)

        recs = []
        if retryable is True:
            recs.append(Recommendation(action="重试发运操作", priority="medium"))
        elif retryable is False:
            recs.append(Recommendation(action="修正数据后重新发运", priority="high",
                                       risk="需要人工确认修正内容"))

        return self._make_result(
            success=True,
            summary="发运链路异常" if evidences else "未发现发运异常",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.MAJOR if evidences else None,
            recommendations=recs,
            details={"retryable": retryable},
        )

    @staticmethod
    def _check_retryable(error_text: str) -> bool | None:
        text = error_text.lower()
        if any(e in text for e in RETRYABLE_ERRORS):
            return True
        if any(e in text for e in PERMANENT_ERRORS):
            return False
        return None
