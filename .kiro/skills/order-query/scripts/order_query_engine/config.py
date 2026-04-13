"""订单全景查询引擎 - 环境配置模块"""

from __future__ import annotations

import os

from pydantic import BaseModel, model_validator


class EngineConfig(BaseModel):
    """引擎环境配置，集中管理所有外部依赖参数。"""

    base_url: str = "https://omsv2-staging.item.com"
    username: str = "lantester@item.com"
    password: str = "LANLT"
    tenant_id: str = "LT"
    merchant_no: str = "LAN0000002"
    request_timeout: int = 15
    token_refresh_buffer: int = 30

    @model_validator(mode="before")
    @classmethod
    def _override_from_env(cls, values: dict) -> dict:
        """支持从环境变量覆盖默认值。"""
        env_map = {
            "OMS_BASE_URL": "base_url",
            "OMS_USERNAME": "username",
            "OMS_PASSWORD": "password",
            "OMS_TENANT_ID": "tenant_id",
            "OMS_MERCHANT_NO": "merchant_no",
            "OMS_REQUEST_TIMEOUT": "request_timeout",
            "OMS_TOKEN_REFRESH_BUFFER": "token_refresh_buffer",
        }
        for env_key, field_name in env_map.items():
            env_val = os.environ.get(env_key)
            if env_val is not None and field_name not in values:
                values[field_name] = env_val
        return values
