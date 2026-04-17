"""寻仓推荐引擎 — 方案生成

根据评分后的候选仓生成单仓直发 / 多仓拆发方案。
"""

from __future__ import annotations

import itertools
from copy import deepcopy

from .distance import estimate_cost, estimate_days, get_distance
from .models import (
    FulfillmentPlan,
    OrderItem,
    ScoredWarehouse,
    Warehouse,
    WarehouseAssignment,
)


class PlanGenerator:
    """方案生成器。

    优先单仓直发，无解时尝试多仓拆发（2 仓、3 仓组合）。
    """

    SPLIT_PENALTY: float = 0.10

    def generate(
        self,
        scored: list[ScoredWarehouse],
        warehouses_map: dict[str, Warehouse],
        items: list[OrderItem],
        dest_state: str,
        allow_split: bool,
        max_split: int,
        backup_mode: bool = False,
    ) -> tuple[FulfillmentPlan | None, list[FulfillmentPlan]]:
        """生成履约方案。

        Parameters
        ----------
        backup_mode : bool
            ONE_WAREHOUSE_BACKUP 模式：即使无仓能满足所有 SKU，
            也选评分最高的仓作为推荐。
        """
        required_skus = {item.sku for item in items}

        # Step 1: 单仓直发（库存充足的仓）
        single_plans = self._single_warehouse_plans(
            scored, warehouses_map, items, dest_state,
        )
        if single_plans:
            return single_plans[0], single_plans[1:3]

        # Step 2: 多仓拆发
        if allow_split:
            multi_plans = self._multi_warehouse_plans(
                scored, warehouses_map, items, dest_state,
                required_skus, max_split,
            )
            if multi_plans:
                return multi_plans[0], multi_plans[1:3]

        # Step 3: Backup 模式 — 库存不足走最高优先级仓
        if backup_mode and scored:
            backup_plan = self._backup_plan(scored[0], warehouses_map, items, dest_state)
            return backup_plan, []

        # Step 4: 无解
        return None, []

    # ── 单仓直发 ──────────────────────────────────────

    def _single_warehouse_plans(
        self,
        scored: list[ScoredWarehouse],
        warehouses_map: dict[str, Warehouse],
        items: list[OrderItem],
        dest_state: str,
    ) -> list[FulfillmentPlan]:
        """从 can_fulfill_all 的仓中生成单仓方案，按评分降序。"""
        full_candidates = [w for w in scored if w.can_fulfill_all]
        if not full_candidates:
            return []

        # 已按评分降序排列
        plans: list[FulfillmentPlan] = []
        for cand in full_candidates:
            wh = warehouses_map.get(cand.warehouse_id)
            wh_state = wh.state or "" if wh else ""
            dist = get_distance(wh_state, dest_state)

            assignment = WarehouseAssignment(
                warehouse_id=cand.warehouse_id,
                warehouse_name=cand.warehouse_name,
                accounting_code=cand.accounting_code,
                items=list(items),
                score=cand.score,
                score_breakdown=cand.score_breakdown,
                estimated_cost=round(estimate_cost(dist), 2),
                estimated_days=round(estimate_days(dist), 1),
                distance_km=round(dist, 1),
            )
            plans.append(FulfillmentPlan(
                plan_type="single_warehouse",
                assignments=[assignment],
                total_score=cand.score,
                recommendation_reason=f"单仓直发：{cand.warehouse_name}（{cand.accounting_code}）可满足所有 SKU",
            ))

        return plans

    # ── 多仓拆发 ──────────────────────────────────────

    def _multi_warehouse_plans(
        self,
        scored: list[ScoredWarehouse],
        warehouses_map: dict[str, Warehouse],
        items: list[OrderItem],
        dest_state: str,
        required_skus: set[str],
        max_split: int,
    ) -> list[FulfillmentPlan]:
        """枚举 2~max_split 仓组合，贪心分配 SKU。"""
        plans: list[FulfillmentPlan] = []

        for n in range(2, min(max_split, len(scored)) + 1):
            for combo in itertools.combinations(scored, n):
                # 检查组合是否覆盖所有 SKU
                union_skus: set[str] = set()
                for w in combo:
                    union_skus.update(w.fulfillable_skus)
                if not required_skus.issubset(union_skus):
                    continue

                # 贪心分配
                assignments = self._greedy_assign(
                    combo, warehouses_map, items, dest_state,
                )
                if assignments is None:
                    continue

                # 计算组合评分
                total_items = sum(item.quantity for item in items)
                combo_score = 0.0
                for a in assignments:
                    item_qty = sum(item.quantity for item in a.items)
                    ratio = item_qty / total_items if total_items > 0 else 0
                    combo_score += a.score * ratio
                combo_score -= self.SPLIT_PENALTY * (n - 1)

                plans.append(FulfillmentPlan(
                    plan_type="multi_warehouse",
                    assignments=assignments,
                    total_score=round(combo_score, 4),
                    split_penalty=round(self.SPLIT_PENALTY * (n - 1), 4),
                    recommendation_reason=f"多仓拆发：{n} 仓组合覆盖所有 SKU",
                ))

        # 按评分降序排列
        plans.sort(key=lambda p: p.total_score, reverse=True)
        return plans

    def _greedy_assign(
        self,
        combo: tuple[ScoredWarehouse, ...],
        warehouses_map: dict[str, Warehouse],
        items: list[OrderItem],
        dest_state: str,
    ) -> list[WarehouseAssignment] | None:
        """贪心 SKU 分配：优先分到评分最高的仓。"""
        # 按评分降序
        sorted_wh = sorted(combo, key=lambda w: w.score, reverse=True)

        # 构建临时库存副本
        inv_copy: dict[str, dict[str, int]] = {}
        for w in sorted_wh:
            wh = warehouses_map.get(w.warehouse_id)
            inv_copy[w.warehouse_id] = deepcopy(wh.inventory) if wh else {}

        # 分配
        assignment_items: dict[str, list[OrderItem]] = {w.warehouse_id: [] for w in sorted_wh}
        for item in items:
            assigned = False
            for w in sorted_wh:
                inv = inv_copy[w.warehouse_id]
                if inv.get(item.sku, 0) >= item.quantity:
                    assignment_items[w.warehouse_id].append(item)
                    inv[item.sku] -= item.quantity
                    assigned = True
                    break
            if not assigned:
                return None  # 无法分配

        # 构建 WarehouseAssignment（过滤空分配）
        assignments: list[WarehouseAssignment] = []
        for w in sorted_wh:
            w_items = assignment_items[w.warehouse_id]
            if not w_items:
                continue
            wh = warehouses_map.get(w.warehouse_id)
            wh_state = wh.state or "" if wh else ""
            dist = get_distance(wh_state, dest_state)

            assignments.append(WarehouseAssignment(
                warehouse_id=w.warehouse_id,
                warehouse_name=w.warehouse_name,
                accounting_code=w.accounting_code,
                items=w_items,
                score=w.score,
                score_breakdown=w.score_breakdown,
                estimated_cost=round(estimate_cost(dist), 2),
                estimated_days=round(estimate_days(dist), 1),
                distance_km=round(dist, 1),
            ))

        return assignments

    def _backup_plan(
        self,
        top_wh: ScoredWarehouse,
        warehouses_map: dict[str, Warehouse],
        items: list[OrderItem],
        dest_state: str,
    ) -> FulfillmentPlan:
        """Backup 模式：库存不足走最高优先级仓。"""
        wh = warehouses_map.get(top_wh.warehouse_id)
        wh_state = wh.state or "" if wh else ""
        dist = get_distance(wh_state, dest_state)

        assignment = WarehouseAssignment(
            warehouse_id=top_wh.warehouse_id,
            warehouse_name=top_wh.warehouse_name,
            accounting_code=top_wh.accounting_code,
            items=list(items),
            score=top_wh.score,
            score_breakdown=top_wh.score_breakdown,
            estimated_cost=round(estimate_cost(dist), 2),
            estimated_days=round(estimate_days(dist), 1),
            distance_km=round(dist, 1),
        )
        missing = top_wh.missing_skus
        reason = f"库存不足走最高优先级仓：{top_wh.warehouse_name}（{top_wh.accounting_code}）"
        if missing:
            reason += f"，缺货 SKU：{'、'.join(missing)}"

        return FulfillmentPlan(
            plan_type="backup_warehouse",
            assignments=[assignment],
            total_score=top_wh.score,
            recommendation_reason=reason,
        )
