import sys, os, json
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))
from oms_query_engine.engine_v2 import OMSQueryEngine
oms = OMSQueryEngine()
c = oms._client
c._ensure_token()

for ps in [5, 20, 50, 100, 200, 500]:
    resp = c.get('/api/linker-oms/opc/app-api/sale-order/shipping/requests/page',
                 {'merchantNo': 'LAN0000002', 'pageNo': 1, 'pageSize': ps})
    data = resp.get('data')
    if data is None:
        print(f'pageSize={ps}: data is None')
    elif isinstance(data, dict):
        lst = data.get('list', [])
        total = data.get('total', '?')
        print(f'pageSize={ps}: {len(lst)} items, total={total}')
    else:
        print(f'pageSize={ps}: data type={type(data)}')
