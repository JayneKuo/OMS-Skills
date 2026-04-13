"""order_query_engine 测试共享 fixtures"""

import pytest

from order_query_engine.config import EngineConfig


@pytest.fixture
def engine_config() -> EngineConfig:
    """提供测试用的引擎配置。"""
    return EngineConfig(
        base_url="https://omsv2-staging.item.com",
        username="test@example.com",
        password="testpass",
        tenant_id="LT",
        merchant_no="LAN0000002",
    )
