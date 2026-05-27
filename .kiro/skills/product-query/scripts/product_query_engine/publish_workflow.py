from __future__ import annotations


def _build_sales_attributes(variants: list[dict]) -> list[dict]:
    attribute_map: dict[str, dict] = {}

    for variant in variants:
        sales_attribute_values = variant.get("salesAttributeValues") or []
        if not sales_attribute_values:
            grip_size = variant.get("gripSize")
            if grip_size:
                sales_attribute_values = [{"attributeName": "Grip Size", "attributeValue": grip_size}]

        for attr_value in sales_attribute_values:
            attr_name = attr_value.get("attributeName")
            attr_actual_value = attr_value.get("attributeValue")
            if not attr_name or attr_actual_value in (None, ""):
                continue

            if attr_name not in attribute_map:
                attribute_map[attr_name] = {
                    "attributeId": attr_value.get("attributeId"),
                    "attributeChannelId": attr_value.get("attributeChannelId"),
                    "channel": "OMS",
                    "productTypeId": None,
                    "attributeName": attr_name,
                    "attributeIsShow": True,
                    "attributeType": 1,
                    "attributeLabel": 0,
                    "attributeValues": [],
                }

            existing_values = attribute_map[attr_name]["attributeValues"]
            if any(value["attributeValue"] == attr_actual_value for value in existing_values):
                continue

            existing_values.append({
                "attributeValueId": attr_value.get("attributeValueId"),
                "attributeChannelValueId": attr_value.get("attributeChannelValueId"),
                "channel": "OMS",
                "attributeValue": attr_actual_value,
                "isShow": True,
                "isCustomAttributeValue": False,
                "customValue": None,
            })

    rebuilt_sales_attributes = list(attribute_map.values())
    if rebuilt_sales_attributes:
        rebuilt_sales_attributes[0]["attributeLabel"] = 1
    return rebuilt_sales_attributes


def _build_product_create_payload(merchant_no: str, request: dict) -> dict:
    product = request.get("product") or {}
    variants = product.get("variants") or []
    default_price = product.get("price")
    sku_info_list = []
    for variant in variants:
        sales_price = variant.get("price", default_price)
        if sales_price is None:
            raise ValueError("missing_variant_price")

        sales_attribute_values = variant.get("salesAttributeValues")
        if sales_attribute_values is None:
            sales_attribute_values = []
            grip_size = variant.get("gripSize")
            if grip_size:
                sales_attribute_values.append({
                    "attributeName": "Grip Size",
                    "attributeValue": grip_size,
                })

        sku_info_list.append({
            "sellerSku": variant["sellerSku"],
            "merchantNo": merchant_no,
            "source": "MANUAL",
            "status": variant.get("status", "ACTIVE"),
            "salesPrice": sales_price,
            "salesPriceUnit": variant.get("salesPriceUnit", "USD"),
            "discountPrice": variant.get("discountPrice"),
            "discountPriceUnit": variant.get("discountPriceUnit", variant.get("salesPriceUnit", "USD")),
            "inventory": variant.get("inventory", 0),
            "inventoryUnit": variant.get("inventoryUnit", "EA"),
            "weight": variant.get("weight", 0),
            "weightUnit": variant.get("weightUnit", "KG"),
            "length": variant.get("length", 0),
            "width": variant.get("width", 0),
            "height": variant.get("height", 0),
            "dimensionUnit": variant.get("dimensionUnit", "CM"),
            "imageInfo": variant.get("imageInfo"),
            "salesAttributeValues": sales_attribute_values,
        })

    if not sku_info_list:
        raise ValueError("missing_variants")

    return {
        "spuInfo": {
            "sellerParentSku": product.get("parentSku") or variants[0]["sellerSku"],
            "merchantNo": merchant_no,
            "itemName": product["name"],
            "source": "MANUAL",
            "itemType": product.get("itemType") or ("VARIANTS" if len(sku_info_list) > 1 else "SINGLE"),
            "productType": product.get("productType", "PHYSICAL_PRODUCT"),
            "status": product.get("status", "ACTIVE"),
            "description": product.get("description", ""),
            "brandId": product.get("brandId"),
            "brandName": product.get("brand"),
            "categoryId": product.get("categoryId"),
            "categoryName": product.get("categoryName"),
            "channelCategory": product.get("channelCategory", []),
            "internalItemId": product.get("internalItemId"),
            "siteList": product.get("siteList"),
            "imageInfo": product.get("imageInfo"),
            "uom": product.get("uom"),
            "barcode": product.get("barcode"),
            "keywords": product.get("keywords") or [value for value in [product.get("brand"), product.get("model"), product.get("categoryName")] if value],
        },
        "skuInfoList": sku_info_list,
        "productAttributes": product.get("productAttributes", []),
        "salesAttributes": _build_sales_attributes(variants),
        "sizeAttributeList": product.get("sizeAttributeList", []),
        "bundleComponentList": product.get("bundleComponentList", []),
    }


class ChannelProductCreateWorkflow:
    def __init__(self, client):
        self._client = client

    def create(self, request: dict | None = None) -> dict:
        request = request or {}
        merchant_no = request.get("merchantNo") or request.get("merchant_no")
        channel_product_create_response = None

        try:
            if not merchant_no:
                raise ValueError("missing_merchant_no")
            if not request.get("internalProducts"):
                raise ValueError("missing_internal_products")

            self._client._ensure_token()
            channel_product_create_response = self._client.post(
                "/api/linker-oms/opc/rpc-api/channel-product/create",
                request,
            )

            response_code = channel_product_create_response.get("code") if isinstance(channel_product_create_response, dict) else None
            if response_code not in (None, 0, 200, "0", "200"):
                response_message = None
                if isinstance(channel_product_create_response, dict):
                    response_message = channel_product_create_response.get("msg") or channel_product_create_response.get("message")
                return {
                    "success": False,
                    "error": "channel_product_create_failed",
                    "message": response_message or "channel_product_create_failed",
                    "details": {
                        "upstream_error": True,
                        "channel_product_create_response": channel_product_create_response,
                    },
                }

            return {
                "success": True,
                "summary": "已创建渠道商品。",
                "details": {
                    "channel_product_create_response": channel_product_create_response,
                },
            }
        except ValueError as e:
            return {"success": False, "error": str(e), "message": str(e)}


class ProductPublishWorkflow:
    def __init__(self, client):
        self._client = client

    def publish(self, merchant_no: str, request: dict | None = None) -> dict:
        request = request or {}
        created_product_response = None
        created_product = {}

        try:
            channels = request.get("channels") or []
            if not channels:
                raise ValueError("missing_channels")

            self._client._ensure_token()

            product_payload = _build_product_create_payload(merchant_no, request)
            created_product_response = self._client.post(
                "/api/linker-oms/baseservice/rpc-api/product/spu/create-complete",
                product_payload,
            )
            created_product = created_product_response.get("data")
            if not isinstance(created_product, dict):
                created_product = created_product_response if isinstance(created_product_response, dict) else {}

            response_code = created_product_response.get("code") if isinstance(created_product_response, dict) else None
            if response_code not in (None, 0, 200, "0", "200"):
                response_message = None
                if isinstance(created_product_response, dict):
                    response_message = created_product_response.get("msg") or created_product_response.get("message")
                return {
                    "success": False,
                    "error": "product_create_failed",
                    "message": response_message or "product_create_failed",
                    "details": {
                        "upstream_error": True,
                        "created_product": created_product,
                        "created_product_response": created_product_response,
                    },
                }

            spu_id = ((created_product.get("spuInfo") or {}).get("id"))
            sku_info_list = created_product.get("skuInfoList") or []
            internal_sku_ids = [sku.get("internalSkuId") for sku in sku_info_list if sku.get("internalSkuId")]
            if not spu_id:
                raise ValueError("missing_spu_id")

            channel_payload = {
                "merchantNo": merchant_no,
                "internalProducts": [{
                    "spuId": spu_id,
                    "channels": channels,
                    "internalSkuIds": internal_sku_ids,
                }],
            }
            channel_sync_response = self._client.post(
                "/api/linker-oms/baseservice/rpc-api/channel-product/create-from-spu",
                channel_payload,
            )

            return {
                "success": True,
                "summary": "已创建 OMS 商品并同步到渠道商品库。",
                "details": {
                    "created_product": created_product,
                    "channel_sync": channel_sync_response,
                },
            }
        except KeyError as e:
            return {"success": False, "error": "missing_required_field", "message": str(e)}
        except ValueError as e:
            response = {"success": False, "error": str(e), "message": str(e)}
            if str(e) == "missing_spu_id":
                response["details"] = {
                    "created_product": created_product,
                    "created_product_response": created_product_response,
                }
            return response
