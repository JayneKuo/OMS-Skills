# 实施计划：装箱计算引擎

## 概述

按依赖顺序实现装箱计算引擎的 13 个模块。先建立数据模型基础，再逐步实现各业务组件，最后通过流水线编排将所有模块串联。每个模块实现后紧跟属性测试和单元测试，确保增量验证。

## 任务列表

- [x] 1. 项目结构初始化与数据模型实现
  - [x] 1.1 创建项目目录结构和依赖配置
    - 创建 `cartonization_engine/` 包目录和 `__init__.py`
    - 创建 `tests/` 目录和 `conftest.py`
    - 创建 `pyproject.toml`，声明依赖：pydantic>=2.0, pytest, hypothesis
    - _需求: 12.1_

  - [x] 1.2 实现枚举类型和基础数据模型
    - 在 `cartonization_engine/models.py` 中实现所有枚举：`TemperatureZone`, `HazmatType`, `CartonStatus`, `FallbackLevel`, `PackageFlag`
    - 实现基础模型：`Dimensions`（含 `volume` 属性）、`SKUItem`、`BoxType`、`CarrierLimits`、`OrderConfig`
    - 所有数值字段使用 `Decimal` 类型
    - _需求: 9.1, 12.1, 12.2_

  - [x] 1.3 实现输出模型和内部模型
    - 在 `cartonization_engine/models.py` 中实现：`PackageItem`, `BillingWeight`, `DecisionLog`, `Package`, `DegradationMark`, `RuleViolation`, `CartonizationResult`
    - 实现内部模型：`SKUGroup`, `FallbackContext`, `FallbackResult`
    - 实现请求模型：`CartonizationRequest`
    - _需求: 9.1, 9.2, 9.4, 9.5, 12.1, 12.2_

  - [x]* 1.4 编写属性测试：序列化往返一致性
    - **Property 26: 序列化往返一致性**
    - 使用 hypothesis 生成随机 `CartonizationResult` 对象，验证 JSON 序列化再反序列化后与原始对象等价
    - **验证: 需求 12.3**

- [x] 2. 输入验证器实现
  - [x] 2.1 实现 `InputValidator`
    - 在 `cartonization_engine/validator.py` 中实现 `InputValidator` 类
    - 实现 `validate()` 方法：验证 SKU 必填字段、箱型列表非空且尺寸/承重为正数
    - 实现 `_apply_degradation()` 方法：缺失 weight/length/width/height 时使用品类平均值，缺失 temperature_zone 默认"常温"，缺失 hazmat_type 默认"无"
    - 返回 `ValidationResult` 包含降级标记列表
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x]* 2.2 编写属性测试：数据降级正确性
    - **Property 1: 数据降级正确性**
    - 使用 hypothesis 生成部分字段为 None 的随机 SKU，验证降级后字段被正确替换且标记为 `DATA_DEGRADED`
    - **验证: 需求 1.2, 1.3, 1.4**

  - [x]* 2.3 编写属性测试：箱型列表有效性
    - **Property 2: 箱型列表有效性**
    - 使用 hypothesis 生成含空列表和无效值的随机箱型列表，验证验证器正确拒绝无效输入
    - **验证: 需求 1.5, 1.6**

- [x] 3. 检查点 - 确保数据模型和验证器测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. 超大件处理器实现
  - [x] 4.1 实现 `OversizeHandler`
    - 在 `cartonization_engine/oversize_handler.py` 中实现 `OversizeHandler` 类
    - 实现 `separate()` 方法：从 SKU 列表中分离 `oversize_flag=True` 的 SKU，每个超大件单独成包并标记 `OVERSIZE_SPECIAL`
    - _需求: 11.1, 11.2, 11.3_

  - [x]* 4.2 编写属性测试：超大件隔离
    - **Property 25: 超大件隔离**
    - 使用 hypothesis 生成含超大件的随机 SKU 列表，验证超大件单独成包、标记正确、不与普通 SKU 混装
    - **验证: 需求 11.1, 11.2, 11.3**

- [x] 5. 预分组器实现
  - [x] 5.1 实现 `PreGrouper`
    - 在 `cartonization_engine/pre_grouper.py` 中实现 `PreGrouper` 类
    - 实现 `group()` 方法，按优先级执行：温区分组 → 危险品隔离 → `cannot_ship_with` 互斥拆分 → `must_ship_with` 绑定合并 → 赠品同包
    - 检测 `must_ship_with` 与温区/禁混规则冲突时抛出 `RuleConflictError`
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 5.2 编写属性测试：温区分组不变量
    - **Property 3: 温区分组不变量**
    - 使用 hypothesis 生成多温区 SKU 列表，验证同组内所有 SKU 温区相同
    - **验证: 需求 2.1**

  - [x]* 5.3 编写属性测试：危险品隔离分组
    - **Property 4: 危险品隔离分组**
    - 使用 hypothesis 生成含危险品的随机 SKU 列表，验证危险品 SKU 单独成组
    - **验证: 需求 2.2**

  - [x]* 5.4 编写属性测试：禁混互斥分组
    - **Property 5: 禁混互斥分组**
    - 使用 hypothesis 生成含 `cannot_ship_with` 约束的 SKU 列表，验证互斥 SKU 不在同组
    - **验证: 需求 2.3**

  - [x]* 5.5 编写属性测试：同包绑定分组
    - **Property 6: 同包绑定分组**
    - 使用 hypothesis 生成含 `must_ship_with` 约束的 SKU 列表，验证绑定 SKU 在同组
    - **验证: 需求 2.4**

  - [x]* 5.6 编写属性测试：赠品同包分组
    - **Property 7: 赠品同包分组**
    - 使用 hypothesis 生成含赠品的 SKU 列表，验证赠品与主商品在同组
    - **验证: 需求 2.6**

- [x] 6. 检查点 - 确保预分组模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 7. FFD 排序器与装箱器实现
  - [x] 7.1 实现 `FFDSorter`
    - 在 `cartonization_engine/sorter.py` 中实现 `FFDSorter` 类
    - 实现 `sort()` 方法：按单件体积降序排列，体积相同按单件重量降序
    - _需求: 3.1, 3.2_

  - [x]* 7.2 编写属性测试：FFD 排序正确性
    - **Property 8: FFD 排序正确性**
    - 使用 hypothesis 生成随机 SKU 列表，验证排序后体积从大到小，体积相同时重量从大到小
    - **验证: 需求 3.1, 3.2**

  - [x] 7.3 实现 `FFDPacker`
    - 在 `cartonization_engine/packer.py` 中实现 `FFDPacker` 类
    - 实现 `pack()` 方法：对排序后的 SKU 逐件尝试放入第一个可容纳的已开箱，无法放入则开新箱
    - 容纳判断同时检查剩余体积和剩余承重
    - _需求: 3.3, 3.4_

  - [x]* 7.4 编写属性测试：装箱容量不变量
    - **Property 9: 装箱容量不变量**
    - 使用 hypothesis 生成随机 SKU + 箱型组合，验证每个包裹内 SKU 总体积不超过箱型内部体积，总重量不超过箱型最大承重
    - **验证: 需求 3.4, 7.3**

- [x] 8. 箱型选择器实现
  - [x] 8.1 实现 `BoxSelector`
    - 在 `cartonization_engine/box_selector.py` 中实现 `BoxSelector` 类
    - 实现 `select()` 方法：筛选物理容纳箱型 → 排除承运商超尺寸 → 按计费重最低 → 包材成本最低 → 承运商兼容性排序
    - 易碎品包裹仅选择 `supports_shock_proof=True` 的箱型
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 8.2 编写属性测试：箱型选择优先级
    - **Property 10: 箱型选择优先级**
    - 使用 hypothesis 生成随机 SKU + 多箱型，验证选中箱型的计费重量和包材成本最优
    - **验证: 需求 4.1, 4.2, 4.3**

  - [x]* 8.3 编写属性测试：箱型承运商尺寸合规
    - **Property 11: 箱型承运商尺寸合规**
    - 使用 hypothesis 生成随机包裹 + 承运商限制，验证所选箱型外部尺寸不超过承运商限制
    - **验证: 需求 4.5, 7.4**

  - [x]* 8.4 编写属性测试：易碎品防震保护
    - **Property 12: 易碎品防震保护**
    - 使用 hypothesis 生成含易碎品的随机 SKU，验证箱型支持防震且不含超 5kg 非易碎品
    - **验证: 需求 4.6, 7.6**

- [x] 9. 多包拆分器实现
  - [x] 9.1 实现 `PackageSplitter`
    - 在 `cartonization_engine/splitter.py` 中实现 `PackageSplitter` 类
    - 实现 `split()` 方法：超重或超体积时拆分为多包，优先均匀分配重量
    - 拆分后包裹数超过 `max_package_count` 时返回失败
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 9.2 编写属性测试：拆分后单包不超限
    - **Property 13: 拆分后单包不超限**
    - 使用 hypothesis 生成超重/超体积 SKU 组，验证拆分后每包不超限
    - **验证: 需求 5.1, 5.2**

  - [x]* 9.3 编写属性测试：拆分后包裹数不超限
    - **Property 14: 拆分后包裹数不超限**
    - 使用 hypothesis 生成随机 SKU + max_package_count，验证成功状态下包裹数不超限
    - **验证: 需求 5.4**

- [x] 10. 填充率校验器实现
  - [x] 10.1 实现 `FillRateChecker`
    - 在 `cartonization_engine/fill_rate_checker.py` 中实现 `FillRateChecker` 类
    - 实现 `check_and_optimize()` 方法：计算填充率，低于阈值时尝试换更小箱型，无更小箱型则标记 `LOW_FILL_RATE`
    - _需求: 6.1, 6.2, 6.3, 6.4_

  - [x]* 10.2 编写属性测试：填充率计算正确性
    - **Property 15: 填充率计算正确性**
    - 使用 hypothesis 生成随机包裹，验证填充率 = SKU 总体积 / 箱型内部体积 × 100%
    - **验证: 需求 6.1**

  - [x]* 10.3 编写属性测试：填充率优化
    - **Property 16: 填充率优化**
    - 使用 hypothesis 生成随机包裹 + 多箱型，验证低填充率时已换用更小箱型或标记 `LOW_FILL_RATE`
    - **验证: 需求 6.2, 6.3**

- [x] 11. 检查点 - 确保装箱核心模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 12. 硬规则校验器实现
  - [x] 12.1 实现 `HardRuleChecker`
    - 在 `cartonization_engine/hard_rule_checker.py` 中实现 `HardRuleChecker` 类
    - 实现 `check()` 方法和 7 条独立规则方法：`_check_temperature_zone`, `_check_hazmat_isolation`, `_check_weight_limit`, `_check_dimension_limit`, `_check_cannot_ship_with`, `_check_fragile_protection`, `_check_liquid_leak_proof`
    - _需求: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x]* 12.2 编写属性测试：温区不混装硬规则
    - **Property 17: 温区不混装硬规则**
    - 使用 hypothesis 生成随机装箱结果，验证同包裹内所有 SKU 温区相同
    - **验证: 需求 7.1**

  - [x]* 12.3 编写属性测试：危险品隔离硬规则
    - **Property 18: 危险品隔离硬规则**
    - 使用 hypothesis 生成随机装箱结果，验证危险品不与普通品混装
    - **验证: 需求 7.2**

  - [x]* 12.4 编写属性测试：禁混品类隔离硬规则
    - **Property 19: 禁混品类隔离硬规则**
    - 使用 hypothesis 生成随机装箱结果，验证 `cannot_ship_with` 中的 SKU 不在同包裹
    - **验证: 需求 7.5**

  - [x]* 12.5 编写属性测试：液体品防漏硬规则
    - **Property 20: 液体品防漏硬规则**
    - 使用 hypothesis 生成含液体类 SKU 的随机包裹，验证箱型 `supports_leak_proof=True`
    - **验证: 需求 7.7**

- [x] 13. 计费重量计算器实现
  - [x] 13.1 实现 `BillingWeightCalculator`
    - 在 `cartonization_engine/billing_calculator.py` 中实现 `BillingWeightCalculator` 类
    - 实现 `calculate()` 方法：actual = Σ(sku.weight × qty) + box.material_weight, volumetric = (外部长×外部宽×外部高) / dim_factor, billing = ceil(max(actual, volumetric) × 10) / 10
    - _需求: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 13.2 编写属性测试：计费重量计算正确性
    - **Property 21: 计费重量计算正确性**
    - 使用 hypothesis 生成随机包裹 + 承运商，验证计费重量公式正确且 billing ≥ actual 且 billing ≥ volumetric
    - **验证: 需求 8.1, 8.2, 8.3, 8.4, 8.5**

- [x] 14. 回退处理器实现
  - [x] 14.1 实现 `FallbackHandler`
    - 在 `cartonization_engine/fallback_handler.py` 中实现 `FallbackHandler` 类
    - 实现 `handle()` 方法：按 F1（非标箱型）→ F2（虚拟箱型 + 人工包装）→ F3（大件承运商切换）→ F4（规则冲突挂起）顺序逐级尝试
    - 每级回退失败后才进入下一级，最终结果的 `fallback_level` 反映实际执行的最高回退级别
    - _需求: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x]* 14.2 编写属性测试：回退顺序不变量
    - **Property 24: 回退顺序不变量**
    - 使用 hypothesis 生成随机失败场景，验证回退按 F1→F2→F3→F4 顺序执行
    - **验证: 需求 10.5**

- [x] 15. 检查点 - 确保所有独立模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 16. 流水线编排引擎实现
  - [x] 16.1 实现 `CartonizationEngine` 主入口
    - 在 `cartonization_engine/engine.py` 中实现 `CartonizationEngine` 类
    - 实现 `cartonize()` 方法，按流水线顺序编排：输入验证 → 超大件分离 → 预分组 → FFD 排序 → FFD 装箱 → 箱型选择 → 填充率校验 → 硬规则校验 → 回退处理 → 计费重计算 → 组装输出
    - 所有异常捕获并转换为结构化 `CartonizationResult`（`status=FAILED`）
    - _需求: 1.1~1.6, 2.1~2.6, 3.1~3.4, 4.1~4.6, 5.1~5.5, 6.1~6.4, 7.1~7.8, 8.1~8.5, 9.1~9.5, 10.1~10.5, 11.1~11.3, 12.1~12.3_

  - [x]* 16.2 编写属性测试：SKU 数量守恒
    - **Property 22: SKU 数量守恒**
    - 使用 hypothesis 生成完整装箱请求，验证成功结果中所有包裹的 SKU 数量之和等于输入
    - **验证: 需求 9.3**

  - [x]* 16.3 编写属性测试：输出完整性
    - **Property 23: 输出完整性**
    - 使用 hypothesis 生成完整装箱请求，验证每个包裹包含非空 SKU 列表、有效箱型、计费重量、决策日志，且 `total_packages` 等于包裹列表长度
    - **验证: 需求 9.1, 9.2, 9.4**

- [ ] 17. 端到端单元测试
  - [ ] 17.1 编写引擎集成单元测试
    - 在 `tests/test_engine.py` 中编写以下场景的单元测试：
      - 单 SKU 单包（最简场景）
      - 多 SKU 温区隔离拆包（生鲜混合订单）
      - 超重拆包（8 件同 SKU 超重）
      - 赠品同包约束
      - 禁混规则冲突（must_ship_with 与 cannot_ship_with 冲突）
      - 箱型列表为空（边界）
      - 包裹数超限（拆分后超过 max_package_count）
      - 失败输出格式（错误码和 SKU 列表）
    - _需求: 9.1~9.5, 2.5, 5.5, 1.6_

  - [ ] 17.2 编写回退策略单元测试
    - 在 `tests/test_fallback.py` 中编写 F1~F4 每级回退的触发和处理测试
    - _需求: 10.1, 10.2, 10.3, 10.4_

  - [ ] 17.3 编写 JSON 序列化单元测试
    - 在 `tests/test_serialization.py` 中编写具体 JSON 格式验证测试
    - _需求: 12.1, 12.2, 12.3_

- [ ] 18. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保需求可追溯
- 检查点任务确保增量验证，及时发现问题
- 属性测试验证通用正确性属性，单元测试验证具体场景和边界条件
- 所有 26 个正确性属性均已覆盖为属性测试子任务
