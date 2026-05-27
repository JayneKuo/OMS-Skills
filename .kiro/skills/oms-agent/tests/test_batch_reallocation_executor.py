from batch_reallocation.config import BatchReallocationConfig
from batch_reallocation.executor import BatchReallocationExecutor
from batch_reallocation.models import ExecuteRequest, OrderDecision


class FakeExecuteClient:
    def __init__(self):
        self.calls = []

    def get_sale_order(self, order_no):
        if order_no == "STALE":
            return {"orderNo": order_no, "status": "Shipped", "items": [{"sku": "SKU-A", "quantity": 1, "fulfilledQty": 1, "hold": 0}]}
        if order_no == "PARTIAL":
            return {
                "orderNo": order_no,
                "status": "Deallocated",
                "items": [
                    {"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0},
                    {"sku": "SKU-B", "quantity": 2, "fulfilledQty": 2, "hold": 0},
                ],
            }
        if order_no == "ONHOLD":
            return {
                "orderNo": order_no,
                "status": "On Hold",
                "items": [
                    {"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 3},
                ],
            }
        return {"orderNo": order_no, "status": "Imported", "items": [{"sku": "SKU-A", "quantity": 3, "fulfilledQty": 0, "hold": 0}]}

    def get_recover_check(self, order_no):
        return order_no != "UNRECOVERABLE"

    def get_recover_query(self, order_no):
        return {"recoverable": order_no != "UNRECOVERABLE"}

    def release_hold(self, order_no):
        self.calls.append(("release_hold", order_no))
        return True

    def recover_dispatch(self, order_no):
        self.calls.append(("recover_dispatch", order_no))
        return True

    def recover_dispatch_part(self, order_no, selected_skus):
        self.calls.append(("recover_dispatch_part", order_no, selected_skus))
        return True


def test_executor_skips_stale_orders_and_executes_whole_order():
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=FakeExecuteClient(),
    )

    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[
                OrderDecision(order_no="SO1", action_mode="whole_order"),
                OrderDecision(order_no="STALE", action_mode="whole_order"),
            ]
        )
    )

    assert result.succeeded_orders == ["SO1"]
    assert result.skipped_orders == {"STALE": "stale_state"}


def test_executor_uses_partial_route_for_selected_skus():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="PARTIAL", action_mode="partial_sku", selected_skus=["SKU-A"])]
        )
    )

    assert result.succeeded_orders == ["PARTIAL"]
    assert client.calls == [("recover_dispatch_part", "PARTIAL", ["SKU-A"])]


def test_executor_skips_orders_that_are_no_longer_recoverable():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="UNRECOVERABLE", action_mode="whole_order")]
        )
    )

    assert result.succeeded_orders == []
    assert result.skipped_orders == {"UNRECOVERABLE": "recover_check_failed"}
    assert client.calls == []


def test_executor_skips_partial_requests_with_non_eligible_skus():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="PARTIAL", action_mode="partial_sku", selected_skus=["SKU-B"])]
        )
    )

    assert result.succeeded_orders == []
    assert result.skipped_orders == {"PARTIAL": "no_eligible_selected_skus"}
    assert client.calls == []


def test_executor_requires_confirmation():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    try:
        executor.execute(
            ExecuteRequest(
                decisions=[OrderDecision(order_no="SO1", action_mode="whole_order")]
            )
        )
    except ValueError as exc:
        assert "confirmed" in str(exc)
    else:
        raise AssertionError("expected execute to require confirmation")


def test_executor_skips_mismatched_live_action_mode_for_deallocated_orders():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="PARTIAL", action_mode="whole_order")]
        )
    )

    assert result.succeeded_orders == []
    assert result.skipped_orders == {"PARTIAL": "action_mode_mismatch"}
    assert client.calls == []


def test_executor_skips_mismatched_live_action_mode_for_on_hold_orders():
    client = FakeExecuteClient()
    executor = BatchReallocationExecutor(
        config=BatchReallocationConfig(
            base_url="https://oms.example.com",
            tenant_id="LT",
            merchant_no="LAN0000002",
            access_token="token-123",
            user="lantester@item.com",
        ),
        client=client,
    )

    result = executor.execute(
        ExecuteRequest(
            confirmed=True,
            decisions=[OrderDecision(order_no="ONHOLD", action_mode="whole_order")]
        )
    )

    assert result.succeeded_orders == []
    assert result.skipped_orders == {"ONHOLD": "action_mode_mismatch"}
    assert client.calls == []
