"""仓库效率分析"""
from __future__ import annotations
import statistics
from collections import defaultdict
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import Severity

# Shipping Request 状态码映射
SR_STATUS_SHIPPED = {3, "3", "SHIPPED"}
SR_STATUS_EXCEPTION = {10, "10", "EXCEPTION"}
SR_STATUS_CANCELLED = {8, "8", "CANCELLED"}


class WarehouseEfficiencyAnalyzer(BaseAnalyzer):
    name = "仓库效率分析"
    version = "1.1.0"
    intent = "warehouse_efficiency"
    required_data = ["warehouse_data", "shipping_requests"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        warehouses = context.warehouse_data
        shipping_requests = context.batch_orders  # 现在是 shipping request 数据，带仓库信息
        status_counts = context.status_counts or {}

        if not shipping_requests:
            return self._make_result(
                summary="无 Shipping Request 数据，无法分析仓库效率",
                details={"data_source": "shipping_requests", "data_available": False},
            )

        evidences = []

        # 全局统计
        sr_status = status_counts.get("shipping_request_status") or {}
        all_info = sr_status.get("All") or {}
        total_all = all_info.get("sum", len(shipping_requests)) if isinstance(all_info, dict) else len(shipping_requests)
        shipped_info = sr_status.get("Shipped") or {}
        shipped_all = shipped_info.get("sum", 0) if isinstance(shipped_info, dict) else 0
        wh_received_info = sr_status.get("Warehouse Received") or {}
        wh_received = wh_received_info.get("sum", 0) if isinstance(wh_received_info, dict) else 0

        evidences.append(self._build_evidence("statistic",
            f"全局 Shipping Request: 总计 {total_all}，仓库已收货 {wh_received}，已发运 {shipped_all}"))

        # 按仓库聚合
        wh_data: dict[str, dict] = defaultdict(lambda: {
            "name": "", "total": 0, "shipped": 0, "exception": 0, "cancelled": 0,
            "durations": [],
        })

        for sr in shipping_requests:
            code = sr.get("accountingCode") or "unknown"
            name = sr.get("warehouseName") or code
            status = sr.get("status")
            create_time = sr.get("createTime")

            wh_data[code]["name"] = name
            wh_data[code]["total"] += 1

            if status in SR_STATUS_SHIPPED or str(status) in ("3", "SHIPPED"):
                wh_data[code]["shipped"] += 1
            if status in SR_STATUS_EXCEPTION or str(status) in ("10", "EXCEPTION"):
                wh_data[code]["exception"] += 1
            if status in SR_STATUS_CANCELLED or str(status) in ("8", "CANCELLED"):
                wh_data[code]["cancelled"] += 1

        # 构建仓库统计
        wh_stats = []
        all_exception_rates = []

        for code, data in wh_data.items():
            if code == "unknown":
                continue
            total = data["total"]
            exc_rate = (data["exception"] / total * 100) if total > 0 else 0
            ship_rate = (data["shipped"] / total * 100) if total > 0 else 0
            cancel_rate = (data["cancelled"] / total * 100) if total > 0 else 0

            all_exception_rates.append(exc_rate)

            wh_stats.append({
                "warehouse_code": code,
                "warehouse_name": data["name"],
                "total_orders": total,
                "shipped_count": data["shipped"],
                "exception_count": data["exception"],
                "cancelled_count": data["cancelled"],
                "exception_rate": round(exc_rate, 1),
                "ship_rate": round(ship_rate, 1),
                "cancel_rate": round(cancel_rate, 1),
            })

        # 按订单量降序排列
        wh_stats.sort(key=lambda x: x["total_orders"], reverse=True)

        # 识别效率异常仓
        avg_exc_rate = statistics.mean(all_exception_rates) if all_exception_rates else 0
        for ws in wh_stats:
            if ws["exception_rate"] > avg_exc_rate * 2 and ws["total_orders"] >= 5:
                ws["efficiency_warning"] = True
                evidences.append(self._build_evidence("statistic",
                    f"⚠️ 仓库 {ws['warehouse_name']}({ws['warehouse_code']}) "
                    f"异常率 {ws['exception_rate']}% 超过平均值 {avg_exc_rate:.1f}% 的 2 倍"))
            else:
                ws["efficiency_warning"] = False

        # 建议
        recs = []
        warning_whs = [ws for ws in wh_stats if ws.get("efficiency_warning")]
        if warning_whs:
            for ws in warning_whs[:3]:
                recs.append(Recommendation(
                    action=f"排查仓库 {ws['warehouse_name']} 异常原因（异常率 {ws['exception_rate']}%）",
                    priority="high",
                ))

        return self._make_result(
            success=True,
            summary=f"共 {len(wh_stats)} 个仓库有 Shipping Request 数据，{len(warning_whs)} 个仓库效率异常",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.MAJOR if warning_whs else Severity.MINOR,
            recommendations=recs,
            metrics={
                "warehouse_count": len(wh_stats),
                "total_shipping_requests": len(shipping_requests),
                "avg_exception_rate": round(avg_exc_rate, 1),
                "warning_warehouse_count": len(warning_whs),
            },
            details={"warehouse_stats": wh_stats},
        )
