"""OMSAPIClient 单元测试"""

import time
from unittest.mock import patch, MagicMock

import pytest
import requests

from order_query_engine.api_client import OMSAPIClient
from order_query_engine.config import EngineConfig
from order_query_engine.errors import (
    AuthenticationError,
    APICallError,
    NetworkTimeoutError,
)


@pytest.fixture
def config():
    return EngineConfig(base_url="https://test.example.com")


@pytest.fixture
def client(config):
    return OMSAPIClient(config)


def _mock_auth_response(status=200, token="test_token", expires_in=300):
    resp = MagicMock()
    resp.status_code = status
    resp.text = '{"code":0}'
    resp.json.return_value = {
        "code": 0,
        "data": {"access_token": token, "expires_in": expires_in},
    }
    return resp


def _mock_api_response(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = str(body or {})
    resp.json.return_value = body or {"code": 0, "data": {}}
    return resp


class TestAuthentication:
    @patch("order_query_engine.api_client.requests.post")
    def test_authenticate_success(self, mock_post, client):
        mock_post.return_value = _mock_auth_response()
        token = client.authenticate()
        assert token == "test_token"
        assert client._token == "test_token"

    @patch("order_query_engine.api_client.requests.post")
    def test_authenticate_failure(self, mock_post, client):
        mock_post.return_value = _mock_auth_response(status=401)
        mock_post.return_value.text = "Unauthorized"
        with pytest.raises(AuthenticationError) as exc_info:
            client.authenticate()
        assert exc_info.value.error_type == "auth_failed"
        assert exc_info.value.context["status_code"] == 401

    @patch("order_query_engine.api_client.requests.post")
    def test_authenticate_timeout(self, mock_post, client):
        mock_post.side_effect = requests.exceptions.Timeout()
        with pytest.raises(NetworkTimeoutError):
            client.authenticate()

    @patch("order_query_engine.api_client.requests.post")
    def test_token_auto_refresh(self, mock_post, client):
        mock_post.return_value = _mock_auth_response(expires_in=10)
        client.authenticate()
        # Token should expire soon (10 - 30 = already expired)
        assert time.time() >= client._token_expires_at
        # Next call should trigger re-auth
        mock_post.return_value = _mock_auth_response(
            token="refreshed", expires_in=300
        )
        mock_get = MagicMock(return_value=_mock_api_response())
        with patch("order_query_engine.api_client.requests.get", mock_get):
            client.get("/test")
        assert client._token == "refreshed"


class TestHTTPMethods:
    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_get_success(self, mock_post, mock_get, client):
        mock_post.return_value = _mock_auth_response()
        mock_get.return_value = _mock_api_response(body={"code": 0, "data": {"id": 1}})
        result = client.get("/api/test", params={"key": "val"})
        assert result == {"code": 0, "data": {"id": 1}}

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_get_api_error(self, mock_post, mock_get, client):
        mock_post.return_value = _mock_auth_response()
        mock_get.return_value = _mock_api_response(status=404)
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
        assert exc_info.value.context["status_code"] == 404

    @patch("order_query_engine.api_client.requests.get")
    @patch("order_query_engine.api_client.requests.post")
    def test_get_network_timeout(self, mock_post, mock_get, client):
        mock_post.return_value = _mock_auth_response()
        client.authenticate()
        mock_get.side_effect = requests.exceptions.Timeout()
        with pytest.raises(NetworkTimeoutError):
            client.get("/api/test")

    @patch("order_query_engine.api_client.requests.post")
    def test_post_success(self, mock_post, client):
        mock_post.side_effect = [
            _mock_auth_response(),
            _mock_api_response(body={"code": 0, "data": []}),
        ]
        result = client.post("/api/test", data={"q": "v"})
        assert result == {"code": 0, "data": []}
