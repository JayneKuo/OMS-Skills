"""预分组器 - 按温区、危险品、禁混、同包、赠品规则将 SKU 分为互斥组"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional
import uuid

from cartonization_engine.models import (
    HazmatType,
    OrderConfig,
    RuleConflictError,
    SKUGroup,
    SKUItem,
    TemperatureZone,
)

from decimal import Decimal


class PreGrouper:
    """预分组器。

    按优先级执行分组规则：
    1. 温区分组（按 temperature_zone 分组）
    2. 危险品隔离（hazmat_type != 无 的 SKU 单独成组）
    3. cannot_ship_with 互斥拆分
    4. must_ship_with 绑定合并
    5. 赠品同包绑定
    """

    def group(
        self, items: list[SKUItem], config: OrderConfig
    ) -> list[SKUGroup]:
        """按规则将 SKU 分为互斥组。冲突时抛出 RuleConflictError。"""
        if not items:
            return []

        # 建立 sku_id → SKUItem 索引
        sku_map: dict[str, SKUItem] = {item.sku_id: item for item in items}

        # 1. 温区分组
        zone_groups: dict[TemperatureZone, list[SKUItem]] = defaultdict(list)
        for item in items:
            zone = item.temperature_zone or TemperatureZone.NORMAL
            zone_groups[zone].append(item)

        # 2. 危险品隔离 - 从温区组中提取危险品单独成组
        hazmat_items: list[SKUItem] = []
        for zone, group_items in zone_groups.items():
            safe_items = []
            for item in group_items:
                if item.hazmat_type is not None and item.hazmat_type != HazmatType.NONE:
                    hazmat_items.append(item)
                else:
                    safe_items.append(item)
            zone_groups[zone] = safe_items

        # 3. cannot_ship_with 互斥拆分 - 在每个温区组内处理
        split_zone_groups: dict[TemperatureZone, list[list[SKUItem]]] = {}
        for zone, group_items in zone_groups.items():
            if not group_items:
                continue
            split_zone_groups[zone] = self._split_by_cannot_ship_with(group_items)

        # 4. must_ship_with 绑定合并 - 检测冲突并合并
        for zone, sub_groups in split_zone_groups.items():
            split_zone_groups[zone] = self._merge_must_ship_with(
                sub_groups, sku_map, zone
            )

        # 检查 must_ship_with 跨温区冲突
        self._check_cross_zone_must_ship_with(items, sku_map)

        # 5. 赠品同包绑定
        if config.gift_same_package_required:
            for zone, sub_groups in split_zone_groups.items():
                split_zone_groups[zone] = self._bind_gifts(sub_groups)

        # 组装最终结果
        result: list[SKUGroup] = []

        # 添加危险品组（每个危险品单独成组）
        for item in hazmat_items:
            result.append(SKUGroup(
                group_id=self._gen_id(),
                temperature_zone=item.temperature_zone or TemperatureZone.NORMAL,
                items=[item],
                group_reason=f"危险品隔离: {item.hazmat_type.value if item.hazmat_type else '未知'}",
            ))

        # 6. 软规则：易碎品与重物拆组（>3kg 非易碎品不与易碎品同组）
        for zone, sub_groups in split_zone_groups.items():
            split_zone_groups[zone] = self._split_fragile_from_heavy(sub_groups)

        # 添加普通组
        for zone, sub_groups in split_zone_groups.items():
            for sub_group in sub_groups:
                if sub_group:
                    # 判断分组原因
                    has_fragile = any(it.fragile_flag for it in sub_group)
                    has_heavy = any(
                        not it.fragile_flag and (it.weight or Decimal(0)) > Decimal("3")
                        for it in sub_group
                    )
                    if has_fragile:
                        reason = f"温区分组: {zone.value} (易碎品保护组)"
                    elif has_heavy:
                        reason = f"温区分组: {zone.value} (含重物，已与易碎品分离)"
                    else:
                        reason = f"温区分组: {zone.value}"
                    result.append(SKUGroup(
                        group_id=self._gen_id(),
                        temperature_zone=zone,
                        items=sub_group,
                        group_reason=reason,
                    ))

        return result

    def _split_by_cannot_ship_with(
        self, items: list[SKUItem]
    ) -> list[list[SKUItem]]:
        """按 cannot_ship_with 约束拆分为互斥子组。

        使用贪心策略：逐个 SKU 尝试放入已有子组，
        如果与子组内任何 SKU 互斥则新建子组。
        """
        sub_groups: list[list[SKUItem]] = []

        for item in items:
            placed = False
            for group in sub_groups:
                if self._can_coexist(item, group):
                    group.append(item)
                    placed = True
                    break
            if not placed:
                sub_groups.append([item])

        return sub_groups

    def _can_coexist(self, item: SKUItem, group: list[SKUItem]) -> bool:
        """检查 item 是否可以与 group 中所有 SKU 共存。"""
        for existing in group:
            if existing.sku_id in item.cannot_ship_with:
                return False
            if item.sku_id in existing.cannot_ship_with:
                return False
        return True

    def _merge_must_ship_with(
        self,
        sub_groups: list[list[SKUItem]],
        sku_map: dict[str, SKUItem],
        zone: TemperatureZone,
    ) -> list[list[SKUItem]]:
        """合并 must_ship_with 绑定的 SKU 到同一子组。

        如果绑定的 SKU 分布在不同子组中（因 cannot_ship_with 拆分），
        则检测冲突并抛出 RuleConflictError。
        """
        # 建立 sku_id → 子组索引
        sku_to_group: dict[str, int] = {}
        for idx, group in enumerate(sub_groups):
            for item in group:
                sku_to_group[item.sku_id] = idx

        # 使用 Union-Find 合并绑定关系
        parent: dict[int, int] = {i: i for i in range(len(sub_groups))}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for group in sub_groups:
            for item in group:
                if not item.must_ship_with:
                    continue
                src_idx = sku_to_group.get(item.sku_id)
                if src_idx is None:
                    continue
                for target_id in item.must_ship_with:
                    tgt_idx = sku_to_group.get(target_id)
                    if tgt_idx is None:
                        continue  # 目标 SKU 不在当前温区组

                    # 检查 cannot_ship_with 冲突
                    src_group = sub_groups[find(src_idx)]
                    tgt_group = sub_groups[find(tgt_idx)]
                    if find(src_idx) != find(tgt_idx):
                        # 检查合并后是否有 cannot_ship_with 冲突
                        all_items = src_group + tgt_group
                        for a in all_items:
                            for b in all_items:
                                if a.sku_id != b.sku_id and b.sku_id in a.cannot_ship_with:
                                    raise RuleConflictError(
                                        f"must_ship_with 与 cannot_ship_with 冲突: "
                                        f"{item.sku_id} 必须与 {target_id} 同包，"
                                        f"但 {a.sku_id} 禁止与 {b.sku_id} 同包",
                                        conflicting_skus=[item.sku_id, target_id, a.sku_id, b.sku_id],
                                    )
                    union(src_idx, tgt_idx)

        # 按合并后的组重新组织
        merged: dict[int, list[SKUItem]] = defaultdict(list)
        for idx, group in enumerate(sub_groups):
            root = find(idx)
            merged[root].extend(group)

        return list(merged.values())

    def _check_cross_zone_must_ship_with(
        self, items: list[SKUItem], sku_map: dict[str, SKUItem]
    ) -> None:
        """检查 must_ship_with 跨温区冲突。"""
        for item in items:
            for target_id in item.must_ship_with:
                target = sku_map.get(target_id)
                if target is None:
                    continue
                src_zone = item.temperature_zone or TemperatureZone.NORMAL
                tgt_zone = target.temperature_zone or TemperatureZone.NORMAL
                if src_zone != tgt_zone:
                    raise RuleConflictError(
                        f"must_ship_with 与温区隔离冲突: "
                        f"{item.sku_id}({src_zone.value}) 必须与 "
                        f"{target_id}({tgt_zone.value}) 同包，但温区不同",
                        conflicting_skus=[item.sku_id, target_id],
                    )
                # 检查危险品冲突
                src_hazmat = item.hazmat_type or HazmatType.NONE
                tgt_hazmat = target.hazmat_type or HazmatType.NONE
                if src_hazmat != HazmatType.NONE and tgt_hazmat == HazmatType.NONE:
                    raise RuleConflictError(
                        f"must_ship_with 与危险品隔离冲突: "
                        f"危险品 {item.sku_id} 必须与普通品 {target_id} 同包",
                        conflicting_skus=[item.sku_id, target_id],
                    )
                if tgt_hazmat != HazmatType.NONE and src_hazmat == HazmatType.NONE:
                    raise RuleConflictError(
                        f"must_ship_with 与危险品隔离冲突: "
                        f"普通品 {item.sku_id} 必须与危险品 {target_id} 同包",
                        conflicting_skus=[item.sku_id, target_id],
                    )

    def _bind_gifts(
        self, sub_groups: list[list[SKUItem]]
    ) -> list[list[SKUItem]]:
        """将赠品绑定到包含非赠品的子组中。

        赠品优先绑定到同一子组中已有非赠品的组。
        如果赠品单独在一个组中，将其合并到第一个包含非赠品的组。
        """
        gift_only_groups: list[list[SKUItem]] = []
        normal_groups: list[list[SKUItem]] = []

        for group in sub_groups:
            has_non_gift = any(not item.is_gift for item in group)
            if has_non_gift:
                normal_groups.append(group)
            else:
                gift_only_groups.append(group)

        # 将纯赠品组合并到第一个普通组
        if gift_only_groups and normal_groups:
            for gift_group in gift_only_groups:
                normal_groups[0].extend(gift_group)
        elif gift_only_groups and not normal_groups:
            # 全是赠品，保持原样
            normal_groups = gift_only_groups

        return normal_groups

    def _split_fragile_from_heavy(
        self, sub_groups: list[list[SKUItem]]
    ) -> list[list[SKUItem]]:
        """软规则：将易碎品与重物（>3kg）拆到不同子组。"""
        result: list[list[SKUItem]] = []
        for group in sub_groups:
            fragile_items = [it for it in group if it.fragile_flag]
            heavy_non_fragile = [
                it for it in group
                if not it.fragile_flag and (it.weight or Decimal(0)) > Decimal("3")
            ]
            light_non_fragile = [
                it for it in group
                if not it.fragile_flag and (it.weight or Decimal(0)) <= Decimal("3")
            ]

            if fragile_items and heavy_non_fragile:
                # 拆分：易碎品 + 轻普通品一组，重物单独一组
                fragile_group = fragile_items + light_non_fragile
                if fragile_group:
                    result.append(fragile_group)
                result.append(heavy_non_fragile)
            else:
                result.append(group)
        return result

    @staticmethod
    def _gen_id() -> str:
        return f"GRP-{uuid.uuid4().hex[:8]}"
