---
name: item-dev-workflow
description: 处理 ITEM 项目的日常开发、接口联调、测试执行、启动验证、401 token 失效排查与 controller 路径规范。用户提到 ITEM 项目开发、修 bug、改接口、跑测试、启动本地服务、重新获取 dev/staging 登录 token，或需要根据 `controller/app`、`controller/rpc`、`controller/open` 目录自动补齐 API 前缀时使用。每完成一轮开发后，都要主动执行相关测试并启动本地服务验证。
---

# ITEM Dev Workflow

## 概览

在 ITEM 项目中开发、联调和验证时，遵循本 skill 的统一流程：先对齐验证方式和最小验证单元，测试先行，再实现、验证、复盘。

按需读取对应 reference：

- 开发和测试阶段的环境变量、端口、token 约定：`references/development-conventions.md`
- 开发约束、接口前缀、RESTful、时间与枚举传参规则：`references/development-rules.md`
- 测试、验证与收尾：`references/verification.md`

## 工作流

1. 先阅读本次修改涉及的模块、controller 和测试。
2. 开始开发前，先和用户沟通本次改动的验证方式，并给出最小验证单元。
3. 测试先行：开始开发前先编写对应的测试用例，再进入实现。
4. 若请求涉及登录态、401、token 过期，先根据当前环境配置重新获取新的 token，再继续测试或联调。
5. 修改接口时，检查 controller 所在目录，并按目录推断默认前缀。
6. 完成一轮开发后，主动执行测试和启动验证，不等待用户再次提醒。
7. 若验证失败，继续检查原因并修改，再次验证，直到问题收敛或明确阻塞点。
8. 开发结束且所有测试用例通过后，整理本轮开发过程中犯过的错误，并询问用户是否需要整理更新到文档、流程或 skill。

## 核心规则

- 开始开发前先对齐验证方式，并给出最小验证单元。
- 测试先行：先写或补测试，再进入实现。
- API 路径必须保持 RESTful 风格。
- 开发完成后必须主动执行测试和启动验证。
- 验证失败后继续排查、修改并重新验证，不能只停留在失败汇报。
- 全部通过后整理本轮错误和易错点，并询问用户是否需要沉淀更新。

## Controller 路径规则

- `**/controller/app/**` 默认补 `app-api`
- `**/controller/rpc/**` 默认补 `rpc-api`
- `**/controller/open/**` 默认补 `open-api`
- 仅在类级或方法级路径未明显声明对应前缀时补齐
- 补齐前缀后，后续路径仍必须保持 RESTful 风格

详细规则见 `references/development-rules.md`。

## 配置要求

- 优先读取项目根目录 `.env`，全局环境变量优先级第二。
- 缺少必需配置时，明确指出缺失项并引导补全，不要猜测默认值。
- token 每次重新获取，不复用旧值。
- 新增测试用例默认放在项目根目录下的 `tests/`。

详细规则见 `references/development-conventions.md` 和 `references/verification.md`。

## 开发约束

- API 路径必须保持 RESTful 风格。
- 没有特殊说明时，服务器、数据库和前端之间传递的时间统一使用 0 时区时间。
- 涉及枚举字段的接口联调时，先确认后端枚举反序列化约定；默认优先传项目定义的 `code`，不要想当然传枚举名字符串。
- 前后端交互、数据库存储、异常、命名和常量使用遵循项目既有约定，不要重复发明轮子。
- Git 线上分支默认是 `release`，测试分支默认是 `staging`；新需求默认基于 `release` 切出新分支开发，自测完成后再提交到 `staging` 用于测试。

详细规则见 `references/development-rules.md`。

## 资源说明

- `references/development-conventions.md`：开发和测试阶段的环境变量、端口、token 与通用约定。
- `references/development-rules.md`：开发约束、controller 前缀、RESTful 路径和时间规则。
- `references/verification.md`：测试先行、测试目录、验证与收尾约定。
