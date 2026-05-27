from __future__ import annotations


def _extract_skus(product: dict | None, fallback_sku: str | None) -> list[dict]:
    if product:
        normalized_skus = product.get("skus")
        if isinstance(normalized_skus, list) and normalized_skus:
            return normalized_skus
        raw = product.get("raw") or {}
        for key in ("childSkus", "skuList", "skus", "sku_list"):
            value = raw.get(key)
            if isinstance(value, list) and value:
                return value
    return [{"sku": fallback_sku}] if fallback_sku else []


def _unique_sorted(values: list) -> list:
    return sorted({value for value in values if value not in (None, "")})


def _channel_summary(channel_products: list[dict], publish_history: list[dict] | None = None) -> list[dict]:
    grouped = {}

    def ensure_group(channel_code, channel_no=None):
        key = (channel_code or "UNKNOWN", channel_no)
        if key not in grouped:
            grouped[key] = {
                "channel_code": key[0],
                "channel_no": channel_no,
                "channel_product_count": 0,
                "publish_history_count": 0,
                "audit_statuses": [],
                "listing_statuses": [],
                "publish_success_count": 0,
                "publish_failure_count": 0,
                "errors": [],
            }
        return grouped[key]

    for product in channel_products:
        item = ensure_group(product.get("channel_code"), product.get("channel_no"))
        item["channel_product_count"] += 1
        item["audit_statuses"].append(product.get("audit_status"))
        item["listing_statuses"].append(product.get("listing_status"))
        if product.get("publish_success") is True:
            item["publish_success_count"] += 1
        elif product.get("publish_success") is False:
            item["publish_failure_count"] += 1
        if product.get("last_error"):
            item["errors"].append(product["last_error"])
        item["errors"].extend(product.get("validation_errors") or [])

    for history in publish_history or []:
        channel_code = history.get("channel_code") or history.get("channel")
        matching_keys = [key for key in grouped if key[0] == (channel_code or "UNKNOWN")]
        item = grouped[matching_keys[0]] if matching_keys else ensure_group(channel_code)
        item["publish_history_count"] += 1
        item["audit_statuses"].append(history.get("audit_status"))
        item["listing_statuses"].append(history.get("listing_status"))
        status = str(history.get("status") or "").lower()
        if status in {"success", "succeeded", "published", "listed"}:
            item["publish_success_count"] += 1
        elif status in {"failed", "fail", "rejected", "error"} or history.get("error_message"):
            item["publish_failure_count"] += 1
        if history.get("error_message"):
            item["errors"].append(history["error_message"])

    summaries = []
    for item in grouped.values():
        item["audit_statuses"] = _unique_sorted(item["audit_statuses"])
        item["listing_statuses"] = _unique_sorted(item["listing_statuses"])
        item["errors"] = _unique_sorted(item["errors"])
        summaries.append(item)
    return sorted(summaries, key=lambda item: item["channel_code"])


def _normalize_lookup_filters(identifier, filters: dict) -> tuple[dict, str | None]:
    normalized = {key: value for key, value in (filters or {}).items() if key != "match_hint"}
    if not identifier:
        return normalized, normalized.get("sku")

    match_hint = (filters or {}).get("match_hint")
    if match_hint == "seller_parent_sku":
        normalized.setdefault("seller_parent_sku", identifier)
        return normalized, None
    if match_hint == "internal_item_id":
        normalized.setdefault("internal_item_id", identifier)
        return normalized, None
    if match_hint == "internal_sku_id":
        normalized.setdefault("internal_sku_id", identifier)
        return normalized, identifier
    if match_hint == "item_name":
        normalized.setdefault("item_name", identifier)
        return normalized, None
    if match_hint == "skc":
        normalized.setdefault("skc", identifier)
        return normalized, None

    if any(token in identifier for token in (" ", "-")) and not identifier.upper().startswith(("SKU", "SPU", "SKC", "ITEM")):
        normalized.setdefault("item_name", identifier)
        return normalized, None

    normalized.setdefault("sku", identifier)
    return normalized, normalized.get("sku")


class ProductQueryEngine:
    def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
        self._inventory_adapter = inventory_adapter
        self._product_adapter = product_adapter
        self._channel_product_adapter = channel_product_adapter

    def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
        filters = filters or {}
        normalized_filters, resolved_sku = _normalize_lookup_filters(identifier, filters)
        product = None
        products = []
        pagination = {}
        errors = []

        is_list_query = bool(normalized_filters.get("keyword")) and not any(
            normalized_filters.get(key)
            for key in ("sku", "spu", "product_id", "internal_item_id", "internal_sku_id", "seller_parent_sku")
        )
        if self._product_adapter and intent in ("overview", "sku_detail", "spu_detail", None):
            try:
                if is_list_query and hasattr(self._product_adapter, "search_products"):
                    search_result = self._product_adapter.search_products(merchant_no, normalized_filters)
                    products = search_result.get("products") or []
                    pagination = search_result.get("pagination") or {}
                else:
                    product = self._product_adapter.find_product(merchant_no, normalized_filters)
            except Exception as e:
                errors.append(f"商品 API 查询失败: {e}")

        performance_query = {}
        if resolved_sku:
            performance_query["sku"] = resolved_sku
        if product:
            if product.get("spu"):
                performance_query["spu"] = product["spu"]
            if product.get("product_id"):
                performance_query["product_id"] = product["product_id"]
        for key in ("channel_code", "shop_id"):
            if normalized_filters.get(key):
                performance_query[key] = normalized_filters[key]

        channel_products = []
        if self._channel_product_adapter and intent in ("overview", "channel_listing", "mapping", "listing_status", "audit_status", None):
            try:
                channel_products = self._channel_product_adapter.list_channel_products(merchant_no, normalized_filters)
            except Exception as e:
                errors.append(f"渠道商品 API 查询失败: {e}")

        publish_history = []
        if self._channel_product_adapter and intent in ("overview", "channel_listing", "listing_status", "audit_status", None):
            try:
                publish_history = self._channel_product_adapter.list_publish_history(merchant_no, normalized_filters)
            except Exception as e:
                errors.append(f"发布历史 API 查询失败: {e}")

        sku_fact = None
        if self._inventory_adapter and resolved_sku and (intent in ("inventory_price", "overview", None)):
            try:
                sku_fact = self._inventory_adapter.fetch_sku_facts(merchant_no, resolved_sku)
            except Exception as e:
                errors.append(f"库存 API 查询失败: {e}")

        product_detail = product or ({"sku": resolved_sku} if resolved_sku else {})
        skus = _extract_skus(product, resolved_sku)
        if sku_fact and sku_fact.get("inventory_records", 0) > 0:
            skus = [dict(skus[0], **sku_fact)] if skus else [sku_fact]

        metrics = {}
        confidence = "high" if product else ("medium" if (resolved_sku or normalized_filters.get("item_name") or normalized_filters.get("seller_parent_sku") or normalized_filters.get("internal_item_id") or normalized_filters.get("skc")) else "low")
        data_completeness = "partial" if (product or resolved_sku or normalized_filters) else "insufficient"
        if sku_fact and sku_fact.get("inventory_records", 0) > 0:
            metrics = {
                "sku_count": len(skus),
                "available_qty": sku_fact.get("available_qty", 0),
                "on_hand_qty": sku_fact.get("on_hand_qty", 0),
            }
            confidence = "high"
        if channel_products:
            metrics["channel_product_count"] = len(channel_products)
            confidence = "high"
        if publish_history:
            metrics["publish_history_count"] = len(publish_history)
            confidence = "high"
        channel_summary = _channel_summary(channel_products, publish_history)
        if channel_summary:
            metrics["channel_count"] = len(channel_summary)
        if products:
            metrics["product_count"] = len(products)
            if pagination.get("total") is not None:
                metrics["product_total"] = pagination["total"]
            confidence = "high"

        resolution = {
            "found_in_oms_product": bool(product),
            "found_in_product_list": bool(products),
            "found_in_channel_product": bool(channel_products),
            "found_in_publish_history": bool(publish_history),
            "best_match_type": None,
            "identifier_type": None,
        }
        if product:
            resolution["best_match_type"] = "oms_product"
        elif products:
            resolution["best_match_type"] = "product_list"
        elif channel_products:
            resolution["best_match_type"] = "channel_product"
        elif publish_history:
            resolution["best_match_type"] = "publish_history"

        for key in ("sku", "seller_parent_sku", "internal_item_id", "internal_sku_id", "item_name", "skc", "keyword"):
            if normalized_filters.get(key):
                resolution["identifier_type"] = key
                break

        resolved_subject = (
            resolved_sku
            or product_detail.get("title")
            or product_detail.get("spu")
            or product_detail.get("product_id")
            or normalized_filters.get("item_name")
            or normalized_filters.get("seller_parent_sku")
            or normalized_filters.get("internal_item_id")
            or normalized_filters.get("skc")
        )

        summary = "已生成商品查询结果。"
        if products:
            total = pagination.get("total", len(products))
            summary = f"找到 {total} 个匹配商品，当前返回 {len(products)} 个。"
        elif not product and channel_products:
            summary = f"未找到 OMS 商品主档，但找到 {len(channel_products)} 个渠道商品。"
        elif resolved_subject:
            if intent == "identity_for_performance":
                summary = f"已确认 {resolved_subject} 可用于商品表现分析。"
            else:
                summary = f"已确认 {resolved_subject} 的商品查询结果。"

        return {
            "success": True,
            "summary": summary,
            "reason": "返回已确认的商品主档、SKU、库存和可继续用于渠道查询或发布的结构化结果。",
            "evidences": [],
            "confidence": confidence,
            "data_completeness": data_completeness,
            "severity": None,
            "recommendations": [],
            "metrics": metrics,
            "details": {
                "product": product_detail,
                "products": products,
                "pagination": pagination,
                "skus": skus,
                "channel_products": channel_products,
                "channel_summary": channel_summary,
                "publish_history": publish_history,
                "mapping": product_detail.get("mapping", []) if isinstance(product_detail, dict) else [],
                "missing_fields": [],
                "performance_query": performance_query,
                "resolution": resolution,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": errors,
        }
