import sys, os, json, traceback
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]
sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))

from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_analysis_engine.data_fetcher import DataFetcher, flatten_shipping_request
from oms_analysis_engine.models.request import AnalysisRequest

oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)

# Manually replicate what fetch() does for warehouse_efficiency
print("=== Step 1: Get client ===")
c = fetcher._get_client()
print(f"Client: {type(c)}")

print("\n=== Step 2: Warm up auth ===")
try:
    c._ensure_token()
    print(f"Token OK: {bool(c._token)}")
except Exception as e:
    print(f"Auth error: {e}")

print("\n=== Step 3: Fetch warehouses ===")
try:
    resp = c.post("/api/linker-oms/opc/app-api/facility/v2/page",
                  {"merchantNo": "LAN0000002", "pageNo": 1, "pageSize": 100})
    data = resp.get("data")
    print(f"Warehouse data type: {type(data)}")
    if isinstance(data, dict):
        lst = data.get("list", [])
        print(f"Warehouses: {len(lst)}")
    elif isinstance(data, list):
        print(f"Warehouses (list): {len(data)}")
    else:
        print(f"Unexpected: {data}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

print("\n=== Step 4: Fetch shipping requests ===")
try:
    resp = c.get("/api/linker-oms/opc/app-api/sale-order/shipping/requests/page",
                 {"merchantNo": "LAN0000002", "pageNo": 1, "pageSize": 100})
    data = resp.get("data")
    print(f"SR data type: {type(data)}")
    if isinstance(data, dict):
        lst = data.get("list", [])
        print(f"Shipping requests: {len(lst)}")
    else:
        print(f"Unexpected: {data}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

print("\n=== Step 5: Full fetch via DataFetcher ===")
from oms_analysis_engine.analyzer_registry import AnalyzerRegistry
from oms_analysis_engine.intent_detector import IntentDetector

registry = AnalyzerRegistry()
registry.auto_discover()
detector = IntentDetector()
req = AnalysisRequest(merchant_no='LAN0000002', intent='warehouse_efficiency')
intents = detector.detect(req)
analyzers = registry.resolve(intents)
print(f"Analyzers: {[a.name for a in analyzers]}")
print(f"Required: {[a.required_data for a in analyzers]}")

ctx = fetcher.fetch(req, analyzers)
print(f"batch_orders: {len(ctx.batch_orders)}")
print(f"warehouse_data: {len(ctx.warehouse_data)}")
