"""枚举定义"""
from enum import Enum


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DataCompleteness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class Urgency(str, Enum):
    URGENT = "urgent"
    SUGGESTED = "suggested"
    OPTIONAL = "optional"


class ExceptionCategory(str, Enum):
    INVENTORY = "inventory"
    RULE = "rule"
    WAREHOUSE = "warehouse"
    SHIPMENT = "shipment"
    SYNC = "sync"
    SYSTEM = "system"


class HoldSource(str, Enum):
    RULE = "rule"
    MANUAL = "manual"
    SYSTEM = "system"


class InventoryHealthLevel(str, Enum):
    OUT_OF_STOCK = "out_of_stock"
    LOW = "low"
    NORMAL = "normal"
    OVERSTOCK = "overstock"
