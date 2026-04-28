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
sys.path.insert(0, os.path.join(_SKILLS_DIR, "warehouse-allocation", "scripts"))
sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP


MISSING_MERCHANT_ERROR = {
    "error": "Missing merchant number. Provide merchant_no or set CRM_MERCHANT_CODE / OMS_MERCHANT_NO in the agent session env."
}


def _resolve_merchant_no(merchant_no: str | None) -> str:
    resolved = merchant_no or os.environ.get("CRM_MERCHANT_CODE") or os.environ.get("OMS_MERCHANT_NO")
    if not resolved:
        raise ValueError(MISSING_MERCHANT_ERROR["error"])
    return resolved


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
def oms_warehouse_list(merchant_no: str | None = None) -> str:
    """查询当前商户下的所有仓库列表。

    返回仓库名称、编码、地址、WMS版本、状态等信息。

    Args:
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    merchant_no = _resolve_merchant_no(merchant_no)
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
def oms_inventory_list(merchant_no: str | None = None) -> str:
    """查询当前商户下的库存列表。

    返回各 SKU 在各仓库的库存情况。

    Args:
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    merchant_no = _resolve_merchant_no(merchant_no)
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
def oms_rule_list(merchant_no: str | None = None) -> str:
    """查询当前商户下的分仓规则配置。

    返回路由规则、自定义规则、Hold 规则、SKU 仓库指定规则。

    Args:
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
    """
    from oms_query_engine.engine_v2 import OMSQueryEngine
    from oms_query_engine.models.request import QueryRequest

    # 用一个虚拟订单号触发规则查询
    engine = OMSQueryEngine()
    # 直接调用 RuleProvider
    from oms_query_engine.models.query_plan import QueryContext
    rule_provider = engine._executor.get_provider("rule")
    merchant_no = _resolve_merchant_no(merchant_no)
    ctx = QueryContext(merchant_no=merchant_no)

    if result.success and result.data:
        rule_info = result.data.get("rule_info")
        if rule_info:
            return json.dumps(rule_info.model_dump(), ensure_ascii=False, indent=2)
    return json.dumps({"error": "规则查询失败"}, ensure_ascii=False)


@mcp.tool()
def oms_hold_rules(merchant_no: str | None = None) -> str:
    """查询当前商户下的 Hold（暂停履约）规则列表。

    Args:
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    merchant_no = _resolve_merchant_no(merchant_no)
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
def oms_channel_list(merchant_no: str | None = None) -> str:
    """查询当前商户已连接的渠道/连接器列表。

    返回渠道名称、连接器类型、连接状态、认证状态等。

    Args:
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    merchant_no = _resolve_merchant_no(merchant_no)
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
def oms_order_logs(order_no: str, merchant_no: str | None = None) -> str:
    """查询订单日志（含异常事件、拆单事件等）。

    Args:
        order_no: 订单号
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
    """
    from oms_query_engine.api_client import OMSAPIClient
    from oms_query_engine.config import EngineConfig

    merchant_no = _resolve_merchant_no(merchant_no)
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


# ══════════════════════════════════════════════════════════
# Tool: oms_knowledge_query — OMS 本体知识查询
# ══════════════════════════════════════════════════════════

@mcp.tool()
def oms_knowledge_query(
    query: str,
    node_type: str | None = None,
    search_mode: str = "name",
    relation_type: str | None = None,
    limit: int = 20,
) -> str:
    """查询 OMS 业务本体知识。

    从 OMS 本体知识图谱中检索业务概念、流程、规则、状态、API 等知识。

    搜索模式：
    - name: 按名称/别名模糊搜索（默认）。如查"订单"、"分仓"、"Hold"
    - type: 按类型列举。node_type 可选 BusinessObject/BusinessProcess/Rule/State/APIEndpoint/Module/SourceArtifact
    - api_path: 按 API 路径关键词搜索。如查"sale-order"、"dispatch"
    - related: 按关系遍历，找与某节点关联的其他节点。可用 node_type 过滤目标类型，relation_type 过滤关系类型
    - stats: 返回知识库统计信息

    Args:
        query: 搜索关键词（如"订单"、"分仓流程"、"sale-order"）
        node_type: 节点类型过滤，可选 BusinessObject/BusinessProcess/Rule/State/APIEndpoint/Module/SourceArtifact，也支持中文如"流程"、"规则"、"状态"
        search_mode: 搜索模式，可选 name/type/api_path/related/stats
        relation_type: 关系类型过滤（仅 related 模式），可选 composition/dependency/flow/action/mapping/constraint/ownership
        limit: 返回数量上限，默认 20
    """
    from oms_query_engine.providers.knowledge import KnowledgeProvider

    provider = KnowledgeProvider()
    result = provider.search(
        query=query,
        node_type=node_type,
        search_mode=search_mode,
        relation_type=relation_type,
        limit=limit,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    merchant_no: str | None = None,
    intent: str | None = None,
    query: str | None = None,
) -> str:
    """OMS 运营分析。支持异常根因分析、Hold 诊断、卡单定位、库存健康、仓库效率、
    渠道业绩、订单趋势、SKU 销售、补货建议、影响评估等 15 种分析能力。

    Args:
        identifier: 订单号（单订单分析时使用）
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
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
# Tool: warehouse_allocate — 寻仓推荐
# ══════════════════════════════════════════════════════════

@mcp.tool()
def warehouse_allocate(
    order_no: str | None = None,
    merchant_no: str | None = None,
    sku_list: str | None = None,
    country: str = "US",
    state: str | None = None,
    allow_split: bool = True,
) -> str:
    """寻仓推荐。根据订单商品、库存、仓库能力，推荐最优发货仓。

    支持两种模式：
    1. 按订单号推荐（自动获取订单数据）
    2. 直接传入 SKU 列表 + 收货地址

    Args:
        order_no: 订单号（模式1，自动获取订单数据）
        merchant_no: 商户号；未传时从 agent session env 的 CRM_MERCHANT_CODE / OMS_MERCHANT_NO 读取
        sku_list: SKU 列表 JSON（模式2），格式 [{"sku":"ABC","quantity":2}]
        country: 收货国家，默认 US
        state: 收货州（如 CA、TX、NY）
        allow_split: 是否允许拆单，默认 true
    """
    from allocation_engine.engine import WarehouseAllocationEngine
    from allocation_engine.data_loader import DataLoader
    from allocation_engine.models import AllocationRequest, OrderItem, Address

    # 初始化
    try:
        from oms_query_engine.engine_v2 import OMSQueryEngine
        oms_engine = OMSQueryEngine()
        loader = DataLoader(oms_engine=oms_engine)
    except Exception:
        loader = DataLoader()

    engine = WarehouseAllocationEngine(data_loader=loader)

    # 构建请求
    items = None
    address = None
    if sku_list:
        raw = json.loads(sku_list)
        items = [OrderItem(sku=i["sku"], quantity=i.get("quantity", 1)) for i in raw]
    if country:
        address = Address(country=country, state=state)

    request = AllocationRequest(
        order_no=order_no,
        merchant_no=merchant_no,
        items=items,
        shipping_address=address,
        allow_split=allow_split,
    )

    result = engine.allocate(request)
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


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


# ══════════════════════════════════════════════════════════
# Tool: get_page_url — OMS 页面导航
# ══════════════════════════════════════════════════════════

def _resolve_frontend_url() -> str:
    raw = os.environ.get("OMS_BASE_URL", "")
    if raw:
        from urllib.parse import urlparse
        p = urlparse(raw)
        return f"{p.scheme}://{p.netloc}"
    return "http://localhost:3000"

_BASE_URL = _resolve_frontend_url()

_ROUTES: dict[str, str] = {
    # Dashboard
    "end-to-end": "/dashboard/end-to-end",
    "plc-report": "/dashboard/plc-report",
    "ots-report": "/dashboard/ots-report",
    # Sales Orders
    "sales-orders": "/sales-orders",
    "sales-order-detail": "/sales-orders/{orderNo}",
    "sales-order-add": "/sales-orders/add",
    "sales-order-edit": "/sales-orders/edit/{orderNo}",
    "shipping-requests": "/shipping-requests",
    "shipping-request-detail": "/shipping-requests/{dispatchNo}",
    "order-track": "/order-track",
    "order-track-detail": "/order-track/{orderNo}",
    "fulfillments": "/fulfillments",
    "fulfillment-detail": "/fulfillments/{shipmentNo}",
    "work-orders": "/work-orders",
    "work-order-detail": "/work-orders/{orderNo}",
    # Purchase
    "purchase-requests": "/purchase-requests",
    "purchase-request-detail": "/purchase-requests/{prNo}",
    "purchase-orders": "/purchase-orders",
    "purchase-order-detail": "/purchase-orders/{orderNo}",
    "quote-orders": "/quote-orders",
    "quote-order-detail": "/quote-orders/{quoteNo}",
    "quote-order-add": "/quote-orders/add",
    "container-tracking": "/container-tracking",
    # Logistics
    "international-freight": "/logistics/international-freight",
    "transaction-management": "/logistics/transaction-management",
    "transaction-detail": "/logistics/transaction-management/{orderNo}",
    "delivery-orders": "/logistics/delivery-orders",
    "delivery-order-create": "/logistics/delivery-orders/create",
    "small-parcel": "/logistics/small-parcel",
    "small-parcel-detail": "/logistics/small-parcel/detail/{orderId}",
    "small-parcel-dispatch": "/logistics/small-parcel-dispatch",
    "tax-payment": "/logistics/tax-payment",
    "lso-claims": "/logistics/lso-claims",
    "pickup-appointment": "/logistics/pickup-appointment",
    "driver-manage": "/logistics/driver-manage",
    "file-manage": "/logistics/file-manage",
    "trip-detail": "/logistics/trip-detail",
    # Inventory
    "inventory-list": "/inventory/inventory-list",
    "inventory-detail": "/inventory/inventory-detail/{sku}",
    "warehouse": "/inventory/warehouse",
    "warehouse-zipcode": "/inventory/warehouse-zipcode",
    # Product
    "item-master": "/item-master",
    "product-list": "/product-list",
    "product-detail": "/product-list/{productId}",
    "product-create": "/product-list/create",
    "brand": "/products/brand",
    "category": "/products/category",
    # POM
    "pom-project": "/pom/project",
    "pom-project-detail": "/pom/project/{projectId}",
    "pom-project-new": "/pom/project/newProject",
    "pom-invoice": "/pom/invoice",
    "pom-invoice-detail": "/pom/invoice/{invoiceId}",
    "pom-ams": "/pom/ams",
    "pom-isf": "/pom/isf",
    "pom-e214": "/pom/e214",
    "pom-form7512": "/pom/form7512List",
    "pom-form3461": "/pom/form3461List",
    "customs-duty": "/pom/customs-duty",
    "customs-ports": "/customs/ports",
    "customs-t86": "/customs/t86List",
    "customs-form7501": "/customs/form7501List",
    # Integrations
    "connected-systems": "/integration/connected-systems",
    "channel-detail": "/integration/{channelNo}",
    # Events
    "order-logs": "/events/order-logs",
    "inventory-sync": "/events/inventory-sync",
    # Automation
    "sales-order-routing": "/automation/sales-order-routing",
    "fulfillment-mode": "/automation/fulfillment-mode",
    "product-designated-warehouse": "/automation/product-designated-warehouse",
    "hold-order-rules": "/automation/hold-order-rules",
    "sku-filters": "/automation/sku-filters-goods",
    "order-update-setting": "/automation/order-update-setting",
    "mappings": "/automation/mappings",
    "inventory-sync-rule": "/automation/inventory-sync-rule",
    "rate-shopping": "/automation/rate-shopping/rate-shopping",
    "shipping-account": "/automation/rate-shopping/shipping-account",
    "shipping-account-detail": "/automation/rate-shopping/shipping-account/{id}",
    "shipping-account-add": "/automation/rate-shopping/shipping-account/add",
    "carrier-service": "/automation/rate-shopping/carrier-service",
    "carrier-service-detail": "/automation/rate-shopping/carrier-service/{id}",
    "carrier-service-add": "/automation/rate-shopping/carrier-service/add",
    "delivery-order-routing": "/automation/delivery-order-routing",
    "form-engine": "/automation/form-engine",
    "form-engine-detail": "/automation/form-engine/{id}",
    "form-engine-add": "/automation/form-engine/add",
    "email-configuration": "/automation/email-configuration",
    "event-callback-routing": "/automation/event-callback-routing",
    # Merchant
    "merchant-list": "/merchant-list",
    # Admin
    "admin-dashboard": "/admin/dashboard",
    "dev-tools": "/admin/dev-tools",
    "json-schema-editor": "/admin/dev-tools/json-schema-editor",
    "variable-text-editor": "/admin/dev-tools/variable-text-editor",
    "widget-tests": "/admin/dev-tools/widget-tests",
    "http-config": "/admin/dev-tools/http-config",
    # Other
    "profile": "/profile",
}

_PAGE_TITLES: dict[str, str] = {
    "sales-orders": "Sales Order List",
    "sales-order-detail": "Sales Order Detail",
    "sales-order-add": "New Sales Order",
    "sales-order-edit": "Edit Sales Order",
    "shipping-requests": "Shipping Requests",
    "shipping-request-detail": "Shipping Request Detail",
    "order-track": "AI Order Track",
    "order-track-detail": "Track Detail",
    "fulfillments": "Fulfillments",
    "fulfillment-detail": "Fulfillment Detail",
    "work-orders": "Work Orders",
    "work-order-detail": "Work Order Detail",
    "inventory-list": "Inventory List",
    "inventory-detail": "Inventory Detail",
    "warehouse": "Warehouse Management",
    "warehouse-zipcode": "Warehouse Zipcodes",
    "international-freight": "International Freight",
    "transaction-management": "Transaction Management",
    "transaction-detail": "Transaction Detail",
    "delivery-orders": "Delivery Orders",
    "delivery-order-create": "Create Delivery Order",
    "small-parcel": "Small Parcel",
    "small-parcel-detail": "Small Parcel Detail",
    "small-parcel-dispatch": "Small Parcel Dispatch",
    "tax-payment": "Tax Payment",
    "lso-claims": "LSO Claims",
    "pickup-appointment": "Pickup Appointment",
    "driver-manage": "Driver Management",
    "file-manage": "File Management",
    "sales-order-routing": "Sales Order Routing",
    "fulfillment-mode": "Fulfillment Mode",
    "product-designated-warehouse": "Product Designated Warehouse",
    "hold-order-rules": "Hold Order Rules",
    "sku-filters": "SKU Filters",
    "order-update-setting": "Order Update Setting",
    "mappings": "Mappings",
    "inventory-sync-rule": "Inventory Sync Rules",
    "rate-shopping": "Rate Shopping",
    "shipping-account": "Shipping Account",
    "shipping-account-detail": "Shipping Account Detail",
    "shipping-account-add": "New Shipping Account",
    "carrier-service": "Carrier Service",
    "carrier-service-detail": "Carrier Service Detail",
    "carrier-service-add": "New Carrier Service",
    "delivery-order-routing": "Delivery Order Routing",
    "form-engine": "Form Engine",
    "form-engine-detail": "Form Detail",
    "form-engine-add": "New Form",
    "email-configuration": "Email Configuration",
    "event-callback-routing": "Event Callback Routing",
}

# 模糊匹配关键词 → page key
_FUZZY_MAP: list[tuple[list[str], str]] = [
    (["销售订单", "sales order", "订单列表"], "sales-orders"),
    (["订单详情", "sales order detail"], "sales-order-detail"),
    (["新建订单", "创建订单"], "sales-order-add"),
    (["出货请求", "shipping request", "发货请求"], "shipping-requests"),
    (["ai追踪", "ai订单追踪", "order track", "订单追踪"], "order-track"),
    (["发货单", "fulfillment"], "fulfillments"),
    (["工作单", "work order"], "work-orders"),
    (["采购申请", "purchase request", "pr"], "purchase-requests"),
    (["采购订单", "purchase order", "po"], "purchase-orders"),
    (["报价单", "quote"], "quote-orders"),
    (["集装箱", "container"], "container-tracking"),
    (["国际运费", "international freight"], "international-freight"),
    (["交易管理", "transaction"], "transaction-management"),
    (["配送单", "delivery order"], "delivery-orders"),
    (["小包裹", "small parcel"], "small-parcel"),
    (["税款", "tax"], "tax-payment"),
    (["lso", "索赔"], "lso-claims"),
    (["取货预约", "pickup"], "pickup-appointment"),
    (["司机", "driver"], "driver-manage"),
    (["文件管理", "file"], "file-manage"),
    (["库存列表", "库存", "inventory"], "inventory-list"),
    (["仓库管理", "仓库", "warehouse"], "warehouse"),
    (["item master", "商品主数据"], "item-master"),
    (["商品列表", "产品列表", "product list"], "product-list"),
    (["新建商品", "创建商品"], "product-create"),
    (["品牌", "brand"], "brand"),
    (["分类", "category"], "category"),
    (["进口项目", "pom project"], "pom-project"),
    (["发票", "invoice"], "pom-invoice"),
    (["ams"], "pom-ams"),
    (["isf"], "pom-isf"),
    (["关税", "customs duty"], "customs-duty"),
    (["港口", "port"], "customs-ports"),
    (["已连接", "集成", "integration", "connected"], "connected-systems"),
    (["订单日志", "order log"], "order-logs"),
    (["库存同步", "inventory sync"], "inventory-sync"),
    (["订单路由", "sales order routing"], "sales-order-routing"),
    (["履约模式", "fulfillment mode"], "fulfillment-mode"),
    (["hold规则", "hold order"], "hold-order-rules"),
    (["sku过滤", "sku filter"], "sku-filters"),
    (["映射", "mapping"], "mappings"),
    (["rate shopping", "运费比价"], "rate-shopping"),
    (["运输账户", "shipping account"], "shipping-account"),
    (["承运商服务", "carrier service"], "carrier-service"),
    (["配送路由", "delivery routing"], "delivery-order-routing"),
    (["表单引擎", "form engine"], "form-engine"),
    (["邮件配置", "email"], "email-configuration"),
    (["事件回调", "callback"], "event-callback-routing"),
    (["商户列表", "merchant"], "merchant-list"),
    (["管理员", "admin"], "admin-dashboard"),
    (["开发者工具", "dev tools"], "dev-tools"),
    (["用户资料", "profile"], "profile"),
]


@mcp.tool()
def get_page_url(page: str, params: str | None = None) -> str:
    """获取 OMS 系统页面的完整 URL，用于导航跳转。

    支持精确 page key 或自然语言模糊描述（如"商品列表"、"销售订单"）。
    带参数的详情页需传入 params（JSON 字符串）。

    Args:
        page: 页面标识或自然语言描述。
              精确 key 示例：sales-orders、sales-order-detail、product-list、rate-shopping
              模糊描述示例：商品列表、销售订单、库存、rate shopping
        params: 路径参数 JSON 字符串，如 '{"orderNo": "SO-12345"}' 或 '{"productId": "P-001"}'
    """
    p = params
    path_params: dict = json.loads(p) if p else {}

    # 精确匹配
    matched_key = page if page in _ROUTES else None
    path = _ROUTES.get(page)

    # 模糊匹配
    if path is None:
        page_lower = page.lower()
        for keywords, key in _FUZZY_MAP:
            if any(kw in page_lower for kw in keywords):
                matched_key = key
                path = _ROUTES.get(key)
                break

    if path is None:
        available = sorted(_ROUTES.keys())
        return json.dumps({
            "error": f"未找到页面 '{page}'",
            "available_pages": available,
        }, ensure_ascii=False, indent=2)

    # 替换路径参数
    for k, v in path_params.items():
        path = path.replace(f"{{{k}}}", str(v))

    url = f"{_BASE_URL}{path}"
    title = _PAGE_TITLES.get(matched_key or page, page)
    return json.dumps({"url": url, "title": title, "page": matched_key or page, "path": path}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
