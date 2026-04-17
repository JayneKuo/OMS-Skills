"""修复建议生成 — 支持单订单和批量场景"""
from __future__ import annotations
from collections import Counter
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import ExceptionCategory

RECOMMENDATION_TEMPLATES = {
    ExceptionCategory.INVENTORY: Recommendation(
        action="补充库存或调整分仓规则允许拆单",
        precondition="确认 SKU 编码和仓库库存数据",
        risk="补货需要时间，期间订单将继续阻塞",
        priority="high",
        expected_effect="解除库存不足导致的分仓/履约异常",
    ),
    ExceptionCategory.RULE: Recommendation(
        action="检查并调整分仓规则配置",
        precondition="确认规则变更不影响其他订单",
        risk="规则变更可能影响全局分仓逻辑",
        priority="high",
        expected_effect="解除规则配置导致的分仓失败",
    ),
    ExceptionCategory.SHIPMENT: Recommendation(
        action="检查发运配置、地址信息和承运商状态",
        precondition="确认承运商服务可用",
        risk="地址修正可能需要客户确认",
        priority="high",
        expected_effect="解除发运链路异常",
    ),
    ExceptionCategory.SYNC: Recommendation(
        action="检查平台连接器认证状态和同步配置",
        precondition="确认平台 API 可用",
        risk="重新认证可能需要平台侧操作",
        priority="medium",
        expected_effect="恢复平台同步功能",
    ),
    ExceptionCategory.SYSTEM: Recommendation(
        action="联系技术支持排查系统错误",
        precondition="收集错误日志和时间点",
        risk="系统问题可能影响多个订单",
        priority="high",
        expected_effect="修复系统级故障",
    ),
}


class FixRecommendationAnalyzer(BaseAnalyzer):
    name = "修复建议生成"
    version = "2.0.0"
    intent = "fix_recommendation"
    required_data = ["order_data", "event_data", "batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        order = context.order_data or {}
        status = order.get("current_status", {})

        # 单订单模式
        if status:
            return self._analyze_single(context, order, status)

        # 批量模式：从 batch_orders + event_data 推断
        if context.batch_orders:
            return self._analyze_batch(context)

        return self._make_result(
            summary="无订单数据，无法生成修复建议",
            recommendations=[Recommendation(action="当前无需修复操作", priority="low")],
        )

    def _analyze_single(self, context, order, status):
        recs = []
        evidences = []
        if status.get("is_exception"):
            reason = status.get("exception_reason", "")
            cat = self._classify(reason)
            template = RECOMMENDATION_TEMPLATES.get(cat)
            if template:
                recs.append(template)
                evidences.append(self._build_evidence("status", f"异常类型: {cat.value}"))
        if status.get("is_hold"):
            recs.append(Recommendation(action="检查 Hold 规则并确认解除条件", priority="high"))
            evidences.append(self._build_evidence("status", "订单处于 Hold 状态"))
        if not recs:
            recs.append(Recommendation(action="当前无需修复操作", priority="low"))
        return self._make_result(
            success=True, summary=f"生成 {len(recs)} 条修复建议",
            evidences=evidences, confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, ["order_data"]),
            recommendations=recs,
        )

    def _analyze_batch(self, context):
        """从批量订单和事件日志中归纳修复建议。"""
        evidences = []
        recs = []
        category_counter = Counter()

        # 从事件日志中提取异常类型
        for evt in (context.event_data or []):
            sub = str(evt.get("eventSubType", "")).lower()
            desc = evt.get("description", "")
            if sub == "inventoryshort" or "out of stock" in desc.lower():
                category_counter[ExceptionCategory.INVENTORY] += 1
            elif sub in ("labelfailed",) or "label" in desc.lower():
                category_counter[ExceptionCategory.SHIPMENT] += 1
            elif "sync" in sub or "auth" in sub:
                category_counter[ExceptionCategory.SYNC] += 1
            elif "rule" in sub:
                category_counter[ExceptionCategory.RULE] += 1
            elif sub and sub != "systemerror":
                category_counter[ExceptionCategory.SYSTEM] += 1

        # 如果事件日志没数据，从订单的 product 字段推断
        if not category_counter:
            exc_orders = [o for o in context.batch_orders
                          if str(o.get("status", "")).upper() in ("EXCEPTION", "10")]
            if exc_orders:
                evidences.append(self._build_evidence(
                    "statistic", f"共 {len(exc_orders)} 单异常订单"))
                # 默认建议
                recs.append(Recommendation(
                    action="逐单排查异常订单的事件日志，确定具体失败原因",
                    priority="high",
                ))

        # 按异常类型生成建议
        for cat, count in category_counter.most_common():
            template = RECOMMENDATION_TEMPLATES.get(cat)
            if template:
                # 定制化建议，加上数量信息
                recs.append(Recommendation(
                    action=f"（涉及 {count} 条异常记录）{template.action}",
                    precondition=template.precondition,
                    risk=template.risk,
                    priority=template.priority,
                    expected_effect=template.expected_effect,
                ))
                cat_cn = {"inventory": "库存不足", "rule": "规则问题",
                          "shipment": "发运问题", "sync": "同步问题",
                          "system": "系统错误"}.get(cat.value, cat.value)
                evidences.append(self._build_evidence(
                    "business_field", f"{count} 条异常记录归类为「{cat_cn}」"))

        if not recs:
            recs.append(Recommendation(action="当前无需修复操作", priority="low"))

        return self._make_result(
            success=True,
            summary=f"基于批量异常数据生成 {len(recs)} 条修复建议",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, ["batch_orders", "event_data"]),
            recommendations=recs,
        )

    @staticmethod
    def _classify(error_text: str) -> ExceptionCategory:
        text = error_text.lower()
        if any(w in text for w in ["stock", "inventory", "缺货", "库存"]):
            return ExceptionCategory.INVENTORY
        if any(w in text for w in ["rule", "规则"]):
            return ExceptionCategory.RULE
        if any(w in text for w in ["ship", "carrier", "label", "address"]):
            return ExceptionCategory.SHIPMENT
        if any(w in text for w in ["sync", "auth", "同步"]):
            return ExceptionCategory.SYNC
        return ExceptionCategory.SYSTEM
