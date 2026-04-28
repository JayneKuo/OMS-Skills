"""批量异常模式识别 — 含事件日志抽样和根因归纳"""
from __future__ import annotations
from collections import Counter
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.context import AnalysisContext
from oms_analysis_engine.models.result import AnalysisResult, Recommendation, ChartSpec
from oms_analysis_engine.models.enums import Severity

BATCH_THRESHOLD = 3
SAMPLE_SIZE = 10  # 抽样查事件日志的异常订单数

# 异常子类型 → 业务语言
EXCEPTION_SUBTYPE_CN = {
    "inventoryshort": "库存不足",
    "systemerror": "系统错误",
    "addressvalidation": "地址校验失败",
    "carrierrejected": "承运商拒绝",
    "labelfailed": "标签生成失败",
    "syncfailed": "同步失败",
    "authexpired": "认证过期",
    "timeout": "超时",
    "ruleconflict": "规则冲突",
}


class BatchPatternAnalyzer(BaseAnalyzer):
    name = "批量异常模式识别"
    version = "2.0.0"
    intent = "batch_pattern"
    required_data = ["batch_orders", "event_data"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        orders = context.batch_orders
        if not orders:
            return self._make_result(summary="无批量订单数据")

        # 1. 按状态分组，提取异常订单
        status_counter = Counter()
        warehouse_counter = Counter()
        channel_counter = Counter()
        exception_orders = []

        for o in orders:
            st = str(o.get("status", "")).upper()
            status_counter[st] += 1
            if st in ("EXCEPTION", "10"):
                exception_orders.append(o)
                wh = o.get("warehouseCode") or o.get("accountingCode")
                ch = o.get("channelName") or o.get("dataChannel")
                if wh:
                    warehouse_counter[wh] += 1
                if ch:
                    channel_counter[ch] += 1

        if not exception_orders:
            return self._make_result(
                success=True,
                summary=f"共 {len(orders)} 单订单，无异常订单",
                metrics={"total_orders": len(orders), "exception_orders": 0},
                details={"status_distribution": dict(status_counter)},
            )

        # 2. 抽样异常订单，查事件日志归纳根因
        root_cause_counter = Counter()  # 异常子类型统计
        affected_skus = Counter()       # 涉及的 SKU
        sample_details = []             # 抽样详情
        sampled = exception_orders[:SAMPLE_SIZE]

        for o in sampled:
            order_no = o.get("orderNo", "")
            logs = self._get_order_logs(context, order_no)
            order_causes = set()
            order_skus = set()
            for log in logs:
                sub_type = str(log.get("eventSubType", "")).lower()
                if sub_type:
                    cause_cn = EXCEPTION_SUBTYPE_CN.get(sub_type, sub_type)
                    order_causes.add(cause_cn)
                # 从描述中提取 SKU
                desc = log.get("description", "")
                sku = self._extract_sku_from_desc(desc, o)
                if sku:
                    order_skus.add(sku)
            # 按订单计数（每个订单每种根因只计一次）
            for cause in order_causes:
                root_cause_counter[cause] += 1
            for sku in order_skus:
                affected_skus[sku] += 1
            sample_details.append({
                "order_no": order_no,
                "channel": o.get("channelName") or o.get("dataChannel"),
                "causes": list(order_causes) or ["未知"],
                "skus": list(order_skus),
            })

        # 3. 构建证据和结论
        evidences = []
        total_exc = len(exception_orders)

        # 根因优先级：业务根因 > 系统包装错误
        CAUSE_PRIORITY = {"库存不足": 0, "地址校验失败": 1, "承运商拒绝": 2,
                          "标签生成失败": 3, "同步失败": 4, "规则冲突": 5,
                          "认证过期": 6, "超时": 7, "系统错误": 8}
        sorted_causes = sorted(root_cause_counter.items(),
                               key=lambda x: (CAUSE_PRIORITY.get(x[0], 99), -x[1]))

        # 根因分布（最重要的结论）
        if sorted_causes:
            top_cause, top_count = sorted_causes[0]
            pct = top_count / len(sampled) * 100
            evidences.append(self._build_evidence(
                "business_field",
                f"抽样 {len(sampled)} 单异常订单中，{pct:.0f}% 的根因是「{top_cause}」",
                data=dict(root_cause_counter),
            ))
            # 其他根因（跳过"系统错误"如果已有更具体的根因）
            for cause, cnt in sorted_causes[1:]:
                if cause == "系统错误" and any(c != "系统错误" for c, _ in sorted_causes[:1]):
                    continue  # 系统错误是包装，跳过
                if cnt > 1:
                    pct2 = cnt / len(sampled) * 100
                    evidences.append(self._build_evidence(
                        "statistic",
                        f"另有 {pct2:.0f}% 涉及「{cause}」",
                    ))

        # 涉及的 SKU
        if affected_skus:
            top_skus = affected_skus.most_common(5)
            sku_desc = "、".join(f"{sku}（{cnt}单）" for sku, cnt in top_skus)
            evidences.append(self._build_evidence(
                "business_field",
                f"涉及的主要商品：{sku_desc}",
            ))

        # 渠道集中度
        for ch, count in channel_counter.most_common(3):
            if count > BATCH_THRESHOLD:
                concentration = count / total_exc * 100
                evidences.append(self._build_evidence(
                    "statistic",
                    f"渠道 {ch} 集中了 {count} 单异常（{concentration:.0f}%）",
                ))

        # 仓库集中度
        for wh, count in warehouse_counter.most_common(3):
            if count > BATCH_THRESHOLD:
                concentration = count / total_exc * 100
                evidences.append(self._build_evidence(
                    "statistic",
                    f"仓库 {wh} 集中了 {count} 单异常（{concentration:.0f}%）",
                ))

        # 4. 生成建议
        recs = []
        if root_cause_counter:
            top_cause = root_cause_counter.most_common(1)[0][0]
            if "库存" in top_cause:
                sku_list = "、".join(s for s, _ in affected_skus.most_common(3))
                recs.append(Recommendation(
                    action=f"补充缺货商品的库存（{sku_list}），补货到位后系统会自动重试分仓",
                    precondition="确认 SKU 编码和仓库库存数据",
                    risk="补货需要时间，期间订单将继续阻塞",
                    priority="high",
                    expected_effect="解除库存不足导致的批量异常",
                ))
            elif "地址" in top_cause:
                recs.append(Recommendation(
                    action="检查异常订单的收货地址信息，修正后重新触发分仓",
                    priority="high",
                ))
            elif "承运商" in top_cause or "标签" in top_cause:
                recs.append(Recommendation(
                    action="检查承运商配置和标签模板",
                    priority="high",
                ))
            else:
                recs.append(Recommendation(
                    action=f"排查「{top_cause}」类异常的具体原因",
                    priority="high",
                ))

        # 5. 构建摘要
        if sorted_causes:
            top_cause = sorted_causes[0][0]
            summary = f"共 {total_exc} 单异常，主要根因是「{top_cause}」"
        else:
            summary = f"共 {total_exc} 单异常，未能识别具体根因"

        return self._make_result(
            success=True,
            summary=summary,
            reason=f"抽样 {len(sampled)} 单异常订单的事件日志，归纳异常根因分布",
            evidences=evidences,
            confidence=self._assess_confidence(evidences),
            data_completeness=self._assess_data_completeness(context, self.required_data),
            severity=Severity.CRITICAL if total_exc > 50 else Severity.MAJOR if total_exc > 10 else Severity.MINOR,
            recommendations=recs,
            metrics={
                "total_orders": len(orders),
                "exception_orders": total_exc,
                "sampled_orders": len(sampled),
                "root_cause_distribution": dict(root_cause_counter),
                "affected_skus": dict(affected_skus),
            },
            details={
                "status_distribution": dict(status_counter),
                "sample_details": sample_details,
                "channel_distribution": dict(channel_counter),
                "warehouse_distribution": dict(warehouse_counter),
            },
            charts=[
                ChartSpec(
                    chart_id="batch_root_cause_distribution",
                    title="Root Cause Distribution",
                    chart_type="bar",
                    data=[{"cause": k, "count": v} for k, v in root_cause_counter.items()],
                    x_key="cause",
                    y_keys=["count"],
                    category_key="cause",
                    value_key="count",
                ),
                ChartSpec(
                    chart_id="batch_status_distribution",
                    title="Status Distribution",
                    chart_type="pie",
                    data=[{"status": k, "count": v} for k, v in status_counter.items()],
                    category_key="status",
                    value_key="count",
                ),
                ChartSpec(
                    chart_id="batch_channel_distribution",
                    title="Channel Distribution",
                    chart_type="bar",
                    data=[{"channel": k, "count": v} for k, v in channel_counter.items()],
                    x_key="channel",
                    y_keys=["count"],
                    category_key="channel",
                    value_key="count",
                ),
                ChartSpec(
                    chart_id="batch_warehouse_distribution",
                    title="Warehouse Distribution",
                    chart_type="bar",
                    data=[{"warehouse": k, "count": v} for k, v in warehouse_counter.items()],
                    x_key="warehouse",
                    y_keys=["count"],
                    category_key="warehouse",
                    value_key="count",
                ),
            ],
        )

    @staticmethod
    def _get_order_logs(context: AnalysisContext, order_no: str) -> list:
        """从 context.event_data 中获取指定订单的事件日志。
        如果 event_data 是按订单号索引的 dict，直接取；
        如果是 list，过滤出匹配的日志。
        """
        events = context.event_data
        if not events:
            return []
        if isinstance(events, dict):
            return events.get(order_no, [])
        if isinstance(events, list):
            return [e for e in events
                    if e.get("omsOrderNo") == order_no
                    and str(e.get("eventType", "")).lower() in ("exception", "error")]
        return []

    @staticmethod
    def _extract_sku_from_desc(desc: str, order: dict) -> str | None:
        """从异常描述中提取 SKU，或从订单的 product 字段获取。"""
        if not desc:
            return order.get("product")
        # 常见模式: "Product XXX is currently out of stock"
        if "Product " in desc and " is " in desc:
            start = desc.index("Product ") + len("Product ")
            end = desc.index(" is ", start)
            sku = desc[start:end].strip()
            if sku:
                return sku
        # 常见模式: "insufficient inventory for SKU XXX"
        if "for SKU " in desc:
            start = desc.index("for SKU ") + len("for SKU ")
            sku = desc[start:].split(".")[0].split(",")[0].strip()
            if sku:
                return sku
        return order.get("product")
