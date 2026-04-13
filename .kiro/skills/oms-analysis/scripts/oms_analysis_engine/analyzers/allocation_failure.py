"""分仓失败分析"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation
from oms_analysis_engine.models.enums import Severity


class AllocationFailureAnalyzer(BaseAnalyzer):
    name = "分仓失败分析"
    version = "1.0.0"
    intent = "allocation_failure"
    required_data = ["order_data", "inventory_data", "warehouse_data", "rule_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        order = context.order_data or {}
        alloc = order.get("allocation_info", {}) or {}
        status = order.get("current_status", {})
        evidences = []

        # 检查是否有库存
        has_inventory = len(context.inventory_data) > 0
        has_warehouses = len(context.warehouse_data) > 0

        if not has_inventory:
            evidences.append(self._build_evidence("status", "无可用库存数据"))
            failure_type = "inventory"
        elif not has_warehouses:
            evidences.append(self._build_evidence("status", "无可用仓库"))
            failure_type = "warehouse"
        else:
            failure_type = "rule"
            evidences.append(self._build_evidence("rule", "候选仓存在但可能被规则排除"))

        recs = []
        if failure_type == "inventory":
            recs.append(Recommendation(action="补充库存", priority="high"))
        elif failure_type == "rule":
            recs.append(Recommendation(action="检查分仓规则配置", priority="high"))

        return self._make_result(
            success=True,
            summary=f"分仓失败原因: {'库存不足' if failure_type == 'inventory' else '规则排除' if failure_type == 'rule' else '无可用仓库'}",
            reason=alloc.get("allocation_reason", ""),
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.MAJOR,
            recommendations=recs,
            details={"failure_type": failure_type},
        )
