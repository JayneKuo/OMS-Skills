# OMS Agent

## 1. 项目说明

OMS Agent 是一个面向 OMS（Order Management System）前端会话的业务助手。

它的目标不是单纯做问答，而是：

- 理解用户自然语言请求
- 识别用户是在查事实、问定义、做分析，还是要完整方案
- 调用合适的 skills
- 在复杂场景下编排多个 skills
- 输出查询结果、分析结论、推荐方案和风险说明

---

## 2. 当前定位

OMS Agent 面向以下典型场景：

- 订单查询
- 订单状态解释
- 订单异常分析
- 业务概念 / 流程 / API 含义解释
- 分仓建议
- 装箱建议
- 运费计算
- 时效计算
- 成本计算
- 完整发货方案推荐

---

## 3. 当前架构

当前采用 3 层结构：

### 前台会话入口层
- `oms_query`：实时事实查询
- `oms-knowledge`：本体知识、流程、规则、API 含义
- `oms_analysis`：异常诊断、趋势洞察、图表输出
- `navigate`：页面导航

### 后台专项能力层
- `warehouse_allocation`
- `cartonization`
- `shipping_rate`
- `eta`
- `cost`

### 编排层
- `fulfillment-planner`：完整发货方案推荐

配套文档：

- `SYSTEM_PROMPT.md`  
  定义 Agent 的角色、原则、任务分类和路由规则

- `SKILL_REGISTRY.md`  
  统一登记当前可用 skills 及其职责边界

- `WORKFLOWS.md`  
  定义复杂业务场景下的多 skill 编排流程

- `OUTPUT_POLICY.md`  
  定义统一输出规范

---

## 4. 设计原则

OMS Agent 设计遵循以下原则：

1. 前台体验优先，普通业务问题优先走最短工具路径  
2. 事实查询、知识解释、分析诊断、方案推荐分层处理  
3. 主 Prompt 轻量稳定，强能力下沉到 skill 和 workflow  
4. 所有推荐必须可解释  
5. 数据不足时必须明确标注为估算或 degraded  
6. 高风险动作默认不执行  
7. 不向用户暴露框架噪音、仓库探索过程和内部实现细节

---

## 5. 如何扩展新的 skill

后续新增 skill 时，建议按以下步骤进行：

### 第一步：先判断它属于哪一层
- 前台会话入口层
- 后台专项能力层
- 编排层

### 第二步：新增 `SKILL.md`
建议每个 skill 统一描述以下内容：

- name
- description（重点写触发条件，而不是流程摘要）
- trigger boundary
- inputs
- outputs
- constraints
- upstream dependencies
- downstream consumers

### 第三步：更新 `SKILL_REGISTRY.md`
将新 skill 注册到统一能力清单中。

### 第四步：如有必要，更新 `WORKFLOWS.md`
如果该 skill 会参与复杂编排，则需要新增或更新 workflow。

### 第五步：仅在必要时更新 `SYSTEM_PROMPT.md`
原则上主 prompt 尽量保持稳定，不要把专项逻辑继续堆回 root prompt。

---

## 6. 如何扩展新的 workflow

新增 workflow 时，建议统一描述：

- workflow name
- trigger
- skill sequence
- degraded strategy
- outputs

适用于：
- 多 skill 决策任务
- 多步骤业务分析任务
- 综合推荐任务

---

## 7. 推荐维护方式

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

## 8. 总结

OMS Agent 的核心目标是：

- 让用户像在和业务助手对话，而不是和脚本集合对话
- 在真实 OMS 场景下，理解问题、路由能力、编排方案、解释原因

这套结构的重点不是把所有逻辑塞进一个 prompt，
而是通过：

- 主 Agent Prompt
- Skill Registry
- Workflows
- Output Policy
- 分层 skill 体系

形成一套稳定、可维护、可扩展的 Agent 架构。
