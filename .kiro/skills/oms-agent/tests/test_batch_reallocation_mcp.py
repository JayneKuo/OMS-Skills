import json
import sys
import types

from test_navigation_routes import load_mcp_server


def test_batch_reallocation_analyze_returns_form_payload(monkeypatch):
    module = load_mcp_server()

    class FakeAnalyzer:
        def __init__(self, config, client):
            pass

        def analyze(self, identifiers, merchant_no=None):
            from batch_reallocation.models import AnalyzeResponse
            return AnalyzeResponse()

    class FakeClient:
        def __init__(self, config):
            pass

    monkeypatch.setitem(sys.modules, "batch_reallocation.analyzer", types.SimpleNamespace(BatchReallocationAnalyzer=FakeAnalyzer))
    monkeypatch.setitem(sys.modules, "batch_reallocation.api_client", types.SimpleNamespace(BatchReallocationAPIClient=FakeClient))

    result = json.loads(module.batch_reallocation_analyze('["SO1"]'))

    assert result["form_type"] == "batch-reallocation-analysis"
    assert result["requires_confirmation"] is True


def test_batch_reallocation_execute_returns_execution_summary(monkeypatch):
    module = load_mcp_server()

    class FakeExecutor:
        def __init__(self, config, client):
            pass

        def execute(self, request):
            from batch_reallocation.models import ExecuteResponse
            return ExecuteResponse(submitted_orders=1, succeeded_orders=["SO1"])

    class FakeClient:
        def __init__(self, config):
            pass

    monkeypatch.setitem(sys.modules, "batch_reallocation.executor", types.SimpleNamespace(BatchReallocationExecutor=FakeExecutor))
    monkeypatch.setitem(sys.modules, "batch_reallocation.api_client", types.SimpleNamespace(BatchReallocationAPIClient=FakeClient))

    result = json.loads(module.batch_reallocation_execute('{"confirmed":true,"decisions":[{"order_no":"SO1","action_mode":"whole_order"}]}'))

    assert result["submitted_orders"] == 1
    assert result["succeeded_orders"] == ["SO1"]


def test_batch_reallocation_execute_requires_confirmation(monkeypatch):
    module = load_mcp_server()

    class FakeExecutor:
        def __init__(self, config, client):
            raise AssertionError("executor should not be constructed without confirmation")

    class FakeClient:
        def __init__(self, config):
            pass

    monkeypatch.setitem(sys.modules, "batch_reallocation.executor", types.SimpleNamespace(BatchReallocationExecutor=FakeExecutor))
    monkeypatch.setitem(sys.modules, "batch_reallocation.api_client", types.SimpleNamespace(BatchReallocationAPIClient=FakeClient))

    try:
        module.batch_reallocation_execute('{"decisions":[{"order_no":"SO1","action_mode":"whole_order"}]}')
    except ValueError as exc:
        assert "confirmed" in str(exc)
    else:
        raise AssertionError("expected batch_reallocation_execute to require confirmation")
