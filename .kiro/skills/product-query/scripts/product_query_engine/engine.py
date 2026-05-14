from __future__ import annotations


def _extract_skus(product: dict | None, fallback_sku: str | None) -> list[dict]:
    if product:
        raw = product.get("raw") or {}
        for key in ("skuList", "skus", "sku_list"):
            value = raw.get(key)
            if isinstance(value, list) and value:
                return value
    return [{"sku": fallback_sku}] if fallback_sku else []


class ProductQueryEngine:
    def __init__(self, inventory_adapter=None, product_adapter=None, channel_product_adapter=None):
        self._inventory_adapter = inventory_adapter
        self._product_adapter = product_adapter
        self._channel_product_adapter = channel_product_adapter

    def query(self, identifier=None, merchant_no=None, intent=None, filters=None):
        filters = filters or {}
        resolved_sku = filters.get("sku") or identifier
        product = None
        errors = ["渠道商品 API 尚未接入"]

        if self._product_adapter and intent in ("overview", "sku_detail", "spu_detail", None):
            try:
                product_filters = dict(filters)
                if resolved_sku and not product_filters.get("sku") and not product_filters.get("product_id"):
                    product_filters["sku"] = resolved_sku
                product = self._product_adapter.find_product(merchant_no, product_filters)
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
            if filters.get(key):
                performance_query[key] = filters[key]

        channel_products = []
        if self._channel_product_adapter and intent in ("overview", "channel_listing", "mapping", "listing_status", "audit_status", None):
            try:
                channel_filters = dict(filters)
                if resolved_sku and not channel_filters.get("sku"):
                    channel_filters["sku"] = resolved_sku
                channel_products = self._channel_product_adapter.list_channel_products(merchant_no, channel_filters)
            except Exception as e:
                errors.append(f"渠道商品 API 查询失败: {e}")

        publish_history = []
        if self._channel_product_adapter and intent in ("overview", "channel_listing", "listing_status", "audit_status", None):
            try:
                history_filters = dict(filters)
                if resolved_sku and not history_filters.get("sku"):
                    history_filters["sku"] = resolved_sku
                publish_history = self._channel_product_adapter.list_publish_history(merchant_no, history_filters)
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
        confidence = "high" if product else ("medium" if resolved_sku else "low")
        data_completeness = "partial" if (product or resolved_sku) else "insufficient"
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

        return {
            "success": True,
            "summary": f"已确认 {resolved_sku or product_detail.get('spu') or product_detail.get('product_id')} 可用于商品表现分析。" if (resolved_sku or product_detail) else "已生成商品表现分析查询条件。",
            "reason": "返回已确认的商品主档、SKU、库存和表现分析过滤条件；渠道商品 API 尚未接入。",
            "evidences": [],
            "confidence": confidence,
            "data_completeness": data_completeness,
            "severity": None,
            "recommendations": [],
            "metrics": metrics,
            "details": {
                "product": product_detail,
                "skus": skus,
                "channel_products": channel_products,
                "publish_history": publish_history,
                "mapping": [],
                "missing_fields": [],
                "performance_query": performance_query,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": errors,
        }
