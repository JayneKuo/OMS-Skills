"""QueryPlanBuilder - 查询计划生成器"""
from __future__ import annotations

import re

from oms_query_engine.models.resolve import ResolveResult
from oms_query_engine.models.query_plan import QueryPlan

# 意图关键词 → Provider 映射
INTENT_KEYWORDS: dict[str, list[str]] = {
    "shipment":    ["shipment", "追踪", "发运", "tracking", "carrier"],
    "warehouse":   ["仓库", "分仓", "warehouse"],
    "rule":        ["规则", "策略", "rule"],
    "inventory":   ["库存", "inventory"],
    "hold":        ["hold", "暂停"],
    "timeline":    ["时间线", "事件", "timeline"],
    "fulfillment": ["履约", "仓内", "fulfillment", "包裹"],
    "sync":        ["同步", "回传", "sync"],
    "integration": ["连接器", "渠道", "集成", "connector", "integration", "channel"],
    "panorama":    ["全景", "panorama"],
}

INTENT_PROVIDER_MAP: dict[str, list[str]] = {
    "shipment":    ["shipment"],
    "warehouse":   ["warehouse"],
    "rule":        ["rule"],
    "inventory":   ["inventory"],
    "hold":        ["rule"],
    "timeline":    ["event"],
    "fulfillment": ["fulfillment"],
    "sync":        ["sync"],
    "integration": ["integration"],
}

ALL_EXTENDED = ["shipment", "fulfillment", "warehouse", "allocation",
                "rule", "inventory", "sync", "event"]


class QueryPlanBuilder:
    """根据对象类型和用户意图生成查询计划。"""

    def build(self, resolve_result: ResolveResult,
              query_intent: str) -> QueryPlan:
        qi = resolve_result.query_input
        obj_type = qi.primary_object_type if qi else "order"
        primary_key = qi.resolved_primary_key if qi else None

        # 按对象类型决定核心 Provider
        if obj_type == "connector":
            return QueryPlan(
                primary_object_type="connector",
                primary_key=primary_key,
                core_providers=["integration"],
            )
        if obj_type == "warehouse":
            return QueryPlan(
                primary_object_type="warehouse",
                primary_key=primary_key,
                core_providers=["warehouse"],
            )
        if obj_type == "sku":
            return QueryPlan(
                primary_object_type="sku",
                primary_key=primary_key,
                core_providers=["inventory"],
            )
        if obj_type == "batch":
            return QueryPlan(
                primary_object_type="batch",
                primary_key=primary_key,
                core_providers=["batch"],
            )

        # 订单类：core = order + event
        intents = self._detect_intents(query_intent)
        extended: list[str] = []

        if "panorama" in intents:
            extended = list(ALL_EXTENDED)
        else:
            seen: set[str] = set()
            for intent in intents:
                for provider in INTENT_PROVIDER_MAP.get(intent, []):
                    if provider not in seen:
                        extended.append(provider)
                        seen.add(provider)

        return QueryPlan(
            primary_object_type="order",
            primary_key=primary_key,
            core_providers=["order", "event"],
            extended_providers=extended,
            context={"intents": intents},
        )

    @staticmethod
    def _detect_intents(query_intent: str) -> list[str]:
        """从用户查询意图字符串中检测关键词。"""
        text = query_intent.lower()
        intents: list[str] = []
        for intent, keywords in INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    intents.append(intent)
                    break
        if "panorama" in intents:
            return ["panorama"]
        return intents
