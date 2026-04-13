"""订单全景查询引擎 - 标识解析器"""

from __future__ import annotations

import re

from order_query_engine.api_client import OMSAPIClient
from order_query_engine.cache import QueryCache
from order_query_engine.errors import IdentifierResolveError
from order_query_engine.models import QueryInput, ResolveResult

# API 路径
SEARCH_PATH = "/api/linker-oms/opc/app-api/tracking-assistant/search-order-no"

# 模式匹配规则
PATTERNS: dict[str, re.Pattern] = {
    "orderNo": re.compile(r"^(SO|PO|WO)", re.IGNORECASE),
    "shipmentNo": re.compile(r"^SH", re.IGNORECASE),
    "eventId": re.compile(r"^evt_|^\d+$"),
}

# API 反查优先级
FALLBACK_ORDER = ["orderNo", "eventId", "shipmentNo", "trackingNo"]


class IdentifierResolver:
    """识别输入标识类型并解析为 orderNo。"""

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._client = client
        self._cache = cache

    def resolve(self, input_value: str) -> ResolveResult:
        """解析标识为 orderNo。"""
        qi = QueryInput(input_value=input_value)

        # 1. 正则模式匹配
        for id_type, pattern in PATTERNS.items():
            if pattern.search(input_value):
                qi.identified_type = id_type
                if id_type == "orderNo":
                    qi.resolved_order_no = input_value
                    return ResolveResult(success=True, query_input=qi)
                # shipmentNo / eventId → 需要 API 反查
                return self._api_resolve(qi, [id_type])

        # 2. 不匹配任何模式 → 按优先级依次 API 反查
        return self._api_resolve(qi, FALLBACK_ORDER)

    def _api_resolve(self, qi: QueryInput,
                     try_types: list[str]) -> ResolveResult:
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
                # 兼容多种返回格式
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
                    qi.resolved_order_no = order_nos[0]
                    return ResolveResult(success=True, query_input=qi)
                elif len(order_nos) > 1:
                    qi.identified_type = id_type
                    return ResolveResult(
                        success=False, query_input=qi,
                        candidates=order_nos,
                    )
            except Exception:
                continue

        # 全部失败
        err = IdentifierResolveError(qi.input_value, tried)
        return ResolveResult(
            success=False, query_input=qi, error=err.to_dict(),
        )
