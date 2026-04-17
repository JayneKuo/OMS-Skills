"""寻仓推荐引擎 — P2 多维评分

对通过 P0 的候选仓进行距离/成本/时效/容量多维评分，归一化后加权求和排序。
"""

from __future__ import annotations

from .distance import estimate_cost, estimate_days, get_distance
from .models import ScoredWarehouse, ScoringWeights, Warehouse


def normalize(values: list[float], reverse: bool = False) -> list[float]:
    """Min-max 归一化到 [0, 1]。

    Parameters
    ----------
    reverse : bool
        True 时越小越好（成本、时效），归一化后反转。
    """
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [1.0] * len(values)
    normed = [(v - min_v) / (max_v - min_v) for v in values]
    if reverse:
        normed = [1.0 - n for n in normed]
    return normed


class P2Scorer:
    """P2 多维评分器。

    对每个候选仓计算距离→成本/时效，归一化后加权求和，
    输出按评分降序排列的 ScoredWarehouse 列表。
    """

    def score(
        self,
        candidates: list[ScoredWarehouse],
        warehouses_map: dict[str, Warehouse],
        dest_state: str,
        weights: ScoringWeights,
        degradation: list[str],
    ) -> list[ScoredWarehouse]:
        """对候选仓评分并排序。

        Returns
        -------
        list[ScoredWarehouse]
            按 score 降序排列的候选仓列表。
        """
        if not candidates:
            return []

        # 1. 计算每个候选仓的距离、成本、时效、容量
        distances: list[float] = []
        costs: list[float] = []
        etas: list[float] = []
        capacities: list[float] = []
        has_capacity_data = False

        for cand in candidates:
            wh = warehouses_map.get(cand.warehouse_id)
            wh_state = wh.state or "" if wh else ""

            dist = get_distance(wh_state, dest_state)
            cost = estimate_cost(dist)
            eta = estimate_days(dist)

            distances.append(dist)
            costs.append(cost)
            etas.append(eta)

            # 容量：有数据时用剩余容量，无数据时后续统一处理
            if wh and wh.daily_capacity is not None and wh.current_load is not None:
                remaining = max(0, wh.daily_capacity - wh.current_load)
                capacities.append(float(remaining))
                has_capacity_data = True
            else:
                capacities.append(0.0)

        # 2. 归一化
        s_costs = normalize(costs, reverse=True)
        s_etas = normalize(etas, reverse=True)

        if has_capacity_data:
            s_caps = normalize(capacities, reverse=False)
        else:
            s_caps = [1.0] * len(candidates)
            if "capacity_estimated" not in degradation:
                degradation.append("capacity_estimated")

        # 3. 加权求和 + 更新候选仓
        scored: list[ScoredWarehouse] = []
        for i, cand in enumerate(candidates):
            total = (
                weights.cost * s_costs[i]
                + weights.eta * s_etas[i]
                + weights.capacity * s_caps[i]
            )
            scored.append(cand.model_copy(update={
                "score": round(total, 4),
                "score_breakdown": {
                    "cost": round(s_costs[i], 4),
                    "eta": round(s_etas[i], 4),
                    "capacity": round(s_caps[i], 4),
                },
            }))

        # 4. 按评分降序排列
        scored.sort(key=lambda w: w.score, reverse=True)
        return scored
