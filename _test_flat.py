import sys, os, json
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]
sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))
from oms_analysis_engine.data_fetcher import DataFetcher, flatten_shipping_request
from oms_query_engine.engine_v2 import OMSQueryEngine

oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)
raw = fetcher._fetch_shipping_requests('LAN0000002', {})
print(f'Raw: {len(raw)}')
if raw:
    flat = flatten_shipping_request(raw[0])
    print(f'createTime: {flat.get("createTime")}')
    print(f'orderDate: {flat.get("orderDate")}')
    print(f'status: {flat.get("status")} (type: {type(flat.get("status")).__name__})')
    print(f'statusName: {flat.get("statusName")}')
    print(f'channelName: {flat.get("channelName")}')
    print(f'accountingCode: {flat.get("accountingCode")}')
    print(f'warehouseName: {flat.get("warehouseName")}')
