"""oms_agent_server 兼容性测试"""
import json
from unittest.mock import MagicMock, patch

from mcp_server.oms_agent_server import _resolve_merchant_no, oms_latest_order


class TestMerchantResolution:
    def test_resolve_merchant_no_accepts_frontend_aliases(self, monkeypatch):
        monkeypatch.setenv("merchant", "MERCHANT-ALIAS")

        assert _resolve_merchant_no(None) == "MERCHANT-ALIAS"


class TestLatestOrderTool:
    def test_oms_latest_order_uses_latest_order_batch_query(self):
        engine = MagicMock()
        engine.query_batch.return_value.model_dump.return_value = {
            "orders": [{"orderNo": "SO999"}],
            "total": 1,
        }

        with patch("oms_query_engine.engine_v2.OMSQueryEngine", return_value=engine):
            payload = json.loads(oms_latest_order())

        request = engine.query_batch.call_args.args[0]
        assert request.query_type == "latest_order"
        assert payload["total"] == 1
        assert payload["orders"][0]["orderNo"] == "SO999"
