#!/usr/bin/env python3
"""OMS 全域强查询 CLI — 基于 oms_query_engine v2"""

import argparse
import json
import sys

from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_query_engine.models.request import BatchQueryRequest, QueryRequest


def main():
    parser = argparse.ArgumentParser(description="OMS 全域强查询")
    parser.add_argument("--order-no", help="按订单号查询")
    parser.add_argument("--event-id", help="按拆单事件 ID 查询")
    parser.add_argument("--search", help="多类型搜索（自动识别标识类型）")
    parser.add_argument("--intent", default="status",
                        help="查询意图: status/shipment/warehouse/rule/"
                             "inventory/hold/timeline/fulfillment/"
                             "sync/integration/panorama")
    parser.add_argument("--status-count", action="store_true",
                        help="查询订单状态统计")
    parser.add_argument("--order-list", action="store_true",
                        help="查询订单列表")
    parser.add_argument("--status-filter", type=int,
                        help="按状态过滤（配合 --order-list）")
    parser.add_argument("--refresh", action="store_true",
                        help="跳过缓存，强制刷新")
    parser.add_argument("--raw", action="store_true",
                        help="输出原始 JSON")
    args = parser.parse_args()

    engine = OMSQueryEngine()

    # 批量查询
    if args.status_count:
        result = engine.query_batch(
            BatchQueryRequest(query_type="status_count"))
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return

    if args.order_list:
        result = engine.query_batch(BatchQueryRequest(
            query_type="order_list",
            status_filter=args.status_filter,
        ))
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return

    # 单对象查询
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
    print("【OMS 全域查询】\n")

    if result.error:
        print(f"查询失败: {result.error.get('message', '未知错误')}")
        return

    # 订单信息
    if result.order_identity:
        oi = result.order_identity
        print(f"📋 订单信息")
        print(f"  订单号: {oi.order_no or '未知'}")
        print(f"  商户: {oi.merchant_no or '未知'}")

    # 来源
    if result.source_info:
        si = result.source_info
        if si.channel_name or si.store_name:
            print(f"\n🏪 来源")
            if si.channel_name:
                print(f"  渠道: {si.channel_name}")
            if si.store_name:
                print(f"  店铺: {si.store_name}")
            if si.platform_order_no:
                print(f"  平台单号: {si.platform_order_no}")

    # 状态
    if result.current_status:
        cs = result.current_status
        print(f"\n📊 状态")
        print(f"  主状态: {cs.main_status or '未知'}")
        if cs.is_exception:
            print(f"  ⚠️ 异常: {cs.exception_reason or '是'}")
        if cs.is_hold:
            print(f"  ⏸️ 暂停履约: {cs.hold_reason or '是'}")
        if cs.is_deallocated:
            print(f"  🔄 已解除分配: {cs.deallocated_reason or '是'}")

    # 商品
    if result.product_info and result.product_info.items:
        items = result.product_info.items
        print(f"\n📦 商品 ({len(items)} 项)")
        for item in items[:5]:
            print(f"  - {item.sku} × {item.quantity}")

    # 发运
    if result.shipment_info and result.shipment_info.tracking_no:
        si = result.shipment_info
        print(f"\n🚚 发运")
        print(f"  承运商: {si.carrier_name or '未知'}")
        print(f"  追踪号: {si.tracking_no}")
        if si.shipment_status:
            print(f"  状态: {si.shipment_status}")

    # 集成
    if result.integration_info and result.integration_info.connected_channels:
        channels = result.integration_info.connected_channels
        print(f"\n🔗 集成中心 ({len(channels)} 个连接器)")
        for ch in channels[:5]:
            print(f"  - {ch.connector_name}: {ch.status}")

    # 解释
    if result.query_explanation:
        qe = result.query_explanation
        print(f"\n💡 查询级解释")
        if qe.current_step:
            print(f"  当前步骤: {qe.current_step}")
        if qe.why_hold:
            print(f"  暂停原因: {qe.why_hold}")
        if qe.why_exception:
            print(f"  异常原因: {qe.why_exception}")
        if qe.why_deallocated:
            print(f"  解除分配: {qe.why_deallocated}")

    # 完整度
    dc = result.data_completeness
    print(f"\n📊 数据完整度: {dc.completeness_level}")
    if dc.missing_fields:
        print(f"  缺失: {', '.join(dc.missing_fields)}")


if __name__ == "__main__":
    main()
