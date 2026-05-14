import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from oms_analysis_engine.analyzers.batch_pattern import BatchPatternAnalyzer
from oms_analysis_engine.analyzers.channel_performance import ChannelPerformanceAnalyzer
from oms_analysis_engine.analyzers.order_trend import OrderTrendAnalyzer
from oms_analysis_engine.analyzers.sku_sales import SkuSalesAnalyzer
from oms_analysis_engine.data_fetcher import DataFetcher
from oms_analysis_engine.models.context import AnalysisContext, SamplingInfo
from oms_analysis_engine.models.enums import Confidence
from oms_analysis_engine.models.request import AnalysisRequest, TimeRange


def test_sku_sales_filters_orders_by_sku_and_channel():
    request = AnalysisRequest(
        merchant_no="M001",
        intent="sku_sales",
        filters={"sku": "SKU-A", "channel_code": "amazon"},
    )
    context = AnalysisContext(
        request=request,
        batch_orders=[
            {
                "channelName": "amazon",
                "totalAmount": 100,
                "itemLines": [{"sku": "SKU-A", "qty": 2, "price": 50}],
            },
            {
                "channelName": "shopify",
                "totalAmount": 999,
                "itemLines": [{"sku": "SKU-A", "qty": 9, "price": 111}],
            },
            {
                "channelName": "amazon",
                "totalAmount": 250,
                "itemLines": [{"sku": "SKU-B", "qty": 5, "price": 50}],
            },
        ],
    )

    result = SkuSalesAnalyzer().analyze(context)

    assert result.metrics["total_quantity"] == 2
    assert result.metrics["total_revenue"] == 100
    assert result.metrics["total_skus"] == 1
    assert result.details["sku_ranking"][0]["sku"] == "SKU-A"


def test_channel_performance_filters_orders_by_sku():
    request = AnalysisRequest(
        merchant_no="M001",
        intent="channel_performance",
        filters={"sku": "SKU-A"},
    )
    context = AnalysisContext(
        request=request,
        batch_orders=[
            {
                "channelName": "amazon",
                "status": "SHIPPED",
                "totalAmount": 100,
                "itemLines": [{"sku": "SKU-A", "qty": 2, "price": 50}],
            },
            {
                "channelName": "shopify",
                "status": "CANCELLED",
                "totalAmount": 999,
                "itemLines": [{"sku": "SKU-B", "qty": 9, "price": 111}],
            },
        ],
    )

    result = ChannelPerformanceAnalyzer().analyze(context)

    assert result.metrics["total_orders"] == 1
    assert result.metrics["total_gmv"] == 100
    assert result.details["channels"] == [
        {
            "channel": "amazon",
            "total": 1,
            "gmv": 100.0,
            "gmv_share": 100.0,
            "avg_order_value": 100.0,
            "exception_rate": 0.0,
            "completion_rate": 100.0,
            "cancel_rate": 0.0,
            "total_qty": 0,
            "confidence": "low",
        }
    ]


def test_data_fetcher_applies_time_range_and_filters_to_batch_orders():
    class FakeClient:
        def _ensure_token(self):
            pass

        def get(self, path, params=None):
            if path.endswith("sale-order/status/num"):
                return {"data": {}}
            if path.endswith("sale-order/page"):
                return {
                    "data": {
                        "list": [
                            {
                                "orderNo": "SO-OLD",
                                "orderTime": "2026-04-01T00:00:00+00:00",
                                "channelName": "amazon",
                                "itemLines": [{"sku": "SKU-A", "qty": 1}],
                            },
                            {
                                "orderNo": "SO-IN",
                                "orderTime": "2026-05-01T00:00:00+00:00",
                                "channelName": "amazon",
                                "itemLines": [{"sku": "SKU-A", "qty": 1}],
                            },
                        ]
                    }
                }
            return {"data": {}}

    class FakeOmsEngine:
        def __init__(self):
            self._client = FakeClient()

    request = AnalysisRequest(
        merchant_no="M001",
        intent="sku_sales",
        time_range=TimeRange(
            start=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        ),
        filters={"sku": "SKU-A", "channel_code": "amazon"},
    )

    context = DataFetcher(FakeOmsEngine()).fetch(request, [SkuSalesAnalyzer()])

    assert [order["orderNo"] for order in context.batch_orders] == ["SO-IN"]


def test_data_fetcher_sampling_is_deterministic_and_annotated():
    data = [{"orderNo": f"SO-{i}"} for i in range(1005)]

    sampled, sampling = DataFetcher._apply_sampling(data, threshold=1000)

    assert len(sampled) == 1000
    assert sampled[0]["orderNo"] == "SO-0"
    assert sampled[-1]["orderNo"] == "SO-999"
    assert sampling is not None
    assert sampling.method == "first_n_after_filters"


def test_order_trend_marks_insufficient_days_for_trend_judgment():
    context = AnalysisContext(
        request=AnalysisRequest(intent="order_trend"),
        batch_orders=[
            {"createTime": "2026-05-01T00:00:00+00:00", "status": "SHIPPED", "totalAmount": 100, "qty": 1},
            {"createTime": "2026-05-02T00:00:00+00:00", "status": "EXCEPTION", "totalAmount": 80, "qty": 1},
        ],
    )

    result = OrderTrendAnalyzer().analyze(context)

    assert result.details["trend_window_complete"] is False
    assert result.details["consecutive_rise_warning"] is False
    assert any("不足以形成趋势判断" in evidence.description for evidence in result.evidences)


def test_sku_sales_marks_estimated_revenue_when_line_amount_missing():
    request = AnalysisRequest(merchant_no="M001", intent="sku_sales")
    context = AnalysisContext(
        request=request,
        batch_orders=[
            {
                "totalAmount": 100,
                "itemLines": [{"sku": "SKU-A", "qty": 1}],
            },
            {
                "totalAmount": 200,
                "itemLines": [
                    {"sku": "SKU-A", "qty": 1},
                    {"sku": "SKU-B", "qty": 1},
                ],
            },
        ],
    )

    result = SkuSalesAnalyzer().analyze(context)

    sku_a = next(item for item in result.details["sku_ranking"] if item["sku"] == "SKU-A")
    assert sku_a["revenue"] == 100.0
    assert sku_a["estimated_revenue"] == 100.0
    assert any("订单级估算" in evidence.description for evidence in result.evidences)


def test_batch_pattern_downgrades_confidence_for_partial_log_sampling():
    request = AnalysisRequest(merchant_no="M001", intent="batch_pattern")
    batch_orders = [
        {"orderNo": f"SO-{i}", "status": "EXCEPTION", "channelName": "amazon", "warehouseCode": "WH-1"}
        for i in range(12)
    ]
    event_data = [
        {"omsOrderNo": f"SO-{i}", "eventType": "exception", "eventSubType": "inventoryshort", "description": "Product SKU-A is currently out of stock"}
        for i in range(10)
    ]
    context = AnalysisContext(
        request=request,
        batch_orders=batch_orders,
        event_data=event_data,
        sampling_info=SamplingInfo(total_count=12, sample_count=12, sample_ratio=1.0),
    )

    result = BatchPatternAnalyzer().analyze(context)

    assert result.confidence == Confidence.MEDIUM
    assert "基于抽样 10 单日志" in result.summary
    assert result.details["sample_scope"]["sampled_order_count"] == 10
