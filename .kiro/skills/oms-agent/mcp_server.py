#!/usr/bin/env python3
"""OMS Agent MCP Server — 统一暴露 oms_query 和 cartonization 能力

使用方式：
  python .kiro/skills/oms-agent/mcp_server.py

MCP 配置（放到目标项目的 .kiro/settings/mcp.json 或 ~/.kiro/settings/mcp.json）：
  {
    "mcpServers": {
      "oms-agent": {
        "command": "python",
        "args": [".kiro/skills/oms-agent/mcp_server.py"]
      }
    }
  }

依赖：pip install mcp pydantic requests
"""

import sys
import os
import json

# 自动定位引擎包路径（相对于本文件位置）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILLS_DIR = os.path.dirname(_THIS_DIR)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SKILLS_DIR))

# 添加引擎包路径
sys.path.insert(0, os.path.join(_SKILLS_DIR, "oms-query", "scripts"))
sys.path.insert(0, os.path.join(_SKILLS_DIR, "oms-analysis", "scripts"))
sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("OMS Agent")


# ══════════════════════════════════════════════════════════
# Tool 1: oms_query — OMS 全域查询
# ══════════════════════════════════════════════════════════

@mcp.tool()
def oms_query(
    identifier: str,
    intent: str = "status",
    force_refresh: bool = False,
) -> str:
    """查询 OMS 订单全景信息。

    支持输入：订单号(SO/PO/WO开头)、shipment号(SH开头)、tracking号、eventId。
    支持意图：status(状态)、shipment(发运)、warehouse(仓库)、rule(规则)、
             inventory(库存)、hold(暂停)、timeline(时间线)、panorama(全景)。

    Args:
        identifier: 订单号、shipment号、tracking号或eventId
        intent: 查询意图，默认 status
        force_refresh: 是否跳过缓存强制刷新
    """
    from oms_query_engine.engine_v2 import OMSQueryEngine
    from oms_query_engine.models.request import QueryRequest

    engine = OMSQueryEngine()
    result = engine.query(QueryRequest(
        identifier=identifier,
        query_intent=intent,
        force_refresh=force_refresh,
    ))
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


@mcp.tool()
def oms_batch_query(
    query_type: str,
    status_filter: int | None = None,
    page_no: int = 1,
    page_size: int = 20,
) -> str:
    """批量查询 OMS 订单。

    Args:
        query_type: 查询类型，status_count(状态统计) 或 order_list(订单列表)
        status_filter: 按状态过滤（仅 order_list 时有效）
        page_no: 页码，默认 1
        page_size: 每页数量，默认 20
    """
    from oms_query_engine.engine_v2 import OMSQueryEngine
    from oms_query_engine.models.request import BatchQueryRequest

    engine = OMSQueryEngine()
    result = engine.query_batch(BatchQueryRequest(
        query_type=query_type,
        status_filter=status_filter,
        page_no=page_no,
        page_size=page_size,
    ))
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════
# Tool 3: 独立对象查询（仓库、库存、规则等）
# ══════════════════════════════════════════════════════════

@mcp.tool()
def oms_warehouse_list(merchant_no: str = "LAN0000002") -> str:
    """查询当前商户下的所有仓库列表。

    返回仓库名称、编码、地址、WMS版本、状态等信息。

    Args:
        merchant_no: 商户号，默认 LAN0000002
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.post(
        "/api/linker-oms/opc/app-api/facility/v2/page",
        {"merchantNo": merchant_no, "pageNo": 1, "pageSize": 100},
    )
    data = resp.get("data", resp)
    wlist = data.get("list", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    warehouses = []
    for w in wlist:
        warehouses.append({
            "warehouse_name": w.get("facility_name", ""),
            "accounting_code": w.get("accountingCode", ""),
            "city": w.get("city", ""),
            "state": w.get("state", ""),
            "country": w.get("country", ""),
            "zipcode": w.get("zipCode", ""),
            "address": w.get("address1", ""),
            "wms_version": w.get("warehouseVersion", ""),
            "status": w.get("status", ""),
            "timezone": w.get("time_zone", ""),
            "fulfillment_enabled": bool(w.get("fulfillmentSwitch")),
            "inventory_enabled": bool(w.get("inventorySwitch")),
        })

    return json.dumps({
        "total": len(warehouses),
        "warehouses": warehouses,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_inventory_list(merchant_no: str = "LAN0000002") -> str:
    """查询当前商户下的库存列表。

    返回各 SKU 在各仓库的库存情况。

    Args:
        merchant_no: 商户号，默认 LAN0000002
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.post(
        "/api/linker-oms/opc/app-api/inventory/list",
        {"merchantNo": merchant_no},
    )
    data = resp.get("data", resp)
    items = data.get("list", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    return json.dumps({
        "total": len(items),
        "inventory": items,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_rule_list(merchant_no: str = "LAN0000002") -> str:
    """查询当前商户下的分仓规则配置。

    返回路由规则、自定义规则、Hold 规则、SKU 仓库指定规则。

    Args:
        merchant_no: 商户号，默认 LAN0000002
    """
    from oms_query_engine.engine_v2 import OMSQueryEngine
    from oms_query_engine.models.request import QueryRequest

    # 用一个虚拟订单号触发规则查询
    engine = OMSQueryEngine()
    # 直接调用 RuleProvider
    from oms_query_engine.models.query_plan import QueryContext
    rule_provider = engine._executor.get_provider("rule")
    ctx = QueryContext(merchant_no=merchant_no)
    result = rule_provider.query(ctx)

    if result.success and result.data:
        rule_info = result.data.get("rule_info")
        if rule_info:
            return json.dumps(rule_info.model_dump(), ensure_ascii=False, indent=2)
    return json.dumps({"error": "规则查询失败"}, ensure_ascii=False)


@mcp.tool()
def oms_hold_rules(merchant_no: str = "LAN0000002") -> str:
    """查询当前商户下的 Hold（暂停履约）规则列表。

    Args:
        merchant_no: 商户号，默认 LAN0000002
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.get(
        "/api/linker-oms/opc/app-api/hold-rule-data/page",
        {"merchantNo": merchant_no},
    )
    data = resp.get("data", resp)
    rules = _extract_list(data)
    return json.dumps({"total": len(rules), "hold_rules": rules}, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_channel_list(merchant_no: str = "LAN0000002") -> str:
    """查询当前商户已连接的渠道/连接器列表。

    返回渠道名称、连接器类型、连接状态、认证状态等。

    Args:
        merchant_no: 商户号，默认 LAN0000002
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.get(
        "/api/linker-oms/opc/app-api/channel/*/list",
        {"tags": merchant_no, "pageSize": -1},
    )
    data = resp.get("data", resp)
    channels = _extract_list(data)

    result = []
    for ch in channels:
        connector = ch.get("connectorDTO") or {}
        result.append({
            "channel_name": ch.get("channelName"),
            "channel_no": ch.get("channelNo"),
            "connector_name": connector.get("connectorName"),
            "connector_type": connector.get("connectorTypeCode"),
            "connection_status": "已连接" if ch.get("connectionStatus") else "未连接",
            "auth_status": "正常" if ch.get("authStatus") else "异常",
            "draft": ch.get("draftStatus"),
            "order_download": bool(ch.get("orderDownloadStatus")),
            "inventory_upload": bool(ch.get("inventoryUploadStatus")),
        })
    return json.dumps({"total": len(result), "channels": result}, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_order_search(
    search_value: str,
    search_type: str = "orderNo",
) -> str:
    """按各种标识搜索订单。

    支持按订单号、shipment号、tracking号、平台订单号等搜索。

    Args:
        search_value: 搜索值（订单号、shipment号、tracking号等）
        search_type: 搜索类型，可选 orderNo/shipmentNo/trackingNo/channelOrderNo
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.post(
        "/api/linker-oms/opc/app-api/tracking-assistant/search-order-no",
        {"searchType": search_type, "searchValue": search_value},
    )
    data = resp.get("data", resp)
    results = _extract_list(data)
    return json.dumps({"total": len(results), "results": results}, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_order_timeline(order_no: str) -> str:
    """查询订单时间线（关键事件节点）。

    Args:
        order_no: 订单号
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.get(f"/api/linker-oms/opc/app-api/payment/time-line/{order_no}")
    data = resp.get("data", resp)
    events = _extract_list(data)
    return json.dumps({"order_no": order_no, "total": len(events), "timeline": events}, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_order_logs(order_no: str, merchant_no: str = "LAN0000002") -> str:
    """查询订单日志（含异常事件、拆单事件等）。

    Args:
        order_no: 订单号
        merchant_no: 商户号，默认 LAN0000002
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.get(
        "/api/linker-oms/opc/app-api/orderLog/list",
        {"merchantNo": merchant_no, "omsOrderNo": order_no},
    )
    data = resp.get("data", resp)
    logs = _extract_list(data)
    return json.dumps({"order_no": order_no, "total": len(logs), "logs": logs}, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_dispatch_log(event_id: str) -> str:
    """查询拆单详情（按 eventId）。

    Args:
        event_id: 拆单事件 ID
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()
    resp = client.get(f"/api/linker-oms/oas/rpc-api/dispatch-log/{event_id}")
    data = resp.get("data", resp)
    return json.dumps({"event_id": event_id, "dispatch_log": data}, ensure_ascii=False, indent=2)


@mcp.tool()
def oms_shipment_tracking(order_no: str) -> str:
    """查询订单的发运和物流追踪信息。

    返回 shipment 详情、承运商、tracking 号、运输状态等。

    Args:
        order_no: 订单号
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    client = OMSAPIClient(EngineConfig())
    client._ensure_token()

    tracking = {}
    try:
        resp = client.get(f"/api/linker-oms/opc/app-api/tracking-assistant/{order_no}")
        tracking["tracking_detail"] = resp.get("data", resp)
    except Exception as e:
        tracking["tracking_detail_error"] = str(e)

    try:
        resp = client.get(f"/api/linker-oms/opc/app-api/tracking-assistant/tracking-status/{order_no}")
        tracking["tracking_status"] = resp.get("data", resp)
    except Exception as e:
        tracking["tracking_status_error"] = str(e)

    try:
        resp = client.get(f"/api/linker-oms/opc/app-api/tracking-assistant/fulfillment-orders/{order_no}")
        tracking["fulfillment_orders"] = resp.get("data", resp)
    except Exception as e:
        tracking["fulfillment_error"] = str(e)

    return json.dumps({"order_no": order_no, **tracking}, ensure_ascii=False, indent=2)


def _extract_list(data) -> list:
    """从各种 API 返回格式中提取列表。"""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


# ══════════════════════════════════════════════════════════
# Tool: oms_analysis — OMS 运营分析
# ══════════════════════════════════════════════════════════

@mcp.tool()
def oms_analysis(
    identifier: str | None = None,
    merchant_no: str = "LAN0000002",
    intent: str | None = None,
    query: str | None = None,
) -> str:
    """OMS 运营分析。支持异常根因分析、Hold 诊断、卡单定位、库存健康、仓库效率、
    渠道业绩、订单趋势、SKU 销售、补货建议、影响评估等 15 种分析能力。

    Args:
        identifier: 订单号（单订单分析时使用）
        merchant_no: 商户号，默认 LAN0000002
        intent: 分析意图（root_cause/hold_analysis/stuck_order/inventory_health/
                warehouse_efficiency/channel_performance/order_trend/sku_sales/
                replenishment/impact_assessment/batch_pattern/fix_recommendation 等）
        query: 自然语言查询（如"这个订单为什么失败"、"哪些SKU缺货"）
    """
    from oms_analysis_engine.engine import OMSAnalysisEngine
    from oms_analysis_engine.models.request import AnalysisRequest
    from oms_analysis_engine.data_fetcher import DataFetcher

    # 初始化 DataFetcher（连接 oms_query_engine）
    init_errors = []
    try:
        from oms_query_engine.engine_v2 import OMSQueryEngine
        oms_engine = OMSQueryEngine()
        fetcher = DataFetcher(oms_engine=oms_engine)
    except Exception as e:
        init_errors.append(f"OMSQueryEngine init failed: {e}")
        fetcher = DataFetcher()

    engine = OMSAnalysisEngine(data_fetcher=fetcher)
    request = AnalysisRequest(
        identifier=identifier,
        merchant_no=merchant_no,
        intent=intent,
        query=query,
    )
    response = engine.analyze(request)
    result = response.model_dump()
    if init_errors:
        result["_init_errors"] = init_errors
    return json.dumps(result, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════
# Tool: cartonize — 装箱计算
# ══════════════════════════════════════════════════════════

@mcp.tool()
def cartonize(input_json: str) -> str:
    """执行装箱计算。

    输入为 JSON 字符串，包含订单商品、箱规、承运商限制等信息。
    输出装箱方案：包裹数、箱型选择、计费重、填充率等。

    Args:
        input_json: 装箱计算输入 JSON（包含 items, box_catalog, carrier_constraints 等）
    """
    from cartonization_engine.engine import CartonizationEngine

    input_data = json.loads(input_json)
    engine = CartonizationEngine()
    result = engine.run(input_data)
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def validate_cartonization(input_json: str, result_json: str) -> str:
    """验证装箱结果是否符合规则。

    Args:
        input_json: 原始装箱输入 JSON
        result_json: 装箱计算结果 JSON
    """
    from cartonization_engine.validator import validate_result

    input_data = json.loads(input_json)
    result_data = json.loads(result_json)
    validation = validate_result(input_data, result_data)
    return json.dumps(validation, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    mcp.run()
