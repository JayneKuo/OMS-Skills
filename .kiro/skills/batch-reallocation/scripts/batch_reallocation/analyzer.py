from __future__ import annotations

from batch_reallocation.api_client import BatchReallocationAPIClient
from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.eligibility import build_sku_candidate, choose_action_mode, classify_order_scenario
from batch_reallocation.models import AnalyzeResponse, FormGroup, OrderCandidate


class BatchReallocationAnalyzer:
    def __init__(self, config: BatchReallocationConfig, client: BatchReallocationAPIClient):
        self.config = config
        self.client = client

    def analyze(self, identifiers: list[str], merchant_no: str | None = None) -> AnalyzeResponse:
        self.config.validate_for_analysis()
        resolved_merchant = merchant_no or self.config.merchant_no or ""
        groups: dict[str, FormGroup] = {}

        for raw_identifier in identifiers:
            if str(raw_identifier).upper().startswith("SO"):
                order_no = raw_identifier
            else:
                order_ref = self.client.resolve_order(raw_identifier)
                if isinstance(order_ref, str):
                    order_no = order_ref or raw_identifier
                else:
                    order_no = order_ref.get("orderNo") or order_ref.get("omsOrderNo") or raw_identifier
            order = self.client.get_sale_order(order_no)
            logs = self.client.get_order_logs(order_no, resolved_merchant)
            fallback_hand_items = None
            try:
                recoverable = self.client.get_recover_check(order_no)
            except Exception:
                recoverable = self.client.get_hand_check(order_no)
                fallback_hand_items = self.client.get_hand_items(order_no)
            recover_query = self.client.get_recover_query(order_no)
            scenario = classify_order_scenario(order)
            item_lines = order.get("items") or order.get("orderItems") or order.get("itemLines") or []
            if fallback_hand_items and fallback_hand_items.get("itemVOList"):
                item_lines = [
                    {
                        "sku": item.get("sku"),
                        "quantity": item.get("totalQty") or item.get("quantity") or 0,
                        "fulfilledQty": (item.get("totalQty") or item.get("quantity") or 0) - (item.get("remaining") or 0),
                        "hold": 0,
                    }
                    for item in fallback_hand_items.get("itemVOList") or []
                ]
            sku_candidates = [build_sku_candidate(line) for line in item_lines]
            order_recoverable = recoverable and recover_query.get("recoverable", True)
            action_mode = choose_action_mode(scenario=scenario, skus=sku_candidates, recoverable=order_recoverable)
            has_eligible_skus = any(sku.eligible for sku in sku_candidates)
            eligible = scenario != "ineligible" and order_recoverable and has_eligible_skus
            reason = None
            if not order_recoverable:
                reason = "recover_check_failed"
            elif scenario == "ineligible":
                reason = "unsupported_status"
            elif not has_eligible_skus:
                reason = "unfulfilled_qty_zero"
            log_items = logs
            if isinstance(logs, dict):
                log_items = logs.get("list") or []
            exception_summary = None
            if log_items:
                first_log = log_items[0]
                exception_summary = first_log.get("remark") or first_log.get("description")
            candidate = OrderCandidate(
                order_no=order_no,
                scenario=scenario,
                status=str(order.get("status") or order.get("statusName") or ""),
                eligible=eligible,
                reason=reason,
                exception_summary=exception_summary,
                hold_reason=order.get("holdReason"),
                skus=sku_candidates,
            )
            title = {
                "imported": "Imported orders",
                "exception": "Exception orders",
                "deallocated": "Deallocated orders",
                "on_hold": "On Hold orders",
                "ineligible": "Ineligible orders",
            }[scenario]
            selection_mode = "sku" if action_mode in {"partial_sku", "release_hold_then_recover"} else "order"
            groups.setdefault(scenario, FormGroup(scenario=scenario, title=title, selection_mode=selection_mode, orders=[])).orders.append(candidate)

        return AnalyzeResponse(groups=list(groups.values()), warnings=[])
