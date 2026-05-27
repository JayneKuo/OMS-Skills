from __future__ import annotations

from batch_reallocation.models import AnalyzeResponse, ExecuteResponse


def build_analysis_view(result: AnalyzeResponse) -> dict:
    orders = []
    for group in result.groups:
        for order in group.orders:
            eligible_count = sum(1 for sku in order.skus if sku.eligible)
            ineligible_count = sum(1 for sku in order.skus if not sku.eligible)
            if group.selection_mode == "order":
                eligible_count = 1 if order.eligible else 0
                ineligible_count = 0 if order.eligible else 1
            sku_facts = [
                {
                    "sku": sku.sku,
                    "ordered_qty": sku.ordered_qty,
                    "fulfilled_qty": sku.fulfilled_qty,
                    "unfulfilled_qty": sku.unfulfilled_qty,
                }
                for sku in order.skus
            ]
            orders.append(
                {
                    "order_no": order.order_no,
                    "current_status": order.status,
                    "scenario_group": group.scenario,
                    "exception_or_hold_summary": order.exception_summary
                    or order.hold_reason
                    or order.reason,
                    "eligibility": {
                        "supported": order.eligible,
                        "action_mode": group.selection_mode,
                        "executable_scope_summary": (
                            f"可执行 {eligible_count} 个 SKU" if group.selection_mode == "sku" else f"可执行 {eligible_count} 个 order"
                        ),
                        "ineligible_scope_summary": (
                            f"不可执行 {ineligible_count} 个 SKU"
                            if group.selection_mode == "sku"
                            else f"不可执行 {ineligible_count} 个 order"
                        ),
                    },
                    "sku_facts": sku_facts,
                }
            )

    return {
        "requires_confirmation": result.requires_confirmation,
        "global_warnings": result.warnings,
        "orders": orders,
    }


def build_confirmation_view(result: AnalyzeResponse, decisions: dict | None = None) -> dict:
    decisions = decisions or {}
    decision_items = decisions.get("decisions", []) or []
    orders = [order for group in result.groups for order in group.orders]
    first_decision = decision_items[0] if decision_items else {}

    return {
        "status": "waiting_for_confirmation",
        "order_nos": [order.order_no for order in orders],
        "scenario_groups": [group.scenario for group in result.groups],
        "action_mode_summary": first_decision.get("action_mode"),
        "includes_release_hold": bool(first_decision.get("release_hold")),
        "selected_skus_by_order": [
            {"order_no": item.get("order_no"), "selected_skus": item.get("selected_skus", [])}
            for item in decision_items
        ],
        "editable_choices": ["action_mode", "selected_skus", "release_hold"],
        "readonly_facts": [f"order status: {order.status}" for order in orders],
        "risks": result.warnings,
    }


def build_execution_view(result: ExecuteResponse) -> dict:
    submitted_orders = list(result.succeeded_orders) + list(result.partial_succeeded_orders) + list(result.failed_orders)
    return {
        "executed": bool(result.submitted_orders or submitted_orders),
        "submitted_orders": submitted_orders,
        "succeeded_orders": result.succeeded_orders,
        "partial_succeeded_orders": result.partial_succeeded_orders,
        "failed_orders": [
            {"order_no": order_no, "reason": reason}
            for order_no, reason in result.failed_orders.items()
        ],
        "skipped_orders": [
            {"order_no": order_no, "reason": reason}
            for order_no, reason in result.skipped_orders.items()
        ],
        "warnings": result.warnings,
    }
