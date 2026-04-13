"""卡单/阻塞诊断"""
from __future__ import annotations
from datetime import datetime, timezone
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import Severity

# 默认环节阈值（分钟）
DEFAULT_THRESHOLDS = {
    "IMPORTED": 120,           # 待分仓 2h
    "OPEN": 120,
    "ALLOCATED": 1440,         # 待履约 24h
    "WAREHOUSE_PROCESSING": 2880,  # 仓库处理 48h
    "PACKED": 1440,            # 待发运 24h
    "SHIPPED": 240,            # 待同步 4h
}

STAGE_CN = {
    "IMPORTED": "待分仓", "OPEN": "待处理", "ALLOCATED": "待履约",
    "WAREHOUSE_PROCESSING": "仓库处理中", "WAREHOUSE_RECEIVED": "仓库已收货",
    "PACKED": "已打包待发运", "SHIPPED": "已发运待同步",
    "PICKED": "已拣货", "LOADED": "已装车",
}


class StuckOrderAnalyzer(BaseAnalyzer):
    name = "卡单诊断"
    version = "1.0.0"
    intent = "stuck_order"
    required_data = ["order_data", "event_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        order = context.order_data or {}
        status = order.get("current_status", {})
        status_code = str(status.get("status_code", "")).upper()
        stage_cn = STAGE_CN.get(status_code, status.get("main_status", "未知"))

        # 计算停留时长
        event_info = order.get("event_info", {}) or {}
        latest_time_str = event_info.get("latest_event_time")
        duration_minutes = None
        if latest_time_str:
            try:
                if "UTC" in str(latest_time_str):
                    latest = datetime.strptime(str(latest_time_str), "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                else:
                    latest = datetime.fromisoformat(str(latest_time_str))
                now = datetime.now(timezone.utc)
                duration_minutes = (now - latest).total_seconds() / 60
            except Exception:
                pass

        threshold = DEFAULT_THRESHOLDS.get(status_code)
        is_stuck = False
        overtime_ratio = None
        if duration_minutes is not None and threshold:
            is_stuck = duration_minutes > threshold
            overtime_ratio = round(duration_minutes / threshold, 2)

        evidences = []
        evidences.append(self._build_evidence("status", f"当前环节: {stage_cn}"))
        if duration_minutes is not None:
            evidences.append(self._build_evidence("status", f"已停留 {int(duration_minutes)} 分钟"))
        if threshold:
            evidences.append(self._build_evidence("rule", f"该环节正常阈值: {threshold} 分钟"))

        severity = None
        if is_stuck:
            if overtime_ratio and overtime_ratio > 5:
                severity = Severity.CRITICAL
            elif overtime_ratio and overtime_ratio > 2:
                severity = Severity.MAJOR
            else:
                severity = Severity.MINOR

        recs = []
        if is_stuck:
            recs.append(Recommendation(
                action=f"排查 {stage_cn} 环节阻塞原因",
                priority="high" if severity in (Severity.CRITICAL, Severity.MAJOR) else "medium",
            ))

        return self._make_result(
            success=True,
            summary=f"{'⚠️ 卡单' if is_stuck else '正常'} — {stage_cn}",
            reason=f"已停留 {int(duration_minutes or 0)} 分钟，阈值 {threshold or '未知'} 分钟" if duration_minutes else "无法计算停留时长",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=severity,
            recommendations=recs,
            metrics={
                "duration_minutes": int(duration_minutes) if duration_minutes else None,
                "threshold_minutes": threshold,
                "is_stuck": is_stuck,
                "overtime_ratio": overtime_ratio,
            },
        )
