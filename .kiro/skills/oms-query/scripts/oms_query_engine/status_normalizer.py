"""订单全景查询引擎 - 状态归一化器"""

from __future__ import annotations

from oms_query_engine.models.status import NormalizedStatus, StatusMapping

# 完整映射表（25 个状态码）— 模块级常量
STATUS_MAP: dict[int, StatusMapping] = {
    0:  StatusMapping(main_status="已导入", category="初始"),
    1:  StatusMapping(main_status="已分仓", category="正常"),
    2:  StatusMapping(main_status="仓库处理中", category="正常"),
    3:  StatusMapping(main_status="已发货", category="正常"),
    4:  StatusMapping(main_status="已关闭", category="终态"),
    5:  StatusMapping(main_status="退货中", category="逆向"),
    6:  StatusMapping(main_status="已退货", category="逆向"),
    7:  StatusMapping(main_status="已退款", category="逆向"),
    8:  StatusMapping(main_status="已取消", category="终态"),
    9:  StatusMapping(main_status="待处理", category="初始"),
    10: StatusMapping(main_status="异常", category="异常",
                      is_exception=True, is_hold=False),
    11: StatusMapping(main_status="重新打开", category="特殊"),
    12: StatusMapping(main_status="取消中", category="过渡"),
    13: StatusMapping(main_status="已接受", category="正常"),
    14: StatusMapping(main_status="已拒绝", category="终态"),
    15: StatusMapping(main_status="强制关闭", category="终态"),
    16: StatusMapping(main_status="暂停履约", category="Hold",
                      is_exception=False, is_hold=True),
    18: StatusMapping(main_status="仓库已收货", category="正常"),
    20: StatusMapping(main_status="已提交", category="正常"),
    21: StatusMapping(main_status="已拣货", category="正常"),
    22: StatusMapping(main_status="已打包", category="正常"),
    23: StatusMapping(main_status="已装车", category="正常"),
    24: StatusMapping(main_status="部分发货", category="正常"),
    25: StatusMapping(main_status="已解除分配", category="特殊", is_deallocated=True),
}


# 字符串状态映射（API 实际返回的格式）
STATUS_STR_MAP: dict[str, StatusMapping] = {
    "IMPORTED": StatusMapping(main_status="已导入", category="初始"),
    "ALLOCATED": StatusMapping(main_status="已分仓", category="正常"),
    "WAREHOUSE_PROCESSING": StatusMapping(main_status="仓库处理中", category="正常"),
    "SHIPPED": StatusMapping(main_status="已发货", category="正常"),
    "CLOSED": StatusMapping(main_status="已关闭", category="终态"),
    "RETURN_STARTED": StatusMapping(main_status="退货中", category="逆向"),
    "RETURNED": StatusMapping(main_status="已退货", category="逆向"),
    "REFUNDED": StatusMapping(main_status="已退款", category="逆向"),
    "CANCELLED": StatusMapping(main_status="已取消", category="终态"),
    "OPEN": StatusMapping(main_status="待处理", category="初始"),
    "EXCEPTION": StatusMapping(main_status="异常", category="异常", is_exception=True),
    "REOPEN": StatusMapping(main_status="重新打开", category="特殊"),
    "CANCELLING": StatusMapping(main_status="取消中", category="过渡"),
    "ACCEPTED": StatusMapping(main_status="已接受", category="正常"),
    "REJECTED": StatusMapping(main_status="已拒绝", category="终态"),
    "FORCE_CLOSED": StatusMapping(main_status="强制关闭", category="终态"),
    "ON_HOLD": StatusMapping(main_status="暂停履约", category="Hold", is_hold=True),
    "WAREHOUSE_RECEIVED": StatusMapping(main_status="仓库已收货", category="正常"),
    "COMMITED": StatusMapping(main_status="已提交", category="正常"),
    "PICKED": StatusMapping(main_status="已拣货", category="正常"),
    "PACKED": StatusMapping(main_status="已打包", category="正常"),
    "LOADED": StatusMapping(main_status="已装车", category="正常"),
    "PARTIALLY_SHIPPED": StatusMapping(main_status="部分发货", category="正常"),
    "DEALLOCATED": StatusMapping(main_status="已解除分配", category="特殊", is_deallocated=True),
    "SHORT_SHIPPED": StatusMapping(main_status="短发", category="特殊"),
    "WAREHOUSE_CANCELLED": StatusMapping(main_status="仓库取消", category="终态"),
}


class StatusNormalizer:
    """将 OMS 原始 status_code 映射为统一中文业务状态。"""

    def normalize(self, status_code: int | str) -> NormalizedStatus:
        """归一化状态码（支持 int 和 str 两种格式）。"""
        # 尝试 int 映射
        if isinstance(status_code, int):
            mapping = STATUS_MAP.get(status_code)
            if mapping:
                return NormalizedStatus(
                    status_code=status_code,
                    main_status=mapping.main_status,
                    category=mapping.category,
                    is_exception=mapping.is_exception,
                    is_hold=mapping.is_hold,
                    is_deallocated=mapping.is_deallocated,
                )
        # 尝试 str 映射
        if isinstance(status_code, str):
            mapping = STATUS_STR_MAP.get(status_code.upper())
            if mapping:
                return NormalizedStatus(
                    status_code=status_code,
                    main_status=mapping.main_status,
                    category=mapping.category,
                    is_exception=mapping.is_exception,
                    is_hold=mapping.is_hold,
                    is_deallocated=mapping.is_deallocated,
                )
            # 尝试将字符串转为 int
            try:
                code_int = int(status_code)
                return self.normalize(code_int)
            except (ValueError, TypeError):
                pass
        return NormalizedStatus(
            status_code=status_code,
            main_status=f"未知状态({status_code})",
            category="未知",
            is_exception=False,
            is_hold=False,
        )
