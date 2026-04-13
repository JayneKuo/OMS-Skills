"""异常根因分析"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import ExceptionCategory, Severity

ERROR_CATEGORY_MAP = {
    "out_of_stock": ExceptionCategory.INVENTORY,
    "inventory_locked": ExceptionCategory.INVENTORY,
    "inventory_short": ExceptionCategory.INVENTORY,
    "no_matching_rule": ExceptionCategory.RULE,
    "rule_conflict": ExceptionCategory.RULE,
    "warehouse_disabled": ExceptionCategory.WAREHOUSE,
    "capacity_exceeded": ExceptionCategory.WAREHOUSE,
    "label_failed": ExceptionCategory.SHIPMENT,
    "carrier_rejected": ExceptionCategory.SHIPMENT,
    "invalid_address": ExceptionCategory.SHIPMENT,
    "sync_rejected": ExceptionCategory.SYNC,
    "auth_expired": ExceptionCategory.SYNC,
    "timeout": ExceptionCategory.SYSTEM,
    "internal_error": ExceptionCategory.SYSTEM,
}

CATEGORY_CN = {
    ExceptionCategory.INVENTORY: "库存问题",
    ExceptionCategory.RULE: "规则问题",
    ExceptionCategory.WAREHOUSE: "仓库问题",
    ExceptionCategory.SHIPMENT: "发运问题",
    ExceptionCategory.SYNC: "同步问题",
    ExceptionCategory.SYSTEM: "系统问题",
}


class ExceptionRootCauseAnalyzer(BaseAnalyzer):
    name = "异常根因分析"
    version = "1.0.0"
    intent = "root_cause"
    required_data = ["order_data", "event_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        evidences = []
        order = context.order_data or {}
        status = order.get("current_status", {})

        if not status.get("is_exception"):
            return self._make_result(summary="订单当前不处于异常状态")

        # 从日志中提取异常信息
        exception_reason = status.get("exception_reason", "")
        category = self._classify_error(exception_reason)
        category_cn = CATEGORY_CN.get(category, "未知")

        if exception_reason:
            evidences.append(self._build_evidence("log", exception_reason))

        # 从事件日志中补充
        for evt in context.event_data:
            if str(evt.get("eventType", "")).lower() == "exception":
                desc = evt.get("description", "")
                if desc and desc != exception_reason:
                    evidences.append(self._build_evidence("event", desc))
                suggestion = evt.get("suggestion")
                if suggestion:
                    evidences.append(self._build_evidence("event", f"系统建议: {suggestion}"))

        confidence = self._assess_confidence(evidences)
        completeness = self._assess_data_completeness(context, self.required_data)

        recs = []
        if category == ExceptionCategory.INVENTORY:
            recs.append(Recommendation(action="检查并补充库存", priority="high",
                                       expected_effect="解除库存不足导致的异常"))
        elif category == ExceptionCategory.RULE:
            recs.append(Recommendation(action="检查分仓规则配置", priority="high"))
        elif category == ExceptionCategory.SHIPMENT:
            recs.append(Recommendation(action="检查发运配置和地址信息", priority="high"))

        return self._make_result(
            success=True,
            summary=f"异常类型: {category_cn}",
            reason=exception_reason or "无法确定具体原因",
            evidences=evidences,
            confidence=confidence,
            data_completeness=completeness,
            severity=Severity.MAJOR,
            recommendations=recs,
            details={"exception_category": category.value if category else None},
        )

    @staticmethod
    def _classify_error(error_text: str) -> ExceptionCategory:
        text = error_text.lower()
        for keyword, cat in ERROR_CATEGORY_MAP.items():
            if keyword.replace("_", " ") in text or keyword in text:
                return cat
        if any(w in text for w in ["stock", "inventory", "缺货", "库存"]):
            return ExceptionCategory.INVENTORY
        if any(w in text for w in ["rule", "规则"]):
            return ExceptionCategory.RULE
        if any(w in text for w in ["warehouse", "仓库"]):
            return ExceptionCategory.WAREHOUSE
        if any(w in text for w in ["ship", "carrier", "label", "发运", "标签"]):
            return ExceptionCategory.SHIPMENT
        if any(w in text for w in ["sync", "同步", "auth"]):
            return ExceptionCategory.SYNC
        return ExceptionCategory.SYSTEM
