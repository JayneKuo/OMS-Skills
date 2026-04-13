"""ObjectResolver - 多对象标识识别器（升级自 IdentifierResolver）"""
from __future__ import annotations

import re

from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.cache import QueryCache
from oms_query_engine.errors import ObjectResolveError
from oms_query_engine.models.resolve import QueryInput, ResolveResult

SEARCH_PATH = "/api/linker-oms/opc/app-api/tracking-assistant/search-order-no"

# 模式匹配规则
ORDER_PATTERN = re.compile(r"^(SO|PO|WO)", re.IGNORECASE)
SHIPMENT_PATTERN = re.compile(r"^SH", re.IGNORECASE)
EVENT_PATTERN = re.compile(r"^evt_|^\d+$")

# API 反查优先级
FALLBACK_ORDER = ["orderNo", "eventId", "shipmentNo", "trackingNo"]


class ObjectResolver:
    """识别输入对象类型并解析主键。"""

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._client = client
        self._cache = cache

    def resolve(self, input_value: str, hint: str | None = None) -> ResolveResult:
        """识别输入类型并解析主键。"""
        qi = QueryInput(input_value=input_value)

        # 1. hint 优先（明确指定对象类型时跳过模式匹配）
        if hint == "connector":
            qi.primary_object_type = "connector"
            qi.resolved_primary_key = input_value
            return ResolveResult(success=True, query_input=qi)
        if hint == "warehouse":
            qi.primary_object_type = "warehouse"
            qi.resolved_primary_key = input_value
            return ResolveResult(success=True, query_input=qi)
        if hint == "sku":
            qi.primary_object_type = "sku"
            qi.resolved_primary_key = input_value
            return ResolveResult(success=True, query_input=qi)
        if hint == "batch":
            qi.primary_object_type = "batch"
            return ResolveResult(success=True, query_input=qi)

        # 2. 模式匹配
        if ORDER_PATTERN.search(input_value):
            qi.identified_type = "orderNo"
            qi.primary_object_type = "order"
            qi.resolved_order_no = input_value
            qi.resolved_primary_key = input_value
            return ResolveResult(success=True, query_input=qi)

        if SHIPMENT_PATTERN.search(input_value):
            qi.identified_type = "shipmentNo"
            qi.primary_object_type = "order"
            return self._api_resolve(qi, ["shipmentNo"])

        if EVENT_PATTERN.search(input_value):
            qi.identified_type = "eventId"
            qi.primary_object_type = "order"
            return self._api_resolve(qi, ["eventId"])

        # 3. 不匹配 → API 反查
        return self._api_resolve(qi, FALLBACK_ORDER)

    def _api_resolve(self, qi: QueryInput, try_types: list[str]) -> ResolveResult:
        """按类型列表依次调用 search-order-no 反查。"""
        tried: list[str] = []
        for id_type in try_types:
            tried.append(id_type)
            try:
                resp = self._client.post(SEARCH_PATH, {
                    "searchType": id_type,
                    "searchValue": qi.input_value,
                })
                data = resp.get("data", {})
                order_nos: list[str] = []
                if isinstance(data, list):
                    for d in data:
                        if isinstance(d, dict):
                            ono = d.get("omsOrderNo") or d.get("orderNo")
                            if ono:
                                order_nos.append(str(ono))
                        elif d:
                            order_nos.append(str(d))
                elif isinstance(data, dict):
                    order_nos = data.get("orderNos", [])
                    if not order_nos and data.get("orderNo"):
                        order_nos = [data["orderNo"]]

                if len(order_nos) == 1:
                    qi.identified_type = id_type
                    qi.primary_object_type = "order"
                    qi.resolved_order_no = order_nos[0]
                    qi.resolved_primary_key = order_nos[0]
                    return ResolveResult(success=True, query_input=qi)
                elif len(order_nos) > 1:
                    qi.identified_type = id_type
                    qi.primary_object_type = "order"
                    return ResolveResult(
                        success=False, query_input=qi, candidates=order_nos,
                    )
            except Exception:
                continue

        err = ObjectResolveError(qi.input_value, tried)
        return ResolveResult(success=False, query_input=qi, error=err.to_dict())
