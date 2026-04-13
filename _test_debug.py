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

# Test fetcher directly
print("=== Direct fetch test ===")
req = AnalysisRequest(merchant_no='LAN0000002', intent='warehouse_efficiency')

from oms_analysis_engine.analyzer_registry import AnalyzerRegistry
from oms_analysis_engine.intent_detector import IntentDetector

registry = AnalyzerRegistry()
registry.auto_discover()
detector = IntentDetector()

intents = detector.detect(req)
analyzers = registry.resolve(intents)
print(f"Analyzers: {[a.name for a in analyzers]}")
print(f"Required data: {[a.required_data for a in analyzers]}")

ctx = fetcher.fetch(req, analyzers)
print(f"batch_orders: {len(ctx.batch_orders)}")
print(f"warehouse_data: {len(ctx.warehouse_data)}")
print(f"status_counts keys: {list(ctx.status_counts.keys())}")

# Now test through engine
print("\n=== Engine test ===")
engine = OMSAnalysisEngine(data_fetcher=fetcher)
result = engine.analyze(req)
for r in result.results:
    print(f"  {r.analyzer_name}: {r.summary}")
