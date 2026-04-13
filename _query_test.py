import sys, os, json
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))
sys.path.insert(0, '.')
from oms_query_engine.engine_v2 import OMSQueryEngine
from oms_query_engine.models.request import QueryRequest

e = OMSQueryEngine()
r = e.query(QueryRequest(identifier='SO00602875', query_intent='panorama', force_refresh=True))
d = r.model_dump()

cs = d['current_status']
oi = d['order_identity']
si = d.get('source_info') or {}
addr = d.get('shipping_address') or {}
pi = d.get('product_info') or {}
ei = d.get('event_info') or {}
qe = d.get('query_explanation') or {}
ship = d.get('shipment_info') or {}
dc = d['data_completeness']

print(f"订单号: {oi['order_no']}")
print(f"参考号: {oi['customer_order_no']}")
print(f"平台单号: {oi['external_order_no']}")
print(f"渠道: {si.get('channel_name')} ({si.get('order_source')})")
print(f"状态: {cs['main_status']} | 异常={cs['is_exception']} Hold={cs['is_hold']} Deallocated={cs['is_deallocated']}")
print(f"异常原因: {cs['exception_reason']}")
print(f"收货: {addr.get('address1')}, {addr.get('city')}, {addr.get('state')} {addr.get('zipcode')}, {addr.get('country')}")
for item in (pi.get('items') or []):
    print(f"商品: {item['sku']} x {item['quantity']}")
print(f"承运商: {ship.get('carrier_name')}")
print(f"追踪号: {ship.get('tracking_no')}")
print(f"日志数: {len(ei.get('order_logs') or [])}")
print(f"最近事件: {ei.get('latest_event_type')} @ {ei.get('latest_event_time')}")
print(f"查询解释: {qe.get('why_exception') or qe.get('why_hold') or qe.get('current_step')}")
print(f"完整度: {dc['completeness_level']}")
