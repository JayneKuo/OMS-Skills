"""分析意图识别"""
from __future__ import annotations
from oms_analysis_engine.models.request import AnalysisRequest, AnalysisIntent

INTENT_KEYWORDS: dict[str, list[str]] = {
    "root_cause":          ["异常", "根因", "为什么失败", "exception", "error"],
    "hold_analysis":       ["hold", "拦截", "为什么不动", "暂停"],
    "stuck_order":         ["卡单", "阻塞", "停滞", "卡住", "stuck"],
    "allocation_failure":  ["分仓失败", "没有分仓", "分仓异常", "allocation"],
    "shipment_exception":  ["发运", "标签", "tracking", "同步失败", "shipment"],
    "batch_pattern":       ["批量", "一批", "同类问题", "模式", "pattern"],
    "inventory_health":    ["库存", "缺货", "积压", "可售天数", "inventory"],
    "warehouse_efficiency":["仓库效率", "处理慢", "积压仓", "warehouse"],
    "channel_performance": ["渠道", "平台表现", "channel"],
    "order_trend":         ["趋势", "变化", "恶化", "trend"],
    "sku_sales":           ["销售", "热销", "滞销", "sku"],
    "fix_recommendation":  ["怎么处理", "修复", "建议", "fix"],
    "replenishment":       ["补货", "补多少", "replenish"],
    "impact_assessment":   ["影响", "严重程度", "优先级", "impact"],
    "cross_dimension":     ["关联", "共振", "跨维度", "cross"],
}


class IntentDetector:
    def detect(self, request: AnalysisRequest) -> list[AnalysisIntent]:
        if request.intent:
            return [AnalysisIntent(intent_type=request.intent)]

        if not request.query:
            return []

        text = request.query.lower()
        intents = []
        for intent_type, keywords in INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    intents.append(AnalysisIntent(intent_type=intent_type))
                    break
        return intents
