#!/usr/bin/env python3
"""OMS 订单全景查询 CLI — 基于 order_query_engine 引擎"""

import argparse
import json
import sys

from order_query_engine.engine import OrderQueryEngine
from order_query_engine.models import BatchQueryRequest, QueryRequest


def main():
    parser = argparse.ArgumentParser(description="OMS 订单全景查询")
    parser.add_argument("--order-no", help="按订单号查询")
    parser.add_argument("--event-id", help="按拆单事件 ID 查询")
    parser.add_argument("--search", help="多类型搜索（自动识别标识类型）")
    parser.add_argument("--intent", default="status",
                        help="查询意图: status/shipment/warehouse/rule/inventory/hold/timeline/panorama")
    parser.add_argument("--status-count", action="store_true", help="查询订单状态统计")
    parser.add_argument("--order-list", action="store_true", help="查询订单列表")
    parser.add_argument("--status-filter", type=int, help="按状态过滤（配合 --order-list）")
    parser.add_argument("--refresh", action="store_true", help="跳过缓存，强制刷新")
    parser.add_argument("--raw", action="store_true", help="输出原始 JSON")
    args = parser.parse_args()

    engine = OrderQueryEngine()

    if args.status_count:
        result = engine.query_batch(BatchQueryRequest(query_type="status_count"))
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return

    if args.order_list:
        req = BatchQueryRequest(query_type="order_list", status_filter=args.status_filter)
        result = engine.query_batch(req)
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return

    identifier = args.order_no or args.event_id or args.search
    if not identifier:
        parser.print_help()
        sys.exit(0)

    request = QueryRequest(
        identifier=identifier,
        query_intent=args.intent,
        force_refresh=args.refresh,
    )
    result = engine.query(request)

    if args.raw:
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    else:
        _print_formatted(result)


def _print_formatted(result):
    """格式化输出查询结果"""
    qi = result.query_input
    print(f"【订单全景查询】\n")

    if result.error:
        print(f"查询失败: {result.error.get('message', '未知错误')}")
        return

    if result.order_identity:
        oi = result.order_identity
        print(f"📋 订单信息")
        print(f"  订单号: {oi.order_no or '未知'}")
        print(f"  商户: {oi.merchant_no or '未知'}")

    if result.current_status:
        cs = result.current_status
        print(f"\n📊 状态")
        print(f"  主状态: {cs.main_status or '未知'}")
        if cs.is_exception:
            print(f"  ⚠️ 异常: {cs.exception_reason or '是'}")
        if cs.is_hold:
            print(f"  ⏸️ 暂停履约: {cs.hold_reason or '是'}")

    if result.order_items:
        print(f"\n📦 商品 ({len(result.order_items)} 项)")
        for item in result.order_items[:5]:
            print(f"  - {item.sku} × {item.quantity}")

    if result.query_explanation:
        qe = result.query_explanation
        print(f"\n💡 查询级解释")
        if qe.current_step:
            print(f"  当前步骤: {qe.current_step}")
        if qe.why_hold:
            print(f"  暂停原因: {qe.why_hold}")
        if qe.why_exception:
            print(f"  异常原因: {qe.why_exception}")

    dc = result.data_completeness
    print(f"\n📊 数据完整度: {dc.completeness_level}")
    if dc.missing_fields:
        print(f"  缺失: {', '.join(dc.missing_fields)}")


if __name__ == "__main__":
    main()
