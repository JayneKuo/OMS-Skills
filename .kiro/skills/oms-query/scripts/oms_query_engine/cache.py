"""订单全景查询引擎 - 内存字典 + TTL 缓存"""

from __future__ import annotations

import time
from typing import Any


class QueryCache:
    """内存字典 + TTL 缓存，同一 workflow 内避免重复 API 调用。"""

    # TTL 常量（秒）
    TTL_ORDER = 60       # 订单详情 / 日志
    TTL_STATIC = 300     # 仓库 / 规则 / Hold 规则

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """获取缓存值，过期返回 None。"""
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        """设置缓存值和 TTL（秒）。"""
        self._store[key] = (time.time() + ttl, value)

    def invalidate_all(self) -> None:
        """清除所有缓存。"""
        self._store.clear()
