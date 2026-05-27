import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from product_listing_planner_engine.engine import ProductListingPlannerEngine


def _execution_form_for(targets, identifier="READY-SKU", merchant_no="LAN0000002"):
    product_query_result = {
        "details": {
            "product": {
                "title": "Ready Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": identifier, "price": 10, "currency": "USD"}],
            "channel_products": targets,
            "channel_summary": [
                {
                    "channel_code": target.get("channel_code"),
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": [target.get("last_error")] if target.get("last_error") else [],
                }
                for target in targets
            ],
        }
    }

    plan = ProductListingPlannerEngine().plan(
        identifier=identifier,
        merchant_no=merchant_no,
        intent="listing_execution_plan",
        filters={
            "target_channels": [target.get("channel_code") for target in targets],
            "action": "submit_existing_channel_product",
        },
        context={"product_query_result": product_query_result},
    )
    return plan["details"]["execution_form"]


def test_oms_listing_execution_adapter_calls_submit_and_verification_endpoints():
    from product_listing_planner_engine.execution import OmsListingExecutionAdapter

    class FakeClient:
        def __init__(self):
            self.calls = []

        def _ensure_token(self):
            self.calls.append(("ensure_token", None, None))

        def get(self, path, params=None):
            self.calls.append(("get", path, params))
            return {"code": 200, "data": {"id": "CP-1"}}

        def post(self, path, payload):
            self.calls.append(("post", path, payload))
            return {"code": 200, "data": True}

    client = FakeClient()
    adapter = OmsListingExecutionAdapter(client)

    assert adapter.get_channel_product("CP-1") == {"code": 200, "data": {"id": "CP-1"}}
    assert adapter.list_publish_history_by_channel_product("CP-1") == {"code": 200, "data": {"id": "CP-1"}}
    assert adapter.submit_channel_product({"id": "CP-1"}) == {"code": 200, "data": True}
    assert client.calls == [
        ("ensure_token", None, None),
        ("get", "/api/linker-oms/baseservice/rpc-api/channel-product/get/CP-1", None),
        ("ensure_token", None, None),
        ("get", "/api/linker-oms/baseservice/rpc-api/publish-history/list/by-channel-product/CP-1", None),
        ("ensure_token", None, None),
        ("post", "/api/linker-oms/baseservice/rpc-api/channel-product/submit", {"id": "CP-1"}),
    ]


def test_direct_shopify_execution_adapter_posts_product_without_returning_token(monkeypatch):
    from product_listing_planner_engine.execution import DirectShopifyExecutionAdapter

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"product":{"id":12345}}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["data"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = DirectShopifyExecutionAdapter().create_shopify_product(
        "example.myshopify.com",
        "2026-01",
        "shpat_test",
        {"title": "Ready Product"},
    )

    assert result == {"product": {"id": 12345}}
    assert captured["url"] == "https://example.myshopify.com/admin/api/2026-01/products.json"
    assert captured["method"] == "POST"
    assert json.loads(captured["data"].decode("utf-8")) == {"product": {"title": "Ready Product"}}
    assert captured["headers"]["X-shopify-access-token"] == "shpat_test"
    assert "shpat_test" not in json.dumps(result)



def test_execute_requires_confirmation_before_submit():
    class FakeAdapter:
        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called without confirmation")

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": False,
            "action": "submit_existing_channel_product",
            "targets": [{"channel_product_id": "CP-1", "channel_code": "SHOPIFY"}],
        }
    )

    assert result == {
        "success": False,
        "summary": "缺少用户确认，未执行发布提交。",
        "final_conclusion": "Execution failed",
        "errors": ["confirmation_required"],
    }


def test_execute_submits_channel_product_and_verifies_successful_business_result():
    class FakeAdapter:
        def __init__(self):
            self.submitted_payloads = []
            self.product_reads = [
                {"code": 200, "data": {"id": "CP-1", "publishStatus": "FAILED"}},
                {"code": 200, "data": {"id": "CP-1", "publishStatus": "PUBLISHING"}},
            ]
            self.history_reads = [
                {"code": 200, "data": []},
                {"code": 200, "data": [{"id": "PH-2", "status": "PUBLISHING"}]},
            ]

        def get_channel_product(self, channel_product_id):
            return self.product_reads.pop(0)

        def list_publish_history_by_channel_product(self, channel_product_id):
            return self.history_reads.pop(0)

        def submit_channel_product(self, payload):
            self.submitted_payloads.append(payload)
            return {"code": 200, "data": True}

    adapter = FakeAdapter()
    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-1",
            "channel_code": "SHOPIFY",
            "listing_status": "FAILED",
            "audit_status": "REJECTED",
            "last_error": "Previous publish failed",
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert adapter.submitted_payloads == [{"id": "CP-1", "channelProductId": "CP-1"}]
    assert result["success"] is True
    assert result["final_conclusion"] == "Executed successfully"
    assert result["details"]["executions"][0]["endpoint"] == "/rpc-api/channel-product/submit"
    assert result["details"]["executions"][0]["raw_response"] == {"code": 200, "data": True}
    assert result["details"]["verification"][0]["business_result_changed"] is True


def test_execute_rejects_missing_targets():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called without targets")

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("history reads should not be called without targets")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called without targets")

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            "action": "submit_existing_channel_product",
            "merchant_no": "LAN0000002",
            "identifier": "READY-SKU",
            "form_token": "irrelevant-without-targets",
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["errors"] == ["missing_targets"]


def test_execute_rejects_invalid_form_token_without_submit():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called with invalid execution form")

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("history reads should not be called with invalid execution form")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called with invalid execution form")

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            "action": "submit_existing_channel_product",
            "merchant_no": "LAN0000002",
            "identifier": "READY-SKU",
            "targets": [{"channel_product_id": "CP-1", "channel_code": "SHOPIFY", "allowed": True}],
            "form_token": "bad-token",
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["errors"] == ["invalid_execution_form"]


def test_execute_rejects_non_boolean_confirmation_without_submit():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called without strict confirmation")

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called without strict confirmation")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called without strict confirmation")

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": "false",
            "action": "submit_existing_channel_product",
            "targets": [{"channel_product_id": "CP-1", "allowed": True}],
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["errors"] == ["confirmation_required"]


def test_execute_rejects_missing_allowed_flag_without_submit():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called for missing allowed flag")

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called for missing allowed flag")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called for missing allowed flag")

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            "action": "submit_existing_channel_product",
            "targets": [{"channel_product_id": "CP-1"}],
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["errors"] == ["invalid_execution_form"]


def test_execute_reports_submitted_but_not_effective_when_state_does_not_change():
    class FakeAdapter:
        def __init__(self):
            self.submitted_payloads = []
            self.product_reads = [
                {"code": 200, "data": {"id": "CP-1", "publishStatus": "DRAFT", "publish_success": False}},
                {"code": 200, "data": {"id": "CP-1", "publishStatus": "DRAFT", "publish_success": False}},
            ]
            self.history_reads = [
                {"code": 200, "data": []},
                {"code": 200, "data": []},
            ]

        def get_channel_product(self, channel_product_id):
            return self.product_reads.pop(0)

        def list_publish_history_by_channel_product(self, channel_product_id):
            return self.history_reads.pop(0)

        def submit_channel_product(self, payload):
            self.submitted_payloads.append(payload)
            return {"code": 200, "data": True}

    product_query_result = {
        "details": {
            "product": {
                "title": "Retry Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_products": [
                {
                    "channel_product_id": "CP-1",
                    "channel_code": "SHOPIFY",
                    "listing_status": "DRAFT",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Previous publish failed",
                }
            ],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": ["Previous publish failed"],
                }
            ],
        }
    }
    plan = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="listing_execution_plan",
        filters={"target_channels": ["SHOPIFY"], "action": "submit_existing_channel_product"},
        context={"product_query_result": product_query_result},
    )
    execution_form = plan["details"]["execution_form"]

    adapter = FakeAdapter()
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert adapter.submitted_payloads == [{"id": "CP-1", "channelProductId": "CP-1"}]
    assert result["success"] is True
    assert result["final_conclusion"] == "Submitted successfully but business result did not take effect"
    assert result["details"]["verification"][0]["business_result_changed"] is False



def test_execute_treats_unchanged_snake_case_publishing_readback_as_success():
    class FakeAdapter:
        def __init__(self):
            self.submitted_payloads = []
            self.product_reads = [
                {"code": 200, "data": {"id": "CP-1", "publish_status": "PUBLISHING", "publish_success": False}},
                {"code": 200, "data": {"id": "CP-1", "publish_status": "PUBLISHING", "publish_success": False}},
            ]
            self.history_reads = [
                {"code": 200, "data": []},
                {"code": 200, "data": []},
            ]

        def get_channel_product(self, channel_product_id):
            return self.product_reads.pop(0)

        def list_publish_history_by_channel_product(self, channel_product_id):
            return self.history_reads.pop(0)

        def submit_channel_product(self, payload):
            self.submitted_payloads.append(payload)
            return {"code": 200, "data": True}

    adapter = FakeAdapter()
    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-1",
            "channel_code": "SHOPIFY",
            "listing_status": "FAILED",
            "audit_status": "REJECTED",
            "last_error": "Previous publish failed",
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert adapter.submitted_payloads == [{"id": "CP-1", "channelProductId": "CP-1"}]
    assert result["success"] is True
    assert result["final_conclusion"] == "Executed successfully"
    assert result["details"]["verification"][0]["business_result_changed"] is True



def test_execute_ignores_metadata_only_verification_changes():
    class FakeAdapter:
        def __init__(self):
            self.submitted_payloads = []
            self.product_reads = [
                {
                    "code": 200,
                    "trace_id": "trace-before",
                    "timestamp": "2026-05-26T10:00:00Z",
                    "data": {"id": "CP-1", "publishStatus": "FAILED", "trace": "before"},
                },
                {
                    "code": 200,
                    "trace_id": "trace-after",
                    "timestamp": "2026-05-26T10:00:01Z",
                    "data": {"id": "CP-1", "publishStatus": "FAILED", "trace": "after"},
                },
            ]
            self.history_reads = [
                {
                    "code": 200,
                    "trace_id": "history-before",
                    "timestamp": "2026-05-26T10:00:00Z",
                    "data": [{"id": "PH-1", "status": "FAILED", "trace": "before"}],
                },
                {
                    "code": 200,
                    "trace_id": "history-after",
                    "timestamp": "2026-05-26T10:00:01Z",
                    "data": [{"id": "PH-1", "status": "FAILED", "trace": "after"}],
                },
            ]

        def get_channel_product(self, channel_product_id):
            return self.product_reads.pop(0)

        def list_publish_history_by_channel_product(self, channel_product_id):
            return self.history_reads.pop(0)

        def submit_channel_product(self, payload):
            self.submitted_payloads.append(payload)
            return {"code": 200, "data": True}

    adapter = FakeAdapter()
    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-1",
            "channel_code": "SHOPIFY",
            "listing_status": "FAILED",
            "audit_status": "REJECTED",
            "last_error": "Previous publish failed",
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert adapter.submitted_payloads == [{"id": "CP-1", "channelProductId": "CP-1"}]
    assert result["final_conclusion"] == "Submitted successfully but business result did not take effect"
    assert result["details"]["verification"][0]["business_result_changed"] is False


def test_execute_rejects_disallowed_confirmed_target_without_submit():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called for disallowed targets")

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("reads should not be called for disallowed targets")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called for disallowed targets")

    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-1",
            "channel_code": "SHOPIFY",
            "listing_status": "LIVE",
            "audit_status": "APPROVED",
            "publish_success": True,
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert "disallowed_target" in result["errors"]
    assert result["details"]["executions"] == [
        {
            "channel_product_id": "CP-1",
            "endpoint": "/rpc-api/channel-product/submit",
            "request_payload": {},
            "raw_response": None,
            "error": "disallowed_target",
        }
    ]


def test_execute_revalidates_live_target_before_submit():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            return {
                "code": 200,
                "data": {
                    "id": channel_product_id,
                    "channelProductId": channel_product_id,
                    "listing_status": "LIVE",
                    "audit_status": "APPROVED",
                    "publish_success": True,
                },
            }

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("history should not be read for live-disallowed targets")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called for live-disallowed targets")

    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-LIVE",
            "channel_code": "SHOPIFY",
            "listing_status": "FAILED",
            "audit_status": "REJECTED",
            "last_error": "Previous publish failed",
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["errors"] == ["live_target_not_allowed"]
    assert result["details"]["executions"] == [
        {
            "channel_product_id": "CP-LIVE",
            "endpoint": "/rpc-api/channel-product/submit",
            "request_payload": {},
            "raw_response": None,
            "error": "live_target_not_allowed",
        }
    ]


def test_execute_rejects_live_merchant_mismatch_before_submit():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            return {
                "id": channel_product_id,
                "channel_product_id": channel_product_id,
                "merchantNo": "DIFFERENT-MERCHANT",
                "publishStatus": "DRAFT",
                "publish_success": False,
            }

        def list_publish_history_by_channel_product(self, channel_product_id):
            raise AssertionError("history should not be read for merchant mismatches")

        def submit_channel_product(self, payload):
            raise AssertionError("submit should not be called for merchant mismatches")

    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-1",
            "channel_code": "SHOPIFY",
            "listing_status": "FAILED",
            "audit_status": "REJECTED",
            "last_error": "Previous publish failed",
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["errors"] == ["merchant_mismatch"]
    assert result["details"]["executions"] == [
        {
            "channel_product_id": "CP-1",
            "endpoint": "/rpc-api/channel-product/submit",
            "request_payload": {},
            "raw_response": None,
            "error": "merchant_mismatch",
        }
    ]


def test_execute_treats_malformed_submit_response_as_failure():
    class FakeAdapter:
        def get_channel_product(self, channel_product_id):
            return {"code": 200, "data": {"id": channel_product_id, "publishStatus": "DRAFT", "publish_success": False}}

        def list_publish_history_by_channel_product(self, channel_product_id):
            return {"code": 200, "data": []}

        def submit_channel_product(self, payload):
            return None

    execution_form = _execution_form_for([
        {
            "channel_product_id": "CP-1",
            "channel_code": "SHOPIFY",
            "listing_status": "FAILED",
            "audit_status": "REJECTED",
            "last_error": "Previous publish failed",
        }
    ])
    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={
            "confirmed": True,
            **execution_form,
        }
    )

    assert result["final_conclusion"] == "Execution failed"
    assert result["success"] is False
    assert "submit_failed" in result["errors"]


def test_listing_planner_degrades_when_product_query_missing():
    result = ProductListingPlannerEngine().plan(
        identifier="SKU-A",
        merchant_no="M001",
        intent="listing_readiness",
        filters={"target_channels": ["SHOPIFY"]},
        context={},
    )

    assert result["success"] is True
    assert result["confidence"] == "low"
    assert result["data_completeness"] == "insufficient"
    assert result["details"]["readiness_checklist"] == [
        {
            "item": "商品事实查询",
            "status": "blocked",
            "evidence": "缺少 product_query_result，无法确认商品主档、SKU、渠道状态和发布历史。",
        }
    ]
    assert result["details"]["launch_steps"][0]["title"] == "先查询商品事实"


def test_listing_planner_builds_channel_plan_for_0324fan():
    fixture_dir = Path(__file__).parent / "fixtures"
    product_query_result = json.loads((fixture_dir / "product_query_0324fan.json").read_text(encoding="utf-8"))
    product_diagnosis_result = json.loads((fixture_dir / "product_diagnosis_0324fan_shopifyv3.json").read_text(encoding="utf-8"))

    result = ProductListingPlannerEngine().plan(
        identifier="0324fan",
        merchant_no="LAN0000002",
        intent="listing_readiness",
        filters={"target_channels": ["SHEIN", "ShopifyV3"]},
        context={
            "product_query_result": product_query_result,
            "product_diagnosis_result": product_diagnosis_result,
        },
    )

    assert result["summary"] == "0324fan 当前不建议直接发布，2 个渠道存在阻塞项。"
    assert result["metrics"] == {
        "target_channel_count": 2,
        "blocked_channel_count": 2,
        "ready_channel_count": 0,
        "launch_step_count": 3,
    }
    assert result["details"]["channel_priority"] == [
        {
            "channel_code": "ShopifyV3",
            "priority": "P0",
            "status": "blocked",
            "reason": "当前 OMS 发布服务对 ShopifyV3 的底层 channel type 支持存在问题。",
            "required_actions": ["确认 ShopifyV3 渠道配置与发布服务支持关系"],
            "risks": ["继续使用 ShopifyV3 会重复发布失败"],
        },
        {
            "channel_code": "SHEIN",
            "priority": "P1",
            "status": "blocked",
            "reason": "SHEIN 渠道存在商品属性/SKC/销售属性缺失错误。",
            "required_actions": ["补齐 SKC", "补齐销售属性", "补齐商品属性"],
            "risks": ["未补齐前重新发布会继续失败"],
        },
    ]
    assert [step["title"] for step in result["details"]["launch_steps"]] == [
        "检查 ShopifyV3 发布服务支持",
        "补齐 SHEIN 商品属性",
        "重新执行发布前置诊断",
    ]
    assert result["details"]["readiness_checklist"] == [
        {"item": "商品标题", "status": "ready", "evidence": "fanfanfan"},
        {"item": "SKU", "status": "ready", "evidence": "1 个 SKU 可用"},
        {"item": "价格", "status": "ready", "evidence": "USD 1999"},
        {"item": "图片", "status": "ready", "evidence": "1 张图片"},
        {"item": "渠道类型", "status": "blocked", "evidence": "ShopifyV3 不被发布服务支持"},
        {"item": "渠道属性", "status": "blocked", "evidence": "SHEIN 缺少商品属性/SKC/销售属性"},
    ]


def test_listing_planner_blocks_non_shein_channel_with_summary_errors():
    product_query_result = {
        "details": {
            "product": {
                "title": "Needs Fix Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "NEEDS-FIX-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": ["Missing required product field"],
                }
            ],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="NEEDS-FIX-SKU",
        merchant_no="LAN0000002",
        intent="listing_readiness",
        filters={"target_channels": ["SHOPIFY"]},
        context={"product_query_result": product_query_result},
    )

    assert result["metrics"]["blocked_channel_count"] == 1
    assert result["metrics"]["ready_channel_count"] == 0
    assert result["details"]["channel_priority"] == [
        {
            "channel_code": "SHOPIFY",
            "priority": "P1",
            "status": "blocked",
            "reason": "该渠道存在发布错误，需要先处理错误后再提交发布。",
            "required_actions": ["查看渠道发布错误并修复源商品或渠道资料"],
            "risks": ["未修复前重新发布可能继续失败"],
        }
    ]
    channel_plan = result["details"]["channel_priority"][0]
    assert channel_plan["reason"] != "当前事实数据未发现该渠道阻塞项。"
    assert channel_plan["risks"]


def test_listing_planner_returns_confirmation_form_for_existing_channel_product_submit():
    product_query_result = {
        "details": {
            "product": {
                "title": "Ready Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_products": [
                {
                    "channel_product_id": "CP-READY-1",
                    "channel_code": "SHOPIFY",
                    "listing_status": "DRAFT",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Previous publish failed",
                }
            ],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": ["Previous publish failed"],
                }
            ],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="listing_execution_plan",
        filters={"target_channels": ["SHOPIFY"], "action": "submit_existing_channel_product"},
        context={"product_query_result": product_query_result},
    )

    assert result["success"] is True
    execution_form = result["details"]["execution_form"]
    assert execution_form["form_token"]
    assert execution_form == {
        "requires_confirmation": True,
        "next_action": "collect_user_decision",
        "action": "submit_existing_channel_product",
        "merchant_no": "LAN0000002",
        "identifier": "READY-SKU",
        "targets": [
            {
                "channel_product_id": "CP-READY-1",
                "channel_code": "SHOPIFY",
                "current_listing_status": "DRAFT",
                "current_audit_status": "DRAFT",
                "allowed": True,
                "warnings": ["Previous publish failed"],
            }
        ],
        "form_token": execution_form["form_token"],
    }
    assert result["details"]["execution_allowed"] is True


def test_listing_planner_lowercase_target_channel_matches_existing_channel_product_submit():
    product_query_result = {
        "details": {
            "product": {
                "title": "Ready Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_products": [
                {
                    "channel_product_id": "CP-READY-1",
                    "channel_code": "SHOPIFY",
                    "listing_status": "DRAFT",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Previous publish failed",
                }
            ],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": ["Previous publish failed"],
                }
            ],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="listing_execution_plan",
        filters={"target_channels": ["shopify"], "action": "submit_existing_channel_product"},
        context={"product_query_result": product_query_result},
    )

    assert result["details"]["execution_form"]["targets"] == [
        {
            "channel_product_id": "CP-READY-1",
            "channel_code": "SHOPIFY",
            "current_listing_status": "DRAFT",
            "current_audit_status": "DRAFT",
            "allowed": True,
            "warnings": ["Previous publish failed"],
        }
    ]
    assert result["details"]["execution_allowed"] is True


def test_listing_planner_lowercase_shopifyv3_target_hits_unsupported_blocker():
    product_query_result = {
        "details": {
            "product": {
                "title": "ShopifyV3 Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "SHOPIFYV3-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [
                {
                    "channel_code": "ShopifyV3",
                    "channel_product_count": 1,
                    "publish_failure_count": 0,
                    "errors": [],
                }
            ],
        }
    }
    product_diagnosis_result = {
        "details": {
            "blocking_issues": [
                {
                    "code": "unsupported_oms_shopify_channel_type",
                    "severity": "critical",
                }
            ]
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="SHOPIFYV3-SKU",
        merchant_no="LAN0000002",
        intent="listing_readiness",
        filters={"target_channels": ["shopifyv3"]},
        context={
            "product_query_result": product_query_result,
            "product_diagnosis_result": product_diagnosis_result,
        },
    )

    assert result["metrics"]["blocked_channel_count"] == 1
    assert result["details"]["channel_priority"][0]["status"] == "blocked"
    assert result["details"]["readiness_checklist"][-1] == {
        "item": "渠道类型",
        "status": "blocked",
        "evidence": "ShopifyV3 不被发布服务支持",
    }
    assert result["details"]["launch_steps"][0]["title"] == "检查 ShopifyV3 发布服务支持"


def test_direct_shopify_plan_collects_missing_auth_before_execution():
    product_query_result = {
        "details": {
            "product": {"title": "Ready Product", "brand": "Acme", "category": "Bags", "image_count": 1},
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={"action": "direct_shopify_product_create"},
        context={"product_query_result": product_query_result},
    )

    form = result["details"]["execution_form"]
    assert form["action"] == "direct_shopify_product_create"
    assert form["requires_confirmation"] is True
    assert form["next_action"] == "collect_auth_and_user_decision"
    assert form["missing_auth_fields"] == ["shop_domain", "admin_access_token"]
    assert form["api_version"] == "2026-01"
    assert result["details"]["execution_allowed"] is False


def test_direct_shopify_plan_builds_draft_product_payload_when_auth_present():
    product_query_result = {
        "details": {
            "product": {
                "title": "Ready Product",
                "brand": "Acme",
                "category": "Bags",
                "image_count": 1,
                "price": 10,
                "currency": "USD",
            },
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": "example.myshopify.com",
            "admin_access_token": "shpat_test",
        },
        context={"product_query_result": product_query_result},
    )

    form = result["details"]["execution_form"]
    assert form["missing_auth_fields"] == []
    assert form["shop_domain"] == "example.myshopify.com"
    assert form["product_payload"] == {
        "title": "Ready Product",
        "vendor": "Acme",
        "productType": "Bags",
        "status": "DRAFT",
        "variants": [{"sku": "READY-SKU", "price": "10"}],
    }
    assert form["contains_secret"] is False
    assert "admin_access_token" not in form
    assert result["details"]["execution_allowed"] is True


def _direct_shopify_form_token(product_title="Ready Product", seller_sku="READY-SKU", shop_domain="example.myshopify.com"):
    product_query_result = {
        "details": {
            "product": {
                "title": product_title,
                "brand": "Acme",
                "category": "Bags",
                "image_count": 1,
                "price": 10,
                "currency": "USD",
            },
            "skus": [{"seller_sku": seller_sku, "price": 10, "currency": "USD"}],
            "channel_summary": [],
            "channel_products": [],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": shop_domain,
            "admin_access_token": "shpat_test",
        },
        context={"product_query_result": product_query_result},
    )
    return result["details"]["execution_form"]["form_token"]


def test_direct_shopify_form_token_changes_when_shop_domain_changes():
    first_token = _direct_shopify_form_token(shop_domain="first-shop.myshopify.com")
    second_token = _direct_shopify_form_token(shop_domain="second-shop.myshopify.com")

    assert first_token != second_token


def test_direct_shopify_form_token_changes_when_product_payload_changes():
    first_token = _direct_shopify_form_token(product_title="Ready Product", seller_sku="READY-SKU")
    title_changed_token = _direct_shopify_form_token(product_title="Updated Product", seller_sku="READY-SKU")
    sku_changed_token = _direct_shopify_form_token(product_title="Ready Product", seller_sku="UPDATED-SKU")

    assert first_token != title_changed_token
    assert first_token != sku_changed_token


def test_listing_planner_disallows_submit_when_channel_product_id_missing():
    product_query_result = {
        "details": {
            "product": {
                "title": "Missing Channel Product Id",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "MISSING-CP-ID", "price": 10, "currency": "USD"}],
            "channel_products": [
                {
                    "channel_product_id": None,
                    "channel_code": "SHOPIFY",
                    "listing_status": "DRAFT",
                    "audit_status": "DRAFT",
                    "publish_success": False,
                    "last_error": "Previous publish failed",
                }
            ],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 1,
                    "errors": ["Previous publish failed"],
                }
            ],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="MISSING-CP-ID",
        merchant_no="LAN0000002",
        intent="listing_execution_plan",
        filters={"target_channels": ["SHOPIFY"], "action": "submit_existing_channel_product"},
        context={"product_query_result": product_query_result},
    )

    assert result["details"]["execution_form"]["targets"][0]["allowed"] is False
    assert result["details"]["execution_allowed"] is False


def test_listing_planner_disallows_submit_for_already_successful_live_approved_channel_product():
    product_query_result = {
        "details": {
            "product": {
                "title": "Already Live Product",
                "price": 10,
                "currency": "USD",
                "image_count": 1,
            },
            "skus": [{"seller_sku": "ALREADY-LIVE", "price": 10, "currency": "USD"}],
            "channel_products": [
                {
                    "channel_product_id": "CP-LIVE-1",
                    "channel_code": "SHOPIFY",
                    "listing_status": "LIVE",
                    "audit_status": "APPROVED",
                    "publish_success": True,
                }
            ],
            "channel_summary": [
                {
                    "channel_code": "SHOPIFY",
                    "channel_product_count": 1,
                    "publish_failure_count": 0,
                    "errors": [],
                }
            ],
        }
    }

    result = ProductListingPlannerEngine().plan(
        identifier="ALREADY-LIVE",
        merchant_no="LAN0000002",
        intent="listing_execution_plan",
        filters={"target_channels": ["SHOPIFY"], "action": "submit_existing_channel_product"},
        context={"product_query_result": product_query_result},
    )

    assert result["details"]["execution_form"]["targets"][0]["allowed"] is False
    assert result["details"]["execution_allowed"] is False


def test_execute_direct_shopify_creates_product_and_verifies_readback():
    class FakeAdapter:
        def __init__(self):
            self.created_payloads = []

        def create_shopify_product(self, shop_domain, api_version, admin_access_token, product_payload):
            self.created_payloads.append((shop_domain, api_version, admin_access_token, product_payload))
            return {"product": {"id": 12345, "title": "Ready Product", "status": "DRAFT"}}

        def get_shopify_product(self, shop_domain, api_version, admin_access_token, product_id):
            return {
                "product": {
                    "id": 12345,
                    "title": "Ready Product",
                    "status": "DRAFT",
                    "variants": [{"sku": "READY-SKU", "price": "10"}],
                }
            }

    product_query_result = {
        "details": {
            "product": {"title": "Ready Product", "brand": "Acme", "category": "Bags", "price": 10, "currency": "USD"},
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
        }
    }
    form = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": "example.myshopify.com",
            "admin_access_token": "shpat_test",
        },
        context={"product_query_result": product_query_result},
    )["details"]["execution_form"]

    adapter = FakeAdapter()
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={"confirmed": True, "admin_access_token": "shpat_test", **form}
    )

    assert adapter.created_payloads == [
        (
            "example.myshopify.com",
            "2026-01",
            "shpat_test",
            {
                "title": "Ready Product",
                "vendor": "Acme",
                "productType": "Bags",
                "status": "DRAFT",
                "variants": [{"sku": "READY-SKU", "price": "10"}],
            },
        )
    ]
    assert result["success"] is True
    assert result["final_conclusion"] == "Executed successfully"
    assert result["details"]["verification"]["business_result_changed"] is True
    assert "shpat_test" not in json.dumps(result)


def test_execute_direct_shopify_reports_submitted_but_not_effective_when_readback_missing():
    class FakeAdapter:
        def create_shopify_product(self, shop_domain, api_version, admin_access_token, product_payload):
            return {"product": {"id": 12345, "title": "Ready Product", "status": "DRAFT"}}

        def get_shopify_product(self, shop_domain, api_version, admin_access_token, product_id):
            return {"product": None}

    product_query_result = {
        "details": {
            "product": {"title": "Ready Product", "price": 10, "currency": "USD"},
            "skus": [{"seller_sku": "READY-SKU", "price": 10, "currency": "USD"}],
        }
    }
    form = ProductListingPlannerEngine().plan(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        intent="direct_shopify_publish",
        filters={
            "action": "direct_shopify_product_create",
            "shop_domain": "example.myshopify.com",
            "admin_access_token": "shpat_test",
        },
        context={"product_query_result": product_query_result},
    )["details"]["execution_form"]

    result = ProductListingPlannerEngine(execution_adapter=FakeAdapter()).execute(
        request={"confirmed": True, "admin_access_token": "shpat_test", **form}
    )

    assert result["success"] is True
    assert result["final_conclusion"] == "Submitted successfully but business result did not take effect"


def test_execute_routes_oms_shopify_publish_to_publish_adapter():
    class FakeAdapter:
        def __init__(self):
            self.publish_requests = []

        def publish_oms_shopify_product(self, merchant_no, request):
            self.publish_requests.append((merchant_no, request))
            return {"success": True, "details": {"channel_sync": {"data": {"successCount": 1}}}}

    request_payload = {
        "product": {
            "name": "Ready Product",
            "variants": [{"sellerSku": "READY-SKU", "price": 10}],
        },
        "channels": [{"channel": "shopify", "channelNo": "SHOP-1"}],
    }
    form = ProductListingPlannerEngine().build_oms_shopify_publish_form(
        identifier="READY-SKU",
        merchant_no="LAN0000002",
        request_payload=request_payload,
    )

    adapter = FakeAdapter()
    result = ProductListingPlannerEngine(execution_adapter=adapter).execute(
        request={"confirmed": True, **form}
    )

    assert adapter.publish_requests == [("LAN0000002", request_payload)]
    assert result["success"] is True
    assert result["final_conclusion"] == "Executed successfully"
