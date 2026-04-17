"""Shipping Rate Engine — 计费区域解析器

根据发货仓地址和收货地址确定计费区域。
支持省/市/区三级地址匹配，优先匹配最精确的区级，逐级回退。
"""

from __future__ import annotations

from .rate_models import Address, ZoneMapping


class ZoneResolveError(Exception):
    """区域解析失败"""
    pass


class ZoneResolver:
    """计费区域解析器（纯函数）"""

    @staticmethod
    def resolve(
        origin: Address,
        destination: Address,
        zone_mappings: list[ZoneMapping],
    ) -> str:
        """返回 charge_zone 编号。

        匹配优先级：区级 > 市级 > 省级。
        同城返回同城区域编号。

        Raises:
            ZoneResolveError: 无法匹配任何计费区域
        """
        if not zone_mappings:
            raise ZoneResolveError("ZONE_NOT_FOUND: 区域映射规则为空")

        # 按匹配精度分桶：district(3) > city(2) > province(1)
        best_match: str | None = None
        best_score = 0

        for zm in zone_mappings:
            score = ZoneResolver._match_score(origin, destination, zm)
            if score > best_score:
                best_score = score
                best_match = zm.charge_zone

        if best_match is None:
            raise ZoneResolveError(
                f"ZONE_NOT_FOUND: 无法匹配计费区域 "
                f"(origin={origin.province}/{origin.city}/{origin.district}, "
                f"dest={destination.province}/{destination.city}/{destination.district})"
            )

        return best_match

    @staticmethod
    def _match_score(origin: Address, destination: Address, zm: ZoneMapping) -> int:
        """计算地址与映射规则的匹配分数。

        返回 0 表示不匹配，分数越高匹配越精确。
        origin 匹配分 + destination 匹配分，各最高 3 分。
        """
        origin_score = ZoneResolver._addr_match_score(
            origin.province, origin.city, origin.district,
            zm.origin_province, zm.origin_city, zm.origin_district,
        )
        dest_score = ZoneResolver._addr_match_score(
            destination.province, destination.city, destination.district,
            zm.dest_province, zm.dest_city, zm.dest_district,
        )

        # 两端都必须匹配
        if origin_score == 0 or dest_score == 0:
            return 0

        return origin_score + dest_score

    @staticmethod
    def _addr_match_score(
        province: str, city: str, district: str,
        rule_province: str, rule_city: str, rule_district: str,
    ) -> int:
        """单端地址匹配分数。

        规则字段为空表示通配（匹配任意值）。
        非空字段必须精确匹配。
        返回匹配的精确度分数：district=3, city=2, province=1, wildcard-only=1。
        """
        # 检查非空规则字段是否匹配
        if rule_province and rule_province != province:
            return 0
        if rule_city and rule_city != city:
            return 0
        if rule_district and rule_district != district:
            return 0

        # 计算精确度分数
        score = 0
        if rule_district:
            score = 3  # 区级匹配最精确
        elif rule_city:
            score = 2  # 市级匹配
        elif rule_province:
            score = 1  # 省级匹配
        else:
            score = 1  # 全通配（兜底规则），最低优先级但仍匹配

        return score

    @staticmethod
    def is_same_city(origin: Address, destination: Address) -> bool:
        """判断是否同城"""
        return (
            bool(origin.city)
            and origin.city == destination.city
            and origin.province == destination.province
        )
