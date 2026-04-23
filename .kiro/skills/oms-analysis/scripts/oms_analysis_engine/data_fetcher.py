"""数据获取层 — 通过 oms_query_engine 获取数据"""
from __future__ import annotations
import random
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.request import AnalysisRequest
from oms_analysis_engine.models.context import AnalysisContext, SamplingInfo

SAMPLING_THRESHOLD = 1000


def flatten_shipping_request(sr: dict) -> dict:
    """将 shipping request 扁平化，合并 orderRespVOList[0] 的字段到顶层。
    
    Shipping request 顶层有: status, statusName, accountingCode, warehouseName, createTime, orderNo
    订单级字段在 orderRespVOList[0] 中: channelName, dataChannel, itemLines, orderDate 等
    """
    flat = dict(sr)
    resp_list = sr.get("orderRespVOList")
    if isinstance(resp_list, list) and resp_list:
        order_info = resp_list[0]
        for key in ("channelName", "dataChannel", "channelSalesOrderNo",
                     "itemLines", "items", "orderDate", "carrierName",
                     "referenceNo", "totalAmount", "qty"):
            if order_info.get(key) and not flat.get(key):
                flat[key] = order_info[key]
    # 去掉嵌套的大对象，减少内存
    flat.pop("orderRespVOList", None)
    flat.pop("orderDispatchVO", None)
    flat.pop("orderDispatchList", None)
    flat.pop("shipmentRespVOList", None)
    return flat


class DataFetcher:
    """通过 oms_query_engine 获取分析所需数据。"""

    def __init__(self, oms_engine=None):
        self._oms = oms_engine
        # Reuse the API client from oms_engine to avoid duplicate token requests
        self._client = None
        if oms_engine and hasattr(oms_engine, '_client'):
            self._client = oms_engine._client

    def _get_client(self):
        """Get or create an API client, ensuring it's authenticated."""
        if not self._client:
            from oms_query_engine.api_client import OMSAPIClient
            from oms_query_engine.config import EngineConfig
            self._client = OMSAPIClient(EngineConfig())
        # Token will be ensured on first API call via get()/post()
        return self._client

    def fetch(self, request: AnalysisRequest,
              analyzers: list[BaseAnalyzer]) -> AnalysisContext:
        needed = set()
        for a in analyzers:
            needed.update(a.required_data)

        ctx = AnalysisContext(request=request)

        _fetch_errors: list[str] = []

        if not self._oms:
            _fetch_errors.append("oms_engine is None, skipping all data fetches")
            return ctx

        # 预热：确保 API client 已认证
        try:
            c = self._get_client()
            c._ensure_token()
        except Exception as e:
            _fetch_errors.append(f"token warmup failed: {e}")

        if "order_data" in needed and request.identifier:
            ctx.order_data = self._fetch_order(request.identifier)

        if "event_data" in needed and request.identifier:
            ctx.event_data = self._fetch_events(request.identifier, request.merchant_no)

        if "inventory_data" in needed:
            ctx.inventory_data = self._fetch_inventory(request.merchant_no)

        if "warehouse_data" in needed:
            ctx.warehouse_data = self._fetch_warehouses(request.merchant_no)

        if "rule_data" in needed:
            ctx.rule_data = self._fetch_rules(request.merchant_no)

        if "batch_orders" in needed:
            try:
                # 优先从订单列表 API 获取（sale-order/page），这是订单级数据
                raw = self._fetch_batch(request.merchant_no, request.filters)
                if not raw:
                    _fetch_errors.append(f"_fetch_batch (sale-order) returned empty, falling back to shipping requests")
                    # 兜底：从 shipping request 获取
                    sr_raw = self._fetch_shipping_requests(request.merchant_no, request.filters)
                    raw = [flatten_shipping_request(sr) for sr in sr_raw]
                # 按时间范围过滤
                if request.time_range and raw:
                    raw = self._filter_by_time(raw, request.time_range)
                ctx.batch_orders = raw
                ctx.batch_orders, sampling = self._apply_sampling(ctx.batch_orders)
                ctx.sampling_info = sampling
            except Exception as e:
                _fetch_errors.append(f"_fetch_batch error: {e}")

        if "shipping_requests" in needed:
            try:
                sr_raw = self._fetch_shipping_requests(request.merchant_no, request.filters)
                raw = [flatten_shipping_request(sr) for sr in sr_raw]
                if request.time_range and raw:
                    raw = self._filter_by_time(raw, request.time_range)
                ctx.batch_orders = raw
                ctx.batch_orders, sampling = self._apply_sampling(ctx.batch_orders)
                ctx.sampling_info = sampling
            except Exception as e:
                _fetch_errors.append(f"_fetch_shipping_requests error: {e}")

        # 总是获取状态统计（轻量级）
        ctx.status_counts = self._fetch_status_counts(request.merchant_no)

        # 补充商品行明细：sale-order/page 不返回 itemLines，需要逐单查详情
        if ctx.batch_orders:
            need_items = [o for o in ctx.batch_orders
                          if not o.get("itemLines") and not o.get("items")]
            if need_items:
                self._enrich_item_lines(need_items[:50], request.merchant_no)

        # 批量模式：batch_orders 获取后，为异常订单抽样获取事件日志
        if "event_data" in needed and not request.identifier and ctx.batch_orders:
            try:
                exc_orders = [o for o in ctx.batch_orders
                              if str(o.get("status", "")).upper() in ("EXCEPTION", "10")]
                sample = exc_orders[:10]
                all_logs = []
                for o in sample:
                    ono = o.get("orderNo", "")
                    if ono:
                        logs = self._fetch_events(ono, request.merchant_no)
                        all_logs.extend(logs)
                ctx.event_data = all_logs
            except Exception as e:
                _fetch_errors.append(f"batch event_data fetch error: {e}")

        # 将获取错误存入 context 供调试
        if _fetch_errors:
            import sys
            print(f"[DataFetcher] errors: {_fetch_errors}", file=sys.stderr)

        return ctx

    def _fetch_order(self, identifier: str) -> dict | None:
        from oms_query_engine.models.request import QueryRequest
        result = self._oms.query(QueryRequest(identifier=identifier, query_intent="panorama"))
        return result.model_dump() if result else None

    def _fetch_events(self, identifier: str, merchant_no: str | None) -> list:
        try:
            c = self._get_client()
            resp = c.get("/api/linker-oms/opc/app-api/orderLog/list",
                         {"merchantNo": merchant_no, "omsOrderNo": identifier})
            data = resp.get("data", resp)
            return _extract_list(data)
        except Exception:
            return []

    def _fetch_inventory(self, merchant_no: str | None) -> list:
        try:
            c = self._get_client()
            resp = c.post("/api/linker-oms/opc/app-api/inventory/list",
                          {"merchantNo": merchant_no})
            return _extract_list(resp.get("data", resp))
        except Exception:
            return []

    def _fetch_warehouses(self, merchant_no: str | None) -> list:
        try:
            c = self._get_client()
            resp = c.post("/api/linker-oms/opc/app-api/facility/v2/page",
                          {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 100})
            return _extract_list(resp.get("data", resp))
        except Exception:
            return []

    def _fetch_rules(self, merchant_no: str | None) -> list:
        try:
            c = self._get_client()
            resp = c.get("/api/linker-oms/opc/app-api/routing/v2/rules",
                         {"merchantNo": merchant_no})
            return _extract_list(resp.get("data", resp))
        except Exception:
            return []

    def _fetch_batch(self, merchant_no: str | None, filters: dict) -> list:
        """获取批量订单数据。从 sale-order/page API 获取，按关键状态分别采样。"""
        c = self._get_client()
        mn = merchant_no

        all_orders = []
        # 先拉一页不带状态过滤的（获取最新订单）
        # 再按关键状态分别采样，确保覆盖异常/Hold/Deallocated 等
        for status_val in [None, 10, 16, 25, 3, 8]:
            params = {"merchantNo": mn, "pageNo": 1, "pageSize": 100}
            if status_val is not None:
                params["status"] = status_val
            params.update(filters)
            try:
                resp = c.get("/api/linker-oms/opc/app-api/sale-order/page", params)
                data = resp.get("data", resp)
                orders = _extract_list(data)
                all_orders.extend(orders)
            except Exception:
                continue

        # 去重
        enriched = []
        seen = set()
        for o in all_orders:
            ono = o.get("orderNo", "")
            if ono in seen:
                continue
            seen.add(ono)
            enriched.append(o)

        return enriched

    def _enrich_item_lines(self, orders: list, merchant_no: str | None) -> None:
        """为缺少 itemLines 的订单逐单查详情补充商品行。"""
        try:
            c = self._get_client()
            for o in orders:
                ono = o.get("orderNo", "")
                if not ono:
                    continue
                try:
                    resp = c.get(f"/api/linker-oms/opc/app-api/sale-order/{ono}")
                    detail = resp.get("data", resp)
                    if isinstance(detail, dict):
                        items = detail.get("itemLines") or detail.get("items") or []
                        if items:
                            o["itemLines"] = items
                        # 顺便补充其他缺失字段
                        for key in ("accountingCode", "warehouseCode", "channelName",
                                    "dataChannel", "carrierName"):
                            if detail.get(key) and not o.get(key):
                                o[key] = detail[key]
                except Exception:
                    continue
        except Exception:
            pass

    @staticmethod
    def _filter_by_time(orders: list, time_range) -> list:
        """按时间范围过滤订单。支持毫秒时间戳和 ISO 字符串。"""
        from datetime import datetime, timezone
        start_ts = time_range.start.timestamp() * 1000  # 转毫秒
        end_ts = time_range.end.timestamp() * 1000

        filtered = []
        for o in orders:
            ts = o.get("orderTime") or o.get("createTime")
            if ts is None:
                filtered.append(o)  # 没有时间字段的保留
                continue
            if isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts)
                    ts = dt.timestamp() * 1000
                except Exception:
                    filtered.append(o)
                    continue
            if start_ts <= ts <= end_ts:
                filtered.append(o)
        return filtered

    @staticmethod
    def _apply_sampling(data: list, threshold: int = SAMPLING_THRESHOLD) -> tuple[list, SamplingInfo | None]:
        if len(data) <= threshold:
            return data, None
        sampled = random.sample(data, threshold)
        return sampled, SamplingInfo(
            total_count=len(data),
            sample_count=threshold,
            sample_ratio=threshold / len(data),
            method="random",
        )

    def _fetch_status_counts(self, merchant_no: str | None) -> dict:
        """获取全局状态统计 + shipping request 状态统计。"""
        result = {}
        mn = merchant_no
        try:
            c = self._get_client()

            # 订单状态统计
            resp = c.get("/api/linker-oms/opc/app-api/sale-order/status/num", {"merchantNo": mn})
            result["order_status"] = resp.get("data") or {}

            # Shipping Request 状态统计
            resp = c.get("/api/linker-oms/opc/app-api/sale-order/shipping/requests/status/num", {"merchantNo": mn})
            result["shipping_request_status"] = resp.get("data") or {}
        except Exception:
            pass
        return result

    def _fetch_shipping_requests(self, merchant_no: str | None, filters: dict) -> list:
        """获取 Shipping Request 列表（带仓库信息）。
        
        多页获取，每页 100（API 最大支持 100），最多 5 页。
        """
        c = self._get_client()
        mn = merchant_no
        all_items: list = []
        page_size = 100
        max_pages = 5

        for page in range(1, max_pages + 1):
            params = {"merchantNo": mn, "pageNo": page, "pageSize": page_size}
            params.update(filters)
            resp = c.get("/api/linker-oms/opc/app-api/sale-order/shipping/requests/page", params)
            data = resp.get("data")
            if data is None:
                break
            items = _extract_list(data)
            if not items:
                break
            all_items.extend(items)
            if len(items) < page_size:
                break

        return all_items


def _extract_list(data) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []
