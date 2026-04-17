"""分析意图识别 — 支持意图扩展联动 + 时间范围提取"""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from oms_analysis_engine.models.request import AnalysisRequest, AnalysisIntent, TimeRange

INTENT_KEYWORDS: dict[str, list[str]] = {
    "root_cause":          ["异常", "根因", "为什么失败", "exception", "error"],
    "hold_analysis":       ["hold", "拦截", "为什么不动", "暂停"],
    "stuck_order":         ["卡单", "阻塞", "停滞", "卡住", "stuck"],
    "allocation_failure":  ["分仓失败", "没有分仓", "分仓异常", "allocation"],
    "shipment_exception":  ["发运", "标签", "tracking", "同步失败", "shipment"],
    "batch_pattern":       ["批量", "一批", "同类问题", "模式", "pattern"],
    "inventory_health":    ["库存", "缺货", "积压", "可售天数", "inventory"],
    "warehouse_efficiency":["仓库效率", "处理慢", "积压仓", "warehouse efficiency"],
    "channel_performance": ["渠道", "平台表现", "channel"],
    "order_trend":         ["趋势", "变化", "恶化", "trend"],
    "sku_sales":           ["销售", "热销", "滞销", "sku", "销量"],
    "fix_recommendation":  ["怎么处理", "修复", "建议", "fix"],
    "replenishment":       ["补货", "补多少", "replenish"],
    "impact_assessment":   ["影响", "严重程度", "优先级", "impact"],
    "cross_dimension":     ["关联", "共振", "跨维度", "cross"],
}

# 意图扩展规则：当命中某个意图时，自动追加关联意图
# 格式：{触发意图: [自动追加的意图]}
INTENT_EXPANSION: dict[str, list[str]] = {
    # 异常诊断类：根因 + 影响 + 修复建议 三件套
    "root_cause":         ["impact_assessment", "fix_recommendation"],
    "batch_pattern":      ["impact_assessment", "fix_recommendation"],
    "allocation_failure": ["inventory_health", "fix_recommendation"],
    "shipment_exception": ["fix_recommendation"],
    "hold_analysis":      ["fix_recommendation"],
    "stuck_order":        ["fix_recommendation"],
    # 库存类：库存健康 + 补货建议
    "inventory_health":   ["replenishment"],
}

# 模糊问题模式：当用户问题比较笼统时，自动扩展为多意图组合
FUZZY_PATTERNS: list[tuple[list[str], list[str]]] = [
    # 关键词列表 → 意图组合
    (["为什么", "总是", "exception"],  ["batch_pattern", "impact_assessment", "fix_recommendation"]),
    (["为什么", "异常"],              ["batch_pattern", "impact_assessment", "fix_recommendation"]),
    (["订单", "问题"],               ["batch_pattern", "impact_assessment", "fix_recommendation"]),
    (["整体", "情况"],               ["order_trend", "channel_performance", "inventory_health"]),
    (["运营", "概览"],               ["order_trend", "channel_performance", "warehouse_efficiency"]),
    (["健康", "检查"],               ["inventory_health", "warehouse_efficiency", "order_trend"]),
]


class IntentDetector:
    def detect(self, request: AnalysisRequest) -> list[AnalysisIntent]:
        # 1. 明确指定 intent 时，仍然扩展关联意图
        if request.intent:
            primary = [AnalysisIntent(intent_type=request.intent)]
            return self._expand(primary)

        if not request.query:
            return []

        text = request.query.lower()

        # 2. 先尝试模糊模式匹配（笼统问题）
        fuzzy_intents = self._match_fuzzy(text)
        if fuzzy_intents:
            return fuzzy_intents

        # 3. 关键词匹配
        intents = []
        for intent_type, keywords in INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    intents.append(AnalysisIntent(intent_type=intent_type))
                    break

        # 4. 扩展关联意图
        return self._expand(intents)

    @staticmethod
    def _expand(intents: list[AnalysisIntent]) -> list[AnalysisIntent]:
        """根据扩展规则追加关联意图，去重保序。"""
        seen = set()
        result = []
        for i in intents:
            if i.intent_type not in seen:
                seen.add(i.intent_type)
                result.append(i)
        # 对每个已有意图，追加扩展意图
        for i in list(result):
            for extra in INTENT_EXPANSION.get(i.intent_type, []):
                if extra not in seen:
                    seen.add(extra)
                    result.append(AnalysisIntent(intent_type=extra))
        return result

    @staticmethod
    def _match_fuzzy(text: str) -> list[AnalysisIntent] | None:
        """匹配模糊问题模式，返回预定义的意图组合。"""
        for keywords, intent_types in FUZZY_PATTERNS:
            if all(kw in text for kw in keywords):
                return [AnalysisIntent(intent_type=t) for t in intent_types]
        return None

    @staticmethod
    def extract_time_range(request: AnalysisRequest) -> TimeRange | None:
        """从 request 中提取时间范围。优先用已有的 time_range，否则从 query 中解析。"""
        if request.time_range:
            return request.time_range

        if not request.query:
            return None

        text = request.query.lower()
        now = datetime.now(timezone.utc)

        # "近N天" / "最近N天" / "过去N天"
        m = re.search(r'(?:近|最近|过去)\s*(\d+)\s*天', text)
        if m:
            days = int(m.group(1))
            return TimeRange(start=now - timedelta(days=days), end=now)

        # "近N周" / "最近N周"
        m = re.search(r'(?:近|最近|过去)\s*(\d+)\s*周', text)
        if m:
            weeks = int(m.group(1))
            return TimeRange(start=now - timedelta(weeks=weeks), end=now)

        # "近N个月" / "最近N个月"
        m = re.search(r'(?:近|最近|过去)\s*(\d+)\s*个?月', text)
        if m:
            months = int(m.group(1))
            return TimeRange(start=now - timedelta(days=months * 30), end=now)

        # "本周"
        if "本周" in text:
            weekday = now.weekday()
            start = now - timedelta(days=weekday)
            return TimeRange(start=start.replace(hour=0, minute=0, second=0), end=now)

        # "本月"
        if "本月" in text:
            return TimeRange(start=now.replace(day=1, hour=0, minute=0, second=0), end=now)

        # "上周"
        if "上周" in text:
            weekday = now.weekday()
            end = now - timedelta(days=weekday)
            start = end - timedelta(days=7)
            return TimeRange(
                start=start.replace(hour=0, minute=0, second=0),
                end=end.replace(hour=0, minute=0, second=0),
            )

        # "today" / "今天"
        if "今天" in text or "today" in text:
            return TimeRange(start=now.replace(hour=0, minute=0, second=0), end=now)

        # "last N days"
        m = re.search(r'last\s+(\d+)\s+days?', text)
        if m:
            days = int(m.group(1))
            return TimeRange(start=now - timedelta(days=days), end=now)

        # "7天" / "30天" 单独出现
        m = re.search(r'(\d+)\s*天', text)
        if m:
            days = int(m.group(1))
            if days <= 365:
                return TimeRange(start=now - timedelta(days=days), end=now)

        return None
