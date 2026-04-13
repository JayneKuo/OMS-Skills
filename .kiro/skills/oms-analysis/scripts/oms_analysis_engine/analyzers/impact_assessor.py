"""影响评估"""
from __future__ import annotations
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult
from oms_analysis_engine.models.enums import Severity


class ImpactAssessor(BaseAnalyzer):
    name = "影响评估"
    version = "1.0.0"
    intent = "impact_assessment"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无批量数据，无法评估影响范围",
                                     details={"data_sufficient": False})

        affected_orders = set()
        affected_skus = set()
        affected_warehouses = set()

        for o in orders:
            st = str(o.get("status", "")).upper()
            if st in ("EXCEPTION", "10", "ON_HOLD", "16", "DEALLOCATED", "25"):
                ono = o.get("orderNo", "")
                if ono:
                    affected_orders.add(ono)
                wh = o.get("accountingCode") or o.get("warehouseCode")
                if wh:
                    affected_warehouses.add(wh)
                items = o.get("itemLines") or o.get("items") or []
                for item in items:
                    sku = item.get("sku")
                    if sku:
                        affected_skus.add(sku)

        count = len(affected_orders)
        if count > 100:
            severity = Severity.CRITICAL
        elif count >= 10:
            severity = Severity.MAJOR
        else:
            severity = Severity.MINOR

        coverage = (count / len(orders) * 100) if orders else 0

        evidences = []
        evidences.append(self._build_evidence("statistic", f"受影响订单 {count} 单"))
        if affected_skus:
            evidences.append(self._build_evidence("statistic", f"涉及 {len(affected_skus)} 个 SKU"))

        return self._make_result(
            success=True,
            summary=f"影响 {count} 单，严重程度: {severity.value}",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=severity,
            metrics={
                "affected_orders": count,
                "affected_skus": len(affected_skus),
                "affected_warehouses": len(affected_warehouses),
                "impact_coverage": round(coverage, 1),
            },
        )
