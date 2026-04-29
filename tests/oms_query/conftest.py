"""oms_query_engine 测试共享 fixtures"""
import pytest
from unittest.mock import MagicMock

from oms_query_engine.config import EngineConfig
from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.cache import QueryCache


@pytest.fixture
def engine_config():
    return EngineConfig(
        base_url="https://test.example.com",
        tenant_id="LT",
        merchant_no="TEST0001",
        access_token="test-token",
    )


@pytest.fixture
def mock_client():
    client = MagicMock(spec=OMSAPIClient)
    return client


@pytest.fixture
def cache():
    return QueryCache()
