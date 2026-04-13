"""QueryPlanBuilder 测试"""
import pytest
from oms_query_engine.query_plan_builder import QueryPlanBuilder
from oms_query_engine.models.resolve import QueryInput, ResolveResult


@pytest.fixture
def builder():
    return QueryPlanBuilder()


def _make_resolve(obj_type="order", key="SO001"):
    qi = QueryInput(
        input_value=key,
        primary_object_type=obj_type,
        resolved_primary_key=key,
        resolved_order_no=key if obj_type == "order" else None,
    )
    return ResolveResult(success=True, query_input=qi)


class TestObjectTypeRouting:
    def test_order_core(self, builder):
        plan = builder.build(_make_resolve("order"), "status")
        assert "order" in plan.core_providers
        assert "event" in plan.core_providers
        assert plan.primary_object_type == "order"

    def test_connector_core(self, builder):
        plan = builder.build(_make_resolve("connector", "shopify"), "")
        assert plan.core_providers == ["integration"]
        assert plan.primary_object_type == "connector"

    def test_warehouse_core(self, builder):
        plan = builder.build(_make_resolve("warehouse", "WH01"), "")
        assert plan.core_providers == ["warehouse"]

    def test_sku_core(self, builder):
        plan = builder.build(_make_resolve("sku", "SKU001"), "")
        assert plan.core_providers == ["inventory"]

    def test_batch_core(self, builder):
        plan = builder.build(_make_resolve("batch", ""), "")
        assert plan.core_providers == ["batch"]


class TestIntentDetection:
    def test_status_only(self, builder):
        plan = builder.build(_make_resolve(), "status")
        assert plan.extended_providers == []

    def test_shipment_intent(self, builder):
        plan = builder.build(_make_resolve(), "shipment 追踪")
        assert "shipment" in plan.extended_providers

    def test_warehouse_intent(self, builder):
        plan = builder.build(_make_resolve(), "仓库")
        assert "warehouse" in plan.extended_providers

    def test_rule_intent(self, builder):
        plan = builder.build(_make_resolve(), "规则")
        assert "rule" in plan.extended_providers

    def test_inventory_intent(self, builder):
        plan = builder.build(_make_resolve(), "库存")
        assert "inventory" in plan.extended_providers

    def test_hold_intent(self, builder):
        plan = builder.build(_make_resolve(), "hold 暂停")
        assert "rule" in plan.extended_providers

    def test_panorama_all(self, builder):
        plan = builder.build(_make_resolve(), "全景")
        assert len(plan.extended_providers) >= 6

    def test_integration_intent(self, builder):
        plan = builder.build(_make_resolve(), "连接器 集成")
        assert "integration" in plan.extended_providers
