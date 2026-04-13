import sys, os, json

# Clear all cached modules
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]

sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))
sys.path.insert(0, '.')

from oms_analysis_engine.engine import OMSAnalysisEngine
from oms_analysis_engine.data_fetcher import DataFetcher
from oms_analysis_engine.models.request import AnalysisRequest
from oms_query_engine.engine_v2 import OMSQueryEngine

oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)

# Test fetcher directly first
print("=== Direct fetch test ===")
sr = fetcher._fetch_shipping_requests('LAN0000002', {})
print(f"Shipping requests: {len(sr)}")
if sr:
    print(f"First item keys: {list(sr[0].keys())[:5]}")

print("\n=== Engine test ===")
engine = OMSAnalysisEngine(data_fetcher=fetcher)
result = engine.analyze(AnalysisRequest(
    merchant_no='LAN0000002',
    intent='warehouse_efficiency',
))

for r in result.results:
    print(f'=== {r.analyzer_name} (v{r.analyzer_version}) ===')
    print(f'结论: {r.summary}')
    for e in r.evidences:
        print(f'  {e.description}')
    stats = r.details.get('warehouse_stats', [])
    if stats:
        print(f'  仓库效率排名:')
        for ws in stats:
            name = ws.get('warehouse_name')
            code = ws.get('warehouse_code')
            total = ws.get('total_orders', 0)
            shipped = ws.get('shipped_count', 0)
            exc = ws.get('exception_count', 0)
            exc_rate = ws.get('exception_rate', 0)
            ship_rate = ws.get('ship_rate', 0)
            warn = ' ⚠️' if ws.get('efficiency_warning') else ''
            print(f'    {name}({code}): {total} 单, 已发运 {shipped}({ship_rate}%), 异常 {exc}({exc_rate}%){warn}')
    for rec in r.recommendations:
        print(f'  建议: [{rec.priority}] {rec.action}')
    print(f'  置信度: {r.confidence}')
    print(f'  指标: {json.dumps(r.metrics, ensure_ascii=False)}')
