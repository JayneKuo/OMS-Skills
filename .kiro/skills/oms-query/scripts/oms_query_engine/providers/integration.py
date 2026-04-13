"""IntegrationProvider - 集成中心查询（独立于订单链路）"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.integration import (
    IntegrationInfo, ConnectorSummary, ConnectorDetail,
)
from .base import BaseProvider

# DI 服务 API 路径（集成中心独立服务）
CHANNEL_LIST = "/api/linker-di/app-api/{customerCode}/channels"
CHANNEL_LIST_OMS = "/api/linker-oms/opc/app-api/channel/*/list"
CHANNEL_DETAIL = "/api/linker-di/app-api/{customerCode}/channels/{channelNo}"
CONNECTOR_GROUPS = "/api/linker-di/app-api/connectors/group"
CONNECTOR_LIST = "/api/linker-di/app-api/connectors"
CONNECTOR_DETAIL = "/api/linker-di/app-api/connectors/{code}/level2"
CONNECTOR_TEST = "/api/linker-di/app-api/connectors/{connectorCode}/test"
CONNECTOR_OPERATES = "/api/linker-di/app-api/connector/{type}/{code}/operates"
INTEGRATION_LOGS = "/api/linker-di/admin-api/connectors/http/logs"


class IntegrationProvider(BaseProvider):
    """连接器、渠道、认证、能力、健康状态。独立于订单链路。"""

    name = "integration"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        merchant_no = context.merchant_no or "LAN0000002"
        connector_key = context.extra.get("connector_key") or context.primary_key
        intents = context.intents

        connected_channels = None
        connector_detail = None
        catalog = None

        # 1. 查询已连接渠道列表
        if any(i in intents for i in ["integration", "panorama", "channel"]) or not connector_key:
            connected_channels = self._query_channels(merchant_no, result)

        # 2. 查询连接器详情（如果有具体 connector key）
        if connector_key and any(i in intents for i in ["integration", "panorama", "connector_detail"]):
            connector_detail = self._query_connector_detail(connector_key, result)

        # 3. 查询可连接平台列表（connector catalog）
        if any(i in intents for i in ["catalog", "available_connectors"]):
            catalog = self._query_connector_catalog(result)

        info = IntegrationInfo(
            connected_channels=connected_channels,
            connector_detail=connector_detail,
            available_connector_catalog=catalog,
        )

        result.success = True
        result.data = {"integration_info": info}
        return result

    def _query_channels(self, merchant_no: str,
                        result: ProviderResult) -> list[ConnectorSummary] | None:
        """查询已连接渠道列表。"""
        cache_key = f"channels:{merchant_no}"
        try:
            resp = self._fetch_get(
                CHANNEL_LIST_OMS,
                cache_key, QueryCache.TTL_STATIC,
                params={"tags": merchant_no, "pageSize": -1},
            )
            data = self._get_data(resp)
            result.called_apis.append(CHANNEL_LIST_OMS)

            if not data:
                return None

            channels = data if isinstance(data, list) else []
            return [
                ConnectorSummary(
                    connector_id=str(ch.get("connectorId", "")),
                    connector_name=ch.get("connectorDTO", {}).get("connectorName") if ch.get("connectorDTO") else None,
                    connector_type=ch.get("connectorDTO", {}).get("connectorTypeCode") if ch.get("connectorDTO") else None,
                    platform_name=ch.get("connectorDTO", {}).get("connectorName") if ch.get("connectorDTO") else None,
                    store_name=ch.get("channelName"),
                    status="connected" if ch.get("connectionStatus") else ("draft" if ch.get("draftStatus") else "disconnected"),
                    auth_status="valid" if ch.get("authStatus") else "invalid",
                    enabled_objects=self._extract_enabled_objects(ch),
                )
                for ch in channels
            ] or None
        except Exception as e:
            result.failed_apis.append("channel_list")
            result.errors.append(f"channel list: {e}")
            return None

    def _query_connector_detail(self, connector_code: str,
                                result: ProviderResult) -> ConnectorDetail | None:
        """查询连接器详情。"""
        cache_key = f"connector_detail:{connector_code}"
        try:
            path = CONNECTOR_DETAIL.format(code=connector_code)
            resp = self._fetch_get(path, cache_key, QueryCache.TTL_STATIC)
            data = self._get_data(resp)
            result.called_apis.append(path)

            if not data:
                return None

            base = data.get("connectorBase", {})
            http_conf = data.get("connectorHttp", {})
            support_types = data.get("connectorSupportTypes", [])

            return ConnectorDetail(
                connector_id=data.get("connectorId"),
                connector_name=base.get("connectorName"),
                connector_type=base.get("connectorTypeCode"),
                platform_name=base.get("connectorName"),
                environment=self._detect_environment(http_conf),
                auth_type=self._detect_auth_type(data),
                config_summary=base.get("connectorDesc"),
                supported_objects=support_types or None,
                supported_actions=self._extract_supported_actions(base),
            )
        except Exception as e:
            result.failed_apis.append("connector_detail")
            result.errors.append(f"connector detail: {e}")
            return None

    def _query_connector_catalog(self, result: ProviderResult) -> list[dict] | None:
        """查询可连接平台列表。"""
        cache_key = "connector_catalog"
        try:
            resp = self._fetch_get(
                CONNECTOR_GROUPS, cache_key, QueryCache.TTL_STATIC,
            )
            data = self._get_data(resp)
            result.called_apis.append(CONNECTOR_GROUPS)

            if not data or not isinstance(data, list):
                return None

            return [
                {
                    "biz_type": group.get("bizType"),
                    "total": group.get("total"),
                    "connectors": [
                        {
                            "code": c.get("connectorCode"),
                            "name": c.get("connectorName"),
                            "type": c.get("connectorTypeCode"),
                            "logo": c.get("connectorLogoUrl"),
                            "available": c.get("available"),
                        }
                        for c in group.get("connectors", [])
                    ],
                }
                for group in data
            ]
        except Exception as e:
            result.failed_apis.append("connector_catalog")
            result.errors.append(f"connector catalog: {e}")
            return None

    @staticmethod
    def _extract_enabled_objects(channel: dict) -> list[str] | None:
        """从 channel 配置中提取已启用的同步对象。"""
        objects = []
        if channel.get("orderDownloadStatus"):
            objects.append("order_download")
        if channel.get("inventoryUploadStatus"):
            objects.append("inventory_upload")
        if channel.get("confirmationPost"):
            objects.append("confirmation_post")
        return objects or None

    @staticmethod
    def _detect_environment(http_conf: dict) -> str | None:
        """检测连接器环境。"""
        if http_conf.get("baseUrlProd"):
            return "production"
        if http_conf.get("baseUrlStage"):
            return "staging"
        if http_conf.get("baseUrlDev"):
            return "development"
        return None

    @staticmethod
    def _detect_auth_type(data: dict) -> str | None:
        """检测认证类型。"""
        if data.get("oauth2Auth"):
            return "OAuth2"
        if data.get("oauth2ClientAuth"):
            return "OAuth2 Client"
        if data.get("sessionAuth"):
            return "Session"
        return "None"

    @staticmethod
    def _extract_supported_actions(base: dict) -> list[str] | None:
        """提取支持的动作。"""
        features = base.get("features", [])
        if not features:
            return None
        return [f.get("key", "") for f in features if isinstance(f, dict)]
