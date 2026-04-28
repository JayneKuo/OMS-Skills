"""SKU 销售分析 — 含销售额"""
from __future__ import annotations
from collections import defaultdict
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, ChartSpec, ChartSeries


class SkuSalesAnalyzer(BaseAnalyzer):
    name = "SKU 销售分析"
    version = "2.0.0"
    intent = "sku_sales"
    required_data = ["batch_orders"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无订单数据")

        sku_data: dict[str, dict] = defaultdict(lambda: {"qty": 0, "revenue": 0.0, "order_count": 0})

        for o in orders:
            items = o.get("itemLines") or o.get("items") or []
            order_amount = float(o.get("totalAmount") or o.get("total") or 0)

            if items:
                for item in items:
                    sku = item.get("sku", "")
                    qty = int(item.get("qty", 0) or item.get("quantity", 0) or 0)
                    # 尝试取行级金额，没有就按订单均摊
                    line_amt = item.get("amount") or item.get("lineTotal") or item.get("price", 0)
                    if line_amt:
                        revenue = float(line_amt) * qty if float(line_amt) < 1000 else float(line_amt)
                    elif order_amount and qty:
                        revenue = order_amount  # 单 SKU 订单直接用订单金额
                    else:
                        revenue = 0
                    if sku:
                        sku_data[sku]["qty"] += qty
                        sku_data[sku]["revenue"] += revenue
                        sku_data[sku]["order_count"] += 1
            elif o.get("product"):
                # 没有 itemLines 但有 product 字段（列表接口）
                sku = o["product"]
                qty = int(o.get("qty", 1) or 1)
                sku_data[sku]["qty"] += qty
                sku_data[sku]["revenue"] += order_amount
                sku_data[sku]["order_count"] += 1

        if not sku_data:
            return self._make_result(summary="无 SKU 销售数据")

        total_qty = sum(d["qty"] for d in sku_data.values())
        total_revenue = sum(d["revenue"] for d in sku_data.values())

        # 按销量排名
        ranked = sorted(sku_data.items(), key=lambda x: x[1]["qty"], reverse=True)
        n = len(ranked)
        top_20_idx = max(1, n // 5)
        bottom_20_idx = max(1, n - n // 5)

        sku_list = []
        for i, (sku, d) in enumerate(ranked):
            qty_pct = (d["qty"] / total_qty * 100) if total_qty > 0 else 0
            rev_pct = (d["revenue"] / total_revenue * 100) if total_revenue > 0 else 0
            if i < top_20_idx:
                tag = "热销"
            elif i >= bottom_20_idx:
                tag = "滞销"
            else:
                tag = "正常"
            sku_list.append({
                "sku": sku,
                "quantity": d["qty"],
                "qty_percentage": round(qty_pct, 1),
                "revenue": round(d["revenue"], 2),
                "revenue_percentage": round(rev_pct, 1),
                "order_count": d["order_count"],
                "tag": tag,
            })

        evidences = []
        hot = [s for s in sku_list if s["tag"] == "热销"]
        cold = [s for s in sku_list if s["tag"] == "滞销"]
        if hot:
            hot_rev = sum(s["revenue"] for s in hot)
            evidences.append(self._build_evidence(
                "statistic",
                f"热销 SKU {len(hot)} 个，贡献销售额 ${hot_rev:,.2f}（占 {hot_rev/total_revenue*100:.0f}%）" if total_revenue > 0
                else f"热销 SKU {len(hot)} 个，占总销量 {sum(s['qty_percentage'] for s in hot):.0f}%",
            ))

        return self._make_result(
            success=True,
            summary=f"共 {n} 个 SKU，总销量 {total_qty} 件，总销售额 ${total_revenue:,.2f}",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            metrics={
                "total_skus": n,
                "total_quantity": total_qty,
                "total_revenue": round(total_revenue, 2),
                "hot_count": len(hot),
                "cold_count": len(cold),
            },
            details={"sku_ranking": sku_list[:30]},
            charts=[
                ChartSpec(
                    chart_id="sku_quantity_ranking",
                    title="SKU Quantity Ranking",
                    chart_type="bar",
                    data=sku_list[:20],
                    x_key="sku",
                    y_keys=["quantity"],
                    series=[ChartSeries(name="Quantity", data_key="quantity")],
                ),
                ChartSpec(
                    chart_id="sku_revenue_ranking",
                    title="SKU Revenue Ranking",
                    chart_type="bar",
                    data=sorted(sku_list, key=lambda x: x["revenue"], reverse=True)[:20],
                    x_key="sku",
                    y_keys=["revenue"],
                    series=[ChartSeries(name="Revenue", data_key="revenue")],
                ),
                ChartSpec(
                    chart_id="sku_abc_distribution",
                    title="SKU Sales Tag Distribution",
                    chart_type="pie",
                    data=[
                        {"tag": tag, "count": sum(1 for s in sku_list if s["tag"] == tag)}
                        for tag in ("热销", "正常", "滞销")
                    ],
                    category_key="tag",
                    value_key="count",
                ),
            ],
        )
