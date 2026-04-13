"""ObjectResolver 测试"""
import pytest
from unittest.mock import MagicMock

from oms_query_engine.object_resolver import ObjectResolver
from oms_query_engine.cache import QueryCache


@pytest.fixture
def resolver(mock_client, cache):
    return ObjectResolver(mock_client, cache)


class TestPatternMatching:
    def test_so_prefix(self, resolver):
        r = resolver.resolve("SO00168596")
        assert r.success is True
        assert r.query_input.identified_type == "orderNo"
        assert r.query_input.primary_object_type == "order"
        assert r.query_input.resolved_order_no == "SO00168596"

    def test_po_prefix(self, resolver):
        r = resolver.resolve("PO12345")
        assert r.success is True
        assert r.query_input.identified_type == "orderNo"

    def test_wo_prefix(self, resolver):
        r = resolver.resolve("WO99999")
        assert r.success is True
        assert r.query_input.identified_type == "orderNo"

    def test_sh_prefix(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO001"}]
        }
        r = resolver.resolve("SH00123")
        assert r.query_input.identified_type == "shipmentNo"
        assert r.query_input.primary_object_type == "order"

    def test_event_id(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO002"}]
        }
        r = resolver.resolve("evt_abc123")
        assert r.query_input.identified_type == "eventId"

    def test_pure_number_as_event(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO003"}]
        }
        r = resolver.resolve("12345")
        assert r.query_input.identified_type == "eventId"


class TestHintDriven:
    def test_connector_hint(self, resolver):
        r = resolver.resolve("shopify-main", hint="connector")
        assert r.success is True
        assert r.query_input.primary_object_type == "connector"

    def test_warehouse_hint(self, resolver):
        r = resolver.resolve("Ontario-WH", hint="warehouse")
        assert r.success is True
        assert r.query_input.primary_object_type == "warehouse"

    def test_sku_hint(self, resolver):
        r = resolver.resolve("SKU-001", hint="sku")
        assert r.success is True
        assert r.query_input.primary_object_type == "sku"

    def test_batch_hint(self, resolver):
        r = resolver.resolve("", hint="batch")
        assert r.success is True
        assert r.query_input.primary_object_type == "batch"


class TestAPIFallback:
    def test_unknown_format_api_resolve(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO999"}]
        }
        r = resolver.resolve("UNKNOWN-123")
        assert r.success is True
        assert r.query_input.resolved_order_no == "SO999"

    def test_multiple_candidates(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO001"}, {"omsOrderNo": "SO002"}]
        }
        r = resolver.resolve("AMBIGUOUS")
        assert r.success is False
        assert r.candidates == ["SO001", "SO002"]

    def test_all_fail(self, resolver, mock_client):
        mock_client.post.side_effect = Exception("API error")
        r = resolver.resolve("NOTHING")
        assert r.success is False
        assert r.error is not None
        assert r.error["error_type"] == "resolve_failed"
