"""Hold 原因分析"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import HoldSource, Severity


class HoldAnalyzer(BaseAnalyzer):
    name = "Hold 原因分析"
    version = "1.0.0"
    intent = "hold_analysis"
    required_data = ["order_data", "rule_data", "event_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        evidences = []
        order = context.order_data or {}
        status = order.get("current_status", {})

        if not status.get("is_hold"):
            return self._make_result(summary="订单当前不处于 Hold 状态")

        # 识别 Hold 来源
        hold_source = self._identify_source(context)
        source_cn = {"rule": "规则拦截", "manual": "人工暂停", "system": "系统安全拦截"}

        evidences.append(self._build_evidence("status", f"Hold 来源: {source_cn.get(hold_source.value, hold_source.value)}"))

        # 规则命中详情
        hold_rules = []
        for rule_page in context.rule_data:
            if isinstance(rule_page, dict):
                for item in rule_page.get("ruleItems", []):
                    if isinstance(item, dict) and "hold" in str(item.get("ruleName", "")).lower():
                        if item.get("switchOn"):
                            hold_rules.append(item)
                            evidences.append(self._build_evidence(
                                "rule",
                                f"命中规则: {item.get('ruleNameCn') or item.get('ruleName')}",
                            ))

        # Hold 原因
        hold_reason = status.get("hold_reason", "")
        if hold_reason:
            evidences.append(self._build_evidence("log", hold_reason))

        recs = [Recommendation(
            action="检查 Hold 规则条件，确认是否可以解除",
            precondition="确认订单数据满足解除条件",
            risk="解除后订单将继续履约流程",
            priority="high",
        )]

        return self._make_result(
            success=True,
            summary=f"订单被{source_cn.get(hold_source.value, 'Hold')}",
            reason=hold_reason or "命中 Hold 规则",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.MAJOR,
            recommendations=recs,
            details={"hold_source": hold_source.value, "hold_rules": hold_rules},
        )

    @staticmethod
    def _identify_source(context: AnalysisContext) -> HoldSource:
        events = context.event_data
        for evt in events:
            by = str(evt.get("by", "")).lower()
            if by in ("manual", "user", "operator"):
                return HoldSource.MANUAL
            if by in ("system", "security"):
                return HoldSource.SYSTEM
        return HoldSource.RULE
