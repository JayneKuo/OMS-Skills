import importlib.util
import json
import sys
import types
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
