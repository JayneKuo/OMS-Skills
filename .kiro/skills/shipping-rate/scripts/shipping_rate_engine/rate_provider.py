"""Shipping Rate Engine — RateProvider 抽象层

定义运费数据提供者接口，抽象价格表和附加费规则的数据来源。
- LocalRateProvider: 基于本地价格表计算运费
- ExternalRateProvider: 第三方承运商 API 扩展点（预留）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .rate_models import (
    Address,
    PackageInput,
    PackageRate,
    PriceTable,
    ProviderRateResult,
    SurchargeContext,
    SurchargeRuleSet,
)
from .zone_resolver import ZoneResolver, ZoneResolveError
from .rate_calculator import RateCalculator
from .surcharge_calculator import SurchargeCalculator


class RateProvider(ABC):
    """运费数据提供者抽象接口"""

    @abstractmethod
    def get_rate(
        self,
        package: PackageInput,
        origin: Address,
        destination: Address,
        carrier: str,
        surcharge_rules: SurchargeRuleSet | None = None,
        surcharge_context: SurchargeContext | None = None,
    ) -> ProviderRateResult:
        """获取单包裹运费"""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级，数字越小优先级越高"""
        ...


class LocalRateProvider(RateProvider):
    """基于本地价格表的运费计算"""

    def __init__(self, price_tables: dict[str, PriceTable] | None = None):
        self._price_tables = price_tables or {}

    @property
    def priority(self) -> int:
        return 100  # 本地 provider 优先级较低

    def set_price_table(self, carrier: str, table: PriceTable) -> None:
        self._price_tables[carrier] = table

    def get_rate(
        self,
        package: PackageInput,
        origin: Address,
        destination: Address,
        carrier: str,
        surcharge_rules: SurchargeRuleSet | None = None,
        surcharge_context: SurchargeContext | None = None,
    ) -> ProviderRateResult:
        """基于本地价格表计算单包裹运费"""
        price_table = self._price_tables.get(carrier)
        if not price_table:
            return ProviderRateResult(
                success=False,
                error=f"PRICE_TABLE_NOT_FOUND: 承运商 {carrier} 的价格表未找到",
            )

        # 1. 区域解析
        try:
            charge_zone = ZoneResolver.resolve(origin, destination, price_table.zone_mappings)
        except ZoneResolveError as e:
            return ProviderRateResult(success=False, error=str(e))

        # 2. 查找区域费率
        zone_rate = None
        for zr in price_table.zone_rates:
            if zr.charge_zone == charge_zone:
                zone_rate = zr
                break

        if zone_rate is None:
            return ProviderRateResult(
                success=False,
                error=f"ZONE_NOT_FOUND: 计费区域 {charge_zone} 无对应费率配置",
            )

        # 3. 基础运费计算
        try:
            freight_base = RateCalculator.calculate(
                package.billing_weight, package.volume_cm3, zone_rate,
            )
        except Exception as e:
            return ProviderRateResult(success=False, error=f"计算失败: {e}")

        # 4. 附加费计算
        ctx = surcharge_context or SurchargeContext(destination=destination)
        rules = surcharge_rules or SurchargeRuleSet()
        surcharge = SurchargeCalculator.calculate_all(freight_base, package, rules, ctx)

        freight_total = freight_base + surcharge.total
        from .rate_calculator import _round2
        freight_total = _round2(freight_total)

        pkg_rate = PackageRate(
            package_id=package.package_id,
            charge_zone=charge_zone,
            billing_mode=zone_rate.billing_mode,
            freight_base=freight_base,
            surcharge_breakdown=surcharge,
            freight_total=freight_total,
        )

        return ProviderRateResult(success=True, package_rate=pkg_rate)


class ExternalRateProvider(RateProvider):
    """第三方承运商 API 扩展点（预留）

    未来可对接 UPS/FedEx/USPS 等实时报价 API。
    """

    def __init__(self, api_url: str = "", api_key: str = ""):
        self._api_url = api_url
        self._api_key = api_key

    @property
    def priority(self) -> int:
        return 10  # 外部 API 优先级较高

    def get_rate(
        self,
        package: PackageInput,
        origin: Address,
        destination: Address,
        carrier: str,
        surcharge_rules: SurchargeRuleSet | None = None,
        surcharge_context: SurchargeContext | None = None,
    ) -> ProviderRateResult:
        """预留：调用第三方 API 获取运费"""
        return ProviderRateResult(
            success=False,
            error="ExternalRateProvider 尚未实现，请使用 LocalRateProvider",
        )
