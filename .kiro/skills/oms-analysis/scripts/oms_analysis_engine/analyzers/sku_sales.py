"""SKU 销售分析"""
from __future__ import annotations
from collections import Counter
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult


class SkuSalesAnalyzer(BaseAnalyzer):
    name = "SKU 销售分析"
    version = "1.0.0"
    intent = "sku_sales"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无订单数据")

        sku_qty = Counter()
        for o in orders:
            items = o.get("itemLines") or o.get("items") or []
            for item in items:
                sku = item.get("sku", "")
                qty = item.get("qty", 0) or item.get("quantity", 0)
                if sku:
                    sku_qty[sku] += qty

        if not sku_qty:
            return self._make_result(summary="无 SKU 销售数据")

        total_qty = sum(sku_qty.values())
        ranked = sku_qty.most_common()
        n = len(ranked)
        top_20_idx = max(1, n // 5)
        bottom_20_idx = max(1, n - n // 5)

        sku_list = []
        for i, (sku, qty) in enumerate(ranked):
            pct = (qty / total_qty * 100) if total_qty > 0 else 0
            if i < top_20_idx:
                tag = "热销"
            elif i >= bottom_20_idx:
                tag = "滞销"
            else:
                tag = "正常"
            sku_list.append({"sku": sku, "quantity": qty, "percentage": round(pct, 1), "tag": tag})

        evidences = []
        hot = [s for s in sku_list if s["tag"] == "热销"]
        cold = [s for s in sku_list if s["tag"] == "滞销"]
        if hot:
            evidences.append(self._build_evidence("statistic", f"热销 SKU {len(hot)} 个，占总销量 {sum(s['percentage'] for s in hot):.0f}%"))

        return self._make_result(
            success=True,
            summary=f"共 {n} 个 SKU，{len(hot)} 个热销，{len(cold)} 个滞销",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            metrics={"total_skus": n, "total_quantity": total_qty, "hot_count": len(hot), "cold_count": len(cold)},
            details={"sku_ranking": sku_list[:30]},
        )
