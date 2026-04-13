"""OMSQueryEngine v2 端到端集成测试（mock API）"""
import pytest
from unittest.mock import MagicMock, patch

from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_query_engine.config import EngineConfig
from oms_query_engine.models.request import QueryRequest, BatchQueryRequest


@pytest.fixture
def mock_engine():
    """创建一个 mock API 的引擎实例。"""
    config = EngineConfig(
        base_url="https://test.example.com",
        username="test@example.com",
        password="testpass",
        tenant_id="LT",
        merchant_no="TEST0001",
    )
    engine = OMSQueryEngine(config)

    # mock API client
    client = MagicMock()
    engine._client = client
    engine._resolver._client = client
    engine._executor = _rebuild_executor(client, engine._cache)
    return engine, client


def _rebuild_executor(client, cache):
    from oms_query_engine.provider_executor import ProviderExecutor
    return ProviderExecutor(client, cache)


def _order_detail_resp(status="ALLOCATED", order_no="SO001"):
    return {"data": {
        "orderNo": order_no,
        "merchantNo": "TEST0001",
        "status": status,
        "channelName": "Shopify",
        "channelSalesOrderNo": "SHOP-001",
        "dataChannel": "Shopify",
        "referenceNo": "REF-001",
        "carrierName": "FedEx",
        "itemLines": [
            {"sku": "SKU-A", "qty": 2, "title": "Widget A"},
            {"sku": "SKU-B", "qty": 1, "title": "Widget B"},
        ],
        "shipToAddress": {
            "country": "US", "state": "CA",
            "city": "LA", "zipCode": "90001",
            "address1": "123 Main St",
        },
    }}


def _logs_resp():
    return {"data": [
        {"eventType": "ORDER_CREATED", "createTime": "2026-04-08T08:00:00"},
        {"eventType": "DISPATCH", "createTime": "2026-04-08T09:00:00",
         "eventId": "evt_001"},
    ]}


class TestNormalOrderQuery:
    def test_basic_status_query(self, mock_engine):
        engine, client = mock_engine

        def api_side_effect(path, *args, **kwargs):
            if "sale-order" in path:
                return _order_detail_resp()
            if "orderLog" in path:
                return _logs_resp()
            return {"data": {}}

        client.get.side_effect = api_side_effect
        client.post.return_value = {"data": [{"omsOrderNo": "SO001"}]}

        result = engine.query(QueryRequest(identifier="SO001"))

        assert result.error is None
        assert result.order_identity is not None
        assert result.order_identity.order_no == "SO001"
        assert result.current_status is not None
        assert result.current_status.main_status == "已分仓"
        assert result.current_status.is_exception is False
        assert result.current_status.is_hold is False
        assert result.product_info is not None
        assert len(result.product_info.items) == 2
        assert result.data_completeness.completeness_level in ("full", "partial")

    def test_panorama_query(self, mock_engine):
        engine, client = mock_engine

        def api_side_effect(path, *args, **kwargs):
            if "sale-order" in path:
                return _order_detail_resp()
            if "orderLog" in path:
                return _logs_resp()
            if "tracking-assistant" in path:
                return {"data": {"shipmentNo": "SH001", "carrierName": "FedEx"}}
            if "facility" in path:
                return {"data": {"records": []}}
            if "inventory" in path:
                return {"data": []}
            return {"data": {}}

        client.get.side_effect = api_side_effect
        client.post.side_effect = api_side_effect

        result = engine.query(QueryRequest(
            identifier="SO001", query_intent="全景"))

        assert result.error is None
        assert result.order_identity is not None


class TestHoldQuery:
    def test_hold_status_auto_expands(self, mock_engine):
        engine, client = mock_engine

        def api_side_effect(path, *args, **kwargs):
            if "sale-order" in path:
                return _order_detail_resp(status="ON_HOLD")
            if "orderLog" in path:
                return _logs_resp()
            if "hold-rule" in path:
                return {"data": [{"ruleName": "Fraud Check"}]}
            if "routing" in path or "custom-rule" in path:
                return {"data": []}
            if "sku-warehouse" in path:
                return {"data": []}
            if "dispatch/recover" in path:
                return {"data": {}}
            return {"data": {}}

        client.get.side_effect = api_side_effect
        client.post.return_value = {"data": [{"omsOrderNo": "SO001"}]}

        result = engine.query(QueryRequest(identifier="SO001"))

        assert result.current_status.is_hold is True
        assert result.current_status.main_status == "暂停履约"
        assert result.query_explanation is not None
        assert result.query_explanation.why_hold is not None


class TestExceptionQuery:
    def test_exception_status(self, mock_engine):
        engine, client = mock_engine

        def api_side_effect(path, *args, **kwargs):
            if "sale-order" in path:
                return _order_detail_resp(status="EXCEPTION")
            if "orderLog" in path:
                return {"data": [
                    {"eventType": "EXCEPTION_OCCURRED",
                     "createTime": "2026-04-08T10:00:00"},
                ]}
            return {"data": {}}

        client.get.side_effect = api_side_effect
        client.post.return_value = {"data": [{"omsOrderNo": "SO001"}]}

        result = engine.query(QueryRequest(identifier="SO001"))

        assert result.current_status.is_exception is True
        assert result.query_explanation.why_exception is not None


class TestDeallocatedQuery:
    def test_deallocated_status(self, mock_engine):
        engine, client = mock_engine

        def api_side_effect(path, *args, **kwargs):
            if "sale-order" in path:
                return _order_detail_resp(status="DEALLOCATED")
            if "orderLog" in path:
                return _logs_resp()
            if "dispatch/recover" in path:
                return {"data": {}}
            return {"data": {}}

        client.get.side_effect = api_side_effect
        client.post.return_value = {"data": [{"omsOrderNo": "SO001"}]}

        result = engine.query(QueryRequest(identifier="SO001"))

        assert result.current_status.is_deallocated is True
        assert result.current_status.main_status == "已解除分配"
        assert result.query_explanation.why_deallocated is not None


class TestErrorHandling:
    def test_resolve_failure(self, mock_engine):
        engine, client = mock_engine
        client.post.side_effect = Exception("API error")

        result = engine.query(QueryRequest(identifier="UNKNOWN"))

        assert result.error is not None
        assert result.data_completeness.completeness_level == "minimal"

    def test_partial_extended_failure(self, mock_engine):
        engine, client = mock_engine
        call_count = [0]

        def api_side_effect(path, *args, **kwargs):
            call_count[0] += 1
            if "sale-order" in path:
                return _order_detail_resp(status="SHIPPED")
            if "orderLog" in path:
                return _logs_resp()
            if "tracking-assistant" in path:
                raise Exception("tracking API down")
            return {"data": {}}

        client.get.side_effect = api_side_effect
        client.post.return_value = {"data": [{"omsOrderNo": "SO001"}]}

        result = engine.query(QueryRequest(
            identifier="SO001", query_intent="shipment"))

        # 核心成功，扩展部分失败
        assert result.error is None
        assert result.order_identity is not None


class TestBatchQuery:
    def test_status_count(self, mock_engine):
        engine, client = mock_engine
        client._ensure_token = MagicMock()
        client.get.return_value = {"data": [
            {"status": "Allocated", "num": 312},
            {"status": "Exception", "num": 110},
        ]}

        result = engine.query_batch(
            BatchQueryRequest(query_type="status_count"))

        assert result.status_counts["Allocated"] == 312
        assert result.total == 422

    def test_order_list(self, mock_engine):
        engine, client = mock_engine
        client._ensure_token = MagicMock()
        client.get.return_value = {"data": {
            "records": [{"orderNo": "SO001"}, {"orderNo": "SO002"}],
            "total": 2,
        }}

        result = engine.query_batch(BatchQueryRequest(
            query_type="order_list", status_filter=10))

        assert result.total == 2
        assert len(result.orders) == 2
