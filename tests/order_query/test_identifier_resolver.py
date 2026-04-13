"""IdentifierResolver 单元测试"""

from unittest.mock import MagicMock

import pytest

from order_query_engine.cache import QueryCache
from order_query_engine.config import EngineConfig
from order_query_engine.identifier_resolver import IdentifierResolver


@pytest.fixture
def mock_client():
    client = MagicMock()
    client._config = EngineConfig(base_url="https://test.example.com")
    return client


@pytest.fixture
def resolver(mock_client):
    return IdentifierResolver(mock_client, QueryCache())


class TestPatternMatching:
    def test_so_prefix_is_order_no(self, resolver):
        result = resolver.resolve("SO00168596")
        assert result.success is True
        assert result.query_input.identified_type == "orderNo"
        assert result.query_input.resolved_order_no == "SO00168596"

    def test_po_prefix_is_order_no(self, resolver):
        result = resolver.resolve("PO00123456")
        assert result.success is True
        assert result.query_input.identified_type == "orderNo"

    def test_wo_prefix_is_order_no(self, resolver):
        result = resolver.resolve("WO00123456")
        assert result.success is True
        assert result.query_input.identified_type == "orderNo"

    def test_sh_prefix_is_shipment_no(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO00168596"}]
        }
        result = resolver.resolve("SH00123456")
        assert result.success is True
        assert result.query_input.identified_type == "shipmentNo"
        assert result.query_input.resolved_order_no == "SO00168596"

    def test_evt_prefix_is_event_id(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO00168596"}]
        }
        result = resolver.resolve("evt_abc123")
        assert result.success is True
        assert result.query_input.identified_type == "eventId"

    def test_pure_number_is_event_id(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO00168596"}]
        }
        result = resolver.resolve("123456")
        assert result.success is True
        assert result.query_input.identified_type == "eventId"


class TestAPIFallback:
    def test_unknown_format_fallback(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [{"omsOrderNo": "SO00168596"}]
        }
        result = resolver.resolve("1Z999AA10123456784")
        assert result.success is True
        assert result.query_input.resolved_order_no == "SO00168596"

    def test_multiple_candidates(self, resolver, mock_client):
        mock_client.post.return_value = {
            "data": [
                {"omsOrderNo": "SO001"},
                {"omsOrderNo": "SO002"},
            ]
        }
        result = resolver.resolve("SH00123456")
        assert result.success is False
        assert result.candidates == ["SO001", "SO002"]

    def test_all_fallback_fail(self, resolver, mock_client):
        mock_client.post.return_value = {"data": []}
        result = resolver.resolve("UNKNOWN_FORMAT_XYZ")
        assert result.success is False
        assert result.error is not None
        assert result.error["error_type"] == "resolve_failed"
