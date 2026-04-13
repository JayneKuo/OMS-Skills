# 设计文档：OMS 全域强查询引擎（oms_query_engine）

## 概述

oms_query_engine 是 OMS Agent 的核心全域查询引擎，以独立 Python 包形式实现。
对外是一个统一的 `oms_query` Skill，对内按能力域拆分为 11 个 Provider，
由 `OMSQueryEngine` 统一编排。

### 设计目标

1. **顶层只编排**：OMSQueryEngine 不做底层字段拼装，只负责流水线调度
2. **Provider 自治**：每个 Provider 只负责本域查询和子结果标准化
3. **集成独立**：IntegrationProvider 不污染订单链路
4. **批量独立**：BatchProvider 不混入单单查询复杂链路
5. **模型拆包**：models.py 拆为 models/ 包，每个域一个子模块
6. **演进式重构**：基于现有 api_client/cache/errors/status_normalizer 做增量升级

### 技术栈

- 语言：Python 3.11+
- 数据模型：Pydantic v2
- HTTP 客户端：requests
- 测试：pytest + hypothesis
- 无外部框架依赖

## 架构

### 系统上下文

```
用户输入（订单号/SKU/仓库/连接器/自然语言）
  → 【OMSQueryEngine】
  → OMSQueryResult
  → 下游 skill / Agent 展示
```

### 执行流水线

```
输入
  → ObjectResolver        识别输入对象类型和主键
  → QueryPlanBuilder      根据对象类型+意图生成查询计划
  → StateAwarePlanExpander 根据核心查询结果中的状态自动扩展计划
  → ProviderExecutor      按计划调度各 Provider 执行查询
  → ResultMerger          合并各 Provider 子结果为 OMSQueryResult
  → 输出
```

### 模块划分

```
oms_query_engine/
├── __init__.py
├── engine.py                    # OMSQueryEngine 顶层编排
├── object_resolver.py           # ObjectResolver 多对象识别
├── query_plan_builder.py        # QueryPlanBuilder 查询计划生成
├── state_aware_plan_expander.py # StateAwarePlanExpander 状态感知增强
├── provider_executor.py         # ProviderExecutor 统一执行器
├── result_merger.py             # ResultMerger 结果合并
│
├── providers/                   # 能力域 Provider
│   ├── __init__.py
│   ├── base.py                  # BaseProvider 接口定义
│   ├── order.py                 # OrderProvider
│   ├── inventory.py             # InventoryProvider
│   ├── warehouse.py             # WarehouseProvider
│   ├── allocation.py            # AllocationProvider
│   ├── rule.py                  # RuleProvider
│   ├── fulfillment.py           # FulfillmentProvider
│   ├── shipment.py              # ShipmentProvider
│   ├── sync.py                  # SyncProvider
│   ├── event.py                 # EventProvider
│   ├── integration.py           # IntegrationProvider
│   └── batch.py                 # BatchProvider
│
├── models/                      # 拆分后的数据模型包
│   ├── __init__.py              # 统一导出
│   ├── request.py               # 请求模型
│   ├── resolve.py               # 标识解析模型
│   ├── status.py                # 状态模型
│   ├── query_plan.py            # 查询计划模型
│   ├── provider_result.py       # Provider 子结果模型
│   ├── order.py                 # 订单域输出模型
│   ├── inventory.py             # 库存域输出模型
│   ├── warehouse.py             # 仓库域输出模型
│   ├── allocation.py            # 分仓域输出模型
│   ├── rule.py                  # 规则域输出模型
│   ├── fulfillment.py           # 履约域输出模型
│   ├── shipment.py              # 发运域输出模型
│   ├── sync.py                  # 同步域输出模型
│   ├── event.py                 # 事件域输出模型
│   ├── integration.py           # 集成域输出模型
│   ├── batch.py                 # 批量域输出模型
│   ├── explanation.py           # 查询级解释模型
│   └── result.py                # OMSQueryResult 顶层输出模型
│
├── api_client.py                # 复用现有，无需改动
├── cache.py                     # 复用现有，无需改动
├── config.py                    # 复用现有，微调
├── errors.py                    # 复用现有，增加新错误类型
└── status_normalizer.py         # 复用现有，增加 is_deallocated
```


## 组件与接口

### 1. OMSQueryEngine（顶层编排器）

```python
class OMSQueryEngine:
    """OMS 全域查询引擎主入口。只负责编排，不做底层字段拼装。"""

    def __init__(self, config: EngineConfig | None = None):
        self._config = config or EngineConfig()
        self._client = OMSAPIClient(self._config)
        self._cache = QueryCache()
        self._resolver = ObjectResolver(self._client, self._cache)
        self._plan_builder = QueryPlanBuilder()
        self._plan_expander = StateAwarePlanExpander()
        self._executor = ProviderExecutor(self._client, self._cache)
        self._merger = ResultMerger(StatusNormalizer())

    def query(self, request: QueryRequest) -> OMSQueryResult:
        """
        主查询入口。流水线：
        1. ObjectResolver.resolve(input) → ResolveResult
        2. QueryPlanBuilder.build(resolve_result, intent) → QueryPlan
        3. ProviderExecutor.execute_core(plan) → core_results
        4. StateAwarePlanExpander.expand(plan, core_results) → expanded_plan
        5. ProviderExecutor.execute_extended(expanded_plan) → all_results
        6. ResultMerger.merge(all_results) → OMSQueryResult
        """
        ...

    def query_batch(self, request: BatchQueryRequest) -> BatchQueryResult:
        """批量查询，直接委托 BatchProvider，不走单单链路。"""
        ...
```

### 2. ObjectResolver（多对象识别器）

```python
class ObjectResolver:
    """
    识别输入对象类型。升级自 IdentifierResolver。
    新增 SKU / 仓库 / 连接器 / 规则 / 批量 识别。
    """

    def resolve(self, input_value: str, hint: str | None = None) -> ResolveResult:
        """
        识别输入类型并解析主键。
        返回 ResolveResult：
          - primary_object_type: order / sku / warehouse / connector / rule / batch
          - resolved_primary_key: 解析后的主键
          - identified_type: 具体标识类型（orderNo/shipmentNo/...）
        """
        ...
```

### 3. QueryPlanBuilder（查询计划生成器）

```python
class QueryPlanBuilder:
    """根据对象类型和用户意图生成查询计划。"""

    def build(self, resolve_result: ResolveResult,
              query_intent: str) -> QueryPlan:
        """
        生成查询计划。QueryPlan 包含：
          - core_providers: list[str]     # 必须执行的 Provider 列表
          - extended_providers: list[str]  # 按需执行的 Provider 列表
          - primary_object_type: str
          - primary_key: str
          - context: dict                  # 传递给 Provider 的上下文
        
        规则：
          - order 类 → core = [OrderProvider, EventProvider]
          - sku 类 → core = [InventoryProvider]
          - warehouse 类 → core = [WarehouseProvider]
          - connector 类 → core = [IntegrationProvider]
          - batch 类 → core = [BatchProvider]
          - 意图关键词 → 追加对应 extended_providers
        """
        ...
```

### 4. StateAwarePlanExpander（状态感知增强器）

```python
class StateAwarePlanExpander:
    """根据核心查询结果中的订单状态，自动扩展查询计划。"""

    def expand(self, plan: QueryPlan,
               core_results: dict[str, ProviderResult]) -> QueryPlan:
        """
        状态感知增强：
          - Shipped/Partially shipped → 追加 ShipmentProvider, SyncProvider
          - On Hold → 追加 RuleProvider(hold), AllocationProvider
          - Exception → 追加 EventProvider(dispatch-log)
          - Deallocated → 追加 AllocationProvider, EventProvider
        
        只追加尚未在计划中的 Provider。
        """
        ...
```

### 5. ProviderExecutor（统一执行器）

```python
class ProviderExecutor:
    """按查询计划调度各 Provider 执行查询。"""

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._providers: dict[str, BaseProvider] = {
            "order": OrderProvider(client, cache),
            "inventory": InventoryProvider(client, cache),
            "warehouse": WarehouseProvider(client, cache),
            "allocation": AllocationProvider(client, cache),
            "rule": RuleProvider(client, cache),
            "fulfillment": FulfillmentProvider(client, cache),
            "shipment": ShipmentProvider(client, cache),
            "sync": SyncProvider(client, cache),
            "event": EventProvider(client, cache),
            "integration": IntegrationProvider(client, cache),
            "batch": BatchProvider(client, cache),
        }

    def execute(self, plan: QueryPlan) -> dict[str, ProviderResult]:
        """
        按计划执行 Provider。
        先执行 core_providers，再执行 extended_providers。
        每个 Provider 失败不阻断其他 Provider。
        返回 {provider_name: ProviderResult}。
        """
        ...
```

### 6. ResultMerger（结果合并器）

```python
class ResultMerger:
    """合并各 Provider 子结果为 OMSQueryResult。"""

    def __init__(self, normalizer: StatusNormalizer):
        self._normalizer = normalizer

    def merge(self, results: dict[str, ProviderResult],
              resolve_result: ResolveResult) -> OMSQueryResult:
        """
        合并逻辑：
        1. 每个 Provider 的 ProviderResult.data 直接映射到 OMSQueryResult 对应字段
        2. 状态归一化（从 OrderProvider 结果中提取 status_code）
        3. 生成查询级解释
        4. 评估数据完整度
        5. 合并 called_apis / failed_apis
        """
        ...

    def _build_explanation(self, results: dict[str, ProviderResult],
                           status: NormalizedStatus) -> QueryExplanation:
        """生成查询级解释，仅描述现象。"""
        ...

    def _assess_completeness(self,
                             results: dict[str, ProviderResult]) -> DataCompleteness:
        """评估数据完整度。"""
        ...
```

### 7. BaseProvider（Provider 接口）

```python
class BaseProvider(ABC):
    """所有 Provider 的基类。"""

    def __init__(self, client: OMSAPIClient, cache: QueryCache):
        self._client = client
        self._cache = cache

    @abstractmethod
    def query(self, context: QueryContext) -> ProviderResult:
        """
        执行本域查询。
        - context: 包含 primary_key, merchant_no, order_detail(可选), intents
        - 返回 ProviderResult: data(域特定 Pydantic 模型), called_apis, failed_apis, errors
        """
        ...
```


## Provider 职责清单

### OrderProvider
- API: sale-order/{orderNo}, search-order-no
- 输出: OrderIdentity, SourceInfo, OrderContext, CurrentStatus, ProductInfo, ShippingAddress
- 从订单详情中提取所有订单级字段

### InventoryProvider
- API: inventory/list, inventory/movement-history
- 输出: InventoryInfo（SKU 库存、可用/占用/实物、变动摘要）
- 依赖: merchantNo + sku（从 OrderProvider 结果或直接输入获取）

### WarehouseProvider
- API: facility/v2/page
- 输出: WarehouseInfo（仓库列表、能力、限制、地址）
- 依赖: merchantNo

### AllocationProvider
- API: dispatch/recover/query/{orderNo}, dispatch/hand/item/{orderNo}
- 输出: AllocationInfo, WarehouseDecisionExplanation, DeallocationDetailInfo
- 依赖: orderNo

### RuleProvider
- API: routing/v2/rules, routing/v2/custom-rule, sku-warehouse/page, hold-rule-data/page, mapping/single
- 输出: RuleInfo（路由规则、自定义规则、Hold 规则、SKU 仓规则、映射规则）
- 依赖: merchantNo

### FulfillmentProvider
- API: tracking-assistant/fulfillment-orders/{orderNo}, shipment/detail
- 输出: WarehouseExecutionInfo, WarehouseStatusInfo
- 依赖: orderNo

### ShipmentProvider
- API: tracking-assistant/{orderNo}, tracking-status/{orderNo}, shipment/detail
- 输出: ShipmentInfo, TrackingProgressInfo
- 依赖: orderNo

### SyncProvider
- API: shipment sync 相关字段/日志
- 输出: ShipmentSyncInfo
- 依赖: orderNo / shipmentNo

### EventProvider
- API: orderLog/list, payment/time-line/{orderNo}, dispatch-log/{eventId}
- 输出: EventInfo, MilestoneTimes, DurationMetrics
- 依赖: orderNo, eventId（从日志中提取）

### IntegrationProvider
- API: connector list, connector detail, capability, auth, test connection, sync logs, catalog
- 输出: IntegrationInfo
- 依赖: connectorKey / merchantNo
- 完全独立于订单链路

### BatchProvider
- API: sale-order/status/num, sale-order/page
- 输出: BatchQueryResult
- 依赖: merchantNo, status_filter, page 参数
- 完全独立于单单查询链路

## 数据模型拆分

### models/ 包结构

每个域一个文件，顶层 `__init__.py` 统一导出：

```python
# models/__init__.py
from .request import QueryRequest, BatchQueryRequest
from .resolve import QueryInput, ResolveResult
from .status import StatusMapping, NormalizedStatus
from .query_plan import QueryPlan, QueryContext
from .provider_result import ProviderResult
from .order import OrderIdentity, SourceInfo, OrderContext, CurrentStatus, ProductInfo, ProductItem
from .inventory import InventoryInfo, SkuInventoryItem
from .warehouse import WarehouseInfo
from .allocation import AllocationInfo, WarehouseDecisionExplanation, DeallocationDetailInfo
from .rule import RuleInfo
from .fulfillment import WarehouseExecutionInfo, WarehouseStatusInfo
from .shipment import ShipmentInfo, TrackingProgressInfo
from .sync import ShipmentSyncInfo, SyncTarget
from .event import EventInfo, MilestoneTimes, DurationMetrics
from .integration import IntegrationInfo, ConnectorSummary, ConnectorDetail
from .batch import BatchQueryResult
from .explanation import QueryExplanation, HoldDetailInfo, ExceptionDetailInfo
from .result import OMSQueryResult, DataCompleteness
```

### 关键新增模型

```python
# models/query_plan.py
class QueryPlan(BaseModel):
    """查询计划。"""
    primary_object_type: str          # order / sku / warehouse / connector / rule / batch
    primary_key: str | None = None
    core_providers: list[str]         # 必须执行的 Provider 名称列表
    extended_providers: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)  # merchantNo, orderNo, sku 等

class QueryContext(BaseModel):
    """传递给 Provider 的查询上下文。"""
    primary_key: str | None = None
    merchant_no: str | None = None
    order_no: str | None = None
    order_detail: dict | None = None  # OrderProvider 的结果，供下游 Provider 使用
    event_ids: list[str] = Field(default_factory=list)
    skus: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)

# models/provider_result.py
class ProviderResult(BaseModel):
    """Provider 统一返回结构。"""
    provider_name: str
    success: bool = False
    data: Any = None                  # 域特定 Pydantic 模型实例
    called_apis: list[str] = Field(default_factory=list)
    failed_apis: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
```

## 现有代码迁移策略

| 现有模块 | 迁移方式 | 改动量 |
|---------|---------|--------|
| api_client.py | 直接复用，零改动 | 无 |
| cache.py | 直接复用，零改动 | 无 |
| config.py | 直接复用，零改动 | 无 |
| errors.py | 复用 + 新增 ObjectResolveError | 小 |
| status_normalizer.py | 复用 + 增加 is_deallocated 字段 | 小 |
| identifier_resolver.py | 升级为 object_resolver.py | 中（增加 SKU/仓库/连接器识别） |
| query_orchestrator.py | 拆分为 QueryPlanBuilder + StateAwarePlanExpander + ProviderExecutor | 大（但逻辑复用） |
| result_assembler.py | 拆分为各 Provider 内部 + ResultMerger | 大（但逻辑复用） |
| models.py | 拆分为 models/ 包 | 大（纯结构重组，逻辑不变） |
| engine.py | 重写为新的 OMSQueryEngine | 中（编排逻辑简化） |

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Provider 粒度 | 11 个 Provider | 每个对应一个业务域，职责清晰 |
| Provider 接口 | 统一 BaseProvider.query(context) → ProviderResult | 编排器不需要知道 Provider 内部实现 |
| 查询计划 | 显式 QueryPlan 对象 | 可审计、可测试、可扩展 |
| 状态感知增强 | 独立 StateAwarePlanExpander | 与计划生成解耦，易于增加新状态规则 |
| 集成中心 | 独立 IntegrationProvider | 不污染订单链路，API 体系完全不同 |
| 批量查询 | 独立 BatchProvider + engine.query_batch() | 不混入单单查询复杂链路 |
| models 拆包 | models/ 包 + __init__.py 统一导出 | 避免单文件膨胀，外部 import 不变 |
| 结果合并 | ResultMerger 只做字段映射 + 解释生成 + 完整度评估 | 不做底层字段拼装 |
