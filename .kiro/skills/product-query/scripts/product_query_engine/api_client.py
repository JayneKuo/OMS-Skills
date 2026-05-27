from __future__ import annotations

import requests

from product_query_engine.config import EngineConfig


class ProductOMSAPIClient:
    def __init__(self, config: EngineConfig):
        self._config = config
        self._token = config.access_token
        self.base_url = (config.base_url or "").rstrip("/")
        api_prefix = "/api/linker-oms"
        if not self.base_url.endswith(api_prefix):
            self.base_url = f"{self.base_url}{api_prefix}"
        self.headers = {
            "Authorization": f"Bearer {self._token}" if self._token else "",
            "Content-Type": "application/json",
            "x-tenant-id": config.tenant_id or "",
        }

    def _login(self) -> None:
        if not (self._config.username and self._config.password):
            raise ValueError("missing session token")
        response = requests.post(
            self._build_url("/api/linker-oms/opc/iam/token"),
            headers={"Content-Type": "application/json"},
            json={
                "grantType": "password",
                "username": self._config.username,
                "password": self._config.password,
            },
            timeout=self._config.request_timeout,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        token = data.get("access_token") or data.get("accessToken") or data.get("token")
        if not token:
            raise ValueError("missing session token")
        self._token = token
        self.headers["Authorization"] = f"Bearer {token}"

    def _ensure_token(self) -> None:
        if not self._token:
            self._login()

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        api_prefix = "/api/linker-oms"
        if self.base_url.endswith(api_prefix) and normalized_path.startswith(api_prefix):
            normalized_path = normalized_path[len(api_prefix):] or "/"
        return f"{self.base_url}{normalized_path}"

    def get(self, path: str, params: dict | None = None) -> dict:
        url = self._build_url(path)
        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=self._config.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict | None = None) -> dict:
        url = self._build_url(path)
        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=self._config.request_timeout,
        )
        response.raise_for_status()
        return response.json()
