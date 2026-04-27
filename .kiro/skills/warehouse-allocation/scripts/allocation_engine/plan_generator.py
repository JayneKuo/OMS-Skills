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
        sku_warehouse_map: dict[str, str] | None = None,
    ) -> tuple[FulfillmentPlan | None, list[FulfillmentPlan]]:
        """生成履约方案。

        Parameters
        ----------
        sku_warehouse_map : dict[str, str] | None
            SKU → accounting_code 的强制指定映射。
            有映射的 SKU 必须从指定仓发货，不参与普通评分分配。
        backup_mode : bool
            ONE_WAREHOUSE_BACKUP 模式：即使无仓能满足所有 SKU，
            也选评分最高的仓作为推荐。
        """
        sku_map = sku_warehouse_map or {}

        # 将 SKU 指定仓的商品行拆分出来单独处理
        pinned_items: list[OrderItem] = []   # 有指定仓的商品
        free_items: list[OrderItem] = []     # 无指定仓的商品
        for item in items:
            if item.sku in sku_map:
                pinned_items.append(item)
            else:
                free_items.append(item)

        # 如果所有商品都有指定仓，直接生成强制方案
        if pinned_items and not free_items:
            plan = self._pinned_plan(pinned_items, sku_map, warehouses_map, scored, dest_state)
            if plan:
                return plan, []

        # 如果有部分商品指定仓，先处理指定仓部分，剩余走正常流程
        if pinned_items and free_items:
            pinned_plan = self._pinned_plan(pinned_items, sku_map, warehouses_map, scored, dest_state)
            # 用 free_items 继续走正常流程，最后合并
            free_scored = [w for w in scored if w.warehouse_id not in {
                wh.warehouse_id for wh in warehouses_map.values()
                if wh.accounting_code in set(sku_map.values())
            }] or scored
            free_plan, _ = self._generate_free(free_scored, warehouses_map, free_items, dest_state, allow_split, max_split, backup_mode)
            if pinned_plan and free_plan:
                # 合并为多仓方案
                merged = FulfillmentPlan(
                    plan_type="multi_warehouse",
                    assignments=pinned_plan.assignments + free_plan.assignments,
                    total_score=round((pinned_plan.total_score + free_plan.total_score) / 2, 4),
                    split_penalty=round(self.SPLIT_PENALTY, 4),
                    recommendation_reason=f"SKU 指定仓 + 自由分配：{len(pinned_plan.assignments + free_plan.assignments)} 仓",
                )
                return merged, []
            if pinned_plan:
                return pinned_plan, []

        return self._generate_free(scored, warehouses_map, items, dest_state, allow_split, max_split, backup_mode)

    def _generate_free(
        self,
        scored: list[ScoredWarehouse],
        warehouses_map: dict[str, Warehouse],
        items: list[OrderItem],
        dest_state: str,
        allow_split: bool,
        max_split: int,
        backup_mode: bool,
    ) -> tuple[FulfillmentPlan | None, list[FulfillmentPlan]]:
        """原有的自由分配逻辑。"""
        required_skus = {item.sku for item in items}

        single_plans = self._single_warehouse_plans(scored, warehouses_map, items, dest_state)
        if single_plans:
            return single_plans[0], single_plans[1:3]

        if allow_split:
            multi_plans = self._multi_warehouse_plans(
                scored, warehouses_map, items, dest_state, required_skus, max_split,
            )
            if multi_plans:
                return multi_plans[0], multi_plans[1:3]

        if backup_mode and scored:
            backup_plan = self._backup_plan(scored[0], warehouses_map, items, dest_state)
            return backup_plan, []

        return None, []

    def _pinned_plan(
        self,
        pinned_items: list[OrderItem],
        sku_map: dict[str, str],
        warehouses_map: dict[str, Warehouse],
        scored: list[ScoredWarehouse],
        dest_state: str,
    ) -> FulfillmentPlan | None:
        """为 SKU 指定仓的商品生成强制分配方案。"""
        # accounting_code → warehouse_id 反查
        code_to_id = {wh.accounting_code: wh.warehouse_id for wh in warehouses_map.values()}
        scored_map = {w.warehouse_id: w for w in scored}

        assignment_items: dict[str, list[OrderItem]] = {}
        for item in pinned_items:
            code = sku_map[item.sku]
            wh_id = code_to_id.get(code)
            if not wh_id:
                return None  # 指定仓不在候选列表，无法生成方案
            assignment_items.setdefault(wh_id, []).append(item)

        assignments = []
        total_score = 0.0
        for wh_id, wh_items in assignment_items.items():
            wh = warehouses_map.get(wh_id)
            wh_state = wh.state or "" if wh else ""
            dist = get_distance(wh_state, dest_state)
            scored_wh = scored_map.get(wh_id)
            score = scored_wh.score if scored_wh else 0.5
            total_score += score
            assignments.append(WarehouseAssignment(
                warehouse_id=wh_id,
                warehouse_name=wh.warehouse_name if wh else wh_id,
                accounting_code=wh.accounting_code if wh else "",
                items=wh_items,
                score=score,
                score_breakdown=scored_wh.score_breakdown if scored_wh else {},
                estimated_cost=round(estimate_cost(dist), 2),
                estimated_days=round(estimate_days(dist), 1),
                distance_km=round(dist, 1),
            ))

        if not assignments:
            return None

        plan_type = "single_warehouse" if len(assignments) == 1 else "multi_warehouse"
        return FulfillmentPlan(
            plan_type=plan_type,
            assignments=assignments,
            total_score=round(total_score / len(assignments), 4),
            recommendation_reason=f"SKU 指定仓强制分配：{len(assignments)} 仓",
        )

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
