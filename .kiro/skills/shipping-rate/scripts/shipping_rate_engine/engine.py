"""Shipping Rate Engine — 顶层编排器

通用映射规则引擎，三种模式：
1. query    — 查询三层映射规则配置
2. execute  — 执行映射规则匹配
3. recommend — 链式推荐：Layer1 → Layer2 → Layer3，逐层丰富上下文

引擎不绑定具体的比价/承运商 API。recommend 的结果可以作为
下游 Rate Shopping / 第三方承运商 API 的输入。
"""

from __future__ import annotations

from typing import Any

from .data_loader import DataLoader, CONDITION_TYPE_MAP, OUTPUT_TYPE_MAP
from .models import (
    MappingQueryRequest,
    MappingQueryResult,
    MappingExecuteRequest,
    MappingExecuteResult,
    ConditionMappingResult,
    ShippingMappingResult,
    RecommendRequest,
    RecommendResult,
    CarrierRecommendation,
)


class ShippingRateEngine:
    """运费映射与承运商推荐引擎。"""

    def __init__(self, data_loader: DataLoader | None = None):
        self._loader = data_loader or DataLoader()
        self._rate_engine = None  # 延迟初始化

    def _get_rate_engine(self):
        """延迟初始化 RateEngine"""
        if self._rate_engine is None:
            from .rate_engine import RateEngine
            self._rate_engine = RateEngine()
        return self._rate_engine

    # ══════════════════════════════════════════════════
    # 模式 4: 运费计算
    # ══════════════════════════════════════════════════

    def calculate_rate(self, request) -> Any:
        """运费计算主入口（代理到 RateEngine）"""
        return self._get_rate_engine().calculate_rate(request)

    def calculate_rate_multi(self, request, recommendations: list) -> list:
        """为多个承运商推荐分别计算运费"""
        return self._get_rate_engine().calculate_rate_multi(request, recommendations)

    # ══════════════════════════════════════════════════
    # 模式 1: 查询映射规则
    # ══════════════════════════════════════════════════

    def query(self, request: MappingQueryRequest) -> MappingQueryResult:
        result = MappingQueryResult()
        summary: dict[str, int] = {}

        try:
            mappings = self._loader.load_one_to_one_mappings(
                merchant_no=request.merchant_no,
                mapping_types=request.mapping_types,
                channel_no=request.channel_no,
            )
            result.one_to_one_mappings = mappings
            summary["one_to_one_mappings"] = len(mappings)
        except Exception as e:
            result.errors.append(f"一对一映射查询失败: {e}")

        if request.include_condition_mappings:
            try:
                cond_mappings = self._loader.load_condition_mappings(
                    merchant_no=request.merchant_no,
                    mapping_key=request.channel_no,
                )
                result.condition_mappings = cond_mappings
                summary["condition_mappings"] = len(cond_mappings)
            except Exception as e:
                result.errors.append(f"条件映射查询失败: {e}")

        if request.include_shipping_rules:
            try:
                rules = self._loader.load_shipping_rules(
                    merchant_no=request.merchant_no,
                    channel_no=request.channel_no,
                )
                result.shipping_rules = rules
                summary["shipping_rules"] = len(rules)
            except Exception as e:
                result.errors.append(f"Shipping Mapping 规则查询失败: {e}")

        result.summary = summary
        result.success = len(result.errors) == 0
        return result

    # ══════════════════════════════════════════════════
    # 模式 2: 执行映射规则
    # ══════════════════════════════════════════════════

    def execute(self, request: MappingExecuteRequest) -> MappingExecuteResult:
        result = MappingExecuteResult()
        explanations: list[str] = []

        # 条件映射执行
        has_condition_input = any([
            request.skus, request.carriers, request.ship_methods,
            request.delivery_services, request.freight_terms,
        ])
        if has_condition_input:
            try:
                raw = self._loader.execute_condition_mapping(
                    merchant_no=request.merchant_no,
                    mapping_key=request.mapping_key,
                    skus=request.skus,
                    carriers=request.carriers,
                    ship_methods=request.ship_methods,
                    delivery_services=request.delivery_services,
                    freight_terms=request.freight_terms,
                )
                mapped_data = raw.get("mappedData", {}) if isinstance(raw, dict) else {}
                for key, item in mapped_data.items():
                    if isinstance(item, dict):
                        result.condition_mapping_results.append(
                            ConditionMappingResult(
                                mapping_key=key,
                                delivery_service=item.get("deliveryService"),
                                ship_method=item.get("shipMethod"),
                                carrier=item.get("carrier"),
                                freight_term=item.get("freightTerm"),
                                shipment_type=item.get("shipmentType"),
                            )
                        )
                if result.condition_mapping_results:
                    explanations.append(
                        f"条件映射匹配成功，返回 {len(result.condition_mapping_results)} 组结果"
                    )
                else:
                    explanations.append("条件映射未匹配到结果")
            except Exception as e:
                result.errors.append(f"条件映射执行失败: {e}")

        # Shipping Mapping 执行
        if request.input_conditions and request.channel_no:
            try:
                raw = self._loader.execute_shipping_mapping(
                    channel_no=request.channel_no,
                    merchant_no=request.merchant_no,
                    input_conditions=request.input_conditions,
                )
                outputs = raw if isinstance(raw, dict) else {}
                matched = len(outputs) > 0
                result.shipping_mapping_result = ShippingMappingResult(
                    matched=matched,
                    outputs=outputs,
                    raw_response=outputs,
                )
                if matched:
                    explanations.append(
                        f"Shipping Mapping 匹配成功，输出 {len(outputs)} 个字段"
                    )
                else:
                    explanations.append("Shipping Mapping 未匹配到规则")
            except Exception as e:
                result.errors.append(f"Shipping Mapping 执行失败: {e}")

        result.explanation = "；".join(explanations) if explanations else "无执行操作"
        result.success = len(result.errors) == 0
        return result

    # ══════════════════════════════════════════════════
    # 模式 3: 链式推荐
    # ══════════════════════════════════════════════════

    def recommend(self, request: RecommendRequest) -> RecommendResult:
        """链式推荐：Layer1 → Layer2 → Layer3。

        每一层的输出会作为下一层的输入上下文，逐步丰富推荐信息。
        最终结果可以作为下游 Rate Shopping / 第三方 API 的输入。
        """
        result = RecommendResult()
        context: dict[str, Any] = {}
        recommendations: list[CarrierRecommendation] = []

        skus = [item.get("sku", "") for item in (request.sku_list or []) if item.get("sku")]

        # ── Layer 1: 一对一映射解析 ──────────────────
        # 查找 SKU 对应的承运商/服务映射
        layer1_carrier: str | None = None
        layer1_ship_method: str | None = None
        layer1_delivery_service: str | None = None
        layer1_freight_term: str | None = None

        try:
            # recommend 只查承运商相关类型，不查 SKU/UOM（减少 API 调用）
            carrier_types = ["CARRIER", "SHIP_METHOD", "DELIVERY_SERVICE", "FREIGHT_TERM", "REVERSE_MAPPING_CARRIER"]
            mappings = self._loader.load_one_to_one_mappings(
                merchant_no=request.merchant_no,
                mapping_types=carrier_types,
                channel_no=request.channel_no,
            )
            context["layer1_total"] = len(mappings)

            # 从一对一映射中提取承运商相关信息
            for m in mappings:
                if m.status != 1:
                    continue
                mt = m.mapping_type or ""
                if mt in ("CARRIER", "REVERSE_MAPPING_CARRIER") and not layer1_carrier:
                    layer1_carrier = m.mapped_value
                elif mt == "SHIP_METHOD" and not layer1_ship_method:
                    layer1_ship_method = m.mapped_value
                elif mt == "DELIVERY_SERVICE" and not layer1_delivery_service:
                    layer1_delivery_service = m.mapped_value
                elif mt == "FREIGHT_TERM" and not layer1_freight_term:
                    layer1_freight_term = m.mapped_value

            if any([layer1_carrier, layer1_ship_method, layer1_delivery_service]):
                recommendations.append(CarrierRecommendation(
                    rank=len(recommendations) + 1,
                    carrier=layer1_carrier,
                    ship_method=layer1_ship_method,
                    delivery_service=layer1_delivery_service,
                    freight_term=layer1_freight_term,
                    source="one_to_one",
                    rule_name="一对一映射",
                    reason="基于一对一映射规则的默认承运商/服务配置",
                ))
                context["layer1_matched"] = True
            else:
                context["layer1_matched"] = False
        except Exception as e:
            result.errors.append(f"Layer1 一对一映射加载失败: {e}")

        # ── Layer 2: 条件映射执行 ────────────────────
        # 用 SKU + Layer1 结果作为输入
        try:
            cond_skus = skus or None
            cond_carriers = [layer1_carrier] if layer1_carrier else None
            cond_ship_methods = [layer1_ship_method] if layer1_ship_method else None

            has_input = any([cond_skus, cond_carriers, cond_ship_methods])
            if has_input:
                raw = self._loader.execute_condition_mapping(
                    merchant_no=request.merchant_no,
                    mapping_key=request.channel_no or "ALL",
                    skus=cond_skus,
                    carriers=cond_carriers,
                    ship_methods=cond_ship_methods,
                )
                mapped_data = raw.get("mappedData", {}) if isinstance(raw, dict) else {}
                for key, item in mapped_data.items():
                    if isinstance(item, dict) and any(item.values()):
                        recommendations.append(CarrierRecommendation(
                            rank=len(recommendations) + 1,
                            carrier=item.get("carrier") or layer1_carrier,
                            ship_method=item.get("shipMethod") or layer1_ship_method,
                            delivery_service=item.get("deliveryService") or layer1_delivery_service,
                            freight_term=item.get("freightTerm") or layer1_freight_term,
                            shipment_type=item.get("shipmentType"),
                            source="condition_mapping",
                            rule_name=f"条件映射 (key={key})",
                            reason=_build_layer2_reason(cond_skus, cond_carriers),
                        ))
                context["layer2_matched"] = len(mapped_data)
            else:
                context["layer2_matched"] = 0
        except Exception as e:
            result.errors.append(f"Layer2 条件映射执行失败: {e}")

        # ── Layer 3: Shipping Mapping 规则匹配 ───────
        # 用 Layer1+Layer2 的结果构建 inputConditions
        if request.channel_no:
            try:
                # 先加载该渠道的规则，了解需要什么 conditionType
                rules = self._loader.load_shipping_rules(
                    merchant_no=request.merchant_no,
                    channel_no=request.channel_no,
                )
                context["layer3_rules_count"] = len(rules)

                if rules:
                    # 从已有推荐中收集可用的条件值
                    known_values = _collect_known_values(recommendations, layer1_carrier, layer1_ship_method)

                    # 为每条规则尝试构建匹配条件
                    for rule in sorted(rules, key=lambda r: r.priority):
                        input_cond = _build_input_for_rule(rule, known_values)
                        if input_cond:
                            raw = self._loader.execute_shipping_mapping(
                                channel_no=request.channel_no,
                                merchant_no=request.merchant_no,
                                input_conditions=[input_cond],
                            )
                            outputs = raw if isinstance(raw, dict) else {}
                            if outputs:
                                rec = _build_recommendation_from_shipping_mapping(
                                    outputs, rule, len(recommendations) + 1,
                                )
                                recommendations.append(rec)
                                context["layer3_matched"] = True
                                break  # 按优先级匹配到第一条就停

                if "layer3_matched" not in context:
                    context["layer3_matched"] = False
            except Exception as e:
                result.errors.append(f"Layer3 Shipping Mapping 执行失败: {e}")

        # ── 构建最终结果 ─────────────────────────────
        if not recommendations:
            result.confidence = "low"
            result.explanation = (
                "三层映射规则均未匹配到结果。"
                "可能原因：该 SKU/渠道未配置映射规则。"
                "建议：检查 OMS 映射配置，或通过 shipping_rate_query 查看当前规则。"
            )
        else:
            # 去重
            seen: set[str] = set()
            unique: list[CarrierRecommendation] = []
            for rec in recommendations:
                key = f"{rec.carrier}|{rec.ship_method}|{rec.delivery_service}"
                if key not in seen:
                    seen.add(key)
                    rec.rank = len(unique) + 1
                    unique.append(rec)
            recommendations = unique

            sources = sorted(set(r.source for r in recommendations))
            result.confidence = "high" if len(sources) >= 2 else "medium"
            result.explanation = (
                f"基于 {' → '.join(sources)} 链式匹配，"
                f"共 {len(recommendations)} 条推荐"
            )

        result.recommendations = recommendations
        result.mapping_context = context
        result.success = len(result.errors) == 0 or len(recommendations) > 0
        return result


# ── 辅助函数 ──────────────────────────────────────────


def _build_layer2_reason(skus: list[str] | None, carriers: list[str] | None) -> str:
    parts = []
    if skus:
        parts.append(f"SKU={skus}")
    if carriers:
        parts.append(f"Carrier={carriers}")
    return f"基于条件映射匹配（{', '.join(parts)}）" if parts else "基于条件映射匹配"


def _collect_known_values(
    recommendations: list[CarrierRecommendation],
    layer1_carrier: str | None,
    layer1_ship_method: str | None,
) -> dict[str, str]:
    """从已有推荐中收集可用的条件值，key 是 conditionType 数字编号。"""
    values: dict[str, str] = {}
    # 优先用最新推荐的值
    for rec in reversed(recommendations):
        if rec.carrier and "4" not in values:
            values["4"] = rec.carrier
        if rec.ship_method and "3" not in values:
            values["3"] = rec.ship_method
        if rec.delivery_service and "5" not in values:
            values["5"] = rec.delivery_service
        if rec.freight_term and "6" not in values:
            values["6"] = rec.freight_term
    # 兜底用 Layer1
    if layer1_carrier and "4" not in values:
        values["4"] = layer1_carrier
    if layer1_ship_method and "3" not in values:
        values["3"] = layer1_ship_method
    return values


def _build_input_for_rule(rule, known_values: dict[str, str]) -> dict[str, str] | None:
    """根据规则的 conditions 和已知值构建 inputConditions。"""
    input_cond: dict[str, str] = {}
    for cond in rule.conditions:
        ct = str(cond.get("conditionType", ""))
        cv = cond.get("conditionValue", "")
        if ct and cv:
            # 如果已知值匹配规则条件，或者直接用规则条件值
            input_cond[ct] = cv
    return input_cond if input_cond else None


def _build_recommendation_from_shipping_mapping(
    outputs: dict[str, str],
    rule,
    rank: int,
) -> CarrierRecommendation:
    """从 Shipping Mapping 输出构建推荐。"""
    return CarrierRecommendation(
        rank=rank,
        carrier=outputs.get("4"),
        ship_method=outputs.get("3"),
        delivery_service=outputs.get("5"),
        freight_term=outputs.get("6"),
        shipment_type=outputs.get("7"),
        source="shipping_mapping",
        rule_name=rule.rule_name,
        priority=rule.priority,
        reason=f"Shipping Mapping 规则 [{rule.rule_name}] (priority={rule.priority}) 匹配",
    )
