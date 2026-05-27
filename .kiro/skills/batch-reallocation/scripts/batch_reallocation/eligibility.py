from __future__ import annotations

from batch_reallocation.models import ActionMode, Scenario, SkuCandidate


def _status_text(order: dict) -> str:
    return str(order.get("status") or order.get("statusName") or "").strip().lower()


def classify_order_scenario(order: dict) -> Scenario:
    status = _status_text(order)
    if status == "imported":
        return "imported"
    if status == "exception":
        return "exception"
    if status == "deallocated":
        return "deallocated"
    if status in {"on hold", "on_hold", "hold"}:
        return "on_hold"
    return "ineligible"


def build_sku_candidate(line: dict) -> SkuCandidate:
    ordered_qty = int(line.get("quantity") or line.get("orderedQty") or 0)
    fulfilled_qty = int(line.get("fulfilledQty") or line.get("shippedQty") or 0)
    hold_qty = int(line.get("hold") or line.get("holdQty") or 0)
    unfulfilled_qty = max(ordered_qty - fulfilled_qty, 0)
    eligible = unfulfilled_qty > 0
    reason = None if eligible else "unfulfilled_qty_zero"
    return SkuCandidate(
        sku=str(line.get("sku") or line.get("skuCode") or ""),
        ordered_qty=ordered_qty,
        fulfilled_qty=fulfilled_qty,
        unfulfilled_qty=unfulfilled_qty,
        hold_qty=hold_qty,
        eligible=eligible,
        reason=reason,
    )


def choose_action_mode(*, scenario: Scenario, skus: list[SkuCandidate], recoverable: bool) -> ActionMode:
    if scenario == "on_hold":
        return "release_hold_then_recover"
    eligible_skus = [sku for sku in skus if sku.eligible]
    if scenario == "deallocated" and len(eligible_skus) != len(skus):
        return "partial_sku"
    if scenario == "deallocated" and any(sku.fulfilled_qty > 0 for sku in skus):
        return "partial_sku"
    return "whole_order"
