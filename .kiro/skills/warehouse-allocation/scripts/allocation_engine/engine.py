"""寻仓推荐引擎 — 顶层编排器

编排流程：
1. DataLoader 加载数据
2. RuleResolver 解析商户规则
3. P0Filter 硬约束过滤（受规则影响）
4. P2Scorer 多维评分
5. PlanGenerator 方案生成（受规则影响）
6. ResultBuilder 结果构建
"""

from __future__ import annotations

from .data_loader import DataLoader
from .models import AllocationRequest, AllocationResult, ScoringWeights
from .p0_filter import P0Filter
from .p2_scorer import P2Scorer
from .plan_generator import PlanGenerator
from .result_builder import ResultBuilder
from .rule_resolver import RuleResolver


class WarehouseAllocationEngine:

    def __init__(self, data_loader: DataLoader | None = None):
        self._data_loader = data_loader or DataLoader()
        self._rule_resolver = RuleResolver()
        self._p0_filter = P0Filter()
        self._p2_scorer = P2Scorer()
        self._plan_generator = PlanGenerator()
        self._result_builder = ResultBuilder()

    def allocate(self, request: AllocationRequest) -> AllocationResult:
        try:
            return self._do_allocate(request)
        except Exception as e:
            return AllocationResult(success=False, error=str(e))

    def _do_allocate(self, request: AllocationRequest) -> AllocationResult:
        weights = request.weights or ScoringWeights()

        # 1. 数据加载
        warehouses, items, address, degradation = self._data_loader.load(request)
        if not warehouses:
            return AllocationResult(
                success=False, error="仓库列表为空", data_degradation=degradation,
            )

        # 2. 解析商户规则
        routing_rules = self._data_loader.load_routing_rules(request.merchant_no)
        sku_warehouse_rules = self._data_loader.load_sku_warehouse_rules(request.merchant_no)
        rules = self._rule_resolver.resolve(routing_rules, sku_warehouse_rules)

        # 规则覆盖请求参数
        if not rules.allow_split:
            request.allow_split = False

        # 如果规则指定了最近仓优先，调整权重
        if rules.prefer_closest:
            weights = ScoringWeights(cost=0.20, eta=0.60, capacity=0.20)

        # 3. P0 硬约束过滤
        candidates, eliminated = self._p0_filter.filter(
            warehouses, items, address, degradation,
            skip_inventory_check=rules.skip_inventory_hard_check,
        )

        if not candidates:
            return self._result_builder.build(
                plan=None, alternatives=[], candidates=candidates,
                eliminated=eliminated, degradation=degradation,
                items=items, address=address,
                matched_rules=rules.matched_rules,
            )

        # 4. P2 多维评分
        dest_state = address.state or ""
        warehouses_map = {wh.warehouse_id: wh for wh in warehouses}
        scored = self._p2_scorer.score(
            candidates, warehouses_map, dest_state, weights, degradation,
        )

        # 5. 方案生成
        recommended, alternatives = self._plan_generator.generate(
            scored, warehouses_map, items, dest_state,
            allow_split=request.allow_split,
            max_split=request.max_split_warehouses,
            backup_mode=rules.skip_inventory_hard_check,
            sku_warehouse_map=rules.sku_warehouse_map,
        )

        # 6. 结果构建
        return self._result_builder.build(
            plan=recommended, alternatives=alternatives,
            candidates=scored, eliminated=eliminated,
            degradation=degradation, items=items, address=address,
            matched_rules=rules.matched_rules,
        )
