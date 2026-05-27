from __future__ import annotations

import os

from pydantic import BaseModel, model_validator


class EngineConfig(BaseModel):
    base_url: str | None = None
    tenant_id: str | None = None
    merchant_no: str | None = None
    access_token: str | None = None
    username: str | None = None
    password: str | None = None
    request_timeout: int = 30
    token_refresh_buffer: int = 30

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

        env_map = {
            "OMS_REQUEST_TIMEOUT": "request_timeout",
            "OMS_TOKEN_REFRESH_BUFFER": "token_refresh_buffer",
        }
        for env_key, field_name in env_map.items():
            env_val = os.environ.get(env_key)
            if env_val is not None and field_name not in values:
                values[field_name] = env_val

        if not values.get("base_url"):
            values["base_url"] = _env("OMS_BASE_URL", "baseUrl", "BASE_URL") or "https://omsv3-staging.item.com/"

        if not values.get("tenant_id"):
            values["tenant_id"] = _env("OMS_TENANT_ID", "TENANT_ID", "tenantId", "x-tenant-id") or "LT"

        if not values.get("merchant_no"):
            values["merchant_no"] = _env(
                "CRM_MERCHANT_CODE",
                "OMS_MERCHANT_NO",
                "merchantNo",
                "merchant_no",
                "merchant",
            ) or "LAN0000002"

        if not values.get("access_token"):
            values["access_token"] = _env(
                "OMS_ACCESS_TOKEN",
                "OMS_SESSION_TOKEN",
                "ACCESS_TOKEN",
                "AUTH_TOKEN",
                "OMS_TOKEN",
                "authorization",
            )

        if not values.get("username"):
            values["username"] = _env("OMS_USERNAME", "OMS_LOGIN_USERNAME", "OMS_TEST_USERNAME")

        if not values.get("password"):
            values["password"] = _env("OMS_PASSWORD", "OMS_LOGIN_PASSWORD", "OMS_TEST_PASSWORD")

        return values

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "EngineConfig":
        if not self.base_url:
            raise ValueError("Missing OMS base URL in agent session env")
        if not self.tenant_id:
            raise ValueError("Missing OMS tenant ID in agent session env")
        if not self.access_token and not (self.username and self.password):
            raise ValueError("Missing OMS access token and login credentials in agent session env")
        return self
