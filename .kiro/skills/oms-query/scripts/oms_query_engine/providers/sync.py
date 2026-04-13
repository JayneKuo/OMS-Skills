"""SyncProvider - 发运同步/回传状态查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.sync import ShipmentSyncInfo, SyncTarget
from .base import BaseProvider

# 同步状态主要从订单日志和 shipment 相关字段中提取
# 集成中心日志可以补充同步失败信息
INTEGRATION_LOGS = "/api/linker-di/admin-api/connectors/http/logs"
ORDER_LOGS = "/api/linker-oms/opc/app-api/orderLog/list"


class SyncProvider(BaseProvider):
    """发运信息同步到三方平台的状态。"""

    name = "sync"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        order_no = context.order_no or context.primary_key

        sync_targets: list[SyncTarget] = []
        all_success = True
        failed_targets: list[str] = []

        # 1. 从订单日志中提取同步事件
        if order_no and context.order_detail:
            logs = self._extract_sync_from_logs(context, result)
            if logs:
                sync_targets.extend(logs)

        # 2. 从集成中心日志中查询同步记录（如果有 orderNo 作为 refId）
        if order_no:
            di_logs = self._query_integration_logs(order_no, result)
            if di_logs:
                sync_targets.extend(di_logs)

        # 计算汇总
        for t in sync_targets:
            if t.sync_status and t.sync_status != "success":
                all_success = False
                if t.target_system:
                    failed_targets.append(t.target_system)

        sync_info = ShipmentSyncInfo(
            sync_targets=sync_targets or None,
            all_sync_success=all_success if sync_targets else None,
            last_sync_time=sync_targets[-1].sync_time if sync_targets else None,
            failed_sync_targets=failed_targets or None,
        )

        result.success = True
        result.data = {"shipment_sync_info": sync_info}
        return result

    def _extract_sync_from_logs(self, context: QueryContext,
                                result: ProviderResult) -> list[SyncTarget]:
        """从订单日志中提取同步相关事件。"""
        targets: list[SyncTarget] = []
        # 如果 event provider 已经查过日志，从 context 中获取
        raw_logs = context.extra.get("raw_logs", [])
        if not raw_logs:
            return targets

        for log in raw_logs:
            event_type = str(log.get("eventType", "")).lower()
            if any(kw in event_type for kw in ["sync", "post", "confirmation", "tracking_update"]):
                targets.append(SyncTarget(
                    target_system=log.get("channelName") or log.get("dataChannel"),
                    sync_object="shipment_confirmation",
                    sync_status="success" if "success" in str(log.get("summary", "")).lower() else "unknown",
                    sync_time=log.get("createTime"),
                    sync_result_message=log.get("summary"),
                ))
        return targets

    def _query_integration_logs(self, order_no: str,
                                result: ProviderResult) -> list[SyncTarget]:
        """从集成中心日志中查询同步记录。"""
        targets: list[SyncTarget] = []
        cache_key = f"di_logs:{order_no}"
        try:
            resp = self._fetch_get(
                INTEGRATION_LOGS, cache_key, 60,
                params={
                    "pageNo": 1,
                    "pageSize": 10,
                    "refIds": order_no,
                },
            )
            data = self._get_data(resp)
            result.called_apis.append(INTEGRATION_LOGS)

            if not data:
                return targets

            logs = data.get("list", []) if isinstance(data, dict) else []
            for log in logs:
                http_resp = log.get("httpResponse", {})
                status_code = http_resp.get("status", 0)
                targets.append(SyncTarget(
                    target_system=log.get("connectorCode"),
                    sync_object=log.get("operateCode"),
                    sync_status="success" if status_code == 200 else "failed",
                    sync_time=log.get("createTime"),
                    external_reference_no=str(log.get("refId", "")),
                    sync_result_message=log.get("errorMsg") if log.get("errorMsg") else None,
                ))
        except Exception as e:
            result.failed_apis.append("integration_logs")
            result.errors.append(f"integration logs: {e}")

        return targets
