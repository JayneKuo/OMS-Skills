"""models 包导入和序列化测试"""
import os

import pytest
from oms_query_engine.config import EngineConfig
from oms_query_engine.models import (
    QueryRequest, BatchQueryRequest,
    QueryInput, ResolveResult,
    StatusMapping, NormalizedStatus,
    QueryPlan, QueryContext,
    ProviderResult,
    OMSQueryResult, DataCompleteness,
    OrderIdentity, SourceInfo, OrderContext, CurrentStatus,
    ProductInfo, ProductItem, ShippingAddress,
    InventoryInfo, SkuInventoryItem,
    WarehouseInfo, AllocationInfo,
    RuleInfo, ShipmentInfo, TrackingProgressInfo,
    EventInfo, QueryExplanation,
    IntegrationInfo, ConnectorSummary,
    BatchQueryResult,
    HoldDetailInfo, ExceptionDetailInfo, DeallocationDetailInfo,
    # 向后兼容
    OrderItem, OrderQueryResult,
)


class TestModelsImport:
    def test_all_models_importable(self):
        """所有模型都能从 models 包导入。"""
        assert QueryRequest is not None
        assert OMSQueryResult is not None
        assert IntegrationInfo is not None
        assert BatchQueryResult is not None

    def test_backward_compat_aliases(self):
        """向后兼容别名。"""
        assert OrderItem is ProductItem
        assert OrderQueryResult is OMSQueryResult


class TestQueryRequest:
    def test_defaults(self):
        r = QueryRequest(identifier="SO001")
        assert r.query_intent == "status"
        assert r.force_refresh is False

    def test_custom(self):
        r = QueryRequest(identifier="SO001", query_intent="panorama", force_refresh=True)
        assert r.query_intent == "panorama"
        assert r.force_refresh is True


class TestBatchQueryRequest:
    def test_sort_fields(self):
        request = BatchQueryRequest(
            query_type="order_list",
            sort_by="createdTime",
            sort_order="desc",
        )

        assert request.sort_by == "createdTime"
        assert request.sort_order == "desc"


class TestEngineConfig:
    def test_accepts_frontend_env_aliases(self, monkeypatch):
        monkeypatch.setenv("baseUrl", "https://alias.example.com")
        monkeypatch.setenv("tenantId", "TENANT-1")
        monkeypatch.setenv("merchant", "MERCHANT-9")
        monkeypatch.setenv("authorization", "token-alias")

        config = EngineConfig()

        assert config.base_url == "https://alias.example.com"
        assert config.tenant_id == "TENANT-1"
        assert config.merchant_no == "MERCHANT-9"
        assert config.access_token == "token-alias"


class TestQueryInput:
    def test_new_fields(self):
        qi = QueryInput(
            input_value="SO001",
            primary_object_type="order",
            resolved_primary_key="SO001",
        )
        assert qi.primary_object_type == "order"
        assert qi.resolved_primary_key == "SO001"

    def test_backward_compat(self):
        qi = QueryInput(input_value="SO001", resolved_order_no="SO001")
        assert qi.resolved_order_no == "SO001"
