# 实施计划：OMS 全域强查询引擎（oms_query_engine）

## 概述

基于现有 order_query_engine 做演进式重构，升级为 oms_query_engine。
核心变化：顶层编排器 + 11 个能力域 Provider + models 拆包。
复用现有 api_client / cache / config / errors / status_normalizer。

## 任务列表

- [x] 1. 项目结构重组与 models 拆包
  - [x] 1.1 创建 oms_query_engine/ 新包结构
  - [x] 1.2 拆分 models.py 为 models/ 包
  - [x] 1.3 升级 status_normalizer.py
  - [x] 1.4 升级 errors.py

- [x] 2. 检查点 - models 拆包完成

- [x] 3. Provider 基类与核心 Provider 实现
  - [x] 3.1 实现 BaseProvider 接口
  - [x] 3.2 实现 OrderProvider
  - [x] 3.3 实现 EventProvider
  - [x] 3.4 实现 InventoryProvider
  - [x] 3.5 实现 WarehouseProvider
  - [x] 3.6 实现 AllocationProvider
  - [x] 3.7 实现 RuleProvider

- [x] 4. 检查点 - 核心 Provider 实现完成

- [x] 5. 扩展 Provider 实现
  - [x] 5.1 实现 FulfillmentProvider
  - [x] 5.2 实现 ShipmentProvider
  - [x] 5.3 实现 SyncProvider
  - [x] 5.4 实现 IntegrationProvider（独立于订单链路）
  - [x] 5.5 实现 BatchProvider（独立于单单查询链路）

- [x] 6. 检查点 - 全部 11 个 Provider 实现完成

- [x] 7. 编排层实现
  - [x] 7.1 实现 ObjectResolver
  - [x] 7.2 实现 QueryPlanBuilder
  - [x] 7.3 实现 StateAwarePlanExpander
  - [x] 7.4 实现 ProviderExecutor
  - [x] 7.5 实现 ResultMerger
  - [x] 7.6 实现 OMSQueryEngine (engine_v2.py)

- [x] 8. 检查点 - 编排层实现完成，端到端流程可跑通

- [x] 9. CLI 重构与测试
  - [x] 9.1 重构 query_oms.py 使用 OMSQueryEngine
  - [x] 9.2 编写 Provider 单元测试（11 个 Provider 全覆盖）
  - [x] 9.3 编写编排层测试（ObjectResolver / QueryPlanBuilder / StateAwarePlanExpander）
  - [x] 9.4 编写 OMSQueryEngine 端到端集成测试（mock API）
  - [x] 9.5 编写 StatusNormalizer v2 测试（含 is_deallocated 三者互斥）
  - [x] 9.6 编写 models 包导入和序列化测试

- [x] 10. 最终检查点 - 全部 103 个测试通过

## 备注

- 标记 `*` 的子任务为可选任务
- 复用现有 api_client / cache / config / errors / status_normalizer，减少重复工作
- Provider 实现可并行开发
- 集成中心 API 具体接口名待前端扫描确认后补充
