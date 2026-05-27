from __future__ import annotations

import requests

from batch_reallocation.config import BatchReallocationConfig


class BatchReallocationAPIClient:
    def __init__(self, config: BatchReallocationConfig):
        self.config = config

    def _headers(self, include_user: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "x-tenant-id": self.config.tenant_id or "",
            "locale": "zh-CN",
        }
        if include_user and self.config.user:
            headers["USER"] = self.config.user
        return headers

    def resolve_order(self, identifier: str) -> dict:
        resp = requests.post(
            f"{self.config.base_url}/app-api/tracking-assistant/search-order-no",
            json={"searchValue": identifier},
            headers=self._headers(),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def get_sale_order(self, order_no: str) -> dict:
        resp = requests.get(
            f"{self.config.base_url}/app-api/sale-order/{order_no}",
            headers=self._headers(),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def get_order_logs(self, order_no: str, merchant_no: str) -> list[dict]:
        resp = requests.get(
            f"{self.config.base_url}/app-api/orderLog/list",
            params={"omsOrderNo": order_no, "merchantNo": merchant_no},
            headers=self._headers(),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or []

    def get_recover_check(self, order_no: str) -> bool:
        resp = requests.get(
            f"{self.config.base_url}/app-api/dispatch/recover/check/{order_no}",
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return bool(resp.json().get("data"))

    def get_recover_query(self, order_no: str) -> dict:
        resp = requests.get(
            f"{self.config.base_url}/app-api/dispatch/recover/query/{order_no}",
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def get_hand_check(self, order_no: str) -> bool:
        resp = requests.get(
            f"{self.config.base_url}/app-api/dispatch/hand/check/{order_no}",
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return bool(resp.json().get("data"))

    def get_hand_items(self, order_no: str) -> dict:
        resp = requests.get(
            f"{self.config.base_url}/app-api/dispatch/hand/item/{order_no}",
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data") or {}

    def release_hold(self, order_no: str) -> bool:
        resp = requests.post(
            f"{self.config.base_url}/app-api/order-hold/release",
            params={"orderNo": order_no},
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return bool(resp.json().get("data"))

    def recover_dispatch(self, order_no: str) -> bool:
        resp = requests.post(
            f"{self.config.base_url}/app-api/dispatch/recover/dispatch",
            json={"orderNo": order_no},
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return True

    def recover_dispatch_part(self, order_no: str, selected_skus: list[str]) -> bool:
        resp = requests.post(
            f"{self.config.base_url}/app-api/dispatch/recover/dispatch/part",
            json={"orderNo": order_no, "skus": selected_skus},
            headers=self._headers(include_user=True),
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return True
