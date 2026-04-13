"""StatusNormalizer v2 测试 — 含 is_deallocated"""
import pytest
from oms_query_engine.status_normalizer import StatusNormalizer


@pytest.fixture
def normalizer():
    return StatusNormalizer()


class TestDeallocated:
    def test_status_25_is_deallocated(self, normalizer):
        n = normalizer.normalize(25)
        assert n.is_deallocated is True
        assert n.is_exception is False
        assert n.is_hold is False
        assert n.main_status == "已解除分配"

    def test_status_str_deallocated(self, normalizer):
        n = normalizer.normalize("DEALLOCATED")
        assert n.is_deallocated is True

    def test_normal_status_not_deallocated(self, normalizer):
        n = normalizer.normalize(1)
        assert n.is_deallocated is False

    def test_exception_not_deallocated(self, normalizer):
        n = normalizer.normalize(10)
        assert n.is_deallocated is False
        assert n.is_exception is True

    def test_hold_not_deallocated(self, normalizer):
        n = normalizer.normalize(16)
        assert n.is_deallocated is False
        assert n.is_hold is True


class TestMutualExclusion:
    """is_exception / is_hold / is_deallocated 三者互斥。"""

    @pytest.mark.parametrize("code", list(range(26)) + [18, 20, 21, 22, 23, 24, 25])
    def test_at_most_one_flag(self, normalizer, code):
        n = normalizer.normalize(code)
        flags = [n.is_exception, n.is_hold, n.is_deallocated]
        assert sum(flags) <= 1, f"status_code={code}: multiple flags set: {flags}"
