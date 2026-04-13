"""ResultAssembler 单元测试"""

import pytest

from order_query_engine.models import (
    CoreQueryResult, ExtendedQueryResult, QueryInput,
)
from order_query_engine.result_assembler import ResultAssembler
from order_query_engine.status_normalizer import StatusNormalizer

assembler = ResultAssembler(StatusNormalizer())


def _core(status=1, order_no="SO001"):
    return CoreQueryResult(
        success=True,
        search_result={"code": 0, "data": {"orderNo": order_no}},
        order_detail={
            "code": 0,
            "data": {
                "omsOrderNo": order_no,
                "merchantNo": "LAN0000002",
                "status": status,
                "itemLines": [
                    {"sku": "SKU001", "quantity": 2, "description": "Test Item"}
                ],
                "shippingAddress": {
                    "country": "US", "state": "CA",
                    "city": "LA", "zipcode": "90001",
                },
            },
        },
        order_logs={
            "code": 0,
            "data": [
                {"eventType": "ORDER_CREATED", "createTime": "2026-04-08T10:00:00"}
            ],
        },
    )


def _qi(order_no="SO001"):
    return QueryInput(
        input_value=order_no,
        identified_type="orderNo",
        resolved_order_no=order_no,
    )


class TestCoreAssembly:
    def test_basic_assembly(self):
        result = assembler.assemble(_core(), None, _qi())
        assert result.order_identity.order_no == "SO001"
        assert result.current_status.main_status == "已分仓"
        assert result.current_status.is_exception is False
        assert result.current_status.is_hold is False
        assert result.order_items is not None
        assert len(result.order_items) == 1
        assert result.shipping_address.country == "US"

    def test_hold_status(self):
        result = assembler.assemble(_core(status=16), None, _qi())
        assert result.current_status.is_hold is True
        assert result.current_status.is_exception is False
        assert result.query_explanation.why_hold is not None

    def test_exception_status(self):
        result = assembler.assemble(_core(status=10), None, _qi())
        assert result.current_status.is_exception is True
        assert result.current_status.is_hold is False
        assert result.query_explanation.why_exception is not None

    def test_allocated_explanation(self):
        result = assembler.assemble(_core(status=1), None, _qi())
        assert result.query_explanation.current_step is not None
        assert "分仓" in result.query_explanation.current_step or "分配" in result.query_explanation.current_step


class TestExtendedAssembly:
    def test_partial_failure_degradation(self):
        ext = ExtendedQueryResult(
            failed_apis=["tracking_detail"],
            called_apis=["hold_rules"],
            hold_rules={"code": 0, "data": [{"ruleName": "TestRule"}]},
        )
        result = assembler.assemble(_core(), ext, _qi())
        assert result.data_completeness.completeness_level == "partial"
        assert "tracking_detail" in result.data_completeness.missing_fields

    def test_full_completeness(self):
        ext = ExtendedQueryResult(called_apis=["hold_rules"])
        result = assembler.assemble(_core(), ext, _qi())
        assert result.data_completeness.completeness_level == "full"

    def test_minimal_completeness(self):
        core = CoreQueryResult(success=False, errors=["failed"])
        result = assembler.assemble(core, None, _qi())
        assert result.data_completeness.completeness_level == "minimal"


class TestHoldExplanation:
    def test_hold_with_rules(self):
        ext = ExtendedQueryResult(
            hold_rules={"code": 0, "data": [{"ruleName": "FraudCheck"}]},
            called_apis=["hold_rules"],
        )
        result = assembler.assemble(_core(status=16), ext, _qi())
        assert "FraudCheck" in result.query_explanation.why_hold

    def test_hold_without_rules(self):
        result = assembler.assemble(_core(status=16), None, _qi())
        assert result.query_explanation.why_hold is not None
