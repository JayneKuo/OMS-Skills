"""QueryOrchestrator 单元测试"""

from unittest.mock import MagicMock

import pytest

from order_query_engine.cache import QueryCache
from order_query_engine.config import EngineConfig
from order_query_engine.errors import APICallError, OrderNotFoundError
from order_query_engine.query_orchestrator import QueryOrchestrator


@pytest.fixture
def mock_client():
    client = MagicMock()
    client._config = EngineConfig(base_url="https://test.example.com")
    return client


@pytest.fixture
def orchestrator(mock_client):
    return QueryOrchestrator(mock_client, QueryCache())


class TestIntentDetection:
    def test_status_only(self, orchestrator):
        assert orchestrator.detect_intents("status") == []
        assert orchestrator.detect_intents("订单状态") == []

    def test_shipment_intent(self, orchestrator):
        assert "shipment" in orchestrator.detect_intents("shipment追踪")

    def test_warehouse_intent(self, orchestrator):
        assert "warehouse" in orchestrator.detect_intents("仓库分仓")

    def test_rule_intent(self, orchestrator):
        assert "rule" in orchestrator.detect_intents("规则策略")

    def test_inventory_intent(self, orchestrator):
        assert "inventory" in orchestrator.detect_intents("库存")

    def test_hold_intent(self, orchestrator):
        assert "hold" in orchestrator.detect_intents("Hold暂停")

    def test_timeline_intent(self, orchestrator):
        assert "timeline" in orchestrator.detect_intents("时间线事件")

    def test_panorama_overrides_all(self, orchestrator):
        result = orchestrator.detect_intents("全景")
        assert result == ["panorama"]


class TestCoreQuery:
    def test_core_query_success(self, orchestrator, mock_client):
        mock_client.post.return_value = {"code": 0, "data": {"orderNo": "SO001"}}
        mock_client.get.return_value = {"code": 0, "data": {"status": 1}}
        result = orchestrator.execute_core("SO001")
        assert result.success is True
        assert result.order_detail is not None

    def test_core_query_order_not_found(self, orchestrator, mock_client):
        mock_client.post.return_value = {"code": 0, "data": {}}
        mock_client.get.side_effect = APICallError("/sale-order/SO999", 404, "Not Found")
        with pytest.raises(OrderNotFoundError):
            orchestrator.execute_core("SO999")

    def test_core_query_cache_hit(self, orchestrator, mock_client):
        mock_client.post.return_value = {"code": 0, "data": {}}
        mock_client.get.return_value = {"code": 0, "data": {"status": 1}}
        orchestrator.execute_core("SO001")
        # Second call should use cache
        mock_client.get.reset_mock()
        mock_client.post.reset_mock()
        result = orchestrator.execute_core("SO001")
        assert result.success is True
        mock_client.get.assert_not_called()
        mock_client.post.assert_not_called()


class TestExtendedQuery:
    def test_shipment_extended(self, orchestrator, mock_client):
        mock_client.get.return_value = {"code": 0, "data": {}}
        from order_query_engine.models import CoreQueryResult
        core = CoreQueryResult(success=True)
        result = orchestrator.execute_extended("SO001", ["shipment"], core)
        assert "tracking_detail" in result.called_apis

    def test_extended_partial_failure(self, orchestrator, mock_client):
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise APICallError("/test", 500, "Error")
            return {"code": 0, "data": {}}
        mock_client.get.side_effect = side_effect
        from order_query_engine.models import CoreQueryResult
        core = CoreQueryResult(success=True)
        result = orchestrator.execute_extended("SO001", ["shipment"], core)
        # Some APIs should succeed, some may fail
        assert len(result.failed_apis) <= 3

    def test_panorama_calls_all(self, orchestrator, mock_client):
        mock_client.get.return_value = {"code": 0, "data": {}}
        mock_client.post.return_value = {"code": 0, "data": {}}
        from order_query_engine.models import CoreQueryResult
        core = CoreQueryResult(success=True)
        result = orchestrator.execute_extended("SO001", ["panorama"], core)
        assert len(result.called_apis) > 0
