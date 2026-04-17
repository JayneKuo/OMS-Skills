"""寻仓推荐引擎 — 商户规则解析

读取商户的分仓规则配置，翻译为引擎行为参数。
规则优先级：商户规则 > 算法模型。
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ResolvedRules:
    """解析后的规则行为参数。"""
    # 库存策略
    skip_inventory_hard_check: bool = False   # ONE_WAREHOUSE_BACKUP 开启时跳过库存硬约束
    # 指定仓
    specified_warehouse_code: str | None = None  # SPECIFY_WAREHOUSE 指定的仓编码
    # 距离优先
    prefer_closest: bool = False              # CLOSEST_WAREHOUSE 开启时按距离优先
    # 拆单策略
    allow_split: bool = True                  # NO_SPLIT 开启时禁止拆单
    # SKU 指定仓
    sku_warehouse_map: dict[str, str] = field(default_factory=dict)  # SKU_SPECIFY_WAREHOUSE
    # 已命中的规则名（用于白盒解释）
    matched_rules: list[str] = field(default_factory=list)


class RuleResolver:
    """从 OMS 路由规则配置中解析引擎行为参数。"""

    def resolve(self, routing_rules: list[dict], sku_warehouse_rules: list[dict] | None = None) -> ResolvedRules:
        """解析路由规则列表。

        Parameters
        ----------
        routing_rules : list[dict]
            从 routing/v2/rules API 返回的规则页列表。
            每页包含 ruleItems，每个 item 有 ruleName 和 switchOn。
        sku_warehouse_rules : list[dict] | None
            从 sku-warehouse/page API 返回的 SKU 指定仓规则。
        """
        result = ResolvedRules()

        for page in routing_rules:
            if not isinstance(page, dict):
                continue
            for item in page.get("ruleItems", []):
                if not isinstance(item, dict):
                    continue
                name = item.get("ruleName", "")
                on = item.get("switchOn", False)
                if not on:
                    continue

                if name == "ONE_WAREHOUSE_BACKUP":
                    result.skip_inventory_hard_check = True
                    result.matched_rules.append("库存不足走最高优先级仓")

                elif name == "SPECIFY_WAREHOUSE":
                    # 指定仓的具体编码需要从规则详情获取，MVP 先标记
                    result.matched_rules.append("按 Accounting Code 指定仓")

                elif name == "CLOSEST_WAREHOUSE":
                    result.prefer_closest = True
                    result.matched_rules.append("最近仓发货")

                elif name == "NO_SPLIT":
                    result.allow_split = False
                    result.matched_rules.append("单仓不拆单")

                elif name == "MINIMAL_SPLIT":
                    result.allow_split = True
                    result.matched_rules.append("允许拆单")

                elif name == "SKU_SPECIFY_WAREHOUSE":
                    result.matched_rules.append("按产品指定仓")

                elif name == "COUNTRY":
                    result.matched_rules.append("按国家/目的地市场过滤")

                elif name == "ZIPCODE":
                    result.matched_rules.append("按邮编过滤仓库")

        # SKU 指定仓映射
        if sku_warehouse_rules:
            for rule in sku_warehouse_rules:
                sku = rule.get("sku", "")
                wh_code = rule.get("accountingCode") or rule.get("warehouseCode", "")
                if sku and wh_code:
                    result.sku_warehouse_map[sku] = wh_code

        return result
