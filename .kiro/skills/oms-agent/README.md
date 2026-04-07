# OMS Agent

## 1. 项目说明

OMS Agent 是一个面向 OMS（Order Management System）业务场景的智能业务 Agent。

它的目标不是单纯做问答，而是：

- 理解用户自然语言请求
- 自动识别业务意图
- 调用合适的 skills
- 在复杂场景下编排多个 skills
- 输出查询结果、分析结论、推荐方案和风险说明

---

## 2. 当前定位

OMS Agent 面向以下典型场景：

- 订单查询
- 订单状态解释
- 订单异常分析
- 分仓建议
- 装箱建议
- 运费计算
- 时效计算
- 成本计算
- 完整发货方案推荐

---

## 3. 当前架构

当前采用以下结构：

- `SYSTEM_PROMPT.md`  
  定义 Agent 的角色、原则、任务分类和编排逻辑

- `SKILL_REGISTRY.md`  
  统一登记当前可用 skills 及其职责边界

- `WORKFLOWS.md`  
  定义复杂业务场景下的多 skill 编排流程

- `OUTPUT_POLICY.md`  
  定义统一输出规范

---

## 4. 当前 skill 体系

当前已接入 / 规划接入的 skills 包括：

- cartonization
- order_query
- order_analysis
- warehouse_allocation
- shipping_rate
- eta
- cost

其中：

### cartonization
属于计算 / 推荐型 skill  
负责：
- 装箱建议
- 箱型选择
- 包裹拆分
- 计费重量计算
- 特殊标记与装箱理由输出

它通常不是最终业务决策的终点，而是以下 workflow 的中间步骤：

- shipping_plan_recommendation_workflow
- warehouse_allocation_recommendation_workflow
- warehouse_plus_shipping_recommendation_workflow

---

## 5. 设计原则

OMS Agent 设计遵循以下原则：

1. Agent 层和 Skill 层解耦  
2. 主 Prompt 稳定，skills 可逐步扩展  
3. workflow 独立维护，不写死在某个 skill 内  
4. 所有推荐必须可解释  
5. 数据不足时必须明确标注为估算  
6. 高风险动作默认不执行  

---

## 6. 如何扩展新的 skill

后续新增 skill 时，建议按以下步骤进行：

### 第一步：新增 skill 目录
例如：
- `order-query/`
- `order-analysis/`
- `shipping-rate/`

### 第二步：新增 `SKILL.md`
建议每个 skill 统一描述以下内容：

- name
- purpose
- use_when
- inputs
- outputs
- constraints
- upstream_dependencies
- downstream_consumers

### 第三步：更新 `SKILL_REGISTRY.md`
将新 skill 注册到统一能力清单中。

### 第四步：如有必要，更新 `WORKFLOWS.md`
如果该 skill 会参与复杂编排，则需要新增或更新 workflow。

### 第五步：仅在必要时更新 `SYSTEM_PROMPT.md`
原则上主 prompt 尽量保持稳定，不要频繁修改。

---

## 7. 如何扩展新的 workflow

新增 workflow 时，建议统一描述：

- workflow name
- trigger
- steps
- outputs

适用于：
- 多 skill 决策任务
- 多步骤业务分析任务
- 综合推荐任务

---

## 8. 推荐维护方式

推荐的维护顺序：

1. 先维护 skill 自身边界  
2. 再更新 skill registry  
3. 再更新 workflow  
4. 最后才考虑是否需要调整主 prompt  

这样可以保证：

- 职责边界清晰
- skill 可复用
- workflow 可扩展
- Agent 逻辑稳定

---

## 9. 后续建议优先级

建议下一阶段优先补齐：

1. `order_query`
2. `order_analysis`

因为这两个能力是大多数 OMS 场景的基础入口。

在此基础上，再逐步增强：

3. `warehouse_allocation`
4. `shipping_rate`
5. `eta`
6. `cost`

这样可以快速从“单 skill 能力”升级到“完整业务编排 Agent”。

---

## 10. 总结

OMS Agent 的核心目标是：

- 不只是会调用单个 skill
- 而是能在真实 OMS 场景下，理解问题、编排能力、输出建议、解释原因

这套结构的重点不是把所有逻辑塞进一个 prompt，
而是通过：

- 主 Agent Prompt
- Skill Registry
- Workflows
- Output Policy

形成一套稳定、可维护、可扩展的 Agent 体系。