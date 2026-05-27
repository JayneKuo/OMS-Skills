from batch_reallocation.analyzer import BatchReallocationAnalyzer
from batch_reallocation.config import BatchReallocationConfig


class FakeOMSClient:
    def resolve_order(self, identifier):
        return {"orderNo": identifier}

    def get_sale_order(self, order_no):
        return {
            "orderNo": order_no,
            "status": "Imported" if order_no == "SO1" else "On Hold",
            "holdReason": None if order_no == "SO1" else "address-risk",
            "items": [
                {"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0},
                {"sku": "SKU-B", "quantity": 2, "fulfilledQty": 2, "hold": 0},
            ],
        }

    def get_order_logs(self, order_no, merchant_no):
        return [{"remark": f"log-for-{order_no}"}]

    def get_recover_check(self, order_no):
        return True

    def get_recover_query(self, order_no):
        return {"recoverable": True}


def test_analyzer_groups_orders_and_filters_zero_unfulfilled_qty():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeOMSClient(),
    )

    result = analyzer.analyze(["SO1", "SO2"])

    groups = {group.scenario: group for group in result.groups}
    assert len(groups["imported"].orders) == 1
    assert len(groups["on_hold"].orders) == 1
    imported_order = groups["imported"].orders[0]
    assert [sku.sku for sku in imported_order.skus if sku.eligible] == ["SKU-A"]
    assert result.requires_confirmation is True
    assert result.next_action == "collect_user_decision"


class FakeMixedDeallocatedClient(FakeOMSClient):
    def get_sale_order(self, order_no):
        return {
            "orderNo": order_no,
            "status": "Deallocated",
            "items": [
                {"sku": "SKU-A", "quantity": 5, "fulfilledQty": 5, "hold": 0},
                {"sku": "SKU-B", "quantity": 4, "fulfilledQty": 1, "hold": 0},
            ],
        }


class FakeUnrecoverableClient(FakeOMSClient):
    def get_sale_order(self, order_no):
        return {
            "orderNo": order_no,
            "status": "Imported",
            "items": [
                {"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0},
            ],
        }

    def get_recover_check(self, order_no):
        return False

    def get_recover_query(self, order_no):
        return {"recoverable": False}


class FakeIneligibleStatusClient(FakeOMSClient):
    def get_sale_order(self, order_no):
        return {
            "orderNo": order_no,
            "status": "Shipped",
            "items": [
                {"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0},
            ],
        }


def test_analyzer_uses_sku_selection_for_mixed_deallocated_orders():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeMixedDeallocatedClient(),
    )

    result = analyzer.analyze(["SO-DEALLOCATED"])

    assert result.groups[0].scenario == "deallocated"
    assert result.groups[0].selection_mode == "sku"


def test_analyzer_marks_unrecoverable_orders_ineligible():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeUnrecoverableClient(),
    )

    result = analyzer.analyze(["SO-UNRECOVERABLE"])
    order = result.groups[0].orders[0]

    assert order.eligible is False
    assert order.reason == "recover_check_failed"


def test_analyzer_marks_ineligible_status_orders_ineligible():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeIneligibleStatusClient(),
    )

    result = analyzer.analyze(["SO-SHIPPED"])
    order = result.groups[0].orders[0]

    assert result.groups[0].scenario == "ineligible"
    assert order.eligible is False


class FakeStringResolveClient(FakeOMSClient):
    def __init__(self):
        self.resolve_calls = []

    def resolve_order(self, identifier):
        self.resolve_calls.append(identifier)
        return "SO00169584"

    def get_sale_order(self, order_no):
        order = super().get_sale_order("SO1")
        order["orderNo"] = order_no
        return order


def test_analyzer_accepts_string_resolve_order_response():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeStringResolveClient(),
    )

    result = analyzer.analyze(["raw-input"])

    assert result.groups[0].orders[0].order_no == "SO00169584"


def test_analyzer_bypasses_resolve_for_explicit_so_order_numbers():
    client = FakeStringResolveClient()
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=client,
    )

    result = analyzer.analyze(["SO01375777"])

    assert client.resolve_calls == []
    assert result.groups[0].orders[0].order_no == "SO01375777"


class FakeRecoverCheckFallbackClient(FakeOMSClient):
    def get_sale_order(self, order_no):
        return {
            "orderNo": order_no,
            "status": "Exception",
            "itemLines": [
                {"sku": "SKU-A", "quantity": 2, "fulfilledQty": 0, "hold": 0},
            ],
        }

    def get_order_logs(self, order_no, merchant_no):
        return {
            "list": [
                {"description": f"log-for-{order_no}"},
            ]
        }

    def get_recover_check(self, order_no):
        raise RuntimeError("404")

    def get_recover_query(self, order_no):
        return {"orderNo": order_no, "orderDispatchVOList": []}

    def get_hand_check(self, order_no):
        return True

    def get_hand_items(self, order_no):
        return {
            "orderNo": order_no,
            "itemVOList": [
                {"sku": "SKU-A", "totalQty": 2, "allocated": 0, "remaining": 2},
            ],
        }


def test_analyzer_falls_back_to_hand_endpoints_when_recover_check_unavailable():
    analyzer = BatchReallocationAnalyzer(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
        ),
        client=FakeRecoverCheckFallbackClient(),
    )

    result = analyzer.analyze(["SO-FALLBACK"])
    order = result.groups[0].orders[0]

    assert result.groups[0].scenario == "exception"
    assert order.eligible is True
    assert order.exception_summary == "log-for-SO-FALLBACK"
    assert [sku.sku for sku in order.skus if sku.eligible] == ["SKU-A"]
