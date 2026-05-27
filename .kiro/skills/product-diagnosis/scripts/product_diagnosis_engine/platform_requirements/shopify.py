from __future__ import annotations


def _issue(code: str, message: str, source: str, field: str | None = None) -> dict:
    result = {"code": code, "message": message, "source": source}
    if field:
        result["field"] = field
    return result


def _checklist_item(item: str, status: str, evidence: str, issue_code: str | None = None) -> dict:
    result = {"item": item, "status": status, "evidence": evidence}
    if issue_code:
        result["issue_code"] = issue_code
    return result


def _option_names(product: dict) -> set[str]:
    options = product.get("options") or product.get("salesAttributes") or product.get("sales_attributes") or []
    return {option.get("name") or option.get("attributeName") for option in options if option.get("name") or option.get("attributeName")}


def _sku_option_names(sku: dict) -> set[str]:
    values = sku.get("option_values") or sku.get("optionValues") or sku.get("salesAttributeValues") or []
    return {value.get("name") or value.get("attributeName") for value in values if value.get("name") or value.get("attributeName")}


def evaluate_shopify_readiness(product: dict, skus: list[dict], channel_summary: list[dict], channel_code: str | None = None) -> dict:
    issues = []
    has_title = bool(product.get("title"))
    has_variants = bool(skus)
    has_variant_sku = all(sku.get("seller_sku") or sku.get("sku") for sku in skus) if skus else True
    has_variant_price = all(sku.get("price") not in (None, "") for sku in skus) if skus else True
    has_variant_currency = all(bool(sku.get("currency")) for sku in skus) if skus else True
    needs_options = len(skus) > 1
    option_names = _option_names(product)
    has_product_options = bool(option_names)
    has_variant_option_values = all(_sku_option_names(sku) == option_names for sku in skus) if skus else True
    has_options = has_product_options and has_variant_option_values
    has_media = (product.get("image_count") or 0) > 0 or bool(product.get("imageInfo"))
    has_unsupported_shopifyv3_error = False

    if not has_title:
        issues.append(_issue("missing_product_title", "Shopify 商品发布需要商品标题。", "shopify_admin_graphql_api", "title"))

    if not has_variants:
        issues.append(_issue("missing_variant", "Shopify 商品至少需要一个 variant。", "shopify_admin_graphql_api", "variants"))
    if not has_variant_sku:
        issues.append(_issue("missing_variant_sku", "Shopify variant 需要可追踪的 SKU。", "shopify_admin_graphql_api", "variants.sku"))
    if not has_variant_price:
        issues.append(_issue("missing_variant_price", "Shopify variant 需要价格。", "shopify_admin_graphql_api", "variants.price"))
    if not has_variant_currency:
        issues.append(_issue("missing_variant_currency", "OMS 到 Shopify 发布前需要明确价格币种。", "shopify_admin_graphql_api", "variants.currency"))

    if needs_options and not has_options:
        issues.append(_issue(
            "missing_variant_options",
            "多 variant 商品使用 Shopify productSet/productVariantsBulkCreate 时需要 options 和每个 variant 的 option values。",
            "shopify_admin_graphql_api",
            "options",
        ))

    if not has_media:
        issues.append(_issue("missing_product_media", "Shopify 商品建议提供 media/image，避免发布后商品无图。", "shopify_admin_graphql_api", "media"))

    if str(channel_code or "").lower() == "shopifyv3":
        for summary in channel_summary:
            errors = summary.get("errors") or []
            if any("Unsupported channel type" in error for error in errors):
                has_unsupported_shopifyv3_error = True
                issues.append(_issue(
                    "unsupported_oms_shopify_channel_type",
                    "当前 OMS 发布错误显示 ShopifyV3 不被发布服务支持，应确认是否使用 SHOPIFY channel type。",
                    "oms_publish_error",
                    "channel_code",
                ))
                break

    checklist = [
        _checklist_item("商品标题", "ready", str(product.get("title")))
        if has_title else _checklist_item("商品标题", "blocked", "缺少 Shopify 商品标题", "missing_product_title"),
        _checklist_item("Variant", "ready", f"{len(skus)} 个 variant 可用")
        if has_variants else _checklist_item("Variant", "blocked", "缺少 Shopify variant", "missing_variant"),
        _checklist_item("Variant SKU", "ready", "variant SKU 已提供")
        if has_variant_sku else _checklist_item("Variant SKU", "blocked", "缺少可追踪的 variant SKU", "missing_variant_sku"),
        _checklist_item("Variant 价格", "ready", "variant 价格已提供")
        if has_variant_price else _checklist_item("Variant 价格", "blocked", "缺少 variant 价格", "missing_variant_price"),
        _checklist_item("Variant 币种", "ready", "variant 币种已提供")
        if has_variant_currency else _checklist_item("Variant 币种", "blocked", "缺少 variant 币种", "missing_variant_currency"),
    ]
    if needs_options:
        checklist.append(
            _checklist_item("Variant Options", "ready", "多 variant options 已提供")
            if has_options else _checklist_item("Variant Options", "blocked", "缺少多 variant options", "missing_variant_options")
        )
    checklist.extend([
        _checklist_item("商品图片", "ready", "商品 media/image 已提供")
        if has_media else _checklist_item("商品图片", "blocked", "缺少商品 media/image", "missing_product_media"),
        _checklist_item("OMS Shopify 渠道类型", "blocked", "ShopifyV3 不被当前 OMS 发布服务支持", "unsupported_oms_shopify_channel_type")
        if has_unsupported_shopifyv3_error else _checklist_item("OMS Shopify 渠道类型", "ready", "SHOPIFY 可用于当前发布服务"),
    ])

    return {
        "ready_to_publish": not issues,
        "blocking_issues": issues,
        "readiness_checklist": checklist,
    }
