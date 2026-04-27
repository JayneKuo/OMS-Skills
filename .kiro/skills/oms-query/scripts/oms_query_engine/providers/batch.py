"""BatchProvider - 批量统计（独立于单单查询链路）"""
from __future__ import annotations

from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.batch import BatchQueryResult
from .base import BaseProvider

STATUS_NUM = "/opc/app-api/sale-order/status/num"
ORDER_PAGE = "/opc/app-api/sale-order/page"


class BatchProvider(BaseProvider):
    """批量统计、列表查询。独立于单单查询链路。"""

    name = "batch"

    def query_status_count(self, merchant_no: str) -> BatchQueryResult:
        """状态统计。"""
        resp = self._client.get(STATUS_NUM, {"merchantNo": merchant_no})
        data = self._get_data(resp)
        if isinstance(data, list):
            counts = {item.get("status", ""): item.get("num", 0) for item in data}
            return BatchQueryResult(status_counts=counts, total=sum(counts.values()))
        return BatchQueryResult(status_counts=data if isinstance(data, dict) else None)

    def query_order_list(self, merchant_no: str,
                         status_filter: int | None = None,
                         page_no: int = 1, page_size: int = 20) -> BatchQueryResult:
        """订单列表。"""
        params: dict = {
            "merchantNo": merchant_no,
            "pageNo": page_no,
            "pageSize": page_size,
        }
        if status_filter is not None:
            params["status"] = status_filter
        resp = self._client.get(ORDER_PAGE, params)
        data = self._get_data(resp)
        if isinstance(data, dict):
            records = data.get("records") or data.get("list", [])
            return BatchQueryResult(
                orders=records, total=data.get("total", 0),
                page_no=page_no, page_size=page_size,
            )
        return BatchQueryResult()

    def query(self, context: QueryContext) -> ProviderResult:
        """通用接口（批量查询一般不走这个）。"""
        result = ProviderResult(provider_name=self.name)
        result.success = True
        return result
