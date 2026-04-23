"""RuleProvider - 规则域查询"""
from __future__ import annotations

from oms_query_engine.cache import QueryCache
from oms_query_engine.models.query_plan import QueryContext
from oms_query_engine.models.provider_result import ProviderResult
from oms_query_engine.models.rule import RuleInfo
from .base import BaseProvider

ROUTING_RULES = "/api/linker-oms/opc/app-api/routing/v2/rules"
CUSTOM_RULES = "/api/linker-oms/opc/app-api/routing/v2/custom-rule"
SKU_WAREHOUSE = "/api/linker-oms/opc/app-api/sku-warehouse/page"
HOLD_RULES = "/api/linker-oms/opc/app-api/hold-rule-data/page"

# 策略翻译表：内部名 → 中文业务名
STRATEGY_NAME_MAP: dict[str, str] = {
    "ZIPCODE": "按邮编过滤仓库",
    "COUNTRY": "按国家/目的地市场过滤",
    "NO_SPLIT": "单仓不拆单",
    "MINIMAL_SPLIT": "允许拆单",
    "SAMPLE_NO_SPLIT": "样品不拆单",
    "SPECIFY_WAREHOUSE": "按 Accounting Code 指定仓",
    "CUSTOM_RULE": "自定义规则选仓",
    "CLOSEST_WAREHOUSE": "最近仓发货",
    "SKU_SPECIFY_WAREHOUSE": "按产品指定仓",
    "ONE_WAREHOUSE_BACKUP": "库存不足走最高优先级仓",
    "MULTI_WAREHOUSE_BACKUP": "多仓兜底",
    "EXCEPTION_BACKUP": "异常挂起",
    "ONE_WAREHOUSE_ONE_ORDER": "一仓一出库单",
    "ONE_ITEM_ONE_ORDER": "一品一单",
    "SPECIFY_CARRIER_DELIVERY": "指定承运商独立出库单",
    "CONFIG_SAMPLE_ORDER": "样品订单配置",
    "CONFIG_CROSS_BORDER_ORDER": "跨境订单配置",
    "CONFIG_REPLACEMENT_ORDER": "替换订单配置",
    "CONFIG_AUTO_CREATE_PRODUCT_IF_NOT_EXISTS": "自动创建不存在的商品",
    "MERGE_ORDER": "合并订单",
}


class RuleProvider(BaseProvider):
    """路由规则、自定义规则、Hold 规则、SKU 仓规则。"""

    name = "rule"

    def query(self, context: QueryContext) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)
        merchant_no = context.merchant_no
        if not merchant_no:
            result.errors.append("缺少 merchantNo")
            return result
        params = {"merchantNo": merchant_no}

        rr = cr = hr = sw = None

        for api_name, path, key in [
            ("routing_rules", ROUTING_RULES, f"routing_rules:{merchant_no}"),
            ("custom_rules", CUSTOM_RULES, f"custom_rules:{merchant_no}"),
            ("hold_rules", HOLD_RULES, f"hold_rules:{merchant_no}"),
            ("sku_warehouse", SKU_WAREHOUSE, f"sku_wh:{merchant_no}"),
        ]:
            try:
                resp = self._fetch_get(path, key, QueryCache.TTL_STATIC, params=params)
                data = self._get_data(resp)
                records = data if isinstance(data, list) else (
                    data.get("records", []) if isinstance(data, dict) else []
                )
                if api_name == "routing_rules":
                    rr = self._translate_routing_rules(records)
                elif api_name == "custom_rules":
                    cr = records
                elif api_name == "hold_rules":
                    hr = records
                elif api_name == "sku_warehouse":
                    sw = records
                result.called_apis.append(path)
            except Exception as e:
                result.failed_apis.append(api_name)
                result.errors.append(f"{api_name}: {e}")

        result.success = any([rr, cr, hr, sw])
        result.data = {
            "rule_info": RuleInfo(
                routing_rules=rr,
                custom_rules=cr,
                hold_rules=hr,
                sku_warehouse_rules=sw,
            ),
        }
        return result

    @staticmethod
    def _translate_routing_rules(pages: list) -> list:
        """翻译路由规则中的策略名称为中文。"""
        translated = []
        for page in pages:
            if not isinstance(page, dict):
                translated.append(page)
                continue
            items = page.get("ruleItems", [])
            translated_items = []
            for item in items:
                if not isinstance(item, dict):
                    translated_items.append(item)
                    continue
                name = item.get("ruleName", "")
                translated_items.append({
                    "ruleId": item.get("ruleId"),
                    "ruleName": name,
                    "ruleNameCn": STRATEGY_NAME_MAP.get(name, name),
                    "switchOn": item.get("switchOn", False),
                })
            translated.append({
                "pageName": page.get("pageName"),
                "isDefault": page.get("isDefault"),
                "ruleItems": translated_items,
            })
        return translated
