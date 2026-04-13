"""EventProvider - 日志/时间线/拆单详情"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.event import EventInfo, MilestoneTimes, DurationMetrics
from .base import BaseProvider

ORDER_LOGS = "/api/linker-oms/opc/app-api/orderLog/list"
TIMELINE = "/api/linker-oms/opc/app-api/payment/time-line/{orderNo}"
DISPATCH_LOG = "/api/linker-oms/oas/rpc-api/dispatch-log/{eventId}"


class EventProvider(BaseProvider):
    """时间线、日志、异常事件、拆单详情。"""

    name = "event"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        order_no = context.order_no or context.primary_key
        merchant_no = context.merchant_no or "LAN0000002"

        logs_data = None
        timeline_data = None
        dispatch_data = None

        # 1. 日志列表
        if order_no:
            try:
                resp = self._fetch_get(
                    ORDER_LOGS, f"logs:{order_no}", QueryCache.TTL_ORDER,
                    params={"merchantNo": merchant_no, "omsOrderNo": order_no},
                )
                logs_data = self._get_data(resp)
                result.called_apis.append(ORDER_LOGS)
            except Exception as e:
                result.failed_apis.append(ORDER_LOGS)
                result.errors.append(f"orderLog: {e}")

        # 2. 时间线（按需）
        if order_no and "timeline" in context.intents:
            try:
                resp = self._fetch_get(
                    TIMELINE.format(orderNo=order_no),
                    f"timeline:{order_no}", QueryCache.TTL_ORDER,
                )
                timeline_data = self._get_data(resp)
                result.called_apis.append(TIMELINE.format(orderNo=order_no))
            except Exception as e:
                result.failed_apis.append("timeline")
                result.errors.append(f"timeline: {e}")

        # 3. 拆单详情（按需，需要 eventId）
        for eid in context.event_ids:
            try:
                resp = self._fetch_get(
                    DISPATCH_LOG.format(eventId=eid),
                    f"dispatch_log:{eid}", QueryCache.TTL_ORDER,
                )
                dispatch_data = self._get_data(resp)
                result.called_apis.append(DISPATCH_LOG.format(eventId=eid))
            except Exception as e:
                result.failed_apis.append(f"dispatch-log:{eid}")
                result.errors.append(f"dispatch-log: {e}")

        # 组装
        logs = _extract_log_list(logs_data)
        latest = logs[0] if logs else {}

        # 提取异常事件
        latest_exception = None
        for log in logs:
            if str(log.get("eventType", "")).lower() == "exception":
                latest_exception = log.get("description")
                break

        event_info = EventInfo(
            timeline=timeline_data if isinstance(timeline_data, list) else None,
            latest_event_type=latest.get("eventType"),
            latest_event_time=_format_timestamp(latest.get("eventTime")),
            latest_exception_event=latest_exception,
            order_logs=logs or None,
        )

        result.success = True
        result.data = {
            "event_info": event_info,
            "raw_logs": logs,
            "raw_dispatch": dispatch_data,
        }
        return result


def _extract_log_list(data) -> list:
    """从各种格式的 API 返回中提取日志列表。"""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # 尝试多种 key：list, records, data
        for key in ("list", "records", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


def _format_timestamp(ts) -> str | None:
    """将毫秒时间戳转为可读字符串。"""
    if ts is None:
        return None
    if isinstance(ts, (int, float)) and ts > 1000000000000:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(ts)
