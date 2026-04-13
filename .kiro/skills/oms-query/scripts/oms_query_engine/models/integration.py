"""集成域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class ConnectorSummary(BaseModel):
    connector_id: str | None = None
    connector_name: str | None = None
    connector_type: str | None = None
    platform_name: str | None = None
    store_name: str | None = None
    status: str | None = None
    auth_status: str | None = None
    enabled_objects: list[str] | None = None


class ConnectorDetail(BaseModel):
    connector_id: str | None = None
    connector_name: str | None = None
    connector_type: str | None = None
    platform_name: str | None = None
    store_name: str | None = None
    environment: str | None = None
    auth_type: str | None = None
    auth_status: str | None = None
    test_connection_status: str | None = None
    last_test_time: str | None = None
    config_summary: str | None = None
    supported_objects: list[str] | None = None
    supported_actions: list[str] | None = None
    sync_directions: list[str] | None = None
    webhook_enabled: bool | None = None
    polling_enabled: bool | None = None
    draft_status: str | None = None
    recent_error_message: str | None = None
    recent_run_status: str | None = None
    last_sync_time: str | None = None


class IntegrationInfo(BaseModel):
    connected_channels: list[ConnectorSummary] | None = None
    connector_detail: ConnectorDetail | None = None
    available_connector_catalog: list[dict] | None = None
