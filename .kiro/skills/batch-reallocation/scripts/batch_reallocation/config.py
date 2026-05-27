from __future__ import annotations

import os

from pydantic import BaseModel, model_validator


class BatchReallocationConfig(BaseModel):
    base_url: str | None = None
    tenant_id: str | None = None
    merchant_no: str | None = None
    access_token: str | None = None
    user: str | None = None
    request_timeout: int = 30

    @model_validator(mode="before")
    @classmethod
    def _override_from_env(cls, values: dict) -> dict:
        values = dict(values or {})

        def _env(*keys: str) -> str | None:
            for key in keys:
                env_val = os.environ.get(key)
                if env_val not in (None, ""):
                    return env_val
            return None

        values.setdefault("base_url", _env("OMS_BASE_URL", "baseUrl", "BASE_URL"))
        values.setdefault("tenant_id", _env("OMS_TENANT_ID", "TENANT_ID", "tenantId", "x-tenant-id"))
        values.setdefault("merchant_no", _env("CRM_MERCHANT_CODE", "OMS_MERCHANT_NO", "merchantNo", "merchant_no", "merchant"))
        values.setdefault("access_token", _env("OMS_ACCESS_TOKEN", "OMS_SESSION_TOKEN", "ACCESS_TOKEN", "AUTH_TOKEN", "OMS_TOKEN", "authorization"))
        values.setdefault("user", _env("USER", "username", "user"))
        return values

    def validate_for_analysis(self) -> None:
        missing = [
            name
            for name, value in {
                "OMS_BASE_URL": self.base_url,
                "OMS_TENANT_ID": self.tenant_id,
                "OMS_ACCESS_TOKEN": self.access_token,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing analysis runtime env: {', '.join(missing)}")

    def validate_for_execution(self) -> None:
        self.validate_for_analysis()
        if not self.user:
            raise ValueError("Missing USER in agent session env")
