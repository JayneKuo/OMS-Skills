"""订单全景查询引擎 - OMS API 客户端"""

from __future__ import annotations

import time

import requests

from oms_query_engine.config import EngineConfig
from oms_query_engine.errors import (
    APICallError,
    AuthenticationError,
    NetworkTimeoutError,
)


class OMSAPIClient:
    """封装 OMS staging 环境的 HTTP 调用，负责认证和请求管理。"""

    TOKEN_PATH = "/api/linker-oms/opc/iam/token"

    def __init__(self, config: EngineConfig):
        self._config = config
        self._token: str | None = None
        self._token_expires_at: float = 0

    # ── 认证 ──────────────────────────────────────────

    def authenticate(self) -> str:
        """使用 password grant 获取 access_token。"""
        url = f"{self._config.base_url}{self.TOKEN_PATH}"
        payload = {
            "grantType": "password",
            "username": self._config.username,
            "password": self._config.password,
        }
        try:
            resp = requests.post(
                url, json=payload,
                timeout=self._config.request_timeout,
            )
        except requests.exceptions.Timeout:
            raise NetworkTimeoutError(url)
        except requests.exceptions.ConnectionError:
            raise NetworkTimeoutError(url)

        if resp.status_code != 200:
            raise AuthenticationError(
                resp.status_code, resp.text[:200],
            )

        data = resp.json().get("data") or {}
        self._token = data.get("access_token", "")
        expires_in = data.get("expires_in", 300)
        self._token_expires_at = (
            time.time() + expires_in - self._config.token_refresh_buffer
        )
        return self._token

    def _ensure_token(self) -> None:
        """检查 token 有效性，剩余有效期 < buffer 时自动刷新。"""
        if self._token is None or time.time() >= self._token_expires_at:
            self.authenticate()

    def _headers(self) -> dict:
        """构建请求头。"""
        return {
            "Authorization": f"Bearer {self._token}",
            "x-tenant-id": self._config.tenant_id,
            "Content-Type": "application/json",
        }

    # ── HTTP 方法 ─────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> dict:
        """发送 GET 请求。"""
        self._ensure_token()
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
        self._ensure_token()
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
