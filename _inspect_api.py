"""检查订单详情 API 返回的所有字段"""
import json, sys
sys.path.insert(0, '.kiro/skills/order-query/scripts')
from order_query_engine.engine import OrderQueryEngine

engine = OrderQueryEngine()
engine._client._ensure_token()

# 1. 订单详情
print("=== 订单详情 API 字段 ===")
detail = engine._client.get('/api/linker-oms/opc/app-api/sale-order/SO00611420')
data = detail.get('data', detail)
if isinstance(data, dict):
    for k, v in data.items():
        t = type(v).__name__
        preview = str(v)[:100] if v is not None else 'null'
        print(f"  {k} ({t}): {preview}")

# 2. 追踪详情
print("\n=== 追踪详情 API 字段 ===")
try:
    track = engine._client.get('/api/linker-oms/opc/app-api/tracking-assistant/SO00611420')
    tdata = track.get('data', track)
    if isinstance(tdata, dict):
        for k, v in tdata.items():
            t = type(v).__name__
            preview = str(v)[:100] if v is not None else 'null'
            print(f"  {k} ({t}): {preview}")
    elif isinstance(tdata, list):
        print(f"  返回列表，{len(tdata)} 条")
        if tdata:
            for k, v in tdata[0].items():
                print(f"  {k}: {str(v)[:80]}")
except Exception as e:
    print(f"  错误: {e}")

# 3. Fulfillment 订单
print("\n=== Fulfillment 订单 API ===")
try:
    ff = engine._client.get('/api/linker-oms/opc/app-api/tracking-assistant/fulfillment-orders/SO00611420')
    fdata = ff.get('data', ff)
    if isinstance(fdata, list) and fdata:
        print(f"  返回 {len(fdata)} 条")
        for k, v in fdata[0].items():
            print(f"  {k}: {str(v)[:80]}")
    else:
        print(f"  返回: {str(fdata)[:200]}")
except Exception as e:
    print(f"  错误: {e}")

# 4. 包裹追踪
print("\n=== 包裹追踪 API ===")
try:
    pkg = engine._client.get('/api/linker-oms/opc/app-api/tracking-assistant/tracking-status/SO00611420')
    pdata = pkg.get('data', pkg)
    if isinstance(pdata, list) and pdata:
        print(f"  返回 {len(pdata)} 条")
        for k, v in pdata[0].items():
            print(f"  {k}: {str(v)[:80]}")
    else:
        print(f"  返回: {str(pdata)[:200]}")
except Exception as e:
    print(f"  错误: {e}")
