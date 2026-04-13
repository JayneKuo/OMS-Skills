"""OMS 全域查询引擎 - 数据模型包"""

# 请求模型
from .request import QueryRequest, BatchQueryRequest
# 标识解析模型
from .resolve import QueryInput, ResolveResult
# 状态模型
from .status import StatusMapping, NormalizedStatus
# 查询计划模型
from .query_plan import QueryPlan, QueryContext
# Provider 结果模型
from .provider_result import ProviderResult
# 订单域
from .order import OrderIdentity, SourceInfo, OrderContext, CurrentStatus, ProductInfo, ProductItem, ShippingAddress
# 库存域
from .inventory import InventoryInfo, SkuInventoryItem
# 仓库域
from .warehouse import WarehouseInfo
# 分仓域
from .allocation import AllocationInfo, WarehouseDecisionExplanation, DeallocationDetailInfo
# 规则域
from .rule import RuleInfo
# 履约域
from .fulfillment import WarehouseExecutionInfo, WarehouseStatusInfo
# 发运域
from .shipment import ShipmentInfo, TrackingProgressInfo
# 同步域
from .sync import ShipmentSyncInfo, SyncTarget
# 事件域
from .event import EventInfo, MilestoneTimes, DurationMetrics
# 集成域
from .integration import IntegrationInfo, ConnectorSummary, ConnectorDetail
# 批量域
from .batch import BatchQueryResult
# 解释模型
from .explanation import QueryExplanation, HoldDetailInfo, ExceptionDetailInfo
# 顶层输出
from .result import OMSQueryResult, DataCompleteness

# 向后兼容：旧模型名映射
OrderItem = ProductItem
OrderQueryResult = OMSQueryResult

__all__ = [
    "QueryRequest", "BatchQueryRequest",
    "QueryInput", "ResolveResult",
    "StatusMapping", "NormalizedStatus",
    "QueryPlan", "QueryContext",
    "ProviderResult",
    "OrderIdentity", "SourceInfo", "OrderContext", "CurrentStatus",
    "ProductInfo", "ProductItem", "ShippingAddress",
    "InventoryInfo", "SkuInventoryItem",
    "WarehouseInfo",
    "AllocationInfo", "WarehouseDecisionExplanation", "DeallocationDetailInfo",
    "RuleInfo",
    "WarehouseExecutionInfo", "WarehouseStatusInfo",
    "ShipmentInfo", "TrackingProgressInfo",
    "ShipmentSyncInfo", "SyncTarget",
    "EventInfo", "MilestoneTimes", "DurationMetrics",
    "IntegrationInfo", "ConnectorSummary", "ConnectorDetail",
    "BatchQueryResult",
    "QueryExplanation", "HoldDetailInfo", "ExceptionDetailInfo",
    "OMSQueryResult", "DataCompleteness",
    "OrderItem", "OrderQueryResult",
]
