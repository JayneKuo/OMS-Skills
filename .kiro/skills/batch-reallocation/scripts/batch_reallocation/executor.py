from __future__ import annotations

from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.eligibility import build_sku_candidate, choose_action_mode, classify_order_scenario
from batch_reallocation.models import ExecuteRequest, ExecuteResponse


class BatchReallocationExecutor:
    def __init__(self, config: BatchReallocationConfig, client):
        self.config = config
        self.client = client

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        self.config.validate_for_execution()
        if not request.confirmed:
            raise ValueError("ExecuteRequest.confirmed must be true before dangerous batch reallocation execution")
        result = ExecuteResponse(submitted_orders=len(request.decisions))

        for decision in request.decisions:
            order = self.client.get_sale_order(decision.order_no)
            scenario = classify_order_scenario(order)
            skus = [build_sku_candidate(line) for line in order.get("items") or order.get("orderItems") or []]
            eligible_skus = {sku.sku for sku in skus if sku.eligible}
            if not eligible_skus:
                result.skipped_orders[decision.order_no] = "stale_state"
                continue
            if scenario == "ineligible":
                result.skipped_orders[decision.order_no] = "stale_state"
                continue
            if not self.client.get_recover_check(decision.order_no):
                result.skipped_orders[decision.order_no] = "recover_check_failed"
                continue
            recover_query = self.client.get_recover_query(decision.order_no)
            if not recover_query.get("recoverable", True):
                result.skipped_orders[decision.order_no] = "recover_check_failed"
                continue

            required_action_mode = choose_action_mode(
                scenario=scenario,
                skus=skus,
                recoverable=True,
            )
            if decision.action_mode != required_action_mode:
                result.skipped_orders[decision.order_no] = "action_mode_mismatch"
                continue

            selected_eligible_skus = [sku for sku in decision.selected_skus if sku in eligible_skus]
            if decision.action_mode == "partial_sku" and not selected_eligible_skus:
                result.skipped_orders[decision.order_no] = "no_eligible_selected_skus"
                continue
            if decision.action_mode == "release_hold_then_recover":
                self.client.release_hold(decision.order_no)
                if selected_eligible_skus:
                    self.client.recover_dispatch_part(decision.order_no, selected_eligible_skus)
                else:
                    self.client.recover_dispatch(decision.order_no)
            elif decision.action_mode == "partial_sku":
                self.client.recover_dispatch_part(decision.order_no, selected_eligible_skus)
            else:
                self.client.recover_dispatch(decision.order_no)

            result.succeeded_orders.append(decision.order_no)

        return result
