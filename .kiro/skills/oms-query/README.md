# OMS Query Skill — OMS 全域强查询

> 迭代记录:
> - v8.0 (2026-04-08): 从 order_query 升级为 oms_query；对外统一 Skill 对内按能力域拆分
> - v4.0 (2026-04-08): 与需求规格 v5.0 对齐
> - v1.0 (2026-04-07): 初始版本

## 定位

oms_query 是 OMS Agent 的核心全域强查询 Skill，以订单为主入口，联动查询 OMS 全链路运营态信息。

对外是一个统一 Skill，对内按能力域拆分，由 OMSQueryEngine 统一编排。

## 架构

```
oms_query（统一 Skill 入口）
  │
  ├── OMSQueryEngine（顶层编排器）
  │     ├── ObjectResolver（多对象识别器）
  │     ├── QueryPlanBuilder（查询计划生成器）
  │     ├── StateAwarePlanExpander（状态感知增强器）
  │     ├── ProviderExecutor（Provider 执行器）
  │     └── ResultMerger（结果合并器）
  │
  ├── 能力域 Provider
  │     ├── OrderProvider        → 订单详情/状态/来源/商品/地址
  │     ├── InventoryProvider    → 库存/库存变动
  │     ├── WarehouseProvider    → 仓库列表/能力/限制
  │     ├── AllocationProvider   → 分仓结果/候选仓/解除分配
  │     ├── RuleProvider         → 路由规则/自定义规则/Hold规则/SKU仓规则
  │     ├── FulfillmentProvider  → 履约执行/仓内状态/包裹
  │     ├── ShipmentProvider     → 发运/追踪/ETA/签收
  │     ├── SyncProvider         → 发运同步/回传状态
  │     ├── EventProvider        → 时间线/日志/异常事件/拆单详情
  │     ├── IntegrationProvider  → 连接器/渠道/认证/能力/健康
  │     ├── BatchProvider        → 批量统计/列表查询
  │     └── KnowledgeProvider    → OMS 本体知识图谱检索
  │
  └── 共享基础设施（复用现有）
        ├── OMSAPIClient
        ├── QueryCache
        ├── StatusNormalizer
        └── errors.py
```

## 文件结构

```
oms-query/
├── SKILL.md              # Agent 指令
├── README.md             # 本文件
├── references/
│   ├── 需求规格.md        # v8.0 需求规格
│   └── api-reference.md  # API 接口参考
└── scripts/
    ├── query_oms.py      # CLI 入口
    └── oms_query_engine/  # 引擎包
```

## 下游消费者

| 下游 skill | 使用 oms_query 输出的内容 |
|-----------|-------------------------|
| order_analysis | 状态、异常、Hold、Deallocated、日志、规则、分仓上下文 |
| warehouse_allocation | 当前仓、规则链、库存、仓能力、候选仓 |
| shipping_rate | shipment、carrier、service、tracking |
| cartonization | 商品、数量、重量、尺寸 |
| integration_manage | connector detail、auth status、capability |
| Agent 直接展示 | OMS 全景信息 |

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
