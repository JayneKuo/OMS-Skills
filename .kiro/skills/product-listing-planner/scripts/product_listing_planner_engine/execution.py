from __future__ import annotations

import json
import urllib.error
import urllib.request


class OmsListingExecutionAdapter:
    def __init__(self, client):
        self._client = client

    def get_channel_product(self, channel_product_id: str) -> dict:
        self._client._ensure_token()
        return self._client.get(
            f"/api/linker-oms/baseservice/rpc-api/channel-product/get/{channel_product_id}"
        )

    def list_publish_history_by_channel_product(self, channel_product_id: str) -> dict:
        self._client._ensure_token()
        return self._client.get(
            f"/api/linker-oms/baseservice/rpc-api/publish-history/list/by-channel-product/{channel_product_id}"
        )

    def submit_channel_product(self, payload: dict) -> dict:
        self._client._ensure_token()
        return self._client.post(
            "/api/linker-oms/baseservice/rpc-api/channel-product/submit",
            payload,
        )

    def publish_oms_shopify_product(self, merchant_no: str, request: dict) -> dict:
        from product_query_engine.publish_workflow import ProductPublishWorkflow

        return ProductPublishWorkflow(self._client).publish(merchant_no=merchant_no, request=request)


class DirectShopifyExecutionAdapter:
    def create_shopify_product(
        self,
        shop_domain: str,
        api_version: str,
        admin_access_token: str,
        product_payload: dict,
    ) -> dict:
        return self._request(
            shop_domain,
            api_version,
            admin_access_token,
            "POST",
            "products.json",
            {"product": product_payload},
        )

    def get_shopify_product(
        self,
        shop_domain: str,
        api_version: str,
        admin_access_token: str,
        product_id,
    ) -> dict:
        return self._request(
            shop_domain,
            api_version,
            admin_access_token,
            "GET",
            f"products/{product_id}.json",
        )

    @staticmethod
    def _request(
        shop_domain: str,
        api_version: str,
        admin_access_token: str,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        url = f"https://{shop_domain}/admin/api/{api_version}/{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": admin_access_token,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body) if response_body else {}
        except urllib.error.HTTPError as e:
            response_body = e.read().decode("utf-8")
            return {
                "error": "shopify_http_error",
                "status": e.code,
                "message": response_body,
            }
