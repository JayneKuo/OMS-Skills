from batch_reallocation.eligibility import build_sku_candidate, classify_order_scenario, choose_action_mode


def test_imported_order_with_unfulfilled_qty_is_eligible_whole_order():
    order = {"status": "Imported", "orderNo": "SO1"}
    sku_lines = [{"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0}]

    scenario = classify_order_scenario(order)
    sku = build_sku_candidate(sku_lines[0])
    mode = choose_action_mode(scenario=scenario, skus=[sku], recoverable=True)

    assert scenario == "imported"
    assert sku.unfulfilled_qty == 3
    assert sku.eligible is True
    assert mode == "whole_order"


def test_deallocated_mixed_fulfillment_forces_partial_sku():
    order = {"status": "Deallocated", "orderNo": "SO2"}
    skus = [
        build_sku_candidate({"sku": "SKU-A", "quantity": 5, "fulfilledQty": 5, "hold": 0}),
        build_sku_candidate({"sku": "SKU-B", "quantity": 4, "fulfilledQty": 1, "hold": 0}),
    ]

    mode = choose_action_mode(scenario=classify_order_scenario(order), skus=skus, recoverable=True)

    assert skus[0].eligible is False
    assert skus[1].unfulfilled_qty == 3
    assert mode == "partial_sku"


def test_on_hold_sku_requires_release_hold_then_recover():
    order = {"status": "On Hold", "orderNo": "SO3", "holdReason": "fraud-check"}
    skus = [build_sku_candidate({"sku": "SKU-C", "quantity": 2, "fulfilledQty": 0, "hold": 2})]

    mode = choose_action_mode(scenario=classify_order_scenario(order), skus=skus, recoverable=True)

    assert classify_order_scenario(order) == "on_hold"
    assert mode == "release_hold_then_recover"


def test_zero_unfulfilled_qty_is_ineligible():
    sku = build_sku_candidate({"sku": "SKU-Z", "quantity": 2, "fulfilledQty": 2, "hold": 0})

    assert sku.unfulfilled_qty == 0
    assert sku.eligible is False
    assert sku.reason == "unfulfilled_qty_zero"
