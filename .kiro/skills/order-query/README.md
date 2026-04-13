# Order Query Skill — 订单全景查询

> 迭代记录:
> - v3.0 (2026-04-08): 基于需求规格 v4.0 同步；新增查询降级矩阵、反查链路、Shipping Mapping 定位、订单类型、批量查询、缓存策略
> - v2.0 (2026-04-08): 从摘要查询升级为订单全景强查询（12 项能力）
> - v1.0 (2026-04-07): 初始版本

OMS Agent 的核心查询 skill，围绕订单及其关联对象做多源查询、状态归一化和查询级解释。

## 定位

order_query 不是只查一个接口，而是让用户一次性了解：
- 订单当前状态、卡在哪一步
- 是否异常、是否暂停履约（Exception ≠ Hold）
- 命中了什么规则、为什么分到这个仓
- shipment / tracking 状态
- 库存 / 仓库对订单的影响
- 最近关键事件

它负责"查清楚 + 解释当前现象"，不负责"深层根因分析"和"推荐决策"。

## 目录结构

```
order-query/
├── SKILL.md              # Agent 指令（查询规则、翻译表、输出模板、行为准则）
├── README.md             # 本文件
├── scripts/
│   └── query_oms.py      # OMS API 调用脚本
└── references/
    ├── 需求规格.md         # 完整需求文档（v3.0）
    └── api-reference.md   # OMS 接口参考
```

## 12 项核心能力

| 编号 | 能力 |
|------|------|
| OQ-1 | 多单号类型识别（orderNo / shipmentNo / trackingNo / eventId） |
| OQ-2 | 订单主查询 |
| OQ-3 | shipment 查询 |
| OQ-4 | 库存查询 |
| OQ-5 | 仓库查询 |
| OQ-6 | 分仓结果查询 |
| OQ-7 | 分仓规则查询 |
| OQ-8 | 异常查询 |
| OQ-9 | 暂停履约查询（Hold ≠ Exception） |
| OQ-10 | 关键事件查询 |
| OQ-11 | 查询级解释 |
| OQ-12 | 结果结构化输出 |

## 当前实现状态

基于前后端代码完整扫描，order_query 的 12 项能力全部有对应 API：

| 能力 | 当前支持度 | 关键 API |
|------|-----------|---------|
| 多单号类型识别 | ✅ | POST tracking-assistant/search-order-no |
| 订单主查询 | ✅ | GET sale-order/{orderNo} |
| shipment 查询 | ✅ | GET shipment/detail, tracking-assistant/tracking-status |
| 库存查询 | ✅ | POST inventory/list |
| 仓库查询 | ✅ | POST facility/v2/page |
| 分仓结果查询 | ✅ | GET dispatch/recover/query/{orderNo} |
| 分仓规则查询 | ✅ | GET routing/v2/rules, routing/v2/custom-rule |
| 异常查询 | ✅ | GET orderLog/list + sale-order/{orderNo} |
| 暂停履约查询 | ✅ | GET hold-rule-data/page |
| 关键事件查询 | ✅ | GET payment/time-line/{orderNo}, orderLog/list |
| 查询级解释 | ✅ | 组合以上 API 结果 |
| 结构化输出 | ✅ | 脚本实现 |

## 使用方式

```bash
# 安装依赖
pip install requests

# 查询拆单日志
python scripts/query_oms.py --event-id {eventId}

# 输出原始 JSON
python scripts/query_oms.py --event-id {eventId} --raw
```

## 下游消费者

| 下游 skill | 使用 order_query 输出的什么 |
|-----------|-------------------------|
| order_analysis | 状态、异常、Hold、规则命中、关键事件 |
| warehouse_allocation | 当前仓、候选仓、规则链、库存和仓能力 |
| shipping_rate | shipment、carrier、service |
| eta | shipment、服务、仓库 |
| cost | 仓库、shipment、服务、库存影响 |
| Agent 直接展示 | 订单全景信息 |
