"""订单全景查询引擎 - 环境配置模块"""

from __future__ import annotations

import os

from pydantic import BaseModel, model_validator


class EngineConfig(BaseModel):
    """引擎环境配置，集中管理所有外部依赖参数。"""

    base_url: str | None = None
    tenant_id: str | None = None
    merchant_no: str | None = None
    access_token: str | None = None
    request_timeout: int = 15
    token_refresh_buffer: int = 30

    @model_validator(mode="before")
    @classmethod
    def _override_from_env(cls, values: dict) -> dict:
        """支持从环境变量覆盖默认值。"""
        env_map = {
            "OMS_BASE_URL": "base_url",
            "OMS_TENANT_ID": "tenant_id",
            "OMS_REQUEST_TIMEOUT": "request_timeout",
            "OMS_TOKEN_REFRESH_BUFFER": "token_refresh_buffer",
        }
        for env_key, field_name in env_map.items():
            env_val = os.environ.get(env_key)
            if env_val is not None and field_name not in values:
                values[field_name] = env_val

        if "merchant_no" not in values:
            values["merchant_no"] = (
                os.environ.get("CRM_MERCHANT_CODE")
                or os.environ.get("OMS_MERCHANT_NO")
            )

        if "access_token" not in values:
            values["access_token"] = (
                os.environ.get("OMS_ACCESS_TOKEN")
                or os.environ.get("OMS_SESSION_TOKEN")
                or os.environ.get("ACCESS_TOKEN")
                or os.environ.get("AUTH_TOKEN")
                or os.environ.get("OMS_TOKEN")
            )

        return values

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "EngineConfig":
        if not self.base_url:
            raise ValueError("Missing OMS_BASE_URL in agent session env")
        if not self.tenant_id:
            raise ValueError("Missing OMS_TENANT_ID in agent session env")
        if not self.access_token:
            raise ValueError("Missing OMS access token in agent session env")
        return self
