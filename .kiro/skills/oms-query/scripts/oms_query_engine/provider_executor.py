"""ProviderExecutor - 统一执行器"""
from __future__ import annotations

from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryPlan, QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.providers.base import BaseProvider
from oms_query_engine.providers.order import OrderProvider
from oms_query_engine.providers.event import EventProvider
from oms_query_engine.providers.inventory import InventoryProvider
from oms_query_engine.providers.warehouse import WarehouseProvider
from oms_query_engine.providers.allocation import AllocationProvider
from oms_query_engine.providers.rule import RuleProvider
from oms_query_engine.providers.fulfillment import FulfillmentProvider
from oms_query_engine.providers.shipment import ShipmentProvider
from oms_query_engine.providers.sync import SyncProvider
from oms_query_engine.providers.integration import IntegrationProvider
from oms_query_engine.providers.batch import BatchProvider


class ProviderExecutor:
    """按查询计划调度各 Provider 执行查询。"""

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._providers: dict[str, BaseProvider] = {
            "order": OrderProvider(client, cache),
            "event": EventProvider(client, cache),
            "inventory": InventoryProvider(client, cache),
            "warehouse": WarehouseProvider(client, cache),
            "allocation": AllocationProvider(client, cache),
            "rule": RuleProvider(client, cache),
            "fulfillment": FulfillmentProvider(client, cache),
            "shipment": ShipmentProvider(client, cache),
            "sync": SyncProvider(client, cache),
            "integration": IntegrationProvider(client, cache),
            "batch": BatchProvider(client, cache),
        }

    def get_provider(self, name: str) -> BaseProvider | None:
        return self._providers.get(name)

    def execute(self, plan: QueryPlan,
                context: QueryContext) -> dict[str, ProviderResult]:
        """按计划执行：先 core，再 extended。单个失败不阻断。"""
        results: dict[str, ProviderResult] = {}

        # 执行 core providers
        for name in plan.core_providers:
            results[name] = self._run_provider(name, context)

        # 从 order 结果中提取上下文供后续 Provider 使用
        order_result = results.get("order")
        if order_result and order_result.success and order_result.data:
            raw = order_result.data.get("raw_detail", {})
            if raw:
                context.order_detail = raw
                context.merchant_no = context.merchant_no or raw.get("merchantNo")
                context.order_no = context.order_no or raw.get("orderNo") or raw.get("omsOrderNo")
                # 提取 SKU 列表
                items = raw.get("items") or raw.get("orderItems") or raw.get("itemLines") or []
                context.skus = [i.get("sku", "") for i in items if i.get("sku")]

        # 从 event 结果中提取 eventId
        event_result = results.get("event")
        if event_result and event_result.success and event_result.data:
            logs = event_result.data.get("raw_logs", [])
            for log in (logs or []):
                eid = log.get("eventId")
                if eid and eid not in context.event_ids:
                    context.event_ids.append(str(eid))

        # 执行 extended providers
        for name in plan.extended_providers:
            if name not in results:
                results[name] = self._run_provider(name, context)

        return results

    def _run_provider(self, name: str, context: QueryContext) -> ProviderResult:
        """执行单个 Provider，捕获异常。"""
        provider = self._providers.get(name)
        if not provider:
            return ProviderResult(
                provider_name=name,
                errors=[f"未知 Provider: {name}"],
            )
        try:
            return provider.query(context)
        except Exception as e:
            return ProviderResult(
                provider_name=name,
                errors=[str(e)],
            )
