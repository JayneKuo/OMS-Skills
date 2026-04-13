import sys, os, json
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]
sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))
from oms_query_engine.api_client import OMSAPIClient
from oms_query_engine.config import EngineConfig
from oms_analysis_engine.data_fetcher import flatten_shipping_request

c = OMSAPIClient(EngineConfig())
c._ensure_token()
resp = c.get('/api/linker-oms/opc/app-api/sale-order/shipping/requests/page',
             {'merchantNo': 'LAN0000002', 'pageNo': 1, 'pageSize': 3})
items = resp['data']['list']
flat = flatten_shipping_request(items[0])
print(f'createTime: {flat.get("createTime")}')
print(f'orderDate: {flat.get("orderDate")}')
print(f'status: {flat.get("status")} (type: {type(flat.get("status")).__name__})')
print(f'statusName: {flat.get("statusName")}')
print(f'channelName: {flat.get("channelName")}')
print(f'dataChannel: {flat.get("dataChannel")}')
print(f'accountingCode: {flat.get("accountingCode")}')
print(f'warehouseName: {flat.get("warehouseName")}')
print(f'keys: {sorted(flat.keys())}')
