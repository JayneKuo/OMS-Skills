"""OrderQueryEngine 集成单元测试"""

from unittest.mock import patch, MagicMock

import pytest
import requests

from order_query_engine.config import EngineConfig
from order_query_engine.engine import OrderQueryEngine
from order_query_engine.models import QueryRequest, BatchQueryRequest


@pytest.fixture
def config():
    return EngineConfig(base_url="https://test.example.com")


def _mock_auth():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": {"access_token": "tok", "expires_in": 3600},
    }
    return resp


def _mock_order_detail(status=1, order_no="SO001"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": {
            "omsOrderNo": order_no,
            "merchantNo": "LAN0000002",
            "status": status,
            "itemLines": [{"sku": "SKU1", "quantity": 1}],
            "shippingAddress": {"country": "US", "state": "CA"},
        },
    }
    return resp


def _mock_logs():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": [{"eventType": "CREATED", "createTime": "2026-04-08"}],
    }
    return resp

def _mock_search():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"code": 0, "data": [{"omsOrderNo": "SO001"}]}
    return resp


def _mock_404():
    resp = MagicMock()
    resp.status_code = 404
    resp.text = "Not Found"
    resp.json.return_value = {"code": 404, "message": "Not Found"}
    return resp


def _mock_status_count():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": [
            {"status": "Allocated", "num": 312},
            {"status": "Exception", "num": 110},
        ],
    }
    return resp


def _mock_order_list():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": 0,
        "data": {
            "list": [{"orderNo": "SO001"}, {"orderNo": "SO002"}],
            "total": 2,
        },
    }
    return resp


def _route_requests(method):
    """Create a side_effect function that routes based on URL/path."""
    def side_effect(url, **kwargs):
        if "iam/token" in url:
            return _mock_auth()
        if "search-order-no" in url:
            return _mock_search()
        if "sale-order/status/num" in url:
            return _mock_status_count()
        if "sale-order/page" in url:
            return _mock_order_list()
        if "sale-order/" in url:
            return _mock_order_detail()
        if "orderLog" in url:
            return _mock_logs()
        # Default for extended APIs
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"code": 0, "data": {}}
        return r
    return side_effect


class TestSingleQuery:
    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_normal_order_query(self, mock_post, mock_get, config):
        mock_post.side_effect = _route_requests("post")
        mock_get.side_effect = _route_requests("get")
        engine = OrderQueryEngine(config)
        result = engine.query(QueryRequest(identifier="SO001"))
        assert result.error is None
        assert result.order_identity is not None
        assert result.current_status.main_status == "已分仓"

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_panorama_query(self, mock_post, mock_get, config):
        mock_post.side_effect = _route_requests("post")
        mock_get.side_effect = _route_requests("get")
        engine = OrderQueryEngine(config)
        result = engine.query(
            QueryRequest(identifier="SO001", query_intent="全景")
        )
        assert result.error is None
        assert result.data_completeness.completeness_level in ("full", "partial")

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_auth_failure(self, mock_post, mock_get, config):
        auth_resp = MagicMock()
        auth_resp.status_code = 401
        auth_resp.text = "Unauthorized"
        mock_post.return_value = auth_resp
        engine = OrderQueryEngine(config)
        result = engine.query(QueryRequest(identifier="SO001"))
        assert result.error is not None
        assert result.error["error_type"] == "auth_failed"

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_order_not_found(self, mock_post, mock_get, config):
        mock_post.side_effect = _route_requests("post")
        def get_side(url, **kwargs):
            if "sale-order/" in url and "status" not in url and "page" not in url:
                return _mock_404()
            return _route_requests("get")(url, **kwargs)
        mock_get.side_effect = get_side
        engine = OrderQueryEngine(config)
        result = engine.query(QueryRequest(identifier="SO999"))
        assert result.error is not None
        assert result.error["error_type"] == "not_found"

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_resolve_failure(self, mock_post, mock_get, config):
        def post_side(url, **kwargs):
            if "iam/token" in url:
                return _mock_auth()
            if "search-order-no" in url:
                r = MagicMock()
                r.status_code = 200
                r.json.return_value = {"code": 0, "data": []}
                return r
            return _mock_auth()
        mock_post.side_effect = post_side
        engine = OrderQueryEngine(config)
        result = engine.query(QueryRequest(identifier="UNKNOWN_XYZ"))
        assert result.error is not None

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_force_refresh(self, mock_post, mock_get, config):
        mock_post.side_effect = _route_requests("post")
        mock_get.side_effect = _route_requests("get")
        engine = OrderQueryEngine(config)
        engine.query(QueryRequest(identifier="SO001"))
        # Force refresh should clear cache
        result = engine.query(
            QueryRequest(identifier="SO001", force_refresh=True)
        )
        assert result.error is None


class TestBatchQuery:
    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_status_count(self, mock_post, mock_get, config):
        mock_post.side_effect = _route_requests("post")
        mock_get.side_effect = _route_requests("get")
        engine = OrderQueryEngine(config)
        result = engine.query_batch(
            BatchQueryRequest(query_type="status_count")
        )
        assert result.status_counts is not None
        assert result.total > 0

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_order_list(self, mock_post, mock_get, config):
        mock_post.side_effect = _route_requests("post")
        mock_get.side_effect = _route_requests("get")
        engine = OrderQueryEngine(config)
        result = engine.query_batch(
            BatchQueryRequest(query_type="order_list", status_filter=10)
        )
        assert result.orders is not None
        assert result.total == 2
