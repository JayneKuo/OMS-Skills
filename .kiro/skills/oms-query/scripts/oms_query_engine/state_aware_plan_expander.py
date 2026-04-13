"""StateAwarePlanExpander - 状态感知增强器"""
from __future__ import annotations

from oms_query_engine.models.query_plan import QueryPlan
from oms_query_engine.models.provider_result import ProviderResult


class StateAwarePlanExpander:
    """根据核心查询结果中的订单状态，自动扩展查询计划。"""

    def expand(self, plan: QueryPlan,
               core_results: dict[str, ProviderResult]) -> QueryPlan:
        """状态感知增强：根据订单状态追加 Provider。"""
        if plan.primary_object_type != "order":
            return plan

        order_result = core_results.get("order")
        if not order_result or not order_result.success or not order_result.data:
            return plan

        raw_detail = order_result.data.get("raw_detail", {})
        status_code = raw_detail.get("status")
        if status_code is None:
            return plan

        existing = set(plan.core_providers + plan.extended_providers)
        to_add: list[str] = []

        # Shipped / Partially shipped (3, 24)
        if status_code in (3, 24, "SHIPPED", "PARTIALLY_SHIPPED"):
            for p in ["shipment", "sync"]:
                if p not in existing:
                    to_add.append(p)

        # On Hold (16)
        if status_code in (16, "ON_HOLD"):
            for p in ["rule", "allocation"]:
                if p not in existing:
                    to_add.append(p)

        # Exception (10)
        if status_code in (10, "EXCEPTION"):
            if "event" not in existing:
                to_add.append("event")

        # Deallocated (25)
        if status_code in (25, "DEALLOCATED"):
            for p in ["allocation", "event"]:
                if p not in existing:
                    to_add.append(p)

        if to_add:
            plan = plan.model_copy()
            plan.extended_providers = list(plan.extended_providers) + to_add

        return plan
