"""ETA Engine — 数据模型

定义 ETA 计算引擎的所有输入/输出 Pydantic 模型。
使用 Decimal 类型处理时间精度，所有时间单位为小时。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── 枚举 ──────────────────────────────────────────────


class RiskLevel(str, Enum):
    """风险化口径"""
    P50 = "P50"   # 乐观
    P75 = "P75"   # 标准
    P90 = "P90"   # 保守


class ServiceLevel(str, Enum):
    """服务级别"""
    GROUND = "Ground"
    EXPRESS = "Express"
    PRIORITY = "Priority"


class WeatherAlert(str, Enum):
    """天气预警类型"""
    NONE = "none"
    RAIN = "rain"           # 暴雨 f=0.3
    SNOW = "snow"           # 暴雪 f=0.5
    TYPHOON = "typhoon"     # 台风 f=0.5


class CongestionLevel(str, Enum):
    """拥堵级别"""
    NONE = "none"
    NORMAL_PROMO = "normal_promo"   # 普通大促 f=0.2
    PEAK = "peak"                   # 高峰（双11） f=0.5


# ── 输入模型 ──────────────────────────────────────────


class WarehouseContext(BaseModel):
    """仓库上下文"""
    warehouse_id: str = ""
    backlog_orders: int = 0           # 当前积压订单数
    processing_speed: int = 400       # 每小时处理速度（单/h）
    cutoff_hour: int = 16             # 截单时间（24h 制）
    work_start_hour: int = 8          # 作业开始时间
    work_end_hour: int = 22           # 作业结束时间
    process_time_hours: Decimal = Decimal("2")  # 标准仓内处理时间


class CarrierContext(BaseModel):
    """承运商上下文"""
    carrier: str = ""
    service_level: str = "Ground"
    next_pickup_hours: Decimal = Decimal("1")  # 距下一次揽收的小时数
    on_time_rate: Decimal = Decimal("0.92")    # 近 7 天准点率
    api_transit_hours: Decimal | None = None   # 承运商 API 返回的 transit time


class RiskFactors(BaseModel):
    """风险因子"""
    weather_alert: str = "none"
    congestion_level: str = "none"
    carrier_on_time_rate: Decimal = Decimal("0.92")


class ETARequest(BaseModel):
    """ETA 计算请求"""
    origin_state: str                  # 发货州
    dest_state: str                    # 收货州
    carrier: str = ""                  # 承运商
    service_level: str = "Ground"      # 服务级别
    risk_level: str = "P75"            # 风险化口径
    sla_hours: Decimal = Decimal("72") # SLA 时限（小时）
    order_hour: int = 14               # 下单时间（24h 制）
    order_month: int | None = None     # 下单月份（1-12），用于节假日检测
    order_day: int | None = None       # 下单日期（1-31），用于节假日检测
    warehouse: WarehouseContext = Field(default_factory=WarehouseContext)
    carrier_ctx: CarrierContext = Field(default_factory=CarrierContext)
    risk_factors: RiskFactors = Field(default_factory=RiskFactors)


# ── 输出模型 ──────────────────────────────────────────


class ETABreakdown(BaseModel):
    """ETA 各组件明细"""
    t_queue: Decimal = Decimal("0")
    t_cutoff_wait: Decimal = Decimal("0")
    t_process: Decimal = Decimal("0")
    t_handover: Decimal = Decimal("0")
    t_transit: Decimal = Decimal("0")
    t_last_mile: Decimal = Decimal("0")
    t_weather: Decimal = Decimal("0")
    t_risk_buffer: Decimal = Decimal("0")


class RiskAdjustment(BaseModel):
    """风险修正明细"""
    f_weather: Decimal = Decimal("0")
    f_congestion: Decimal = Decimal("0")
    f_carrier_risk: Decimal = Decimal("0")
    risk_factor: Decimal = Decimal("0")
    eta_before_adjustment: Decimal = Decimal("0")
    eta_after_adjustment: Decimal = Decimal("0")


class ETAByRiskLevel(BaseModel):
    """各口径 ETA"""
    p50_hours: Decimal = Decimal("0")
    p75_hours: Decimal = Decimal("0")
    p90_hours: Decimal = Decimal("0")


class ETAResult(BaseModel):
    """ETA 计算结果"""
    success: bool = True
    eta_hours: Decimal = Decimal("0")          # 最终 ETA（小时）
    eta_days: Decimal = Decimal("0")           # 最终 ETA（天）
    risk_level: str = "P75"
    breakdown: ETABreakdown = Field(default_factory=ETABreakdown)
    risk_adjustment: RiskAdjustment = Field(default_factory=RiskAdjustment)
    eta_by_risk_level: ETAByRiskLevel = Field(default_factory=ETAByRiskLevel)
    on_time_probability: Decimal = Decimal("0")
    on_time_risk: bool = False                 # True = 时效风险
    sla_hours: Decimal = Decimal("72")
    degraded: bool = False
    degraded_fields: list[str] = Field(default_factory=list)
    confidence: str = "high"                   # high / medium / estimated
    carrier: str = ""
    service_level: str = "Ground"
    origin_state: str = ""
    dest_state: str = ""
    transit_source: str = ""                   # 数据来源说明
    explanation: str = ""
    errors: list[str] = Field(default_factory=list)
