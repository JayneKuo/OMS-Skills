"""订单全景查询引擎 - 结构化错误类型"""

from __future__ import annotations


class QueryError(Exception):
    """查询引擎基础错误。"""

    def __init__(self, error_type: str, message: str,
                 context: dict | None = None):
        self.error_type = error_type
        self.message = message
        self.context = context or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "context": self.context,
        }


class AuthenticationError(QueryError):
    def __init__(self, status_code: int, response_summary: str):
        super().__init__(
            error_type="auth_failed",
            message=f"认证失败 (HTTP {status_code}): {response_summary}",
            context={"status_code": status_code,
                     "response_summary": response_summary},
        )


class OrderNotFoundError(QueryError):
    def __init__(self, order_no: str):
        super().__init__(
            error_type="not_found",
            message=f"订单不存在: {order_no}",
            context={"order_no": order_no},
        )


class APICallError(QueryError):
    def __init__(self, path: str, status_code: int,
                 response_summary: str):
        super().__init__(
            error_type="api_error",
            message=f"API 调用失败 {path} (HTTP {status_code}): {response_summary}",
            context={"path": path, "status_code": status_code,
                     "response_summary": response_summary},
        )


class NetworkTimeoutError(QueryError):
    def __init__(self, url: str):
        super().__init__(
            error_type="network_error",
            message=f"网络连接超时: {url}",
            context={"url": url},
        )


class IdentifierResolveError(QueryError):
    def __init__(self, input_value: str, tried_types: list[str]):
        super().__init__(
            error_type="resolve_failed",
            message=f"标识解析失败: {input_value}，已尝试类型: {tried_types}",
            context={"input_value": input_value,
                     "tried_types": tried_types},
        )


class ObjectResolveError(QueryError):
    """多对象标识解析失败。"""
    def __init__(self, input_value: str, tried_types: list[str],
                 object_type: str | None = None):
        super().__init__(
            error_type="resolve_failed",
            message=f"对象解析失败: {input_value}，已尝试类型: {tried_types}",
            context={"input_value": input_value,
                     "tried_types": tried_types,
                     "object_type": object_type},
        )
