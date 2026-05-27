from batch_reallocation.form_builder import build_form_payload
from batch_reallocation.models import AnalyzeResponse, FormGroup, OrderCandidate, SkuCandidate


def test_form_builder_emits_order_and_sku_groups_with_confirmation_flags():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="imported",
                title="Imported orders",
                selection_mode="order",
                orders=[
                    OrderCandidate(
                        order_no="SO1",
                        scenario="imported",
                        status="Imported",
                        eligible=True,
                        skus=[SkuCandidate(sku="SKU-A", ordered_qty=3, fulfilled_qty=0, unfulfilled_qty=3, eligible=True)],
                    )
                ],
            ),
            FormGroup(
                scenario="on_hold",
                title="On Hold orders",
                selection_mode="sku",
                orders=[
                    OrderCandidate(
                        order_no="SO2",
                        scenario="on_hold",
                        status="On Hold",
                        eligible=True,
                        hold_reason="risk",
                        skus=[SkuCandidate(sku="SKU-B", ordered_qty=2, fulfilled_qty=0, unfulfilled_qty=2, hold_qty=2, eligible=True)],
                    )
                ],
            ),
        ]
    )

    payload = build_form_payload(response)

    assert payload["form_type"] == "batch-reallocation-analysis"
    assert payload["requires_confirmation"] is True
    assert payload["groups"][0]["selection_mode"] == "order"
    assert payload["groups"][1]["selection_mode"] == "sku"
    assert payload["groups"][1]["orders"][0]["hold_reason"] == "risk"
