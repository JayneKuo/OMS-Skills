"""属性测试：状态归一化完整性与互斥性

**Validates: Requirements 4.11, 4.12, 4.14, 4.15**
"""

from hypothesis import given, strategies as st, settings

from order_query_engine.status_normalizer import StatusNormalizer, STATUS_MAP

normalizer = StatusNormalizer()

KNOWN_CODES = set(STATUS_MAP.keys())


@given(status_code=st.integers(min_value=0, max_value=30))
@settings(max_examples=100)
def test_exception_and_hold_mutually_exclusive(status_code: int):
    """is_exception 和 is_hold 不同时为 true。

    **Validates: Requirements 4.15**
    """
    result = normalizer.normalize(status_code)
    assert not (result.is_exception and result.is_hold), (
        f"status_code={status_code}: is_exception 和 is_hold 不应同时为 True"
    )


@given(status_code=st.integers(min_value=0, max_value=30))
@settings(max_examples=100)
def test_known_codes_return_chinese_name(status_code: int):
    """已知状态码返回正确的中文名称和分类。

    **Validates: Requirements 4.11, 4.12**
    """
    result = normalizer.normalize(status_code)
    if status_code in KNOWN_CODES:
        expected = STATUS_MAP[status_code]
        assert result.main_status == expected.main_status
        assert result.category == expected.category
    else:
        assert result.main_status == f"未知状态({status_code})"
        assert result.category == "未知"


@given(status_code=st.integers(min_value=-100, max_value=100))
@settings(max_examples=200)
def test_unknown_codes_return_fallback(status_code: int):
    """未知状态码返回"未知状态({code})"。

    **Validates: Requirements 4.14**
    """
    result = normalizer.normalize(status_code)
    if status_code not in KNOWN_CODES:
        assert result.main_status == f"未知状态({status_code})"
        assert result.category == "未知"
        assert result.is_exception is False
        assert result.is_hold is False
