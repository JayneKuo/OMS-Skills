"""寻仓推荐引擎 — 美国州级距离计算

提供 Haversine 公式、州级距离查表、成本/时效估算。
"""

from __future__ import annotations

import math

# ── 常量 ──────────────────────────────────────────────────

BASE_COST: float = 5.0       # 基础运费 $5
COST_PER_KM: float = 0.02    # 每 km $0.02
ETA_KM_PER_DAY: float = 500  # 每天 500km
MAX_DISTANCE: float = 5000.0 # 未知州的默认最大距离 (km)

# ── 美国 50 州 + DC 中心点经纬度 ──────────────────────────

US_STATE_COORDS: dict[str, tuple[float, float]] = {
    "AL": (32.32, -86.90),
    "AK": (63.59, -154.49),
    "AZ": (34.05, -111.09),
    "AR": (35.20, -91.83),
    "CA": (36.78, -119.42),
    "CO": (39.55, -105.78),
    "CT": (41.60, -72.90),
    "DE": (38.91, -75.53),
    "DC": (38.91, -77.04),
    "FL": (27.66, -81.52),
    "GA": (32.16, -82.90),
    "HI": (19.90, -155.58),
    "ID": (44.07, -114.74),
    "IL": (40.63, -89.40),
    "IN": (40.27, -86.13),
    "IA": (41.88, -93.10),
    "KS": (39.01, -98.48),
    "KY": (37.67, -84.67),
    "LA": (30.46, -91.87),
    "ME": (45.25, -69.45),
    "MD": (39.05, -76.64),
    "MA": (42.41, -71.38),
    "MI": (44.31, -84.36),
    "MN": (46.73, -94.69),
    "MS": (32.35, -89.40),
    "MO": (37.96, -91.83),
    "MT": (46.88, -110.36),
    "NE": (41.49, -99.90),
    "NV": (38.80, -116.42),
    "NH": (43.19, -71.57),
    "NJ": (40.06, -74.41),
    "NM": (34.52, -105.87),
    "NY": (42.17, -74.95),
    "NC": (35.76, -79.02),
    "ND": (47.55, -101.00),
    "OH": (40.42, -82.91),
    "OK": (35.47, -97.52),
    "OR": (43.80, -120.55),
    "PA": (41.20, -77.19),
    "RI": (41.58, -71.48),
    "SC": (33.84, -81.16),
    "SD": (43.97, -99.90),
    "TN": (35.52, -86.58),
    "TX": (31.97, -99.90),
    "UT": (39.32, -111.09),
    "VT": (44.56, -72.58),
    "VA": (37.43, -78.66),
    "WA": (47.75, -120.74),
    "WV": (38.60, -80.45),
    "WI": (43.78, -88.79),
    "WY": (43.08, -107.29),
}


# ── Haversine 公式 ────────────────────────────────────────

_EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """返回两点间大圆距离（km）。"""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _EARTH_RADIUS_KM * c


# ── 州级距离查询 ──────────────────────────────────────────


def get_distance(wh_state: str, dest_state: str) -> float:
    """返回仓库州到目的地州的距离（km）。

    - 同州 → 0
    - 未知州 → MAX_DISTANCE (5000)
    """
    wh_upper = wh_state.upper() if wh_state else ""
    dest_upper = dest_state.upper() if dest_state else ""

    if wh_upper == dest_upper and wh_upper in US_STATE_COORDS:
        return 0.0

    coord1 = US_STATE_COORDS.get(wh_upper)
    coord2 = US_STATE_COORDS.get(dest_upper)

    if not coord1 or not coord2:
        return MAX_DISTANCE

    return haversine(*coord1, *coord2)


# ── 成本 / 时效估算 ──────────────────────────────────────


def estimate_cost(distance_km: float) -> float:
    """距离 → 估算运费（$）。"""
    return BASE_COST + distance_km * COST_PER_KM


def estimate_days(distance_km: float) -> float:
    """距离 → 估算送达天数。最少 1 天。"""
    return max(1.0, distance_km / ETA_KM_PER_DAY)
