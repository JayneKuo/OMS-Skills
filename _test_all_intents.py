import sys, os, json

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
engine = OMSAnalysisEngine(data_fetcher=fetcher)

intents = [
    'warehouse_efficiency',
    'inventory_health',
    'channel_performance',
    'order_trend',
    'batch_pattern',
    'impact_assessment',
]

for intent in intents:
    print(f'\n--- {intent} ---')
    result = engine.analyze(AnalysisRequest(merchant_no='LAN0000002', intent=intent))
    for r in result.results:
        print(f'  {r.analyzer_name}: {r.summary}')
        if r.metrics:
            print(f'  指标: {json.dumps(r.metrics, ensure_ascii=False)}')
