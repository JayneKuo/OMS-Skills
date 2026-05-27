from __future__ import annotations


class ProductOptimizationEngine:
    def optimize(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
        filters = filters or {}
        context = context or {}
        if intent == "product_creation_brief":
            return self._product_creation_brief(identifier, filters)

        return {
            "success": True,
            "summary": "当前 product_optimization MVP 仅支持 product_creation_brief。",
            "reason": "第一版先支持弱输入商品创建资料生成。",
            "evidences": [],
            "confidence": "low",
            "data_completeness": "insufficient",
            "severity": None,
            "recommendations": [],
            "metrics": {},
            "details": {"supported_intents": ["product_creation_brief"]},
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": ["unsupported_intent"],
        }

    def _product_creation_brief(self, identifier, filters):
        seed = str(identifier or filters.get("keyword") or "").strip().lower()
        target_channel = filters.get("target_channel") or filters.get("channel_code") or "ShopifyV3"
        sku_suffix = filters.get("sku_suffix") or "TEST"
        if seed not in {"tennis", "网球"}:
            return {
                "success": True,
                "summary": f"已基于 {identifier} 生成通用测试商品创建方案。",
                "reason": "用户输入较弱，当前只做可测试的商品资料补全，不声明市场验证结论。",
                "evidences": [],
                "confidence": "low",
                "data_completeness": "estimated",
                "severity": None,
                "recommendations": [{
                    "action": "review_generated_product_brief",
                    "precondition": "确认商品类目、价格、图片和渠道配置",
                    "risk": "弱输入生成的商品资料可能不符合真实经营目标",
                    "priority": "high",
                    "expected_effect": "确认后可进入 OMS 测试商品创建",
                }],
                "metrics": {"variant_count": 1, "target_channel_count": 1},
                "details": {
                    "creation_brief": self._tennis_brief(target_channel, sku_suffix),
                    "assumptions": [f"用户只提供 {identifier}，商品资料为测试用估算方案。"],
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }

        return {
            "success": True,
            "summary": "已基于 tennis 场景生成 ShopifyV3 测试商品创建方案。",
            "reason": "用户只提供弱输入，先生成一个网球训练套装测试商品，用于验证 OMS 到 ShopifyV3 的创建链路。",
            "evidences": [],
            "confidence": "medium",
            "data_completeness": "estimated",
            "severity": None,
            "recommendations": [{
                "action": "create_test_product_after_confirmation",
                "precondition": "确认允许在 staging 创建新的测试 SKU 和渠道商品",
                "risk": "会在 OMS/ShopifyV3 测试环境产生真实测试数据",
                "priority": "high",
                "expected_effect": "验证弱输入到商品创建的完整链路",
            }],
            "metrics": {"variant_count": 1, "target_channel_count": 1},
            "details": {
                "creation_brief": self._tennis_brief(target_channel, sku_suffix),
                "assumptions": [
                    "用户只提供 tennis，商品资料为测试用估算方案。",
                    "没有外部市场、竞品、关键词搜索量或转化数据，不能作为确定性市场结论。",
                    "Shopify 在当前业务语境中默认指 OMS ShopifyV3 渠道。",
                ],
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": [],
        }

    def _tennis_brief(self, target_channel, sku_suffix="TEST"):
        parent_sku = f"TENNIS-AI-{sku_suffix}"
        return {
            "product": {
                "parentSku": parent_sku,
                "name": "AI Test ProSpin Tennis Training Set",
                "brand": "CourtLab",
                "model": "ProSpin Starter",
                "categoryName": "Tennis Training Equipment",
                "description": "A test tennis training set for validating OMS to ShopifyV3 product creation workflows.",
                "price": 49.99,
                "keywords": ["tennis", "training", "practice", "sports"],
                "variants": [{
                    "sellerSku": parent_sku,
                    "price": 49.99,
                    "salesPriceUnit": "USD",
                    "inventory": 20,
                    "weight": 1.2,
                    "weightUnit": "KG",
                    "length": 35,
                    "width": 25,
                    "height": 8,
                    "dimensionUnit": "CM",
                    "salesAttributeValues": [
                        {"attributeName": "Package", "attributeValue": "Standard"}
                    ],
                }],
            },
            "channels": [{"channel": target_channel}],
        }
