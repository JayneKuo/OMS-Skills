"""OMSQueryEngine - OMS 全域查询引擎顶层编排入口（v2）"""
from __future__ import annotations

from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.cache import QueryCache
from oms_query_engine.config import EngineConfig
from oms_query_engine.errors import AuthenticationError, QueryError
from oms_query_engine.models.request import QueryRequest, BatchQueryRequest
from oms_query_engine.models.resolve import QueryInput
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.result import OMSQueryResult, DataCompleteness
from oms_query_engine.models.batch import BatchQueryResult
from oms_query_engine.object_resolver import ObjectResolver
from oms_query_engine.query_plan_builder import QueryPlanBuilder
from oms_query_engine.state_aware_plan_expander import StateAwarePlanExpander
from oms_query_engine.provider_executor import ProviderExecutor
from oms_query_engine.result_merger import ResultMerger
from oms_query_engine.status_normalizer import StatusNormalizer


class OMSQueryEngine:
    """OMS 全域查询引擎主入口。只负责编排，不做底层字段拼装。"""

    def __init__(self, config: EngineConfig | None = None):
        self._config = config or EngineConfig()
        self._client = OMSAPIClient(self._config)
        self._cache = QueryCache()
        self._resolver = ObjectResolver(self._client, self._cache)
        self._plan_builder = QueryPlanBuilder()
        self._plan_expander = StateAwarePlanExpander()
        self._executor = ProviderExecutor(self._client, self._cache)
        self._merger = ResultMerger(StatusNormalizer())

    def query(self, request: QueryRequest) -> OMSQueryResult:
        """
        主查询入口。流水线：
        1. ObjectResolver → ResolveResult
        2. QueryPlanBuilder → QueryPlan
        3. ProviderExecutor(core) → core_results
        4. StateAwarePlanExpander → expanded_plan
        5. ProviderExecutor(extended) → all_results
        6. ResultMerger → OMSQueryResult
        """
        qi = QueryInput(input_value=request.identifier)

        if request.force_refresh:
            self._cache.invalidate_all()

        # 1. 对象识别
        try:
            resolve = self._resolver.resolve(request.identifier)
        except AuthenticationError as e:
            return self._error_result(qi, e)
        except QueryError as e:
            return self._error_result(qi, e)

        if not resolve.success:
            qi = resolve.query_input or qi
            return OMSQueryResult(
                query_input=qi,
                error=resolve.error,
                data_completeness=DataCompleteness(completeness_level="minimal"),
            )

        qi = resolve.query_input or qi

        # 2. 生成查询计划
        plan = self._plan_builder.build(resolve, request.query_intent)

        # 3. 构建查询上下文
        context = QueryContext(
            primary_key=qi.resolved_primary_key,
            order_no=qi.resolved_order_no,
            merchant_no=self._config.merchant_no,
            intents=plan.context.get("intents", []),
        )

        # 4. 执行核心 Provider
        try:
            results = self._executor.execute(plan, context)
        except AuthenticationError as e:
            return self._error_result(qi, e)
        except QueryError as e:
            return self._error_result(qi, e)

        # 5. 状态感知增强
        expanded_plan = self._plan_expander.expand(plan, results)

        # 6. 执行增强后新增的 Provider
        new_providers = [
            p for p in expanded_plan.extended_providers
            if p not in results
        ]
        if new_providers:
            for name in new_providers:
                results[name] = self._executor._run_provider(name, context)

        # 7. 合并结果
        return self._merger.merge(results, qi)

    def query_batch(self, request: BatchQueryRequest) -> BatchQueryResult:
        """批量查询，直接委托 BatchProvider，不走单单链路。"""
        self._client._ensure_token()
        batch_provider = self._executor.get_provider("batch")
        if not batch_provider:
            return BatchQueryResult()

        from oms_query_engine.providers.batch import BatchProvider
        if not isinstance(batch_provider, BatchProvider):
            return BatchQueryResult()

        if request.query_type == "status_count":
            return batch_provider.query_status_count(self._config.merchant_no)
        if request.query_type == "order_list":
            return batch_provider.query_order_list(
                self._config.merchant_no,
                request.status_filter,
                request.page_no,
                request.page_size,
                request.sort_by,
                request.sort_order,
            )
        if request.query_type == "latest_order":
            return batch_provider.query_latest_order(self._config.merchant_no)
        return BatchQueryResult()

    @staticmethod
    def _error_result(qi: QueryInput, err: QueryError) -> OMSQueryResult:
        return OMSQueryResult(
            query_input=qi,
            error=err.to_dict(),
            data_completeness=DataCompleteness(completeness_level="minimal"),
        )
