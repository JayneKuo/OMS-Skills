"""AllocationProvider - 分仓域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.allocation import (
    AllocationInfo, DeallocationDetailInfo, WarehouseDecisionExplanation,
)
from .base import BaseProvider

DISPATCH_QUERY = "/api/linker-oms/opc/app-api/dispatch/recover/query/{orderNo}"
DISPATCH_HAND = "/api/linker-oms/opc/app-api/dispatch/hand/item/{orderNo}"

# 策略翻译
STRATEGY_MAP = {
    1: "按邮编过滤仓库", 2: "按国家/目的地市场过滤",
    11: "单仓不拆单", 12: "允许拆单", 13: "样品不拆单",
    14: "按 Accounting Code 指定仓", 15: "自定义规则选仓",
    16: "最近仓发货", 17: "按产品指定仓",
    -1: "库存不足走最高优先级仓", -2: "多仓兜底", -3: "异常挂起",
    21: "一仓一出库单", 22: "一品一单", 23: "指定承运商独立出库单",
}


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


class AllocationProvider(BaseProvider):
    """分仓结果、候选仓、解除分配、分仓决策解释。"""

    name = "allocation"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        order_no = context.order_no or context.primary_key
        if not order_no:
            result.errors.append("缺少 orderNo")
            return result

        dispatch_data = None
        hand_data = None

        # 1. 分配查询
        try:
            path = DISPATCH_QUERY.format(orderNo=order_no)
            resp = self._fetch_get(path, f"dealloc:{order_no}", QueryCache.TTL_ORDER)
            dispatch_data = self._get_data(resp)
            result.called_apis.append(path)
        except Exception as e:
            result.errors.append(f"dispatch query: {e}")
            result.failed_apis.append("dispatch_query")

        # 2. 手动分配/候选仓
        try:
            path = DISPATCH_HAND.format(orderNo=order_no)
            resp = self._fetch_get(path, f"hand:{order_no}", QueryCache.TTL_ORDER)
            hand_data = self._get_data(resp)
            result.called_apis.append(path)
        except Exception as e:
            # hand item 可能不存在，不算失败
            pass

        detail = context.order_detail or {}

        # 构建分仓信息
        alloc = AllocationInfo(
            allocation_status=detail.get("allocationStatus") or detail.get("status"),
            allocation_reason=detail.get("allocationReason"),
        )

        # 从 dispatch 数据中提取策略
        if isinstance(dispatch_data, dict):
            strategies = dispatch_data.get("dispatchStrategies") or []
            filter_strats = dispatch_data.get("filterStrategies") or []
            backup = dispatch_data.get("backupDispatchStrategy")

            alloc.dispatch_strategies = [
                STRATEGY_MAP.get(s, str(s)) for s in strategies
            ] if strategies else None
            alloc.filter_strategies = [
                STRATEGY_MAP.get(s, str(s)) for s in filter_strats
            ] if filter_strats else None
            alloc.backup_strategy = STRATEGY_MAP.get(backup, str(backup)) if backup else None

            # 候选仓
            candidates = dispatch_data.get("candidateWarehouses") or dispatch_data.get("dispatchList") or []
            if candidates:
                alloc.candidate_warehouses = candidates

        # 构建仓库决策解释
        decision = None
        if detail.get("warehouseCode") or detail.get("accountingCode"):
            decision = WarehouseDecisionExplanation(
                final_warehouse_no=detail.get("warehouseCode"),
                final_warehouse_name=detail.get("warehouseName"),
                decision_summary=alloc.allocation_reason,
                decision_factors=alloc.dispatch_strategies,
                candidate_warehouses=alloc.candidate_warehouses,
            )

        # 构建解除分配信息（如果状态是 Deallocated）
        dealloc_info = None
        status = detail.get("status")
        if status in (25, "DEALLOCATED"):
            dealloc_info = DeallocationDetailInfo(
                is_deallocated=True,
                deallocated_reason=detail.get("deallocatedReason"),
                previous_warehouse_no=detail.get("previousWarehouseCode"),
                previous_warehouse_name=detail.get("previousWarehouseName"),
                current_allocation_status="已解除分配",
                candidate_warehouses=alloc.candidate_warehouses,
            )

        result.success = True
        result.data = {
            "allocation_info": alloc,
            "warehouse_decision_explanation": decision,
            "deallocation_detail_info": dealloc_info,
            "raw_dispatch": dispatch_data,
        }
        return result
