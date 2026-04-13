"""OrderProvider - 订单域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.errors import AuthenticationError, OrderNotFoundError
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.order import (
    OrderIdentity, SourceInfo, OrderContext as OrderCtx,
    CurrentStatus, ProductInfo, ProductItem, ShippingAddress,
)
from .base import BaseProvider

ORDER_DETAIL = "/api/linker-oms/opc/app-api/sale-order/{orderNo}"


class OrderProvider(BaseProvider):
    """订单详情/状态/来源/商品/地址。"""

    name = "order"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        order_no = context.order_no or context.primary_key
        if not order_no:
            result.errors.append("缺少 orderNo")
            return result

        try:
            cache_key = f"detail:{order_no}"
            resp = self._fetch_get(
                ORDER_DETAIL.format(orderNo=order_no),
                cache_key, QueryCache.TTL_ORDER,
            )
            result.called_apis.append(ORDER_DETAIL.format(orderNo=order_no))
        except AuthenticationError:
            raise
        except Exception as e:
            if "404" in str(e):
                raise OrderNotFoundError(order_no)
            result.errors.append(f"sale-order: {e}")
            return result

        detail = self._get_data(resp)
        if not detail:
            result.errors.append("订单详情为空")
            return result

        result.success = True
        result.data = {
            "order_identity": self._extract_identity(detail),
            "source_info": self._extract_source(detail),
            "order_context": self._extract_context(detail),
            "current_status": self._extract_status(detail),
            "product_info": self._extract_products(detail),
            "shipping_address": self._extract_address(detail),
            "raw_detail": detail,
        }
        return result

    @staticmethod
    def _extract_identity(d: dict) -> OrderIdentity:
        return OrderIdentity(
            order_no=d.get("orderNo"),
            customer_order_no=d.get("referenceNo"),
            external_order_no=d.get("channelSalesOrderNo"),
            merchant_no=d.get("merchantNo"),
        )

    @staticmethod
    def _extract_source(d: dict) -> SourceInfo:
        return SourceInfo(
            order_source=d.get("dataChannel"),
            channel_no=d.get("channelCode"),
            channel_name=d.get("channelName") or d.get("dataChannel"),
            store_no=None,
            store_name=None,
            platform_order_no=d.get("channelSalesOrderNo"),
        )

    @staticmethod
    def _extract_context(d: dict) -> OrderCtx:
        return OrderCtx(
            order_type=d.get("orderType"),
            order_type_tags=d.get("orderTypeTags"),
            related_order_no=d.get("purchaseOrderNo"),
        )

    @staticmethod
    def _extract_status(d: dict) -> CurrentStatus:
        raw_status = d.get("status")
        return CurrentStatus(
            status_code=raw_status,
            status_name=str(raw_status) if raw_status is not None else None,
            main_status=None,
            fulfillment_status=d.get("fulfillmentStatus"),
            warehouse_process_status=d.get("warehouseProcessStatus"),
        )

    @staticmethod
    def _extract_products(d: dict) -> ProductInfo | None:
        items_raw = d.get("itemLines") or d.get("items") or d.get("orderItems") or []
        if not items_raw:
            return None
        items = [
            ProductItem(
                sku=item.get("sku", ""),
                product_name=item.get("title") or item.get("itemDescription"),
                quantity=item.get("qty", 0) or item.get("quantity", 0),
                description=item.get("itemDescription") or item.get("title"),
                weight=item.get("weight"),
                dimensions=_build_dimensions(item),
                tags=None,
            )
            for item in items_raw
        ]
        return ProductInfo(
            items=items,
            product_summary=f"共 {len(items)} 个 SKU，{sum(i.quantity for i in items)} 件",
        )

    @staticmethod
    def _extract_address(d: dict) -> ShippingAddress | None:
        addr = d.get("shipToAddress")
        if not addr:
            return None
        return ShippingAddress(
            country=addr.get("country"),
            state=addr.get("state"),
            city=addr.get("city"),
            zipcode=addr.get("zipCode") or addr.get("zipcode"),
            address1=addr.get("address1"),
        )


def _build_dimensions(item: dict) -> str | None:
    l = item.get("length")
    w = item.get("width")
    h = item.get("height")
    if l and w and h:
        uom = item.get("linearUom", "")
        return f"{l}×{w}×{h} {uom}".strip()
    return None
