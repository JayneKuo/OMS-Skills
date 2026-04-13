"""订单全景查询引擎 - 结果组装器"""

from __future__ import annotations

from order_query_engine.models import (
    AllocationInfo,
    CoreQueryResult,
    CurrentStatus,
    DataCompleteness,
    EventInfo,
    ExtendedQueryResult,
    InventoryInfo,
    NormalizedStatus,
    OrderContext,
    OrderIdentity,
    OrderItem,
    OrderQueryResult,
    QueryExplanation,
    QueryInput,
    RuleInfo,
    ShipmentInfo,
    ShippingAddress,
    WarehouseInfo,
)
from order_query_engine.status_normalizer import StatusNormalizer


class ResultAssembler:
    """将多个 API 返回合并为 OrderQueryResult，生成查询级解释。"""

    def __init__(self, normalizer: StatusNormalizer):
        self._normalizer = normalizer

    def assemble(self, core: CoreQueryResult,
                 extended: ExtendedQueryResult | None,
                 query_input: QueryInput) -> OrderQueryResult:
        """合并核心查询和扩展查询结果为 OrderQueryResult。"""
        detail = _get_data(core.order_detail)
        logs_data = _get_data(core.order_logs)

        # 状态归一化
        status_code = detail.get("status", -1) if detail else -1
        norm = self._normalizer.normalize(status_code)

        # 核心字段提取
        identity = self._extract_identity(detail)
        context = self._extract_context(detail)
        items = self._extract_items(detail)
        address = self._extract_address(detail)
        event_info = self._extract_events(logs_data)

        # 异常 / Hold 原因
        exception_reason = None
        hold_reason = None
        if norm.is_exception:
            exception_reason = self._extract_exception_reason(logs_data)
        if norm.is_hold and extended and extended.hold_rules:
            hold_reason = self._extract_hold_reason(extended.hold_rules)

        current_status = CurrentStatus(
            main_status=norm.main_status,
            fulfillment_status=detail.get("fulfillmentStatus") if detail else None,
            shipment_status=None,
            is_exception=norm.is_exception,
            is_hold=norm.is_hold,
            hold_reason=hold_reason,
            exception_reason=exception_reason,
        )

        # 扩展字段
        shipment_info = None
        inventory_info = None
        warehouse_info = None
        allocation_info = None
        rule_info = None
        missing_fields: list[str] = []

        if extended:
            shipment_info = self._extract_shipment(extended)
            inventory_info = self._extract_inventory(extended)
            warehouse_info = self._extract_warehouse(detail, extended)
            allocation_info = self._extract_allocation(detail, extended)
            rule_info = self._extract_rules(extended)
            # 记录失败字段
            for api in extended.failed_apis:
                if api not in missing_fields:
                    missing_fields.append(api)

        # 查询级解释
        explanation = self._build_explanation(norm, core, extended)

        # 数据完整度
        completeness = self._assess_completeness(
            core.success,
            extended.failed_apis if extended else [],
        )
        completeness.missing_fields = missing_fields
        # 记录数据源
        sources: list[str] = []
        if extended:
            sources.extend(extended.called_apis)
        completeness.data_sources = sources

        return OrderQueryResult(
            query_input=query_input,
            order_identity=identity,
            order_context=context,
            current_status=current_status,
            order_items=items,
            shipping_address=address,
            shipment_info=shipment_info,
            inventory_info=inventory_info,
            warehouse_info=warehouse_info,
            allocation_info=allocation_info,
            rule_info=rule_info,
            event_info=event_info,
            query_explanation=explanation,
            data_completeness=completeness,
        )

    # ── 查询级解释 ────────────────────────────────────

    def _build_explanation(self, status: NormalizedStatus,
                           core: CoreQueryResult,
                           extended: ExtendedQueryResult | None,
                           ) -> QueryExplanation:
        """生成查询级解释，仅描述现象。"""
        exp = QueryExplanation()

        # current_step
        step_map = {
            "初始": "订单已导入系统，等待处理",
            "正常": f"订单处于正常流转中（{status.main_status}）",
            "终态": f"订单已结束（{status.main_status}）",
            "逆向": f"订单进入逆向流程（{status.main_status}）",
            "异常": "订单出现异常，需要排查",
            "Hold": "订单被暂停履约",
            "特殊": f"订单处于特殊状态（{status.main_status}）",
            "过渡": f"订单处于过渡状态（{status.main_status}）",
        }
        exp.current_step = step_map.get(status.category,
                                        f"当前状态: {status.main_status}")

        # why_hold
        if status.is_hold and extended and extended.hold_rules:
            hold_data = _get_data(extended.hold_rules)
            if isinstance(hold_data, list) and hold_data:
                rule = hold_data[0]
                name = rule.get("ruleName", "未知规则")
                exp.why_hold = f"命中 Hold 规则: {name}"
            elif isinstance(hold_data, dict):
                records = hold_data.get("records", [])
                if records:
                    name = records[0].get("ruleName", "未知规则")
                    exp.why_hold = f"命中 Hold 规则: {name}"
            if not exp.why_hold:
                exp.why_hold = "订单被暂停履约，具体规则需查询 Hold 规则"
        elif status.is_hold:
            exp.why_hold = "订单被暂停履约，具体规则需查询 Hold 规则"

        # why_exception
        if status.is_exception:
            logs_data = _get_data(core.order_logs)
            if isinstance(logs_data, list):
                for log in reversed(logs_data):
                    if "exception" in str(log.get("eventType", "")).lower():
                        exp.why_exception = (
                            f"异常事件: {log.get('eventType')} "
                            f"({log.get('createTime', '未知时间')})"
                        )
                        break
            if not exp.why_exception:
                exp.why_exception = "订单标记为异常状态"

        # why_this_warehouse
        if status.main_status == "已分仓":
            detail = _get_data(core.order_detail)
            if detail:
                wh = detail.get("warehouseName") or detail.get("warehouseCode")
                if wh:
                    exp.why_this_warehouse = f"分配至仓库: {wh}"

        return exp

    # ── 数据完整度 ────────────────────────────────────

    def _assess_completeness(self, core_success: bool,
                             extended_failures: list[str],
                             ) -> DataCompleteness:
        """评估数据完整度。"""
        if not core_success:
            return DataCompleteness(completeness_level="minimal")
        if extended_failures:
            return DataCompleteness(completeness_level="partial")
        return DataCompleteness(completeness_level="full")

    # ── 核心字段提取 ──────────────────────────────────

    @staticmethod
    def _extract_identity(detail: dict | None) -> OrderIdentity | None:
        if not detail:
            return None
        return OrderIdentity(
            order_no=detail.get("orderNo") or detail.get("omsOrderNo"),
            customer_order_no=detail.get("customerOrderNo"),
            external_order_no=detail.get("externalOrderNo"),
            merchant_no=detail.get("merchantNo"),
            channel_no=detail.get("channelNo"),
            channel_name=detail.get("channelName"),
        )

    @staticmethod
    def _extract_context(detail: dict | None) -> OrderContext | None:
        if not detail:
            return None
        return OrderContext(
            order_type=detail.get("orderType"),
            order_type_tags=detail.get("orderTypeTags"),
            related_order_no=detail.get("relatedOrderNo"),
            order_source=detail.get("orderSource"),
        )

    @staticmethod
    def _extract_items(detail: dict | None) -> list[OrderItem] | None:
        if not detail:
            return None
        items_raw = (detail.get("items") or detail.get("orderItems")
                     or detail.get("itemLines") or [])
        if not items_raw:
            return None
        return [
            OrderItem(
                sku=item.get("sku", ""),
                quantity=item.get("quantity", 0),
                description=item.get("description") or item.get("itemName"),
                weight=item.get("weight"),
                dimensions=item.get("dimensions"),
            )
            for item in items_raw
        ]

    @staticmethod
    def _extract_address(detail: dict | None) -> ShippingAddress | None:
        if not detail:
            return None
        addr = detail.get("shippingAddress") or detail.get("address") or detail
        return ShippingAddress(
            country=addr.get("country"),
            state=addr.get("state"),
            city=addr.get("city"),
            zipcode=addr.get("zipcode") or addr.get("postalCode"),
            address1=addr.get("address1") or addr.get("addressLine1"),
        )

    @staticmethod
    def _extract_events(logs_data: dict | list | None) -> EventInfo | None:
        if not logs_data:
            return None
        logs = logs_data if isinstance(logs_data, list) else logs_data.get("records", [])
        if not logs:
            return EventInfo(order_logs=[])
        latest = logs[0] if logs else {}
        return EventInfo(
            order_logs=logs,
            latest_event_type=latest.get("eventType"),
            latest_event_time=latest.get("createTime"),
        )

    # ── 扩展字段提取 ──────────────────────────────────

    @staticmethod
    def _extract_shipment(ext: ExtendedQueryResult) -> ShipmentInfo | None:
        td = _get_data(ext.tracking_detail)
        if not td:
            return None
        return ShipmentInfo(
            shipment_no=td.get("shipmentNo"),
            carrier_name=td.get("carrierName"),
            carrier_scac=td.get("carrierScac"),
            delivery_service=td.get("deliveryService"),
            tracking_no=td.get("trackingNo"),
            shipment_status=td.get("shipmentStatus"),
        )

    @staticmethod
    def _extract_inventory(ext: ExtendedQueryResult) -> InventoryInfo | None:
        inv = _get_data(ext.inventory)
        if not inv:
            return None
        items = inv if isinstance(inv, list) else inv.get("records", [])
        return InventoryInfo(
            sku_inventory=items,
            inventory_summary=f"共 {len(items)} 条库存记录",
        )

    @staticmethod
    def _extract_warehouse(detail: dict | None,
                           ext: ExtendedQueryResult) -> WarehouseInfo | None:
        wh = _get_data(ext.warehouse_list)
        if not detail and not wh:
            return None
        return WarehouseInfo(
            allocated_warehouse=detail.get("warehouseCode") if detail else None,
            warehouse_name=detail.get("warehouseName") if detail else None,
            warehouse_accounting_code=detail.get("accountingCode") if detail else None,
        )

    @staticmethod
    def _extract_allocation(detail: dict | None,
                            ext: ExtendedQueryResult) -> AllocationInfo | None:
        dealloc = _get_data(ext.deallocate_info)
        if not detail and not dealloc:
            return None
        return AllocationInfo(
            allocation_reason=detail.get("allocationReason") if detail else None,
        )

    @staticmethod
    def _extract_rules(ext: ExtendedQueryResult) -> RuleInfo | None:
        rr = _get_data(ext.routing_rules)
        cr = _get_data(ext.custom_rules)
        hr = _get_data(ext.hold_rules)
        sw = _get_data(ext.sku_warehouse_rules)
        if not any([rr, cr, hr, sw]):
            return None
        return RuleInfo(
            routing_rules=rr if isinstance(rr, list) else (rr.get("records") if rr else None),
            custom_rules=cr if isinstance(cr, list) else (cr.get("records") if cr else None),
            hold_rules=hr if isinstance(hr, list) else (hr.get("records") if hr else None),
            sku_warehouse_rules=sw if isinstance(sw, list) else (sw.get("records") if sw else None),
        )

    @staticmethod
    def _extract_exception_reason(logs_data: dict | list | None) -> str | None:
        if not logs_data:
            return None
        logs = logs_data if isinstance(logs_data, list) else logs_data.get("records", [])
        for log in reversed(logs):
            if "exception" in str(log.get("eventType", "")).lower():
                return f"{log.get('eventType')} ({log.get('createTime', '')})"
        return "订单标记为异常状态"

    @staticmethod
    def _extract_hold_reason(hold_rules_resp: dict | None) -> str | None:
        if not hold_rules_resp:
            return None
        data = _get_data(hold_rules_resp)
        if isinstance(data, list) and data:
            return data[0].get("ruleName", "Hold 规则命中")
        if isinstance(data, dict):
            records = data.get("records", [])
            if records:
                return records[0].get("ruleName", "Hold 规则命中")
        return "Hold 规则命中"


def _get_data(resp: dict | None) -> dict | list | None:
    """从 API 响应中提取 data 字段。"""
    if resp is None:
        return None
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp
