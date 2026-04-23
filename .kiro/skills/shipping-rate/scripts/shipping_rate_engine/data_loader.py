"""Shipping Rate Engine — 数据加载器

通过 oms_query_engine 的 API client 加载 OMS 三层映射规则数据。
不包含 Rate Shopping / 第三方承运商 API，这些通过 recommend provider 扩展。
"""

from __future__ import annotations

from typing import Any

from .models import (
    OneToOneMapping,
    ConditionMapping,
    ShippingRule,
)

# ── OMS API 路径 ──────────────────────────────────────

MAPPING_SINGLE = "/api/linker-oms/oas/app-api/mapping/single"
MAPPING_CONDITION_LIST = "/api/linker-oms/oas/rpc-api/mapping/condition"
MAPPING_CONDITION_EXECUTE = "/api/linker-oms/oas/rpc-api/mapping/condition/execute"
SHIPPING_MAPPING_EXECUTE = "/api/linker-oms/oas/rpc-api/mapping/condition/multi"
SHIPPING_RULE_PAGE = "/api/linker-oms/oas/app-api/mapping/multiple/rule/page"

# ── conditionType 编号 ↔ 可读名 ──────────────────────

CONDITION_TYPE_MAP = {
    "0": "productName",
    "1": "sku",
    "2": "uom",
    "3": "shipMethod",
    "4": "carrier",
    "5": "deliveryService",
    "6": "freightTerm",
    "7": "shipmentType",
    "8": "custom",
}

OUTPUT_TYPE_MAP = CONDITION_TYPE_MAP  # 输出类型编号与条件类型共用


def _extract_list(data: Any) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


class DataLoader:
    """加载 OMS 映射规则数据。"""

    def __init__(self, oms_engine=None):
        self._client = None
        if oms_engine is not None:
            self._client = oms_engine._client

    def _ensure_client(self):
        if self._client is None:
            from oms_query_engine.api_client import OMSAPIClient
            from oms_query_engine.config import EngineConfig
            self._client = OMSAPIClient(EngineConfig())
        self._client._ensure_token()

    # ── Layer 1: 一对一映射 ─────────────────────────

    def load_one_to_one_mappings(
        self,
        merchant_no: str,
        mapping_types: list[str] | None = None,
        channel_no: str | None = None,
    ) -> list[OneToOneMapping]:
        """查询一对一映射列表。

        POST /mapping/single，mappingKeyCriteria=1 必填。
        优化：单次请求查所有类型（不按类型拆分），减少 API 调用次数。
        """
        self._ensure_client()

        types_to_query = mapping_types or [
            "CARRIER", "SHIP_METHOD", "DELIVERY_SERVICE",
            "FREIGHT_TERM", "SHIPMENT_TYPE", "REVERSE_MAPPING_CARRIER",
            "SKU", "UOM",
        ]

        all_mappings: list[OneToOneMapping] = []

        # 单次请求查所有类型（API 支持 mappingType 数组）
        for direction in [1, 2]:
            try:
                payload: dict[str, Any] = {
                    "merchantNo": merchant_no,
                    "mappingType": types_to_query,
                    "mappingKeyCriteria": 1,
                    "mappingDirection": direction,
                    "pageNo": 1,
                    "pageSize": 500,
                }
                if channel_no:
                    payload["mappingKey"] = channel_no

                resp = self._client.post(MAPPING_SINGLE, payload)
                data = resp.get("data", resp)
                items = _extract_list(data)

                for item in items:
                    all_mappings.append(OneToOneMapping(
                        id=item.get("id"),
                        mapping_type=str(item.get("mappingType", "")),
                        mapped_type=str(item.get("mappedType", "")),
                        origin_value=item.get("originValue"),
                        mapped_value=item.get("mappedValue"),
                        mapping_key=item.get("mappingKey"),
                        mapping_direction=item.get("mappingDirection", 1),
                        status=item.get("status", 1),
                    ))
            except Exception:
                continue

        return all_mappings

    # ── Layer 2: 条件映射 ──────────────────────────

    def load_condition_mappings(
        self,
        merchant_no: str,
        mapping_key: str | None = None,
    ) -> list[ConditionMapping]:
        """查询条件映射列表。"""
        self._ensure_client()
        params: dict[str, Any] = {"merchantNo": merchant_no}
        if mapping_key:
            params["mappingKey"] = mapping_key

        resp = self._client.get(MAPPING_CONDITION_LIST, params)
        data = resp.get("data", resp)
        items = _extract_list(data)

        return [
            ConditionMapping(
                id=item.get("id"),
                condition_in_list=item.get("conditionInList", []),
                condition_out=item.get("conditionOut"),
                condition_out_value=item.get("conditionOutValue"),
                mapping_key=item.get("mappingKey"),
                status=item.get("status", 1),
            )
            for item in items
        ]

    # ── Layer 3: Shipping Mapping 规则 ─────────────

    def load_shipping_rules(
        self,
        merchant_no: str,
        channel_no: str | None = None,
    ) -> list[ShippingRule]:
        """查询 Shipping Mapping 规则配置。"""
        self._ensure_client()
        params: dict[str, Any] = {
            "merchantNo": merchant_no,
            "pageNo": 1,
            "pageSize": 100,
        }
        if channel_no:
            params["channelNo"] = channel_no

        resp = self._client.get(SHIPPING_RULE_PAGE, params)
        data = resp.get("data", resp)
        items = _extract_list(data)

        return [
            ShippingRule(
                id=item.get("id"),
                rule_name=item.get("ruleName"),
                channel_no=item.get("channelNo"),
                priority=item.get("priority", 0),
                conditions=item.get("conditions", []),
                outputs=item.get("outputs", []),
                mapping_key=item.get("mappingKey"),
            )
            for item in items
        ]

    # ── 条件映射执行 ────────────────────────────────

    def execute_condition_mapping(
        self,
        merchant_no: str,
        mapping_key: str = "ALL",
        skus: list[str] | None = None,
        carriers: list[str] | None = None,
        ship_methods: list[str] | None = None,
        delivery_services: list[str] | None = None,
        freight_terms: list[str] | None = None,
    ) -> dict:
        """执行条件映射规则。"""
        self._ensure_client()
        mapping_data: dict[str, Any] = {}
        if skus:
            mapping_data["skus"] = skus
        if carriers:
            mapping_data["carriers"] = carriers
        if ship_methods:
            mapping_data["shipMethods"] = ship_methods
        if delivery_services:
            mapping_data["deliveryServices"] = delivery_services
        if freight_terms:
            mapping_data["freightTerms"] = freight_terms

        payload = {
            "merchantNo": merchant_no,
            "mapping": {mapping_key: mapping_data},
        }

        resp = self._client.post(MAPPING_CONDITION_EXECUTE, payload)
        return resp.get("data", resp)

    # ── Shipping Mapping 执行 ───────────────────────

    def execute_shipping_mapping(
        self,
        channel_no: str,
        merchant_no: str,
        input_conditions: list[dict[str, str]],
    ) -> dict:
        """执行 Shipping Mapping 规则。

        注意：inputConditions 的 key 是 conditionType 数字编号（如 "4" = Carrier），
        不是字段名。参考 CONDITION_TYPE_MAP。
        """
        self._ensure_client()
        payload = {
            "channelNo": channel_no,
            "merchantNo": merchant_no,
            "inputConditions": input_conditions,
        }

        resp = self._client.post(SHIPPING_MAPPING_EXECUTE, payload)
        return resp.get("data", resp)
