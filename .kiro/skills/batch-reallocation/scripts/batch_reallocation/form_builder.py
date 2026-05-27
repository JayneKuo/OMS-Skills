from __future__ import annotations

from batch_reallocation.models import AnalyzeResponse


def build_form_payload(result: AnalyzeResponse) -> dict:
    return {
        "form_type": result.form_type,
        "groups": [
            {
                "scenario": group.scenario,
                "title": group.title,
                "selection_mode": group.selection_mode,
                "orders": [
                    {
                        "order_no": order.order_no,
                        "status": order.status,
                        "eligible": order.eligible,
                        "reason": order.reason,
                        "exception_summary": order.exception_summary,
                        "hold_reason": order.hold_reason,
                        "skus": [
                            {
                                "sku": sku.sku,
                                "ordered_qty": sku.ordered_qty,
                                "fulfilled_qty": sku.fulfilled_qty,
                                "unfulfilled_qty": sku.unfulfilled_qty,
                                "hold_qty": sku.hold_qty,
                                "eligible": sku.eligible,
                                "reason": sku.reason,
                            }
                            for sku in order.skus
                        ],
                    }
                    for order in group.orders
                ],
            }
            for group in result.groups
        ],
        "warnings": result.warnings,
        "requires_confirmation": result.requires_confirmation,
        "next_action": result.next_action,
    }
