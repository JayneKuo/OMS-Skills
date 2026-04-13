"""Provider 基类"""
from __future__ import annotations
from abc import ABC, abstractmethod

from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult


class BaseProvider(ABC):
    """所有 Provider 的基类。"""

    name: str = "base"

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._client = client
        self._cache = cache

    @abstractmethod
    def query(self, context: QueryContext) -> ProviderResult:
        """执行本域查询，返回 ProviderResult。"""
        ...

    def _fetch_get(self, path: str, cache_key: str, ttl: int,
                   params: dict | None = None) -> dict | None:
        """GET + 缓存辅助。"""
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        resp = self._client.get(path, params=params)
        self._cache.set(cache_key, resp, ttl)
        return resp

    def _fetch_post(self, path: str, data: dict,
                    cache_key: str, ttl: int) -> dict | None:
        """POST + 缓存辅助。"""
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        resp = self._client.post(path, data)
        self._cache.set(cache_key, resp, ttl)
        return resp

    @staticmethod
    def _get_data(resp: dict | None):
        """从 API 响应中提取 data 字段。"""
        if resp is None:
            return None
        if isinstance(resp, dict) and "data" in resp:
            return resp["data"]
        return resp
