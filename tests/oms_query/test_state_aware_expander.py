"""StateAwarePlanExpander 测试"""
import pytest
from oms_query_engine.state_aware_plan_expander import StateAwarePlanExpander
from oms_query_engine.models.query_plan import QueryPlan
from oms_query_engine.models.provider_result import ProviderResult


@pytest.fixture
def expander():
    return StateAwarePlanExpander()


def _make_plan(extended=None):
    return QueryPlan(
        primary_object_type="order",
        primary_key="SO001",
        core_providers=["order", "event"],
        extended_providers=extended or [],
    )


def _make_order_result(status_code):
    return ProviderResult(
        provider_name="order",
        success=True,
        data={"raw_detail": {"status": status_code}},
    )


class TestShippedExpansion:
    def test_shipped_adds_shipment_sync(self, expander):
        plan = _make_plan()
        results = {"order": _make_order_result(3)}
        expanded = expander.expand(plan, results)
        assert "shipment" in expanded.extended_providers
        assert "sync" in expanded.extended_providers

    def test_partially_shipped(self, expander):
        plan = _make_plan()
        results = {"order": _make_order_result(24)}
        expanded = expander.expand(plan, results)
        assert "shipment" in expanded.extended_providers

    def test_no_duplicate_if_already_present(self, expander):
        plan = _make_plan(extended=["shipment"])
        results = {"order": _make_order_result(3)}
        expanded = expander.expand(plan, results)
        assert expanded.extended_providers.count("shipment") == 1


class TestHoldExpansion:
    def test_hold_adds_rule_allocation(self, expander):
        plan = _make_plan()
        results = {"order": _make_order_result(16)}
        expanded = expander.expand(plan, results)
        assert "rule" in expanded.extended_providers
        assert "allocation" in expanded.extended_providers


class TestExceptionExpansion:
    def test_exception_adds_event(self, expander):
        plan = _make_plan()
        results = {"order": _make_order_result(10)}
        expanded = expander.expand(plan, results)
        # event 已在 core，不应重复
        assert "event" not in expanded.extended_providers


class TestDeallocatedExpansion:
    def test_deallocated_adds_allocation_event(self, expander):
        plan = _make_plan()
        results = {"order": _make_order_result(25)}
        expanded = expander.expand(plan, results)
        assert "allocation" in expanded.extended_providers


class TestNoExpansion:
    def test_normal_status_no_expansion(self, expander):
        plan = _make_plan()
        results = {"order": _make_order_result(1)}
        expanded = expander.expand(plan, results)
        assert expanded.extended_providers == []

    def test_non_order_type_no_expansion(self, expander):
        plan = QueryPlan(
            primary_object_type="connector",
            core_providers=["integration"],
        )
        results = {}
        expanded = expander.expand(plan, results)
        assert expanded.extended_providers == []
