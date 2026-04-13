"""订单全景查询引擎 - 查询编排器"""

from __future__ import annotations

import re

from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.cache import QueryCache
from oms_query_engine.errors import AuthenticationError, OrderNotFoundError
from oms_query_engine.models import CoreQueryResult, ExtendedQueryResult

# ── API 路径常量 ──────────────────────────────────────────

SEARCH_PATH = "/api/linker-oms/opc/app-api/tracking-assistant/search-order-no"
ORDER_DETAIL = "/api/linker-oms/opc/app-api/sale-order/{orderNo}"
ORDER_LOGS = "/api/linker-oms/opc/app-api/orderLog/list"
TRACKING_DETAIL = "/api/linker-oms/opc/app-api/tracking-assistant/{orderNo}"
FULFILLMENT_ORDERS = "/api/linker-oms/opc/app-api/tracking-assistant/fulfillment-orders/{orderNo}"
TRACKING_STATUS = "/api/linker-oms/opc/app-api/tracking-assistant/tracking-status/{orderNo}"
WAREHOUSE_LIST = "/api/linker-oms/opc/app-api/facility/v2/page"
DEALLOCATE_QUERY = "/api/linker-oms/opc/app-api/dispatch/recover/query/{orderNo}"
ROUTING_RULES = "/api/linker-oms/opc/app-api/routing/v2/rules"
CUSTOM_RULES = "/api/linker-oms/opc/app-api/routing/v2/custom-rule"
SKU_WAREHOUSE = "/api/linker-oms/opc/app-api/sku-warehouse/page"
INVENTORY_LIST = "/api/linker-oms/opc/app-api/inventory/list"
HOLD_RULES = "/api/linker-oms/opc/app-api/hold-rule-data/page"
TIMELINE = "/api/linker-oms/opc/app-api/payment/time-line/{orderNo}"

# ── 意图关键词映射 ────────────────────────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "shipment":  ["shipment", "追踪", "发运"],
    "warehouse": ["仓库", "分仓"],
    "rule":      ["规则", "策略"],
    "inventory": ["库存"],
    "hold":      ["hold", "暂停"],
    "timeline":  ["时间线", "事件"],
    "panorama":  ["全景"],
}


# ── 意图 → 扩展 API 映射 ─────────────────────────────────

INTENT_API_MAP: dict[str, list[str]] = {
    "shipment":  ["tracking_detail", "fulfillment_orders", "tracking_status"],
    "warehouse": ["warehouse_list", "deallocate_query"],
    "rule":      ["routing_rules", "custom_rules", "sku_warehouse"],
    "inventory": ["inventory_list"],
    "hold":      ["hold_rules"],
    "timeline":  ["order_timeline"],
}

ALL_EXTENDED_APIS = list({
    api for apis in INTENT_API_MAP.values() for api in apis
})


class QueryOrchestrator:
    """根据用户意图决定调用哪些 API，执行核心查询和扩展查询。"""

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._client = client
        self._cache = cache

    # ── 意图检测 ──────────────────────────────────────

    def detect_intents(self, query_intent: str) -> list[str]:
        """从用户查询意图字符串中检测需要的扩展查询类别。"""
        text = query_intent.lower()
        intents: list[str] = []
        for intent, keywords in INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    intents.append(intent)
                    break
        # panorama → 全部扩展
        if "panorama" in intents:
            return ["panorama"]
        return intents

    # ── 核心查询 ──────────────────────────────────────

    def execute_core(self, order_no: str,
                     merchant_no: str = "LAN0000002") -> CoreQueryResult:
        """执行核心查询：search + sale-order + orderLog。"""
        result = CoreQueryResult()
        called: list[str] = []

        # 1. search-order-no
        cache_key = f"search:{order_no}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            result.search_result = cached
        else:
            try:
                resp = self._client.post(SEARCH_PATH, {
                    "searchType": "orderNo",
                    "searchValue": order_no,
                })
                result.search_result = resp
                self._cache.set(cache_key, resp, QueryCache.TTL_ORDER)
                called.append(SEARCH_PATH)
            except AuthenticationError:
                raise
            except Exception as e:
                result.errors.append(f"search-order-no: {e}")

        # 2. sale-order detail
        cache_key = f"detail:{order_no}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            result.order_detail = cached
        else:
            try:
                path = ORDER_DETAIL.format(orderNo=order_no)
                resp = self._client.get(path)
                result.order_detail = resp
                self._cache.set(cache_key, resp, QueryCache.TTL_ORDER)
                called.append(path)
            except AuthenticationError:
                raise
            except Exception as e:
                # 404 → OrderNotFoundError
                if "404" in str(e):
                    raise OrderNotFoundError(order_no)
                result.errors.append(f"sale-order: {e}")

        # 3. orderLog
        cache_key = f"logs:{order_no}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            result.order_logs = cached
        else:
            try:
                resp = self._client.get(ORDER_LOGS, {
                    "merchantNo": merchant_no,
                    "omsOrderNo": order_no,
                })
                result.order_logs = resp
                self._cache.set(cache_key, resp, QueryCache.TTL_ORDER)
                called.append(ORDER_LOGS)
            except AuthenticationError:
                raise
            except Exception as e:
                result.errors.append(f"orderLog: {e}")

        result.success = result.order_detail is not None
        return result

    # ── 扩展查询 ──────────────────────────────────────

    def execute_extended(self, order_no: str, intents: list[str],
                         core_result: CoreQueryResult,
                         merchant_no: str = "LAN0000002",
                         ) -> ExtendedQueryResult:
        """根据意图执行扩展查询，缓存命中时跳过 API 调用。"""
        ext = ExtendedQueryResult()

        # 确定需要调用的 API 集合
        if "panorama" in intents:
            apis_needed = set(ALL_EXTENDED_APIS)
        else:
            apis_needed: set[str] = set()
            for intent in intents:
                apis_needed.update(INTENT_API_MAP.get(intent, []))

        api_handlers = {
            "tracking_detail": lambda: self._fetch_get(
                TRACKING_DETAIL.format(orderNo=order_no),
                f"tracking:{order_no}", QueryCache.TTL_ORDER),
            "fulfillment_orders": lambda: self._fetch_get(
                FULFILLMENT_ORDERS.format(orderNo=order_no),
                f"fulfillment:{order_no}", QueryCache.TTL_ORDER),
            "tracking_status": lambda: self._fetch_get(
                TRACKING_STATUS.format(orderNo=order_no),
                f"track_status:{order_no}", QueryCache.TTL_ORDER),
            "warehouse_list": lambda: self._fetch_post(
                WAREHOUSE_LIST,
                {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 100},
                "warehouses", QueryCache.TTL_STATIC),
            "deallocate_query": lambda: self._fetch_get(
                DEALLOCATE_QUERY.format(orderNo=order_no),
                f"dealloc:{order_no}", QueryCache.TTL_ORDER),
            "routing_rules": lambda: self._fetch_get(
                ROUTING_RULES,
                f"routing_rules:{merchant_no}", QueryCache.TTL_STATIC,
                params={"merchantNo": merchant_no}),
            "custom_rules": lambda: self._fetch_get(
                CUSTOM_RULES,
                f"custom_rules:{merchant_no}", QueryCache.TTL_STATIC,
                params={"merchantNo": merchant_no}),
            "sku_warehouse": lambda: self._fetch_get(
                SKU_WAREHOUSE,
                f"sku_wh:{merchant_no}", QueryCache.TTL_STATIC,
                params={"merchantNo": merchant_no}),
            "inventory_list": lambda: self._fetch_post(
                INVENTORY_LIST,
                {"merchantNo": merchant_no},
                f"inventory:{merchant_no}", QueryCache.TTL_STATIC),
            "hold_rules": lambda: self._fetch_get(
                HOLD_RULES,
                f"hold_rules:{merchant_no}", QueryCache.TTL_STATIC,
                params={"merchantNo": merchant_no}),
            "order_timeline": lambda: self._fetch_get(
                TIMELINE.format(orderNo=order_no),
                f"timeline:{order_no}", QueryCache.TTL_ORDER),
        }

        field_map = {
            "tracking_detail": "tracking_detail",
            "fulfillment_orders": "fulfillment_orders",
            "tracking_status": "tracking_status",
            "warehouse_list": "warehouse_list",
            "deallocate_query": "deallocate_info",
            "routing_rules": "routing_rules",
            "custom_rules": "custom_rules",
            "sku_warehouse": "sku_warehouse_rules",
            "inventory_list": "inventory",
            "hold_rules": "hold_rules",
            "order_timeline": "timeline",
        }

        for api_name in apis_needed:
            handler = api_handlers.get(api_name)
            if not handler:
                continue
            field = field_map.get(api_name)
            try:
                data, path = handler()
                if field:
                    setattr(ext, field, data)
                ext.called_apis.append(api_name)
            except Exception as e:
                ext.failed_apis.append(api_name)

        return ext

    # ── 内部辅助 ──────────────────────────────────────

    def _fetch_get(self, path: str, cache_key: str, ttl: int,
                   params: dict | None = None) -> tuple[dict, str]:
        """GET 请求 + 缓存。"""
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached, path
        resp = self._client.get(path, params=params)
        self._cache.set(cache_key, resp, ttl)
        return resp, path

    def _fetch_post(self, path: str, data: dict,
                    cache_key: str, ttl: int) -> tuple[dict, str]:
        """POST 请求 + 缓存。"""
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached, path
        resp = self._client.post(path, data)
        self._cache.set(cache_key, resp, ttl)
        return resp, path
