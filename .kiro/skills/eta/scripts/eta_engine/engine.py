"""ETA Engine — 时效计算引擎

实现 8 组件 ETA 公式、P50/P75/P90 三口径、风险修正、OnTimeProbability。
内置美国市场默认 transit time 表，无历史数据时降级估算。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import (
    ETABreakdown,
    ETAByRiskLevel,
    ETARequest,
    ETAResult,
    RiskAdjustment,
)


def _round2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── 美国州→区域映射 ──────────────────────────────────

US_REGIONS: dict[str, list[str]] = {
    "WEST": ["CA", "OR", "WA", "NV", "AZ", "UT", "CO", "NM", "ID", "MT", "WY", "HI", "AK"],
    "CENTRAL": ["TX", "OK", "KS", "NE", "SD", "ND", "MN", "IA", "MO", "AR", "LA",
                 "WI", "IL", "IN", "MI", "OH"],
    "SOUTH": ["FL", "GA", "SC", "NC", "VA", "WV", "KY", "TN", "AL", "MS", "MD", "DE", "DC"],
    "EAST": ["NY", "NJ", "PA", "CT", "MA", "RI", "VT", "NH", "ME"],
}

_STATE_TO_REGION: dict[str, str] = {}
for _region, _states in US_REGIONS.items():
    for _st in _states:
        _STATE_TO_REGION[_st] = _region

# 邻接区域
_ADJACENT: dict[str, set[str]] = {
    "WEST": {"CENTRAL"},
    "CENTRAL": {"WEST", "SOUTH", "EAST"},
    "SOUTH": {"CENTRAL", "EAST"},
    "EAST": {"CENTRAL", "SOUTH"},
}

# ── 默认 Transit Time 表（小时） ─────────────────────
# 距离分段 × 服务级别

_DEFAULT_TRANSIT: dict[str, dict[str, Decimal]] = {
    "same_state": {"Ground": Decimal("24"), "Express": Decimal("12"), "Priority": Decimal("8")},
    "adjacent":   {"Ground": Decimal("48"), "Express": Decimal("24"), "Priority": Decimal("12")},
    "cross":      {"Ground": Decimal("72"), "Express": Decimal("36"), "Priority": Decimal("24")},
    "remote":     {"Ground": Decimal("120"), "Express": Decimal("48"), "Priority": Decimal("36")},
}

# ── 默认末端配送时间（小时） ─────────────────────────

_DEFAULT_LAST_MILE: dict[str, Decimal] = {
    "Ground": Decimal("6"),
    "Express": Decimal("4"),
    "Priority": Decimal("2"),
}

# ── 节假日/旺季日期表（月-日） ───────────────────────
# 格式：(月, 日起, 日止, congestion_level)
_US_PEAK_PERIODS: list[tuple[int, int, int, str]] = [
    (11, 25, 30, "peak"),        # 黑五/网一
    (12, 15, 31, "peak"),        # 圣诞旺季
    (1,  1,  3,  "peak"),        # 元旦
    (2,  10, 16, "normal_promo"),# 情人节
    (5,  20, 27, "normal_promo"),# 阵亡将士纪念日
    (7,  1,  7,  "normal_promo"),# 独立日
    (9,  1,  7,  "normal_promo"),# 劳工节
    (10, 28, 31, "normal_promo"),# 万圣节
]


def _detect_congestion(month: int, day: int) -> str:
    """根据日期自动判断拥堵级别"""
    for m, d_start, d_end, level in _US_PEAK_PERIODS:
        if month == m and d_start <= day <= d_end:
            return level
    return "none"


# ── 风险化口径乘数（基于承运商准点率动态计算） ────────

def _risk_multipliers(on_time_rate: Decimal) -> dict[str, Decimal]:
    """
    P75/P90 乘数随承运商准点率动态调整：
    准点率越低 → 分位数越分散 → P90 乘数越大
    基准：on_time_rate=0.92 时 P75=1.15, P90=1.35
    """
    spread = _round2((Decimal("1") - on_time_rate) * Decimal("2"))
    return {
        "P50": Decimal("1.00"),
        "P75": _round2(Decimal("1.15") + spread * Decimal("0.3")),
        "P90": _round2(Decimal("1.35") + spread * Decimal("0.6")),
    }

# ── 天气风险因子 ─────────────────────────────────────

_WEATHER_FACTOR: dict[str, Decimal] = {
    "none": Decimal("0"),
    "rain": Decimal("0.3"),
    "snow": Decimal("0.5"),
    "typhoon": Decimal("0.5"),
}

# ── 拥堵风险因子 ─────────────────────────────────────

_CONGESTION_FACTOR: dict[str, Decimal] = {
    "none": Decimal("0"),
    "normal_promo": Decimal("0.2"),
    "peak": Decimal("0.5"),
}


def _get_distance_segment(origin_state: str, dest_state: str) -> str:
    """根据州级距离确定分段"""
    o = origin_state.upper()
    d = dest_state.upper()
    if o == d:
        return "same_state"
    o_region = _STATE_TO_REGION.get(o)
    d_region = _STATE_TO_REGION.get(d)
    if not o_region or not d_region:
        return "remote"
    if o_region == d_region:
        return "adjacent"  # 同区域不同州 → 邻州
    if d_region in _ADJACENT.get(o_region, set()):
        return "cross"     # 邻接区域 → 跨区
    return "remote"        # 其他 → 远距


def _get_transit_hours(segment: str, service: str) -> Decimal:
    """获取默认 transit time"""
    svc = service if service in ("Ground", "Express", "Priority") else "Ground"
    return _DEFAULT_TRANSIT.get(segment, _DEFAULT_TRANSIT["remote"]).get(svc, Decimal("72"))


def _get_last_mile_hours(service: str) -> Decimal:
    svc = service if service in ("Ground", "Express", "Priority") else "Ground"
    return _DEFAULT_LAST_MILE.get(svc, Decimal("6"))


class ETAEngine:
    """ETA 计算引擎"""

    def calculate(self, request: ETARequest) -> ETAResult:
        """执行 ETA 计算"""
        errors: list[str] = []
        degraded_fields: list[str] = []

        # 节假日自动检测：如果传了日期且 congestion_level 未手动设置，自动推断
        if (request.order_month and request.order_day
                and request.risk_factors.congestion_level == "none"):
            auto_congestion = _detect_congestion(request.order_month, request.order_day)
            if auto_congestion != "none":
                request.risk_factors.congestion_level = auto_congestion

        # ── 1. 计算各组件 ──

        # T_queue: 排队等待
        wh = request.warehouse
        if wh.processing_speed > 0:
            t_queue = _round2(Decimal(str(wh.backlog_orders)) / Decimal(str(wh.processing_speed)))
        else:
            # processing_speed 未知才降级，backlog=0 是正常状态
            t_queue = Decimal("0.5")
            degraded_fields.append("t_queue")

        # T_cutoff_wait: 截单等待
        if request.order_hour < wh.cutoff_hour:
            t_cutoff_wait = Decimal("0")
        else:
            # 需等待到下一工作日开始
            hours_to_next_day = Decimal(str(24 - request.order_hour + wh.work_start_hour))
            t_cutoff_wait = hours_to_next_day

        # T_process: 仓内处理
        t_process = wh.process_time_hours

        # T_handover: 交接时间
        t_handover = request.carrier_ctx.next_pickup_hours

        # T_transit: 干线运输
        svc = request.service_level
        carrier_api = request.carrier_ctx.api_transit_hours
        if carrier_api is not None and carrier_api > 0:
            # 有承运商 API 数据，乘以校准系数 1.2
            t_transit = _round2(carrier_api * Decimal("1.2"))
            transit_source = "carrier_api_calibrated"
        else:
            # 使用默认 transit time
            segment = _get_distance_segment(request.origin_state, request.dest_state)
            t_transit = _get_transit_hours(segment, svc)
            transit_source = f"default_us_{segment}"
            degraded_fields.append("t_transit")

        # T_last_mile: 末端配送
        t_last_mile = _get_last_mile_hours(svc)
        degraded_fields.append("t_last_mile")

        # T_weather: 天气影响
        weather = request.risk_factors.weather_alert
        f_weather = _WEATHER_FACTOR.get(weather, Decimal("0"))
        t_weather = _round2(t_transit * f_weather) if f_weather > 0 else Decimal("0")

        # T_risk_buffer: 风险缓冲
        on_time_rate = request.risk_factors.carrier_on_time_rate
        if on_time_rate < Decimal("1"):
            t_risk_buffer = _round2(t_transit * (Decimal("1") - on_time_rate) * Decimal("0.5"))
        else:
            t_risk_buffer = Decimal("0")

        breakdown = ETABreakdown(
            t_queue=t_queue,
            t_cutoff_wait=t_cutoff_wait,
            t_process=t_process,
            t_handover=t_handover,
            t_transit=t_transit,
            t_last_mile=t_last_mile,
            t_weather=t_weather,
            t_risk_buffer=t_risk_buffer,
        )

        # ── 2. 基础 ETA ──
        eta_base = (t_queue + t_cutoff_wait + t_process + t_handover
                    + t_transit + t_last_mile + t_weather + t_risk_buffer)

        # ── 3. 风险修正 ──
        f_cong = _CONGESTION_FACTOR.get(
            request.risk_factors.congestion_level, Decimal("0"))
        f_carrier = Decimal("0")
        if on_time_rate < Decimal("0.8"):
            f_carrier = _round2((Decimal("1") - on_time_rate) * Decimal("0.5"))

        risk_factor = max(f_weather, f_cong, f_carrier)
        eta_adjusted = _round2(eta_base * (Decimal("1") + risk_factor))

        risk_adj = RiskAdjustment(
            f_weather=f_weather,
            f_congestion=f_cong,
            f_carrier_risk=f_carrier,
            risk_factor=risk_factor,
            eta_before_adjustment=_round2(eta_base),
            eta_after_adjustment=eta_adjusted,
        )

        # ── 4. 三口径（基于承运商准点率动态计算乘数） ──
        risk_mults = _risk_multipliers(on_time_rate)
        p50 = _round2(eta_adjusted * risk_mults["P50"])
        p75 = _round2(eta_adjusted * risk_mults["P75"])
        p90 = _round2(eta_adjusted * risk_mults["P90"])

        eta_by_risk = ETAByRiskLevel(
            p50_hours=p50,
            p75_hours=p75,
            p90_hours=p90,
        )

        # 选择请求的口径
        risk_level = request.risk_level if request.risk_level in risk_mults else "P75"
        eta_final = _round2(eta_adjusted * risk_mults[risk_level])

        # ── 5. OnTimeProbability ──
        sla = request.sla_hours
        on_time_prob = self._calc_on_time_probability(eta_final, sla, p50, p90)
        on_time_risk = on_time_prob < Decimal("0.85")

        # ── 6. 构建结果 ──
        is_degraded = len(degraded_fields) > 0
        # 置信度三档，以 t_transit 数据来源为主要判断依据：
        # - t_transit 来自承运商 API → high
        # - t_transit 用默认表，其他字段正常 → medium
        # - t_queue 也降级（仓库无积压数据）→ estimated
        meaningful_degraded = [f for f in degraded_fields if f != "t_last_mile"]
        if not meaningful_degraded:
            confidence = "high"
        elif meaningful_degraded == ["t_transit"]:
            confidence = "medium"
        else:
            confidence = "estimated"

        eta_days = _round2(eta_final / Decimal("24"))

        explanation_parts = [
            f"ETA 计算：{request.origin_state} → {request.dest_state}",
            f"承运商: {request.carrier or '默认'}, 服务: {svc}",
            f"基础 ETA = {_round2(eta_base)}h",
        ]
        if risk_factor > 0:
            explanation_parts.append(f"风险修正 +{_round2(risk_factor * 100)}%")
        explanation_parts.append(f"最终 ETA({risk_level}) = {eta_final}h ≈ {eta_days}天")
        explanation_parts.append(f"OnTimeProbability = {on_time_prob}")

        return ETAResult(
            success=True,
            eta_hours=eta_final,
            eta_days=eta_days,
            risk_level=risk_level,
            breakdown=breakdown,
            risk_adjustment=risk_adj,
            eta_by_risk_level=eta_by_risk,
            on_time_probability=on_time_prob,
            on_time_risk=on_time_risk,
            sla_hours=sla,
            degraded=is_degraded,
            degraded_fields=degraded_fields,
            confidence=confidence,
            carrier=request.carrier,
            service_level=svc,
            origin_state=request.origin_state,
            dest_state=request.dest_state,
            transit_source=transit_source,
            explanation=" | ".join(explanation_parts),
            errors=errors,
        )

    def _calc_on_time_probability(
        self,
        eta_final: Decimal,
        sla: Decimal,
        p50: Decimal,
        p90: Decimal,
    ) -> Decimal:
        """基于 P50/P90 估算 OnTimeProbability

        使用线性插值近似：
        - 如果 SLA >= P90 → 概率 ≈ 0.95
        - 如果 SLA >= P50 → 线性插值 0.50 ~ 0.90
        - 如果 SLA < P50 → 线性插值 0.10 ~ 0.50
        """
        if sla <= 0:
            return Decimal("0")
        if p90 <= 0:
            return Decimal("0.50")

        if sla >= p90:
            # SLA 宽裕，高概率准时
            surplus = sla - p90
            extra = min(_round2(surplus / p90 * Decimal("0.05")), Decimal("0.04"))
            return min(_round2(Decimal("0.91") + extra), Decimal("0.99"))
        elif sla >= p50:
            # 在 P50 和 P90 之间线性插值
            if p90 == p50:
                return Decimal("0.70")
            ratio = (sla - p50) / (p90 - p50)
            prob = Decimal("0.50") + ratio * Decimal("0.40")
            return _round2(prob)
        else:
            # SLA 比 P50 还紧
            if p50 <= 0:
                return Decimal("0.10")
            ratio = sla / p50
            prob = ratio * Decimal("0.50")
            return _round2(max(prob, Decimal("0.05")))
