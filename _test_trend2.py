import sys, os, json

for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]

sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))

from oms_analysis_engine.engine import OMSAnalysisEngine
from oms_analysis_engine.data_fetcher import DataFetcher
from oms_analysis_engine.models.request import AnalysisRequest
from oms_query_engine.engine_v2 import OMSQueryEngine

oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)
engine = OMSAnalysisEngine(data_fetcher=fetcher)

# Test ONLY order_trend (no prior calls)
print("=== order_trend only ===")
result = engine.analyze(AnalysisRequest(merchant_no='LAN0000002', intent='order_trend'))
for r in result.results:
    print(f'  {r.analyzer_name}: {r.summary}')
    if r.details.get('daily_trend'):
        print(f'  Days: {len(r.details["daily_trend"])}')
