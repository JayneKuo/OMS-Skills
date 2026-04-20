#!/usr/bin/env python3
"""OMS Agent MCP Server — 统一暴露 oms_query、cartonization、shipping_rate 能力

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
sys.path.insert(0, os.path.join(_SKILLS_DIR, "shipping-rate", "scripts"))
sys.path.insert(0, os.path.join(_SKILLS_DIR, "eta", "scripts"))
sys.path.insert(0, os.path.join(_SKILLS_DIR, "cost", "scripts"))
sys.path.insert(0, os.path.join(_SKILLS_DIR, "oms-agent", "scripts"))
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
# Tool: warehouse_allocate — 寻仓推荐
# ══════════════════════════════════════════════════════════

@mcp.tool()
def warehouse_allocate(
    order_no: str | None = None,
    merchant_no: str = "LAN0000002",
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
        merchant_no: 商户号，默认 LAN0000002
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
# Tool: shipping_rate — 运费映射与承运商推荐
# ══════════════════════════════════════════════════════════

@mcp.tool()
def shipping_rate_query(
    merchant_no: str = "LAN0000002",
    mapping_types: str | None = None,
    channel_no: str | None = None,
) -> str:
    """查询运费映射规则配置。

    返回 OMS 三层映射规则：
    - Layer 1: 一对一映射（Carrier/ShipMethod/DeliveryService/FreightTerm）
    - Layer 2: 条件映射（多条件→输出）
    - Layer 3: Shipping Mapping 规则（渠道级多条件规则）

    Args:
        merchant_no: 商户号，默认 LAN0000002
        mapping_types: 映射类型过滤（逗号分隔），可选 CARRIER,SHIP_METHOD,DELIVERY_SERVICE,FREIGHT_TERM,SKU,UOM
        channel_no: 渠道号过滤
    """
    from shipping_rate_engine.engine import ShippingRateEngine
    from shipping_rate_engine.data_loader import DataLoader
    from shipping_rate_engine.models import MappingQueryRequest

    init_errors = []
    try:
        from oms_query_engine.engine_v2 import OMSQueryEngine
        oms_engine = OMSQueryEngine()
        loader = DataLoader(oms_engine=oms_engine)
    except Exception as e:
        init_errors.append(f"OMSQueryEngine init failed: {e}")
        loader = DataLoader()

    engine = ShippingRateEngine(data_loader=loader)
    types_list = [t.strip() for t in mapping_types.split(",")] if mapping_types else None

    request = MappingQueryRequest(
        merchant_no=merchant_no,
        mapping_types=types_list,
        channel_no=channel_no,
    )
    result = engine.query(request)
    out = result.model_dump()
    if init_errors:
        out["_init_errors"] = init_errors
    return json.dumps(out, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def shipping_rate_execute(
    merchant_no: str = "LAN0000002",
    channel_no: str | None = None,
    skus: str | None = None,
    carriers: str | None = None,
    ship_methods: str | None = None,
    delivery_services: str | None = None,
    freight_terms: str | None = None,
    mapping_key: str = "ALL",
    input_conditions: str | None = None,
) -> str:
    """执行运费映射规则匹配。

    支持两种执行模式：
    1. 条件映射执行：传入 skus/carriers/ship_methods 等参数
    2. Shipping Mapping 执行：传入 channel_no + input_conditions（JSON 数组）

    Args:
        merchant_no: 商户号，默认 LAN0000002
        channel_no: 渠道号（Shipping Mapping 执行时必填）
        skus: SKU 列表（逗号分隔），如 "SKU001,SKU002"
        carriers: 承运商列表（逗号分隔），如 "FedEx,UPS"
        ship_methods: 运输方式列表（逗号分隔），如 "Ground,Express"
        delivery_services: 配送服务列表（逗号分隔）
        freight_terms: 运费条款列表（逗号分隔）
        mapping_key: 映射范围键，默认 ALL
        input_conditions: Shipping Mapping 输入条件 JSON，格式 [{"carrier":"FedEx","shipMethod":"Ground"}]
    """
    from shipping_rate_engine.engine import ShippingRateEngine
    from shipping_rate_engine.data_loader import DataLoader
    from shipping_rate_engine.models import MappingExecuteRequest

    init_errors = []
    try:
        from oms_query_engine.engine_v2 import OMSQueryEngine
        oms_engine = OMSQueryEngine()
        loader = DataLoader(oms_engine=oms_engine)
    except Exception as e:
        init_errors.append(f"OMSQueryEngine init failed: {e}")
        loader = DataLoader()

    engine = ShippingRateEngine(data_loader=loader)

    parsed_conditions = None
    if input_conditions:
        parsed_conditions = json.loads(input_conditions)

    request = MappingExecuteRequest(
        merchant_no=merchant_no,
        channel_no=channel_no,
        skus=_split_csv(skus),
        carriers=_split_csv(carriers),
        ship_methods=_split_csv(ship_methods),
        delivery_services=_split_csv(delivery_services),
        freight_terms=_split_csv(freight_terms),
        mapping_key=mapping_key,
        input_conditions=parsed_conditions,
    )
    result = engine.execute(request)
    out = result.model_dump()
    if init_errors:
        out["_init_errors"] = init_errors
    return json.dumps(out, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def shipping_rate_recommend(
    order_no: str | None = None,
    merchant_no: str = "LAN0000002",
    channel_no: str | None = None,
    sku_list: str | None = None,
    country: str = "US",
    state: str | None = None,
) -> str:
    """承运商推荐。综合一对一映射、条件映射和 Shipping Mapping 规则，推荐最优承运商。

    支持两种模式：
    1. 按订单号推荐（自动获取订单数据）
    2. 直接传入 SKU 列表 + 渠道号

    Args:
        order_no: 订单号（模式1）
        merchant_no: 商户号，默认 LAN0000002
        channel_no: 渠道号
        sku_list: SKU 列表 JSON，格式 [{"sku":"ABC","quantity":2}]
        country: 收货国家，默认 US
        state: 收货州
    """
    from shipping_rate_engine.engine import ShippingRateEngine
    from shipping_rate_engine.data_loader import DataLoader
    from shipping_rate_engine.models import RecommendRequest

    init_errors = []
    try:
        from oms_query_engine.engine_v2 import OMSQueryEngine
        oms_engine = OMSQueryEngine()
        loader = DataLoader(oms_engine=oms_engine)
    except Exception as e:
        init_errors.append(f"OMSQueryEngine init failed: {e}")
        loader = DataLoader()

    engine = ShippingRateEngine(data_loader=loader)

    parsed_skus = None
    if sku_list:
        parsed_skus = json.loads(sku_list)

    request = RecommendRequest(
        order_no=order_no,
        merchant_no=merchant_no,
        channel_no=channel_no,
        sku_list=parsed_skus,
        country=country,
        state=state,
    )
    result = engine.recommend(request)
    out = result.model_dump()
    if init_errors:
        out["_init_errors"] = init_errors
    return json.dumps(out, ensure_ascii=False, indent=2, default=str)


def _split_csv(value: str | None) -> list[str] | None:
    """将逗号分隔的字符串拆为列表。"""
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


# ══════════════════════════════════════════════════════════
# Tool: shipping_rate_calculate — 运费计算
# ══════════════════════════════════════════════════════════

@mcp.tool()
def shipping_rate_calculate(
    packages_json: str,
    origin_province: str = "",
    origin_city: str = "",
    origin_district: str = "",
    dest_province: str = "",
    dest_city: str = "",
    dest_district: str = "",
    carrier: str | None = None,
    price_table_json: str | None = None,
    surcharge_rules_json: str | None = None,
    order_no: str | None = None,
) -> str:
    """运费计算。基于包裹信息、承运商价格表和附加费规则计算运费。

    支持 4 种计费模式（首重+续重、阶梯重量、体积计费、固定费用）和 8 种附加费。
    当不指定 carrier 和 price_table 时，自动使用美国公开牌价（UPS/FedEx/USPS）进行多承运商比价估算。

    Args:
        packages_json: 包裹列表 JSON，格式 [{"package_id":"P1","billing_weight":2.5,"actual_weight":2.0}]
        origin_province: 发货仓省/州（如 CA、上海）
        origin_city: 发货仓城市
        origin_district: 发货仓区县
        dest_province: 收货省/州（如 NY、四川）
        dest_city: 收货城市
        dest_district: 收货区县
        carrier: 承运商名称（可选，不指定则自动比价 UPS/FedEx/USPS）
        price_table_json: 价格表 JSON（可选，不指定则使用公开牌价估算）
        surcharge_rules_json: 附加费规则 JSON（可选）
        order_no: 订单号（可选，用于日志追踪）
    """
    from shipping_rate_engine.rate_engine import RateEngine
    from shipping_rate_engine.rate_models import (
        Address, PackageInput, PriceTable, RateRequest, SurchargeRuleSet,
    )
    from decimal import Decimal

    # 解析包裹
    raw_packages = json.loads(packages_json)
    packages = []
    for p in raw_packages:
        packages.append(PackageInput(
            package_id=p.get("package_id", f"PKG-{len(packages)+1}"),
            billing_weight=Decimal(str(p.get("billing_weight", 0))),
            actual_weight=Decimal(str(p.get("actual_weight", 0))),
            volume_cm3=Decimal(str(p["volume_cm3"])) if p.get("volume_cm3") else None,
            length_cm=Decimal(str(p["length_cm"])) if p.get("length_cm") else None,
            width_cm=Decimal(str(p["width_cm"])) if p.get("width_cm") else None,
            height_cm=Decimal(str(p["height_cm"])) if p.get("height_cm") else None,
            has_cold_items=p.get("has_cold_items", False),
            is_bulky=p.get("is_bulky", False),
            declared_value=Decimal(str(p.get("declared_value", 0))),
        ))

    origin = Address(province=origin_province, city=origin_city, district=origin_district)
    destination = Address(province=dest_province, city=dest_city, district=dest_district)

    # 解析价格表
    price_table = None
    if price_table_json:
        price_table = PriceTable.model_validate_json(price_table_json)

    # 解析附加费规则
    surcharge_rules = SurchargeRuleSet()
    if surcharge_rules_json:
        surcharge_rules = SurchargeRuleSet.model_validate_json(surcharge_rules_json)

    request = RateRequest(
        packages=packages,
        origin=origin,
        destination=destination,
        carrier=carrier or "",
        price_table=price_table,
        surcharge_rules=surcharge_rules,
    )

    engine = RateEngine()
    result = engine.calculate_rate(request)

    out = result.model_dump()
    # Decimal → str for JSON serialization
    return json.dumps(out, ensure_ascii=False, indent=2, default=str)


# ══════════════════════════════════════════════════════════
# Tool: eta_calculate — 时效计算
# ══════════════════════════════════════════════════════════

@mcp.tool()
def eta_calculate(
    origin_state: str,
    dest_state: str,
    carrier: str = "",
    service_level: str = "Ground",
    risk_level: str = "P75",
    sla_hours: float = 72,
    order_hour: int = 14,
    backlog_orders: int = 0,
    processing_speed: int = 400,
    cutoff_hour: int = 16,
    process_time_hours: float = 2.0,
    next_pickup_hours: float = 1.0,
    carrier_on_time_rate: float = 0.92,
    carrier_api_transit_hours: float | None = None,
    weather_alert: str = "none",
    congestion_level: str = "none",
) -> str:
    """计算 ETA（预估送达时间）。

    基于 8 组件 ETA 公式，计算订单从发货仓到收货地的预估送达时间。
    支持 P50/P75/P90 三个风险化口径，内置美国市场默认 transit time。

    Args:
        origin_state: 发货州（如 CA、NY、TX）
        dest_state: 收货州（如 OH、FL、WA）
        carrier: 承运商名称（可选）
        service_level: 服务级别，可选 Ground/Express/Priority，默认 Ground
        risk_level: 风险化口径，可选 P50/P75/P90，默认 P75
        sla_hours: SLA 时限（小时），默认 72
        order_hour: 下单时间（24h 制），默认 14
        backlog_orders: 仓当前积压订单数，默认 0
        processing_speed: 仓每小时处理速度，默认 400
        cutoff_hour: 截单时间（24h 制），默认 16
        process_time_hours: 仓内处理时间（小时），默认 2.0
        next_pickup_hours: 距下一次揽收的小时数，默认 1.0
        carrier_on_time_rate: 承运商近 7 天准点率（0~1），默认 0.92
        carrier_api_transit_hours: 承运商 API 返回的 transit time（可选）
        weather_alert: 天气预警，可选 none/rain/snow/typhoon，默认 none
        congestion_level: 拥堵级别，可选 none/normal_promo/peak，默认 none
    """
    from eta_engine.engine import ETAEngine
    from eta_engine.models import (
        CarrierContext,
        ETARequest,
        RiskFactors,
        WarehouseContext,
    )
    from decimal import Decimal

    wh = WarehouseContext(
        backlog_orders=backlog_orders,
        processing_speed=processing_speed,
        cutoff_hour=cutoff_hour,
        process_time_hours=Decimal(str(process_time_hours)),
    )
    carrier_ctx = CarrierContext(
        carrier=carrier,
        service_level=service_level,
        next_pickup_hours=Decimal(str(next_pickup_hours)),
        on_time_rate=Decimal(str(carrier_on_time_rate)),
        api_transit_hours=Decimal(str(carrier_api_transit_hours)) if carrier_api_transit_hours is not None else None,
    )
    risk = RiskFactors(
        weather_alert=weather_alert,
        congestion_level=congestion_level,
        carrier_on_time_rate=Decimal(str(carrier_on_time_rate)),
    )

    request = ETARequest(
        origin_state=origin_state,
        dest_state=dest_state,
        carrier=carrier,
        service_level=service_level,
        risk_level=risk_level,
        sla_hours=Decimal(str(sla_hours)),
        order_hour=order_hour,
        warehouse=wh,
        carrier_ctx=carrier_ctx,
        risk_factors=risk,
    )

    engine = ETAEngine()
    result = engine.calculate(request)
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str)


# ══════════════════════════════════════════════════════════
# Tool: cost_calculate — 综合成本计算
# ══════════════════════════════════════════════════════════

@mcp.tool()
def cost_calculate(
    plans_json: str,
    w_cost: float = 0.40,
    w_eta: float = 0.30,
    w_ontime: float = 0.15,
    w_cap: float = 0.15,
    split_penalty_unit: float = 5.0,
    sla_hours: float = 72,
    cost_ref_max: float | None = None,
    eta_ref_max: float | None = None,
) -> str:
    """综合成本计算与方案评分。

    计算每个方案的 Cost_total 和 Score，支持多方案对比排序。
    Score = w_cost × Normalize(Cost) + w_eta × Normalize(ETA) + w_ontime × OnTimeProb + w_cap × Normalize(Capacity)

    Args:
        plans_json: 方案列表 JSON，格式 [{"plan_id":"A","plan_name":"上海单仓","freight_order":25.3,"cost_warehouse":3.0,"cost_transfer":0,"n_warehouses":1,"capacity_utilization":0.65,"cost_risk":0,"eta_hours":45.5,"on_time_probability":0.94}]
        w_cost: 成本权重，默认 0.40
        w_eta: 时效权重，默认 0.30
        w_ontime: 准时率权重，默认 0.15
        w_cap: 容量权重，默认 0.15
        split_penalty_unit: 拆单惩罚单价（元/仓），默认 5.0
        sla_hours: SLA 时限（小时），默认 72
        cost_ref_max: 成本归一化参考最大值（可选，不指定则使用方案集内 min-max）
        eta_ref_max: 时效归一化参考最大值（可选，不指定则使用方案集内 min-max）
    """
    from cost_engine.engine import CostEngine
    from cost_engine.models import CostRequest, PlanInput, ScoreWeights
    from decimal import Decimal

    raw_plans = json.loads(plans_json)
    plans = []
    for p in raw_plans:
        plans.append(PlanInput(
            plan_id=p["plan_id"],
            plan_name=p.get("plan_name", ""),
            freight_order=Decimal(str(p.get("freight_order", 0))),
            cost_warehouse=Decimal(str(p.get("cost_warehouse", 0))),
            cost_transfer=Decimal(str(p.get("cost_transfer", 0))),
            n_warehouses=p.get("n_warehouses", 1),
            capacity_utilization=Decimal(str(p.get("capacity_utilization", 0))),
            cost_risk=Decimal(str(p.get("cost_risk", 0))),
            eta_hours=Decimal(str(p.get("eta_hours", 0))),
            on_time_probability=Decimal(str(p.get("on_time_probability", 0))),
            remain_capacity_pct=Decimal(str(p["remain_capacity_pct"])) if p.get("remain_capacity_pct") is not None else None,
        ))

    weights = ScoreWeights(
        w_cost=Decimal(str(w_cost)),
        w_eta=Decimal(str(w_eta)),
        w_ontime=Decimal(str(w_ontime)),
        w_cap=Decimal(str(w_cap)),
    )

    request = CostRequest(
        plans=plans,
        weights=weights,
        split_penalty_unit=Decimal(str(split_penalty_unit)),
        sla_hours=Decimal(str(sla_hours)),
        cost_ref_max=Decimal(str(cost_ref_max)) if cost_ref_max is not None else None,
        eta_ref_max=Decimal(str(eta_ref_max)) if eta_ref_max is not None else None,
    )

    engine = CostEngine()
    result = engine.calculate(request)
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str)


# ══════════════════════════════════════════════════════════
# Tool: shipping_plan_recommend — 全链路物流方案推荐
# ══════════════════════════════════════════════════════════

@mcp.tool()
def shipping_plan_recommend(
    order_no: str,
    merchant_no: str = "LAN0000002",
    risk_level: str = "P75",
) -> str:
    """全链路物流方案推荐。输入订单号，自动串联查询→包裹→运费→时效→评分，输出 Top-3 推荐方案。

    流水线：
    1. oms_query → 查订单（SKU、数量、地址、仓库）
    2. 构建包裹信息（无 SKU 物理数据时用默认重量估算）
    3. shipping_rate → 多承运商运费比价（UPS/FedEx/USPS）
    4. eta → 每个承运商方案的 ETA
    5. cost → 综合评分排序
    6. 输出 Top-3 推荐方案 + 白盒解释

    每一步失败不阻断流水线，降级继续并标注。

    Args:
        order_no: 订单号（如 SO00993148）
        merchant_no: 商户号，默认 LAN0000002
        risk_level: 风险化口径，可选 P50/P75/P90，默认 P75
    """
    from workflow_engine.shipping_plan import ShippingPlanWorkflow

    workflow = ShippingPlanWorkflow()
    result = workflow.run(
        order_no=order_no,
        merchant_no=merchant_no,
        risk_level=risk_level,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    mcp.run()
