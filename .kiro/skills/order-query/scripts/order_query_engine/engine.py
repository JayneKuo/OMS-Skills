"""订单全景查询引擎 - 顶层编排入口"""

from __future__ import annotations

from order_query_engine.api_client import OMSAPIClient
from order_query_engine.cache import QueryCache
from order_query_engine.config import EngineConfig
from order_query_engine.errors import (
    AuthenticationError,
    OrderNotFoundError,
    QueryError,
)
from order_query_engine.identifier_resolver import IdentifierResolver
from order_query_engine.models import (
    BatchQueryRequest,
    BatchQueryResult,
    DataCompleteness,
    OrderQueryResult,
    QueryInput,
    QueryRequest,
)
from order_query_engine.query_orchestrator import QueryOrchestrator
from order_query_engine.result_assembler import ResultAssembler
from order_query_engine.status_normalizer import StatusNormalizer

# 批量查询 API 路径
STATUS_NUM_PATH = "/api/linker-oms/opc/app-api/sale-order/status/num"
ORDER_PAGE_PATH = "/api/linker-oms/opc/app-api/sale-order/page"


class OrderQueryEngine:
    """订单全景查询引擎主入口。"""

    def __init__(self, config: EngineConfig | None = None):
        self._config = config or EngineConfig()
        self._client = OMSAPIClient(self._config)
        self._cache = QueryCache()
        self._resolver = IdentifierResolver(self._client, self._cache)
        self._orchestrator = QueryOrchestrator(self._client, self._cache)
        self._normalizer = StatusNormalizer()
        self._assembler = ResultAssembler(self._normalizer)

    def query(self, request: QueryRequest) -> OrderQueryResult:
        """
        查询主入口。
        流程：标识解析 → 查询编排 → 状态归一化 → 结果组装 → 输出。
        """
        qi = QueryInput(input_value=request.identifier)

        # force_refresh → 清除缓存
        if request.force_refresh:
            self._cache.invalidate_all()

        # 1. 标识解析
        try:
            resolve = self._resolver.resolve(request.identifier)
        except AuthenticationError as e:
            return self._error_result(qi, e)
        except QueryError as e:
            return self._error_result(qi, e)

        if not resolve.success:
            qi = resolve.query_input or qi
            return OrderQueryResult(
                query_input=qi,
                error=resolve.error,
                data_completeness=DataCompleteness(
                    completeness_level="minimal"),
            )

        qi = resolve.query_input or qi
        order_no = qi.resolved_order_no or request.identifier

        # 2. 核心查询
        try:
            core = self._orchestrator.execute_core(
                order_no, self._config.merchant_no)
        except AuthenticationError as e:
            return self._error_result(qi, e)
        except OrderNotFoundError as e:
            return self._error_result(qi, e)
        except QueryError as e:
            return self._error_result(qi, e)

        # 3. 扩展查询
        intents = self._orchestrator.detect_intents(request.query_intent)
        extended = None
        if intents:
            try:
                extended = self._orchestrator.execute_extended(
                    order_no, intents, core, self._config.merchant_no)
            except Exception:
                pass  # 扩展查询失败不阻断

        # 4. 结果组装
        return self._assembler.assemble(core, extended, qi)

    def query_batch(self, request: BatchQueryRequest) -> BatchQueryResult:
        """批量查询：状态统计或按状态过滤的订单列表。"""
        self._client._ensure_token()

        if request.query_type == "status_count":
            resp = self._client.get(STATUS_NUM_PATH, {
                "merchantNo": self._config.merchant_no,
            })
            data = resp.get("data", {})
            # data 可能是 list[{status, num}] 或 dict
            if isinstance(data, list):
                counts = {item.get("status", ""): item.get("num", 0)
                          for item in data}
                return BatchQueryResult(
                    status_counts=counts,
                    total=sum(counts.values()),
                )
            return BatchQueryResult(status_counts=data)

        if request.query_type == "order_list":
            params: dict = {
                "merchantNo": self._config.merchant_no,
                "pageNo": request.page_no,
                "pageSize": request.page_size,
            }
            if request.status_filter is not None:
                params["status"] = request.status_filter
            resp = self._client.get(ORDER_PAGE_PATH, params)
            data = resp.get("data", {})
            records = data.get("records") or data.get("list", [])
            total = data.get("total", 0)
            return BatchQueryResult(
                orders=records,
                total=total,
                page_no=request.page_no,
                page_size=request.page_size,
            )

        return BatchQueryResult()

    @staticmethod
    def _error_result(qi: QueryInput, err: QueryError) -> OrderQueryResult:
        return OrderQueryResult(
            query_input=qi,
            error=err.to_dict(),
            data_completeness=DataCompleteness(
                completeness_level="minimal"),
        )
