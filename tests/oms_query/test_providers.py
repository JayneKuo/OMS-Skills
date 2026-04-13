"""Provider 单元测试"""
import pytest
from unittest.mock import MagicMock

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.providers.order import OrderProvider
from oms_query_engine.providers.event import EventProvider
from oms_query_engine.providers.inventory import InventoryProvider
from oms_query_engine.providers.warehouse import WarehouseProvider
from oms_query_engine.providers.allocation import AllocationProvider
from oms_query_engine.providers.rule import RuleProvider
from oms_query_engine.providers.fulfillment import FulfillmentProvider
from oms_query_engine.providers.shipment import ShipmentProvider
from oms_query_engine.providers.sync import SyncProvider
from oms_query_engine.providers.integration import IntegrationProvider
from oms_query_engine.providers.batch import BatchProvider


@pytest.fixture
def ctx():
    return QueryContext(
        primary_key="SO001",
        order_no="SO001",
        merchant_no="TEST0001",
        intents=["timeline"],
    )


# ── OrderProvider ─────────────────────────────────────

class TestOrderProvider:
    def test_success(self, mock_client, cache, ctx):
        mock_client.get.return_value = {"data": {
            "orderNo": "SO001",
            "merchantNo": "TEST0001",
            "status": "ALLOCATED",
            "channelName": "Shopify",
            "channelSalesOrderNo": "SHOP-001",
            "referenceNo": "REF-001",
            "carrierName": "FedEx",
            "itemLines": [{"sku": "SKU-A", "qty": 2}],
            "shipToAddress": {"country": "US", "state": "CA", "zipCode": "90001"},
        }}
        p = OrderProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True
        assert r.data["order_identity"].order_no == "SO001"
        assert r.data["order_identity"].external_order_no == "SHOP-001"
        assert r.data["product_info"].items[0].sku == "SKU-A"
        assert r.data["product_info"].items[0].quantity == 2
        assert r.data["shipping_address"].country == "US"
        assert r.data["shipping_address"].zipcode == "90001"

    def test_missing_order_no(self, mock_client, cache):
        ctx = QueryContext()
        p = OrderProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is False
        assert "缺少 orderNo" in r.errors[0]

    def test_api_failure(self, mock_client, cache, ctx):
        mock_client.get.side_effect = Exception("timeout")
        p = OrderProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is False


# ── EventProvider ─────────────────────────────────────

class TestEventProvider:
    def test_success(self, mock_client, cache, ctx):
        mock_client.get.return_value = {"data": [
            {"eventType": "DISPATCH", "createTime": "2026-04-08T10:00:00"},
        ]}
        p = EventProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True
        assert r.data["event_info"].latest_event_type == "DISPATCH"

    def test_failure_graceful(self, mock_client, cache, ctx):
        mock_client.get.side_effect = Exception("fail")
        p = EventProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True  # event 即使日志失败也返回成功（空数据）


# ── InventoryProvider ─────────────────────────────────

class TestInventoryProvider:
    def test_success(self, mock_client, cache, ctx):
        mock_client.post.return_value = {"data": [
            {"sku": "SKU-A", "warehouseNo": "WH01", "availableQty": 100},
        ]}
        p = InventoryProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True
        assert r.data["inventory_info"].sku_inventory[0].sku == "SKU-A"

    def test_failure(self, mock_client, cache, ctx):
        mock_client.post.side_effect = Exception("fail")
        p = InventoryProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is False


# ── WarehouseProvider ─────────────────────────────────

class TestWarehouseProvider:
    def test_success(self, mock_client, cache, ctx):
        mock_client.post.return_value = {"data": {"records": []}}
        p = WarehouseProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True

    def test_failure(self, mock_client, cache, ctx):
        mock_client.post.side_effect = Exception("fail")
        p = WarehouseProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is False


# ── RuleProvider ──────────────────────────────────────

class TestRuleProvider:
    def test_success(self, mock_client, cache, ctx):
        mock_client.get.return_value = {"data": [{"ruleName": "R1"}]}
        p = RuleProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True
        assert r.data["rule_info"].routing_rules is not None

    def test_partial_failure(self, mock_client, cache, ctx):
        call_count = [0]
        def side_effect(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("fail")
            return {"data": []}
        mock_client.get.side_effect = side_effect
        p = RuleProvider(mock_client, cache)
        r = p.query(ctx)
        assert len(r.failed_apis) >= 1


# ── ShipmentProvider ──────────────────────────────────

class TestShipmentProvider:
    def test_success(self, mock_client, cache, ctx):
        mock_client.get.return_value = {"data": {
            "shipmentNo": "SH001",
            "carrierName": "FedEx",
            "trackingNo": "1Z999",
        }}
        p = ShipmentProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True
        assert r.data["shipment_info"].carrier_name == "FedEx"


# ── SyncProvider ──────────────────────────────────────

class TestSyncProvider:
    def test_stub(self, mock_client, cache, ctx):
        p = SyncProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True


# ── IntegrationProvider ───────────────────────────────

class TestIntegrationProvider:
    def test_stub(self, mock_client, cache, ctx):
        p = IntegrationProvider(mock_client, cache)
        r = p.query(ctx)
        assert r.success is True


# ── BatchProvider ─────────────────────────────────────

class TestBatchProvider:
    def test_status_count(self, mock_client, cache):
        mock_client.get.return_value = {"data": [
            {"status": "Allocated", "num": 100},
            {"status": "Exception", "num": 10},
        ]}
        mock_client._ensure_token = MagicMock()
        p = BatchProvider(mock_client, cache)
        r = p.query_status_count("TEST0001")
        assert r.status_counts["Allocated"] == 100
        assert r.total == 110

    def test_order_list(self, mock_client, cache):
        mock_client.get.return_value = {"data": {
            "records": [{"orderNo": "SO001"}],
            "total": 1,
        }}
        mock_client._ensure_token = MagicMock()
        p = BatchProvider(mock_client, cache)
        r = p.query_order_list("TEST0001")
        assert r.total == 1
        assert len(r.orders) == 1
