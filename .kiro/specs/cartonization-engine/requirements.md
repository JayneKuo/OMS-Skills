# 需求文档：装箱计算引擎

## 简介

装箱计算引擎（Cartonization Engine）是智能分仓决策系统中的核心模块，位于候选仓确定之后、运费计算之前。该引擎接收订单 SKU 列表及其物理属性、可用箱型库和承运商限制，按照物理约束和业务规则将商品装入标准箱型，输出包裹列表及每个包裹的计费重量。装箱结果直接影响包裹数量（拆单惩罚）、计费重（运费）和承运商可用性（超规淘汰）。

## 术语表

- **Cartonization_Engine（装箱引擎）**：执行装箱计算的核心模块，接收 SKU 列表和箱型库，输出包裹方案
- **SKU**：最小库存管理单元，包含物理属性（长宽高、重量）和业务属性（温区、危险品类型等）
- **Box_Type（箱型）**：标准包装箱规格，包含内部尺寸、最大承重、箱型编号
- **Package（包裹）**：装箱输出的最小发货单元，包含 SKU 列表、箱型、计费重量
- **Billing_Weight（计费重量）**：取实际重量和体积重量中的较大值，用于运费计算
- **Volumetric_Weight（体积重量）**：箱型外部尺寸的长×宽×高除以体积因子得到的换算重量
- **Dim_Factor（体积因子）**：承运商定义的体积重量换算系数，快递通常为 6000，零担为 5000
- **Temperature_Zone（温区）**：SKU 的温度存储要求，取值为常温、冷藏、冷冻三种
- **Hazmat_Type（危险品类型）**：SKU 的危险品分类，取值为无、易燃、易爆、腐蚀
- **Fill_Rate（填充率）**：包裹内 SKU 总体积占箱型内部体积的百分比
- **FFD（First Fit Decreasing）**：首次适配递减算法，按体积从大到小排序后依次装入第一个能容纳的箱型
- **Pre_Grouping（预分组）**：装箱前按温区和禁混规则将 SKU 分为互斥组的过程
- **Hard_Rule（硬规则）**：不可违反的装箱约束，违反则装箱方案不合法
- **Fallback（回退）**：装箱失败时的降级处理策略
- **Carrier（承运商）**：提供物流运输服务的第三方，对包裹有重量和尺寸限制
- **Must_Ship_With（必须同包）**：SKU 级绑定关系，指定哪些 SKU 必须放在同一个包裹
- **Cannot_Ship_With（禁止同包）**：SKU 级互斥关系，指定哪些 SKU 不能放在同一个包裹

## 需求

### 需求 1：装箱输入验证

**用户故事：** 作为分仓决策系统，我需要装箱引擎验证所有输入数据的完整性和合法性，以便在装箱计算前发现数据问题并采取相应的降级或阻断策略。

#### 验收标准

1. WHEN Cartonization_Engine 接收到装箱请求，THE Cartonization_Engine SHALL 验证每个 SKU 的 sku_id、weight、length、width、height、temperature_zone 字段是否存在且类型正确
2. IF SKU 的 weight 或 length 或 width 或 height 字段缺失，THEN THE Cartonization_Engine SHALL 使用该 SKU 所属品类的平均值替代缺失字段，并在输出中标记该 SKU 为"数据降级"
3. IF SKU 的 temperature_zone 字段缺失，THEN THE Cartonization_Engine SHALL 将该 SKU 的 temperature_zone 默认设置为"常温"，并在输出中标记该 SKU 为"数据降级"
4. IF SKU 的 hazmat_type 字段缺失，THEN THE Cartonization_Engine SHALL 将该 SKU 的 hazmat_type 默认设置为"无"，并在输出中标记该 SKU 为"数据降级"
5. WHEN Cartonization_Engine 接收到装箱请求，THE Cartonization_Engine SHALL 验证可用箱型列表至少包含一个箱型，且每个箱型的内部尺寸和最大承重均为正数
6. IF 可用箱型列表为空，THEN THE Cartonization_Engine SHALL 返回装箱失败结果，错误码为 CARTON_FAILED，原因为"无可用箱型"

### 需求 2：预分组

**用户故事：** 作为装箱引擎，我需要在装箱计算前按温区和禁混规则将 SKU 分为互斥组，以便后续装箱过程中每组内的 SKU 可以安全地装入同一包裹。

#### 验收标准

1. WHEN Cartonization_Engine 执行预分组，THE Cartonization_Engine SHALL 将所有 SKU 按 temperature_zone 值（常温、冷藏、冷冻）分为不同的组，同一组内所有 SKU 的 temperature_zone 值相同
2. WHEN 某个 SKU 的 hazmat_type 不为"无"，THE Cartonization_Engine SHALL 将该 SKU 单独分为一组，该组仅包含该 SKU 的所有数量
3. WHEN 某个 SKU 的 cannot_ship_with 列表包含同一温区内其他 SKU 的 sku_id，THE Cartonization_Engine SHALL 将这些互斥的 SKU 分到不同的组中
4. WHEN 某个 SKU 的 must_ship_with 列表包含其他 SKU 的 sku_id，THE Cartonization_Engine SHALL 将这些绑定的 SKU 放入同一组中
5. IF must_ship_with 约束与 temperature_zone 隔离规则或 cannot_ship_with 约束产生冲突，THEN THE Cartonization_Engine SHALL 返回装箱失败结果，错误码为 CARTON_FAILED，原因为"规则冲突"，并记录冲突的具体 SKU 和规则
6. WHEN 订单配置 gift_same_package_required 为 true，THE Cartonization_Engine SHALL 将赠品 SKU（is_gift 为 true）与其关联的主商品 SKU 放入同一组中

### 需求 3：FFD 排序与装箱

**用户故事：** 作为装箱引擎，我需要在每个预分组内按 First Fit Decreasing 策略排序并装入箱型，以便高效利用箱型空间并减少包裹数量。

#### 验收标准

1. WHEN Cartonization_Engine 对一个预分组执行装箱，THE Cartonization_Engine SHALL 将该组内所有 SKU 按单件体积（length × width × height）从大到小排序
2. WHEN 多个 SKU 的单件体积相同，THE Cartonization_Engine SHALL 按单件重量从大到小作为次要排序条件
3. WHEN Cartonization_Engine 对排序后的 SKU 列表执行装箱，THE Cartonization_Engine SHALL 按顺序将每个 SKU 尝试放入第一个能容纳该 SKU 的已开箱型中，如果所有已开箱型均无法容纳，则开启一个新箱型
4. THE Cartonization_Engine SHALL 在判断箱型能否容纳 SKU 时，同时检查箱型剩余体积是否足够和箱型剩余承重是否足够

### 需求 4：箱型匹配与选择

**用户故事：** 作为装箱引擎，我需要为每个包裹选择最优箱型，以便在满足物理约束的前提下最小化计费重量和包材成本。

#### 验收标准

1. WHEN Cartonization_Engine 为一个包裹选择箱型，THE Cartonization_Engine SHALL 从可用箱型列表中筛选出内部尺寸能容纳该包裹所有 SKU 且最大承重不低于该包裹实际重量的箱型
2. WHEN 存在多个满足物理容纳条件的箱型，THE Cartonization_Engine SHALL 优先选择计费重量最低的箱型
3. WHEN 存在多个计费重量相同的箱型，THE Cartonization_Engine SHALL 优先选择包材成本最低的箱型
4. WHEN 存在多个计费重量和包材成本均相同的箱型，THE Cartonization_Engine SHALL 优先选择承运商兼容性最高的箱型
5. WHEN 选定箱型的外部尺寸超过承运商的 max_dimension 限制，THE Cartonization_Engine SHALL 排除该箱型并选择下一个满足条件的箱型
6. WHEN 包裹内包含 fragile_flag 为 true 的 SKU，THE Cartonization_Engine SHALL 仅选择支持防震填充的箱型

### 需求 5：多包拆分

**用户故事：** 作为装箱引擎，我需要在单个箱型无法容纳一组所有 SKU 时将该组拆分为多个包裹，以便每个包裹均满足重量和尺寸限制。

#### 验收标准

1. WHEN 一个预分组内所有 SKU 的总重量超过最大可用箱型的承重限制或承运商的 max_weight 限制（取两者较小值），THE Cartonization_Engine SHALL 将该组拆分为多个包裹，每个包裹的实际重量不超过该限制
2. WHEN 一个预分组内所有 SKU 的总体积超过最大可用箱型的内部体积，THE Cartonization_Engine SHALL 将该组拆分为多个包裹，每个包裹的 SKU 总体积不超过所选箱型的内部体积
3. WHEN 执行多包拆分，THE Cartonization_Engine SHALL 优先均匀分配重量，避免出现一个包裹接近满载而另一个包裹几乎为空的情况
4. WHEN 执行多包拆分，THE Cartonization_Engine SHALL 确保拆分后的包裹总数不超过订单配置的 max_package_count（默认为 5）
5. IF 拆分后的包裹总数超过 max_package_count，THEN THE Cartonization_Engine SHALL 返回装箱失败结果，错误码为 CARTON_FAILED，原因为"包裹数超限"

### 需求 6：填充率校验

**用户故事：** 作为装箱引擎，我需要校验每个包裹的填充率，以便避免使用过大的箱型造成空间浪费和体积重量虚高。

#### 验收标准

1. WHEN Cartonization_Engine 完成装箱后，THE Cartonization_Engine SHALL 计算每个包裹的填充率，公式为：填充率 = 包裹内所有 SKU 总体积 / 箱型内部体积 × 100%
2. WHEN 某个包裹的填充率低于最低填充率阈值（默认 60%），THE Cartonization_Engine SHALL 尝试为该包裹换用更小的箱型
3. WHEN 换用更小箱型后填充率仍低于阈值但无更小箱型可用，THE Cartonization_Engine SHALL 保留当前箱型并在输出中标记该包裹为"低填充率"
4. THE Cartonization_Engine SHALL 优先选择填充率在 60% 至 90% 之间的箱型方案


### 需求 7：硬规则校验

**用户故事：** 作为装箱引擎，我需要在装箱过程中严格执行 7 条硬规则，以便确保每个包裹方案的物理安全性和业务合规性。

#### 验收标准

1. THE Cartonization_Engine SHALL 确保同一包裹内所有 SKU 的 temperature_zone 值相同（温区不混装规则）
2. THE Cartonization_Engine SHALL 确保 hazmat_type 不为"无"的 SKU 单独成包，不与 hazmat_type 为"无"的 SKU 混装（危险品隔离规则）
3. THE Cartonization_Engine SHALL 确保每个包裹的实际重量不超过所选箱型的最大承重和承运商 max_weight 中的较小值（单包不超重规则）
4. THE Cartonization_Engine SHALL 确保每个包裹所选箱型的外部尺寸不超过承运商的 max_dimension 限制（单包不超尺寸规则）
5. THE Cartonization_Engine SHALL 确保 cannot_ship_with 列表中指定的 SKU 不出现在同一包裹中（禁混品类隔离规则）
6. WHEN 包裹内包含 fragile_flag 为 true 的 SKU，THE Cartonization_Engine SHALL 确保该包裹使用支持防震填充的箱型，且该包裹内不包含单件重量超过 5kg 的非易碎 SKU（易碎品保护规则）
7. WHEN 包裹内包含液体类 SKU，THE Cartonization_Engine SHALL 确保该包裹使用防漏包装箱型（液体品防漏规则）
8. WHEN 装箱结果违反任一硬规则，THE Cartonization_Engine SHALL 拒绝该装箱方案并记录违反的具体规则和涉及的 SKU

### 需求 8：计费重量计算

**用户故事：** 作为装箱引擎，我需要为每个包裹计算准确的计费重量，以便下游运费计算模块使用正确的计费基数。

#### 验收标准

1. WHEN Cartonization_Engine 计算包裹的实际重量，THE Cartonization_Engine SHALL 使用公式：实际重量 = Σ(SKU_weight × SKU_qty) + 包装材料重量
2. WHEN Cartonization_Engine 计算包裹的体积重量，THE Cartonization_Engine SHALL 使用公式：体积重量 = (箱型外部长 × 箱型外部宽 × 箱型外部高) / 承运商体积因子
3. THE Cartonization_Engine SHALL 使用公式：计费重量 = max(实际重量, 体积重量) 计算每个包裹的计费重量
4. THE Cartonization_Engine SHALL 对计费重量执行向上取整到 0.1kg，公式为：计费重量取整 = ceil(计费重量 × 10) / 10
5. FOR ALL 有效的 SKU 列表和箱型组合，THE Billing_Weight_Calculator SHALL 确保计算结果满足：计费重量 ≥ 实际重量 且 计费重量 ≥ 体积重量（计费重量不变性）

### 需求 9：装箱输出

**用户故事：** 作为分仓决策系统，我需要装箱引擎输出完整的包裹方案信息，以便下游模块（运费计算、成本引擎）使用装箱结果进行后续计算。

#### 验收标准

1. WHEN 装箱计算成功，THE Cartonization_Engine SHALL 输出包裹列表，每个包裹包含：包裹内 SKU 列表及各 SKU 数量、箱型编号及箱型尺寸、计费重量
2. WHEN 装箱计算成功，THE Cartonization_Engine SHALL 输出包裹总数
3. THE Cartonization_Engine SHALL 确保输出的所有包裹中 SKU 总数量之和等于输入的 SKU 总数量（SKU 数量守恒）
4. WHEN 装箱计算成功，THE Cartonization_Engine SHALL 输出每个包裹的决策日志，包含：分组原因、箱型选择原因、拆包原因（如有）
5. WHEN 装箱计算失败，THE Cartonization_Engine SHALL 输出失败原因、错误码和涉及的 SKU 列表

### 需求 10：装箱失败回退

**用户故事：** 作为装箱引擎，我需要在标准装箱失败时按 4 级回退策略逐级尝试，以便最大程度地完成装箱计算并减少人工介入。

#### 验收标准

1. WHEN 标准箱型无法容纳某组 SKU，THE Cartonization_Engine SHALL 尝试使用该仓的非标箱型进行装箱（F1 级回退）
2. WHEN 所有箱型（含非标箱型）均无法容纳某组 SKU，THE Cartonization_Engine SHALL 将该组标记为"需人工包装"，并使用虚拟箱型按 SKU 总体积估算计费重量（F2 级回退）
3. WHEN 选定箱型的外部尺寸超过当前承运商的 max_dimension 限制，THE Cartonization_Engine SHALL 标记该包裹为"承运商尺寸超限"，建议切换到支持大件的承运商（F3 级回退）
4. WHEN 装箱硬规则之间产生无法调和的冲突（如 must_ship_with 与 temperature_zone 隔离冲突），THE Cartonization_Engine SHALL 记录冲突详情，将该方案标记为"规则冲突待人工介入"，并挂起该方案（F4 级回退）
5. THE Cartonization_Engine SHALL 按 F1 → F2 → F3 → F4 的顺序逐级尝试回退，每级回退失败后才进入下一级

### 需求 11：超大件处理

**用户故事：** 作为装箱引擎，我需要识别并单独处理超大件 SKU，以便超大件走专线物流而不影响普通商品的装箱。

#### 验收标准

1. WHEN SKU 的 oversize_flag 为 true，THE Cartonization_Engine SHALL 将该 SKU 从普通装箱流程中排除，单独成包
2. WHEN 超大件 SKU 单独成包，THE Cartonization_Engine SHALL 在输出中标记该包裹为"超大件专线"
3. THE Cartonization_Engine SHALL 确保超大件 SKU 不与普通 SKU 混装在同一包裹中

### 需求 12：装箱结果序列化与反序列化

**用户故事：** 作为分仓决策系统，我需要装箱引擎的输入和输出支持 JSON 格式的序列化与反序列化，以便在系统间传递装箱请求和结果。

#### 验收标准

1. THE Cartonization_Engine SHALL 支持将装箱请求（SKU 列表、箱型列表、承运商限制、业务规则）从 JSON 格式反序列化为内部数据结构
2. THE Cartonization_Engine SHALL 支持将装箱结果（包裹列表、计费重量、决策日志）序列化为 JSON 格式
3. FOR ALL 有效的装箱结果对象，将装箱结果序列化为 JSON 再反序列化回对象 SHALL 产生与原始对象等价的结果（往返一致性）
