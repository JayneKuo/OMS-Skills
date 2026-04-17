# Shipping Rate Skill — 运费映射与承运商推荐 + 运费计算引擎

> v2.0 (2026-04-18): 新增运费计算引擎（RateEngine），支持 4 种计费模式、8 种附加费、DefaultUSRateProvider
> v1.0 (2026-04-16): MVP 版本，映射查询 + 条件执行 + 规则匹配 + 承运商推荐

## 定位

shipping_rate 是 OMS Agent 的运费映射与承运商推荐 + 运费计算 Skill，包含两部分：
- Part 1（v1.0）：基于 OMS 三层映射规则体系（一对一映射 → 条件映射 → Shipping Mapping），为订单推荐最优承运商和服务方式
- Part 2（v2.0）：基于承运商价格表，计算包裹级和订单级运费，支持 4 种计费模式、8 种附加费、促销减免

## 架构

### Part 1: 映射规则引擎（v1.0）

```
ShippingRateEngine（顶层编排器）
  ├── DataLoader              # 加载映射规则、渠道、订单数据
  │     ├── 一对一映射查询     # GET /mapping/list
  │     ├── 条件映射查询       # GET /mapping/condition
  │     ├── Shipping Mapping 规则查询  # GET /mapping/multiple/rule/page
  │     ├── 比价策略查询       # GET /rate-shopping/rate-shopping/page
  │     └── 渠道查询           # GET /channel（共享能力）
  ├── MappingResolver         # 映射解析
  │     ├── 一对一映射解析     # SKU/Carrier/ShipMethod/DeliveryService/FreightTerm
  │     └── 条件映射解析       # 多条件→输出
  ├── RuleExecutor            # 规则执行
  │     ├── 条件映射执行       # POST /mapping/condition/execute
  │     └── Shipping Mapping 执行  # POST /mapping/condition/multi
  ├── Recommender             # 承运商推荐
  │     ├── 规则匹配排序
  │     ├── 推荐理由生成
  │     └── 降级处理
  └── ResultBuilder           # 结果构建 + 白盒解释
```

### Part 2: 运费计算引擎（v2.0 新增）

```
RateEngine（运费计算顶层编排器）
  ├── ZoneResolver            # 计费区域解析（省/市/区三级匹配）
  ├── RateCalculator          # 基础运费计算（4 种计费模式）
  ├── SurchargeCalculator     # 附加费计算（8 种附加费，5 步叠加）
  ├── RateAggregator          # 订单级运费汇总 + 促销减免
  └── RateProvider（抽象层）   # 运费数据提供者
        ├── LocalRateProvider         # 基于本地价格表计算
        ├── DefaultUSRateProvider     # 美国公开牌价降级估算（兜底）
        └── ExternalRateProvider      # 第三方承运商 API 扩展点（预留）
```

#### DefaultUSRateProvider

内置美国市场三大承运商（UPS Ground / FedEx Ground / USPS Priority Mail）的公开牌价，
作为无签约价格表时的降级估算方案。结果标注 `degraded=True`、`confidence="estimated"`，
并提示实际签约价通常有 30-70% 折扣。

#### 4 种基础运费计费模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| 首重+续重 | 首重 N kg 收费 A 元，超出部分每 M kg 收费 B 元 | 快递（最常用） |
| 阶梯重量 | 按重量区间分段计费，每个区间不同单价 | 零担物流 |
| 体积计费 | 按体积（立方米）计费，单价 × 体积 | 泡货/轻抛货 |
| 固定费用 | 不论重量体积，固定收费 | 同城配送、特殊线路 |

#### 8 种附加费

| 编号 | 类型 | 触发条件 |
|------|------|----------|
| 1 | 偏远地区 | 收货地址在偏远地区列表中 |
| 2 | 超重 | 单包裹计费重量 > 超重阈值 |
| 3 | 超尺寸 | 单包裹最长边 > 超尺寸阈值 |
| 4 | 燃油 | 始终触发，基础运费 × 燃油费率 |
| 5 | 节假日 | 发货日或送达日在节假日期间 |
| 6 | 保价 | 商品声明价值 > 保价阈值 |
| 7 | 冷链 | 包裹包含冷藏/冷冻商品 |
| 8 | 上楼 | 大件商品且收货地址无电梯 |


## OMS 映射规则体系

### 第一层：一对一映射（OneToOneMapping）
简单的值→值映射，支持类型：
- SKU 映射（mappingType=1）
- UOM 映射（mappingType=2）
- ShipMethod 映射（mappingType=3）
- Carrier 映射（mappingType=4）
- DeliveryService 映射（mappingType=5）
- FreightTerm 映射（mappingType=6）
- ShipmentType 映射（mappingType=7）
- Reverse Carrier 映射（mappingType=101）

### 第二层：条件映射（ConditionMapping）
多条件输入→单输出映射，输入条件包括 SKU、承运商、服务方式等。

### 第三层：Shipping Mapping 规则
多条件→多输出的复杂规则，按渠道和优先级匹配，支持多组条件同时执行。

## 数据来源

### 映射规则数据（Part 1）
通过 oms_query_engine 的 API client 获取：
- 一对一映射：/mapping/list, /mapping/id
- 条件映射：/mapping/condition, /mapping/condition/id
- 条件映射执行：/mapping/condition/execute
- Shipping Mapping 执行：/mapping/condition/multi
- Shipping Mapping 规则：/mapping/multiple/rule/page
- 比价策略：/rate-shopping/rate-shopping/page
- 渠道信息：/channel（共享能力）

### 运费计算数据（Part 2）
- 承运商价格表（PriceTable）：由商户配置或系统导入，含区域映射和区域费率
- 附加费规则（SurchargeRuleSet）：由商户配置
- 促销规则（PromotionRule）：由运营配置
- DefaultUSRateProvider：内置美国三大承运商公开牌价，无需外部数据

## MCP Tools

| Tool | 说明 | 版本 |
|------|------|------|
| `shipping_rate_query(merchant_no, mapping_types, channel_no)` | 查询映射规则 | v1.0 |
| `shipping_rate_execute(merchant_no, channel_no, conditions)` | 执行映射规则匹配 | v1.0 |
| `shipping_rate_recommend(order_no, merchant_no, channel_no, sku_list)` | 承运商推荐 | v1.0 |
| `shipping_rate_calculate(packages, origin, destination, carrier, price_table, surcharge_rules, promotion_rules)` | 运费计算 | v2.0 |

详细需求规格见 [references/需求规格.md](references/需求规格.md)。
