import sys, os, json
for mod_name in list(sys.modules.keys()):
    if 'oms_analysis' in mod_name or 'oms_query' in mod_name:
        del sys.modules[mod_name]
sys.path.insert(0, os.path.join('.kiro','skills','oms-analysis','scripts'))
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))

from oms_analysis_engine.engine import OMSAnalysisEngine
from oms_analysis_engine.data_fetcher import DataFetcher
from oms_analysis_engine.models.request import AnalysisRequest
from oms_analysis_engine.analyzer_registry import AnalyzerRegistry
from oms_analysis_engine.intent_detector import IntentDetector
from oms_query_engine.engine_v2 import OMSQueryEngine

oms = OMSQueryEngine()
fetcher = DataFetcher(oms_engine=oms)

# Check what intent detector returns
detector = IntentDetector()
req = AnalysisRequest(merchant_no='LAN0000002', intent='order_trend')
intents = detector.detect(req)
print(f'Detected intents: {intents}')

# Check what analyzer is resolved
registry = AnalyzerRegistry()
registry.auto_discover()
analyzers = registry.resolve(intents)
print(f'Resolved analyzers: {[a.name for a in analyzers]}')
if analyzers:
    print(f'Required data: {analyzers[0].required_data}')

# Fetch context
ctx = fetcher.fetch(req, analyzers)
print(f'batch_orders count: {len(ctx.batch_orders)}')
if ctx.batch_orders:
    o = ctx.batch_orders[0]
    print(f'First order createTime: {o.get("createTime")}')
    print(f'First order status: {o.get("status")}')
