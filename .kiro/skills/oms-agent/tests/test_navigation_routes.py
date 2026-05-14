import importlib.util
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


class _FakeFastMCP:
    def __init__(self, _name):
        pass

    def tool(self):
        def decorator(func):
            return func

        return decorator

    def run(self):
        pass


def load_mcp_server():
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = _FakeFastMCP
    server_module = types.ModuleType("mcp.server")
    server_module.fastmcp = fastmcp_module
    mcp_module = types.ModuleType("mcp")
    mcp_module.server = server_module

    sys.modules.setdefault("mcp", mcp_module)
    sys.modules.setdefault("mcp.server", server_module)
    sys.modules.setdefault("mcp.server.fastmcp", fastmcp_module)

    module_path = Path(__file__).resolve().parents[1] / "mcp_server.py"
    spec = importlib.util.spec_from_file_location("oms_agent_mcp_server", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def page_result(page):
    module = load_mcp_server()
    return json.loads(module.get_page_url(page))


def test_delivery_order_exception_maps_to_delivery_orders_page():
    result = page_result("订单履约异常")

    assert result["path"] == "/logistics/delivery-orders"
    assert result["page"] == "delivery-orders"


def test_dispatch_explain_maps_to_delivery_order_routing_page():
    result = page_result("DO 路由解释")

    assert result["path"] == "/automation/delivery-order-routing"
    assert result["page"] == "delivery-order-routing"


def test_sales_order_routing_explain_maps_to_sales_order_routing_page():
    result = page_result("SO 路由解释")

    assert result["path"] == "/automation/sales-order-routing"
    assert result["page"] == "sales-order-routing"


def test_warehouse_exception_maps_to_warehouse_page():
    result = page_result("仓库库存异常")

    assert result["path"] == "/inventory/warehouse"
    assert result["page"] == "warehouse"


def test_unknown_oms_page_returns_error_without_url():
    result = page_result("oms-order-exception")

    assert "error" in result
    assert "url" not in result


def test_oms_analysis_parses_filters_and_time_range(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeEngine:
        def __init__(self, data_fetcher=None):
            pass

        def analyze(self, request):
            captured["request"] = request

            class FakeResponse:
                def model_dump(self):
                    return {"success": True}

            return FakeResponse()

    class FakeDataFetcher:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setitem(sys.modules, "oms_analysis_engine.engine", types.SimpleNamespace(OMSAnalysisEngine=FakeEngine))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.data_fetcher", types.SimpleNamespace(DataFetcher=FakeDataFetcher))
    monkeypatch.setitem(
        sys.modules,
        "oms_query_engine.engine_v2",
        types.SimpleNamespace(OMSQueryEngine=lambda: object()),
    )

    result = json.loads(module.oms_analysis(
        merchant_no="M001",
        intent="sku_sales",
        filters='{"sku":"SKU-A","channel_code":"amazon"}',
        time_range='{"start":"2026-04-11T00:00:00Z","end":"2026-05-11T23:59:59Z"}',
    ))

    assert result["success"] is True
    assert captured["request"].filters == {"sku": "SKU-A", "channel_code": "amazon"}
    assert captured["request"].time_range.start == datetime(2026, 4, 11, tzinfo=timezone.utc)
    assert captured["request"].time_range.end == datetime(2026, 5, 11, 23, 59, 59, tzinfo=timezone.utc)


def test_oms_analysis_returns_error_for_invalid_json_filters():
    module = load_mcp_server()

    result = json.loads(module.oms_analysis(intent="sku_sales", filters="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_filters_json"


def test_product_query_mcp_parses_filters_and_returns_result(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
            captured["has_inventory_adapter"] = inventory_adapter is not None
            captured["has_product_adapter"] = product_adapter is not None
            captured["has_channel_product_adapter"] = channel_product_adapter is not None

        def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
            captured["query"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
            }
            return {"success": True, "details": {"performance_query": filters}}

    class FakeInventoryAdapter:
        def __init__(self, client):
            pass

    class FakeProductApiAdapter:
        def __init__(self, client):
            pass

    class FakeChannelProductApiAdapter:
        def __init__(self, client):
            pass

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeInventoryAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.product_adapter", types.SimpleNamespace(ProductApiAdapter=FakeProductApiAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.channel_product_adapter", types.SimpleNamespace(ChannelProductApiAdapter=FakeChannelProductApiAdapter))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))

    result = json.loads(module.product_query(
        identifier="SKU-A",
        merchant_no="M001",
        intent="identity_for_performance",
        filters='{"channel_code":"amazon"}',
    ))

    assert result["success"] is True
    assert captured["has_inventory_adapter"] is True
    assert captured["has_product_adapter"] is True
    assert captured["has_channel_product_adapter"] is True
    assert captured["query"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "identity_for_performance",
        "filters": {"channel_code": "amazon"},
    }


def test_product_query_returns_error_for_invalid_filters_json():
    module = load_mcp_server()

    result = json.loads(module.product_query(identifier="SKU-A", merchant_no="M001", filters="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_filters_json"


def test_product_query_returns_error_when_merchant_missing(monkeypatch):
    module = load_mcp_server()
    monkeypatch.delenv("CRM_MERCHANT_CODE", raising=False)
    monkeypatch.delenv("OMS_MERCHANT_NO", raising=False)

    result = json.loads(module.product_query(identifier="SKU-A"))

    assert result["success"] is False
    assert result["error"] == "missing_merchant_no"


def test_product_performance_composes_product_query_and_sku_sales(monkeypatch):
    module = load_mcp_server()
    captured = {"analysis_requests": []}

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
            pass

        def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
            captured["product_query"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
            }
            return {
                "success": True,
                "details": {
                    "product": {"sku": "SKU-A"},
                    "skus": [{"sku": "SKU-A", "available_qty": 3}],
                    "performance_query": {"sku": "SKU-A", "channel_code": "amazon"},
                },
                "errors": ["渠道商品 API 尚未接入"],
            }

    class FakeInventoryAdapter:
        def __init__(self, client):
            pass

    class FakeProductApiAdapter:
        def __init__(self, client):
            pass

    class FakeChannelProductApiAdapter:
        def __init__(self, client):
            pass

    class FakeDataFetcher:
        def __init__(self, *args, **kwargs):
            pass

    class FakeOMSAnalysisEngine:
        def __init__(self, data_fetcher=None):
            pass

        def analyze(self, request):
            captured["analysis_requests"].append(request)

            class FakeResponse:
                def model_dump(self):
                    return {"success": True, "metrics": {"total_quantity": 2, "total_revenue": 100}}

            return FakeResponse()

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeInventoryAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.product_adapter", types.SimpleNamespace(ProductApiAdapter=FakeProductApiAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.channel_product_adapter", types.SimpleNamespace(ChannelProductApiAdapter=FakeChannelProductApiAdapter))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.engine_v2", types.SimpleNamespace(OMSQueryEngine=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.data_fetcher", types.SimpleNamespace(DataFetcher=FakeDataFetcher))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.engine", types.SimpleNamespace(OMSAnalysisEngine=FakeOMSAnalysisEngine))

    result = json.loads(module.product_performance(
        identifier="SKU-A",
        merchant_no="M001",
        filters='{"channel_code":"amazon"}',
    ))

    assert result["success"] is True
    assert captured["product_query"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "identity_for_performance",
        "filters": {"channel_code": "amazon"},
    }
    assert len(captured["analysis_requests"]) == 1
    assert captured["analysis_requests"][0].intent == "sku_sales"
    assert captured["analysis_requests"][0].filters == {"sku": "SKU-A", "channel_code": "amazon"}
    assert result["metrics"] == {"total_quantity": 2, "total_revenue": 100}
    assert result["details"]["product_query"]["details"]["product"] == {"sku": "SKU-A"}
    assert result["details"]["sku_sales"]["metrics"] == {"total_quantity": 2, "total_revenue": 100}


def test_product_performance_include_channel_runs_second_analysis(monkeypatch):
    module = load_mcp_server()
    intents = []

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
            pass

        def query(self, **kwargs):
            return {"success": True, "details": {"performance_query": {"sku": "SKU-A"}}, "errors": []}

    class FakeInventoryAdapter:
        def __init__(self, client):
            pass

    class FakeProductApiAdapter:
        def __init__(self, client):
            pass

    class FakeChannelProductApiAdapter:
        def __init__(self, client):
            pass

    class FakeDataFetcher:
        def __init__(self, *args, **kwargs):
            pass

    class FakeOMSAnalysisEngine:
        def __init__(self, data_fetcher=None):
            pass

        def analyze(self, request):
            intents.append(request.intent)

            class FakeResponse:
                def model_dump(self):
                    return {"success": True, "metrics": {request.intent: 1}, "errors": []}

            return FakeResponse()

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeInventoryAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.product_adapter", types.SimpleNamespace(ProductApiAdapter=FakeProductApiAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.channel_product_adapter", types.SimpleNamespace(ChannelProductApiAdapter=FakeChannelProductApiAdapter))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.engine_v2", types.SimpleNamespace(OMSQueryEngine=lambda: object()))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.data_fetcher", types.SimpleNamespace(DataFetcher=FakeDataFetcher))
    monkeypatch.setitem(sys.modules, "oms_analysis_engine.engine", types.SimpleNamespace(OMSAnalysisEngine=FakeOMSAnalysisEngine))

    result = json.loads(module.product_performance(identifier="SKU-A", merchant_no="M001", include_channel=True))

    assert intents == ["sku_sales", "channel_performance"]
    assert result["details"]["channel_performance"]["metrics"] == {"channel_performance": 1}


def test_product_performance_returns_error_for_invalid_time_range_json():
    module = load_mcp_server()

    result = json.loads(module.product_performance(identifier="SKU-A", merchant_no="M001", time_range="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_time_range_json"


def test_product_diagnosis_mcp_parses_context_and_filters(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeProductDiagnosisEngine:
        def diagnose(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
            captured["args"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
                "context": context,
            }
            return {"success": True, "summary": "diagnosed"}

    monkeypatch.setitem(sys.modules, "product_diagnosis_engine.engine", types.SimpleNamespace(ProductDiagnosisEngine=FakeProductDiagnosisEngine))

    result = json.loads(module.product_diagnosis(
        identifier="SKU-A",
        merchant_no="M001",
        intent="missing_required_fields",
        filters='{"channel_code":"amazon"}',
        context='{"missing_fields":[{"field":"material","required":true}]}',
    ))

    assert result == {"success": True, "summary": "diagnosed"}
    assert captured["args"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "missing_required_fields",
        "filters": {"channel_code": "amazon"},
        "context": {"missing_fields": [{"field": "material", "required": True}]},
    }


def test_product_diagnosis_auto_hydrates_context_when_missing(monkeypatch):
    module = load_mcp_server()
    captured = {}

    class FakeProductQueryEngine:
        def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
            pass

        def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
            captured["product_query"] = {
                "identifier": identifier,
                "merchant_no": merchant_no,
                "intent": intent,
                "filters": filters,
            }
            return {
                "details": {
                    "product": {"sku": "SKU-A"},
                    "skus": [{"sku": "SKU-A"}],
                    "channel_products": [{"channel_product_id": "CP-1", "audit_status": "rejected"}],
                    "publish_history": [{"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}],
                }
            }

    class FakeProductDiagnosisEngine:
        def diagnose(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
            captured["diagnosis_context"] = context
            return {"success": True, "summary": "diagnosed from hydrated context"}

    class FakeAdapter:
        def __init__(self, client):
            pass

    monkeypatch.setitem(sys.modules, "product_query_engine.engine", types.SimpleNamespace(ProductQueryEngine=FakeProductQueryEngine))
    monkeypatch.setitem(sys.modules, "product_query_engine.inventory_adapter", types.SimpleNamespace(InventoryAdapter=FakeAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.product_adapter", types.SimpleNamespace(ProductApiAdapter=FakeAdapter))
    monkeypatch.setitem(sys.modules, "product_query_engine.channel_product_adapter", types.SimpleNamespace(ChannelProductApiAdapter=FakeAdapter))
    monkeypatch.setitem(sys.modules, "product_diagnosis_engine.engine", types.SimpleNamespace(ProductDiagnosisEngine=FakeProductDiagnosisEngine))
    monkeypatch.setitem(sys.modules, "oms_query_engine.api_client", types.SimpleNamespace(OMSAPIClient=lambda config: object()))
    monkeypatch.setitem(sys.modules, "oms_query_engine.config", types.SimpleNamespace(EngineConfig=lambda: object()))

    result = json.loads(module.product_diagnosis(
        identifier="SKU-A",
        merchant_no="M001",
        intent="listing_failed",
        filters='{"channel_code":"amazon"}',
    ))

    assert result == {"success": True, "summary": "diagnosed from hydrated context"}
    assert captured["product_query"] == {
        "identifier": "SKU-A",
        "merchant_no": "M001",
        "intent": "listing_status",
        "filters": {"channel_code": "amazon"},
    }
    assert captured["diagnosis_context"]["publish_history"] == [
        {"publish_history_id": "PH-1", "status": "failed", "error_message": "Missing material"}
    ]
    assert captured["diagnosis_context"]["channel_products"] == [
        {"channel_product_id": "CP-1", "audit_status": "rejected"}
    ]


def test_product_diagnosis_returns_error_for_invalid_context_json():
    module = load_mcp_server()

    result = json.loads(module.product_diagnosis(identifier="SKU-A", merchant_no="M001", context="not-json"))

    assert result["success"] is False
    assert result["error"] == "invalid_context_json"
