import sys, os, json

for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]

sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))

from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_analysis_engine.data_fetcher import DataFetcher

oms = OMSQueryEngine()
print(f"oms._client: {type(oms._client)}")
print(f"oms._client._token: {oms._client._token is not None}")

fetcher = DataFetcher(oms_engine=oms)
print(f"fetcher._client: {type(fetcher._client)}")
print(f"fetcher._client is oms._client: {fetcher._client is oms._client}")

# Try _get_client
c = fetcher._get_client()
print(f"After _get_client, token: {c._token is not None}")

# Try a direct API call
try:
    resp = c.get('/api/linker-oms/opc/app-api/sale-order/shipping/requests/page',
                 {'merchantNo': 'LAN0000002', 'pageNo': 1, 'pageSize': 3})
    data = resp.get('data')
    if data is None:
        print(f"API returned data=None, full resp keys: {list(resp.keys())}")
        print(f"resp code: {resp.get('code')}, msg: {resp.get('msg')}")
    else:
        items = data.get('list', [])
        print(f"API returned {len(items)} items")
except Exception as e:
    print(f"API error: {e}")
