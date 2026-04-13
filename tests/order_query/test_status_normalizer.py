"""StatusNormalizer 单元测试 - 逐一验证 25 个状态码"""

import pytest

from order_query_engine.status_normalizer import StatusNormalizer

normalizer = StatusNormalizer()

EXPECTED = [
    (0, "已导入", "初始", False, False),
    (1, "已分仓", "正常", False, False),
    (2, "仓库处理中", "正常", False, False),
    (3, "已发货", "正常", False, False),
    (4, "已关闭", "终态", False, False),
    (5, "退货中", "逆向", False, False),
    (6, "已退货", "逆向", False, False),
    (7, "已退款", "逆向", False, False),
    (8, "已取消", "终态", False, False),
    (9, "待处理", "初始", False, False),
    (10, "异常", "异常", True, False),
    (11, "重新打开", "特殊", False, False),
    (12, "取消中", "过渡", False, False),
    (13, "已接受", "正常", False, False),
    (14, "已拒绝", "终态", False, False),
    (15, "强制关闭", "终态", False, False),
    (16, "暂停履约", "Hold", False, True),
    (18, "仓库已收货", "正常", False, False),
    (20, "已提交", "正常", False, False),
    (21, "已拣货", "正常", False, False),
    (22, "已打包", "正常", False, False),
    (23, "已装车", "正常", False, False),
    (24, "部分发货", "正常", False, False),
    (25, "已解除分配", "特殊", False, False),
]


@pytest.mark.parametrize(
    "code,status,category,is_exc,is_hold", EXPECTED
)
def test_status_mapping(code, status, category, is_exc, is_hold):
    result = normalizer.normalize(code)
    assert result.main_status == status
    assert result.category == category
    assert result.is_exception == is_exc
    assert result.is_hold == is_hold


def test_unknown_status_code():
    result = normalizer.normalize(99)
    assert result.main_status == "未知状态(99)"
    assert result.category == "未知"
    assert result.is_exception is False
    assert result.is_hold is False
