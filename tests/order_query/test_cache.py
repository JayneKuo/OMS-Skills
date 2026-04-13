"""QueryCache 单元测试"""

import time
from unittest.mock import patch

from order_query_engine.cache import QueryCache


class TestQueryCache:
    def test_set_and_get(self):
        cache = QueryCache()
        cache.set("key1", {"data": 1}, ttl=60)
        assert cache.get("key1") == {"data": 1}

    def test_get_missing_key(self):
        cache = QueryCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = QueryCache()
        cache.set("key1", "value", ttl=1)
        with patch("order_query_engine.cache.time") as mock_time:
            # First call to set uses real time, simulate expiry on get
            mock_time.time.return_value = time.time() + 2
            assert cache.get("key1") is None

    def test_invalidate_all(self):
        cache = QueryCache()
        cache.set("a", 1, ttl=60)
        cache.set("b", 2, ttl=300)
        cache.invalidate_all()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_different_ttl_strategies(self):
        cache = QueryCache()
        cache.set("order_detail", {"order": "data"}, ttl=60)
        cache.set("warehouse", {"wh": "data"}, ttl=300)
        assert cache.get("order_detail") is not None
        assert cache.get("warehouse") is not None
