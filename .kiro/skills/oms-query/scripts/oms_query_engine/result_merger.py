"""ResultMerger - 结果合并器"""
from __future__ import annotations

from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.resolve import QueryInput
from oms_query_engine.models.result import OMSQueryResult, DataCompleteness
from oms_query_engine.models.explanation import QueryExplanation
from oms_query_engine.status_normalizer import StatusNormalizer


class ResultMerger:
    """合并各 Provider 子结果为 OMSQueryResult。"""

    def __init__(self, normalizer: StatusNormalizer):
        self._normalizer = normalizer

    def merge(self, results: dict[str, ProviderResult],
              query_input: QueryInput) -> OMSQueryResult:
        """合并所有 Provider 结果。"""
        out = OMSQueryResult(query_input=query_input)

        # 订单域
        order = results.get("order")
        if order and order.success and order.data:
            out.order_identity = order.data.get("order_identity")
            out.source_info = order.data.get("source_info")
            out.order_context = order.data.get("order_context")
            out.product_info = order.data.get("product_info")
            out.shipping_address = order.data.get("shipping_address")

            # 状态归一化
            status = order.data.get("current_status")
            if status and status.status_code is not None:
                norm = self._normalizer.normalize(status.status_code)
                status.main_status = norm.main_status
                status.status_category = norm.category
                status.is_exception = norm.is_exception
                status.is_hold = norm.is_hold
                status.is_deallocated = norm.is_deallocated
            out.current_status = status

            # OrderProvider 也提取了仓库和履约信息
            if not out.warehouse_info:
                out.warehouse_info = order.data.get("warehouse_info")
            if not out.warehouse_execution_info:
                out.warehouse_execution_info = order.data.get("warehouse_execution_info")
            if not out.warehouse_status_info:
                out.warehouse_status_info = order.data.get("warehouse_status_info")

        # 事件域
        event = results.get("event")
        if event and event.success and event.data:
            out.event_info = event.data.get("event_info")

            # 从日志中提取异常原因（补充到 current_status）
            if out.current_status and out.current_status.is_exception:
                raw_logs = event.data.get("raw_logs", [])
                for log in raw_logs:
                    if str(log.get("eventType", "")).lower() == "exception":
                        out.current_status.exception_reason = log.get("description")
                        break

        # 库存域
        inv = results.get("inventory")
        if inv and inv.success and inv.data:
            out.inventory_info = inv.data.get("inventory_info")

        # 仓库域
        wh = results.get("warehouse")
        if wh and wh.success and wh.data:
            out.warehouse_info = wh.data.get("warehouse_info")

        # 分仓域
        alloc = results.get("allocation")
        if alloc and alloc.success and alloc.data:
            out.allocation_info = alloc.data.get("allocation_info")
            out.warehouse_decision_explanation = alloc.data.get("warehouse_decision_explanation")
            out.deallocation_detail_info = alloc.data.get("deallocation_detail_info")

        # 规则域
        rule = results.get("rule")
        if rule and rule.success and rule.data:
            out.rule_info = rule.data.get("rule_info")

        # 履约域
        ff = results.get("fulfillment")
        if ff and ff.success and ff.data:
            out.warehouse_execution_info = ff.data.get("warehouse_execution_info")
            out.warehouse_status_info = ff.data.get("warehouse_status_info")

        # 发运域
        ship = results.get("shipment")
        if ship and ship.success and ship.data:
            out.shipment_info = ship.data.get("shipment_info")
            out.tracking_progress_info = ship.data.get("tracking_progress_info")

        # 同步域
        sync = results.get("sync")
        if sync and sync.success and sync.data:
            out.shipment_sync_info = sync.data.get("shipment_sync_info")

        # 集成域
        integ = results.get("integration")
        if integ and integ.success and integ.data:
            out.integration_info = integ.data.get("integration_info")

        # 查询级解释
        out.query_explanation = self._build_explanation(results)

        # 数据完整度
        out.data_completeness = self._assess_completeness(results)

        return out

    def _build_explanation(self, results: dict[str, ProviderResult]) -> QueryExplanation:
        """生成查询级解释。"""
        exp = QueryExplanation()

        order = results.get("order")
        if not order or not order.success or not order.data:
            return exp

        status = order.data.get("current_status")
        if not status:
            return exp

        norm = self._normalizer.normalize(status.status_code) if status.status_code is not None else None
        if not norm:
            return exp

        # current_step
        step_map = {
            "初始": "订单已导入系统，等待处理",
            "正常": f"订单处于正常流转中（{norm.main_status}）",
            "终态": f"订单已结束（{norm.main_status}）",
            "逆向": f"订单进入逆向流程（{norm.main_status}）",
            "异常": "订单出现异常，需要排查",
            "Hold": "订单被暂停履约",
            "特殊": f"订单处于特殊状态（{norm.main_status}）",
            "过渡": f"订单处于过渡状态（{norm.main_status}）",
        }
        exp.current_step = step_map.get(norm.category, f"当前状态: {norm.main_status}")

        # why_hold
        if norm.is_hold:
            rule = results.get("rule")
            if rule and rule.success and rule.data:
                ri = rule.data.get("rule_info")
                if ri and ri.hold_rules:
                    first = ri.hold_rules[0] if ri.hold_rules else {}
                    name = first.get("ruleName", "未知规则") if isinstance(first, dict) else "未知规则"
                    exp.why_hold = f"命中 Hold 规则: {name}"
            if not exp.why_hold:
                exp.why_hold = "订单被暂停履约，具体规则需查询 Hold 规则"

        # why_exception
        if norm.is_exception:
            event = results.get("event")
            if event and event.success and event.data:
                logs = event.data.get("raw_logs", [])
                for log in reversed(logs or []):
                    if str(log.get("eventType", "")).lower() == "exception":
                        desc = log.get("description", "")
                        suggestion = log.get("suggestion", "")
                        exp.why_exception = desc
                        if suggestion:
                            exp.why_exception += f"（建议: {suggestion}）"
                        break
            if not exp.why_exception:
                exp.why_exception = "订单标记为异常状态"

        # why_deallocated
        if norm.is_deallocated:
            exp.why_deallocated = "订单已解除分配，原有仓分配被撤销"

        # why_this_warehouse
        if norm.main_status == "已分仓":
            raw = order.data.get("raw_detail", {})
            wh = raw.get("warehouseName") or raw.get("warehouseCode")
            if wh:
                exp.why_this_warehouse = f"分配至仓库: {wh}"

        return exp

    @staticmethod
    def _assess_completeness(results: dict[str, ProviderResult]) -> DataCompleteness:
        """评估数据完整度。"""
        all_apis: list[str] = []
        missing: list[str] = []
        has_core_success = False

        for name, pr in results.items():
            all_apis.extend(pr.called_apis)
            if name in ("order", "event") and pr.success:
                has_core_success = True
            if pr.failed_apis:
                missing.extend(pr.failed_apis)

        if not has_core_success:
            level = "minimal"
        elif missing:
            level = "partial"
        else:
            level = "full"

        return DataCompleteness(
            completeness_level=level,
            missing_fields=missing,
            data_sources=all_apis,
        )
