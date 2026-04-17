"""Cost Engine — 数据模型

定义综合成本计算引擎的所有输入/输出 Pydantic 模型。
使用 Decimal 类型处理金额，避免浮点误差，所有金额保留 2 位小数。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, Field


# ── 输入模型 ──────────────────────────────────────────


class ScoreWeights(BaseModel):
    """评分权重"""
    w_cost: Decimal = Decimal("0.40")
    w_eta: Decimal = Decimal("0.30")
    w_ontime: Decimal = Decimal("0.15")
    w_cap: Decimal = Decimal("0.15")


class PlanInput(BaseModel):
    """单个方案输入"""
    plan_id: str                                    # 方案标识
    plan_name: str = ""                             # 方案名称
    freight_order: Decimal = Decimal("0")           # 订单运费
    cost_warehouse: Decimal = Decimal("0")          # 仓操费
    cost_transfer: Decimal = Decimal("0")           # 调拨费
    n_warehouses: int = 1                           # 发货仓数量
    capacity_utilization: Decimal = Decimal("0")    # 仓容量利用率 (0~1)
    cost_risk: Decimal = Decimal("0")               # 风险成本
    eta_hours: Decimal = Decimal("0")               # 预估送达时间（小时）
    on_time_probability: Decimal = Decimal("0")     # 准时送达概率 (0~1)
    remain_capacity_pct: Decimal | None = None      # 剩余容量百分比 (0~1)，None 时自动计算


class CostRequest(BaseModel):
    """综合成本计算请求"""
    plans: list[PlanInput] = Field(default_factory=list)
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    split_penalty_unit: Decimal = Decimal("5")      # 拆单惩罚单价（元/仓）
    sla_hours: Decimal = Decimal("72")              # SLA 时限
    # 归一化参考范围（可选，不指定则使用方案集内 min-max）
    cost_ref_max: Decimal | None = None             # 成本归一化参考最大值
    eta_ref_max: Decimal | None = None              # 时效归一化参考最大值


# ── 输出模型 ──────────────────────────────────────────


class CostBreakdown(BaseModel):
    """成本明细"""
    freight_order: Decimal = Decimal("0")
    cost_warehouse: Decimal = Decimal("0")
    cost_transfer: Decimal = Decimal("0")
    penalty_split: Decimal = Decimal("0")
    penalty_capacity: Decimal = Decimal("0")
    cost_risk: Decimal = Decimal("0")
    cost_total: Decimal = Decimal("0")


class NormalizedScores(BaseModel):
    """归一化后的各维度分数"""
    cost_score: Decimal = Decimal("0")       # 成本归一化（越低越好→越高分）
    eta_score: Decimal = Decimal("0")        # 时效归一化（越快越好→越高分）
    ontime_score: Decimal = Decimal("0")     # 准时率（直接使用）
    capacity_score: Decimal = Decimal("0")   # 容量（直接使用）


class ScoreBreakdown(BaseModel):
    """评分明细"""
    normalized: NormalizedScores = Field(default_factory=NormalizedScores)
    weighted_cost: Decimal = Decimal("0")
    weighted_eta: Decimal = Decimal("0")
    weighted_ontime: Decimal = Decimal("0")
    weighted_cap: Decimal = Decimal("0")
    score: Decimal = Decimal("0")


class PlanResult(BaseModel):
    """单方案结果"""
    plan_id: str
    plan_name: str = ""
    rank: int = 0
    recommended: bool = False
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    score: Decimal = Decimal("0")
    eta_hours: Decimal = Decimal("0")
    on_time_probability: Decimal = Decimal("0")
    on_time_risk: bool = False
    explanation: str = ""


class CostResult(BaseModel):
    """综合成本计算结果"""
    success: bool = True
    plans: list[PlanResult] = Field(default_factory=list)
    recommended_plan_id: str = ""
    weights_used: ScoreWeights = Field(default_factory=ScoreWeights)
    degraded: bool = False
    degraded_fields: list[str] = Field(default_factory=list)
    confidence: str = "high"
    explanation: str = ""
    errors: list[str] = Field(default_factory=list)
