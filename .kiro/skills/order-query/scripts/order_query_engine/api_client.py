"""订单全景查询引擎 - OMS API 客户端"""

from __future__ import annotations

import requests

from order_query_engine.config import EngineConfig
from order_query_engine.errors import (
    APICallError,
    AuthenticationError,
    NetworkTimeoutError,
)


class OMSAPIClient:
    """封装 OMS HTTP 调用，直接使用 agent session token。"""

    def __init__(self, config: EngineConfig):
        self._config = config
        self._token = config.access_token

    def _ensure_token(self) -> None:
        """确认 session token 已存在。"""
        if not self._token:
            raise AuthenticationError(401, "missing session token")

    def _headers(self) -> dict:
        """构建请求头。"""
        self._ensure_token()
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        if self._config.tenant_id:
            headers["x-tenant-id"] = self._config.tenant_id
        return headers

    def get(self, path: str, params: dict | None = None) -> dict:
        """发送 GET 请求。"""
        url = f"{self._config.base_url}{path}"
        try:
            resp = requests.get(
                url, headers=self._headers(), params=params,
                timeout=self._config.request_timeout,
            )
        except requests.exceptions.Timeout:
            raise NetworkTimeoutError(url)
        except requests.exceptions.ConnectionError:
            raise NetworkTimeoutError(url)

        if resp.status_code != 200:
            raise APICallError(path, resp.status_code, resp.text[:200])
        return resp.json()

    def post(self, path: str, data: dict | None = None) -> dict:
        """发送 POST 请求。"""
        url = f"{self._config.base_url}{path}"
        try:
            resp = requests.post(
                url, headers=self._headers(), json=data,
                timeout=self._config.request_timeout,
            )
        except requests.exceptions.Timeout:
            raise NetworkTimeoutError(url)
        except requests.exceptions.ConnectionError:
            raise NetworkTimeoutError(url)

        if resp.status_code != 200:
            raise APICallError(path, resp.status_code, resp.text[:200])
        return resp.json()
