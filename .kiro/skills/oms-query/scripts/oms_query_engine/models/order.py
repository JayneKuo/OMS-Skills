"""订单域输出模型"""
from __future__ import annotations
from pydantic import BaseModel


class OrderIdentity(BaseModel):
    order_no: str | None = None
    customer_order_no: str | None = None
    external_order_no: str | None = None
    merchant_no: str | None = None


class SourceInfo(BaseModel):
    order_source: str | None = None
    channel_no: str | None = None
    channel_name: str | None = None
    store_no: str | None = None
    store_name: str | None = None
    platform_order_no: str | None = None


class OrderContext(BaseModel):
    order_type: str | None = None
    order_type_tags: list[str] | None = None
    related_order_no: str | None = None


class CurrentStatus(BaseModel):
    status_code: int | str | None = None
    status_name: str | None = None
    status_category: str | None = None
    main_status: str | None = None
    fulfillment_status: str | None = None
    shipment_status: str | None = None
    warehouse_process_status: str | None = None
    is_exception: bool | None = None
    is_hold: bool | None = None
    is_deallocated: bool | None = None
    hold_reason: str | None = None
    exception_reason: str | None = None
    deallocated_reason: str | None = None


class ProductItem(BaseModel):
    sku: str
    product_name: str | None = None
    quantity: int = 0
    description: str | None = None
    weight: float | None = None
    dimensions: str | None = None
    tags: list[str] | None = None


class ProductInfo(BaseModel):
    items: list[ProductItem] | None = None
    product_summary: str | None = None


class ShippingAddress(BaseModel):
    country: str | None = None
    state: str | None = None
    city: str | None = None
    zipcode: str | None = None
    address1: str | None = None
