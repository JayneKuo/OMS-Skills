from batch_reallocation.models import AnalyzeResponse, ExecuteResponse, FormGroup, OrderCandidate, SkuCandidate
from batch_reallocation.user_view_builder import (
    build_analysis_view,
    build_confirmation_view,
    build_execution_view,
)


def test_build_analysis_view_returns_business_safe_order_summary():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="on_hold",
                title="On Hold orders",
                selection_mode="sku",
                orders=[
                    OrderCandidate(
                        order_no="SO1001",
                        scenario="on_hold",
                        status="On Hold",
                        eligible=True,
                        reason="requires_hold_release",
                        hold_reason="risk-review",
                        skus=[
                            SkuCandidate(
                                sku="SKU-A",
                                ordered_qty=3,
                                fulfilled_qty=1,
                                unfulfilled_qty=2,
                                hold_qty=2,
                                eligible=True,
                                reason="eligible",
                            ),
                            SkuCandidate(
                                sku="SKU-B",
                                ordered_qty=1,
                                fulfilled_qty=1,
                                unfulfilled_qty=0,
                                hold_qty=0,
                                eligible=False,
                                reason="unfulfilled_qty_zero",
                            ),
                        ],
                    )
                ],
            )
        ],
        warnings=["状态可能变化，执行前会再次校验"],
    )

    view = build_analysis_view(response)

    assert view["requires_confirmation"] is True
    assert view["global_warnings"] == ["状态可能变化，执行前会再次校验"]
    assert len(view["orders"]) == 1
    assert view["orders"][0]["order_no"] == "SO1001"
    assert view["orders"][0]["current_status"] == "On Hold"
    assert view["orders"][0]["scenario_group"] == "on_hold"
    assert view["orders"][0]["exception_or_hold_summary"] == "risk-review"
    assert view["orders"][0]["eligibility"]["supported"] is True
    assert view["orders"][0]["eligibility"]["action_mode"] == "sku"
    assert view["orders"][0]["eligibility"]["executable_scope_summary"] == "可执行 1 个 SKU"
    assert view["orders"][0]["eligibility"]["ineligible_scope_summary"] == "不可执行 1 个 SKU"
    assert view["orders"][0]["sku_facts"] == [
        {"sku": "SKU-A", "ordered_qty": 3, "fulfilled_qty": 1, "unfulfilled_qty": 2},
        {"sku": "SKU-B", "ordered_qty": 1, "fulfilled_qty": 1, "unfulfilled_qty": 0},
    ]


def test_build_analysis_view_returns_order_level_eligibility_summary_for_order_mode():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="on_hold",
                title="On Hold orders",
                selection_mode="order",
                orders=[
                    OrderCandidate(
                        order_no="SO3001",
                        scenario="on_hold",
                        status="On Hold",
                        eligible=True,
                        reason="requires_hold_release",
                        hold_reason="risk-review",
                        skus=[
                            SkuCandidate(
                                sku="SKU-A",
                                ordered_qty=3,
                                fulfilled_qty=1,
                                unfulfilled_qty=2,
                                hold_qty=2,
                                eligible=True,
                                reason="eligible",
                            ),
                            SkuCandidate(
                                sku="SKU-B",
                                ordered_qty=2,
                                fulfilled_qty=0,
                                unfulfilled_qty=2,
                                hold_qty=2,
                                eligible=True,
                                reason="eligible",
                            ),
                        ],
                    )
                ],
            )
        ]
    )

    view = build_analysis_view(response)

    assert view["orders"][0]["eligibility"]["action_mode"] == "order"
    assert view["orders"][0]["eligibility"]["executable_scope_summary"] == "可执行 1 个 order"
    assert view["orders"][0]["eligibility"]["ineligible_scope_summary"] == "不可执行 0 个 order"


def test_build_analysis_view_hides_internal_protocol_fields():
    view = build_analysis_view(AnalyzeResponse())

    serialized = str(view)
    assert "form_type" not in view
    assert "next_action" not in view
    assert "payload" not in serialized
    assert "endpoint" not in serialized
    assert "raw_response" not in serialized
    assert "MCP" not in serialized


def test_build_confirmation_view_marks_editable_choices_and_waiting_status():
    response = AnalyzeResponse(
        groups=[
            FormGroup(
                scenario="deallocated",
                title="Deallocated orders",
                selection_mode="sku",
                orders=[
                    OrderCandidate(
                        order_no="SO2001",
                        scenario="deallocated",
                        status="Deallocated",
                        eligible=True,
                        skus=[
                            SkuCandidate(sku="SKU-X", ordered_qty=2, fulfilled_qty=0, unfulfilled_qty=2, eligible=True),
                            SkuCandidate(
                                sku="SKU-Y",
                                ordered_qty=1,
                                fulfilled_qty=1,
                                unfulfilled_qty=0,
                                eligible=False,
                                reason="unfulfilled_qty_zero",
                            ),
                        ],
                    )
                ],
            )
        ],
        warnings=["部分 SKU 已履约，必须按 SKU 选择"],
    )

    decisions = {
        "decisions": [
            {
                "order_no": "SO2001",
                "action_mode": "partial_sku",
                "selected_skus": ["SKU-X"],
                "release_hold": False,
            }
        ]
    }

    view = build_confirmation_view(response, decisions)

    assert view["status"] == "waiting_for_confirmation"
    assert view["order_nos"] == ["SO2001"]
    assert view["scenario_groups"] == ["deallocated"]
    assert view["action_mode_summary"] == "partial_sku"
    assert view["includes_release_hold"] is False
    assert view["selected_skus_by_order"] == [{"order_no": "SO2001", "selected_skus": ["SKU-X"]}]
    assert "selected_skus" in view["editable_choices"]
    assert "order status: Deallocated" in view["readonly_facts"]
    assert view["risks"] == ["部分 SKU 已履约，必须按 SKU 选择"]


def test_build_execution_view_returns_business_summary_without_transport_details():
    response = ExecuteResponse(
        submitted_orders=3,
        succeeded_orders=["SO1"],
        partial_succeeded_orders=["SO2"],
        failed_orders={"SO3": "order no longer recoverable"},
        skipped_orders={"SO4": "status changed before execution"},
        warnings=["SO2 仅部分 SKU 提交成功"],
    )

    view = build_execution_view(response)

    assert view["executed"] is True
    assert view["submitted_orders"] == ["SO1", "SO2", "SO3"]
    assert view["succeeded_orders"] == ["SO1"]
    assert view["partial_succeeded_orders"] == ["SO2"]
    assert view["failed_orders"] == [{"order_no": "SO3", "reason": "order no longer recoverable"}]
    assert view["skipped_orders"] == [{"order_no": "SO4", "reason": "status changed before execution"}]
    assert view["warnings"] == ["SO2 仅部分 SKU 提交成功"]
    assert "endpoint" not in str(view)
    assert "payload" not in str(view)
    assert "raw_response" not in str(view)
