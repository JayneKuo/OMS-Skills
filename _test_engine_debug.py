import sys, os, json
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]
sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))

from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_analysis_engine.data_fetcher import DataFetcher
from oms_analysis_engine.models.request import AnalysisRequest

# Create engine and fetcher
oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)

# Monkey-patch _fetch_shipping_requests to add logging
original_fetch_sr = fetcher._fetch_shipping_requests
def debug_fetch_sr(merchant_no, filters):
    print(f"  [TRACE] _fetch_shipping_requests called, merchant={merchant_no}")
    result = original_fetch_sr(merchant_no, filters)
    print(f"  [TRACE] _fetch_shipping_requests returned {len(result)} items")
    return result
fetcher._fetch_shipping_requests = debug_fetch_sr

original_fetch_wh = fetcher._fetch_warehouses
def debug_fetch_wh(merchant_no):
    print(f"  [TRACE] _fetch_warehouses called")
    result = original_fetch_wh(merchant_no)
    print(f"  [TRACE] _fetch_warehouses returned {len(result)} items")
    return result
fetcher._fetch_warehouses = debug_fetch_wh

# Now create engine with this fetcher
from oms_analysis_engine.engine import OMSAnalysisEngine
engine = OMSAnalysisEngine(data_fetcher=fetcher)

print("=== Testing warehouse_efficiency ===")
result = engine.analyze(AnalysisRequest(merchant_no='LAN0000002', intent='warehouse_efficiency'))
for r in result.results:
    print(f"  Result: {r.summary}")
