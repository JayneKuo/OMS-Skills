import sys, os, json
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]
sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))

from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_analysis_engine.data_fetcher import DataFetcher

oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)
c = fetcher._get_client()

print(f"Token before auth: {c._token}")
try:
    c._ensure_token()
    print(f"Token after auth: {c._token is not None and len(c._token) > 0}")
except Exception as e:
    print(f"Auth failed: {type(e).__name__}: {e}")

# Try direct API call
try:
    resp = c.get('/api/linker-oms/opc/app-api/sale-order/shipping/requests/page',
                 {'merchantNo': 'LAN0000002', 'pageNo': 1, 'pageSize': 2})
    data = resp.get('data')
    if data and isinstance(data, dict):
        items = data.get('list', [])
        print(f"API call success: {len(items)} items")
    else:
        print(f"API returned data={data}")
        print(f"Full resp: {json.dumps(resp, ensure_ascii=False)[:300]}")
except Exception as e:
    print(f"API call failed: {type(e).__name__}: {e}")
