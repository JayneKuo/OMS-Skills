"""属性测试：OrderQueryResult 序列化往返一致性

**Validates: Requirements 11.3**
"""

from hypothesis import given, strategies as st, settings

from order_query_engine.models import (
    OrderQueryResult, QueryInput, OrderIdentity, OrderContext,
    CurrentStatus, OrderItem, ShippingAddress, ShipmentInfo,
    InventoryInfo, WarehouseInfo, AllocationInfo, RuleInfo,
    EventInfo, QueryExplanation, DataCompleteness,
)

# ── Strategies ──

st_optional_str = st.one_of(st.none(), st.text(min_size=1, max_size=30))
st_optional_bool = st.one_of(st.none(), st.booleans())

st_query_input = st.builds(
    QueryInput,
    input_value=st.text(min_size=1, max_size=30),
    identified_type=st_optional_str,
    resolved_order_no=st_optional_str,
)

st_order_identity = st.one_of(st.none(), st.builds(
    OrderIdentity,
    order_no=st_optional_str,
    merchant_no=st_optional_str,
    channel_name=st_optional_str,
))

st_current_status = st.one_of(st.none(), st.builds(
    CurrentStatus,
    main_status=st_optional_str,
    is_exception=st_optional_bool,
    is_hold=st_optional_bool,
))

st_order_item = st.builds(
    OrderItem,
    sku=st.text(min_size=1, max_size=20),
    quantity=st.integers(min_value=1, max_value=999),
    description=st_optional_str,
)

st_data_completeness = st.builds(
    DataCompleteness,
    completeness_level=st.sampled_from(["full", "partial", "minimal"]),
    missing_fields=st.lists(st.text(min_size=1, max_size=20), max_size=5),
    data_sources=st.lists(st.text(min_size=1, max_size=50), max_size=5),
)

st_order_query_result = st.builds(
    OrderQueryResult,
    query_input=st_query_input,
    order_identity=st_order_identity,
    current_status=st_current_status,
    order_items=st.one_of(st.none(), st.lists(st_order_item, max_size=3)),
    shipping_address=st.one_of(st.none(), st.builds(ShippingAddress)),
    shipment_info=st.one_of(st.none(), st.builds(ShipmentInfo)),
    inventory_info=st.one_of(st.none(), st.builds(InventoryInfo)),
    warehouse_info=st.one_of(st.none(), st.builds(WarehouseInfo)),
    allocation_info=st.one_of(st.none(), st.builds(AllocationInfo)),
    rule_info=st.one_of(st.none(), st.builds(RuleInfo)),
    event_info=st.one_of(st.none(), st.builds(EventInfo)),
    query_explanation=st.one_of(st.none(), st.builds(QueryExplanation)),
    data_completeness=st_data_completeness,
    error=st.none(),
)


@given(result=st_order_query_result)
@settings(max_examples=100)
def test_order_query_result_roundtrip(result: OrderQueryResult):
    """OrderQueryResult 序列化为 JSON 再反序列化后应与原始对象等价。

    **Validates: Requirements 11.3**
    """
    json_str = result.model_dump_json()
    restored = OrderQueryResult.model_validate_json(json_str)
    assert restored == result
