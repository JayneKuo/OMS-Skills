# 开发约束

## 枚举约束

- 前端交互和数据库存储都使用枚举约定，不要直接用未定义语义的 `Integer`
- 枚举相关字段优先传递和存储项目既定的 code 或枚举映射值
- 涉及枚举时，优先复用已有枚举定义，不要重复定义相同语义
- 在接口联调前，先确认枚举字段的请求反序列化规则；不要默认认为可以直接传枚举名字符串
- 如果枚举实现了类似 `BaseEnum` 并通过 `fromCode(int code)` 反序列化，请求体和查询参数默认传 `code`，不要传 `name` / `value`
- 例如角色状态 `RoleStatusEnum.ACTIVE` / `RoleStatusEnum.DEPRECATED`，联调时应优先传 `10` / `20`，而不是 `"ACTIVE"` / `"DEPRECATED"`
- 只有代码中明确提供了字符串反序列化能力，例如 `@JsonCreator` 支持按字符串解析、专用 Converter 或自定义反序列化器时，才允许传枚举字符串
- 排查接口 `param error`、`HttpMessageNotReadableException`、绑定失败时，优先检查是否把枚举字符串误传成了后端只接受数字 code 的字段

## 参数与模型命名

- Database Entity 使用 `DO`
- Request Entity 使用 `VO`
- Response Entity 使用 `DTO`

## 常量、错误码与异常

- 错误码维护在项目既有的 `ErrorCodeConstants`
- 全局常量维护在项目既有的 `Constants`
- 不要抛出未定义语义的异常，例如直接抛 `RuntimeException`
- 优先复用框架已封装的异常类；确有需要时再封装业务异常

## 业务能力复用

- 业务编号生成优先复用项目已有的 `SequenceGenerator.generate()`
- 文件类型识别优先复用项目已有的 `FileTypeDetectionUtil`
- 能复用现有工具、封装和框架能力时，不要重复发明轮子

## Git 分支约定

- Git 线上分支默认是 `release`
- 测试分支默认是 `staging`
- 新需求如果没有明确要求，默认从 `release` 切出新的开发分支
- 开发、测试先行、自测和问题修复都在新开发分支上完成
- 自测完成后，再将改动提交到 `staging` 用于测试
- 只有用户明确指定其他分支策略时，才偏离这套默认流程

## 数据约定

- 百分比存储直接使用百分数值
- `100% = 100`
- `5% = 5`
- `5.5% = 5.5`

## Controller 前缀

- `**/controller/app/**`：默认前缀 `app-api`
- `**/controller/rpc/**`：默认前缀 `rpc-api`
- `**/controller/open/**`：默认前缀 `open-api`

仅在 controller 没有明显声明对应前缀时应用该规则；若类级或方法级映射已包含同类前缀，不重复追加。

## RESTful 约束

接口路径必须保持 RESTful 风格：

- 使用资源名而不是动作名
- 使用 HTTP 方法表达行为语义
- 使用层级路径表达从属关系
- 避免 `/getXxx`、`/createXxx`、`/deleteXxx`、`/updateXxx` 这类路径命名

推荐示例：

- `/users`
- `/users/{id}`
- `/orders/{id}/items`

避免示例：

- `/getUser`
- `/createOrder`
- `/updateStatus`

## 时间规则

没有特殊说明时，服务器、数据库和前端之间传递的时间统一使用 0 时区时间。

- 默认按 UTC 处理和传输时间
- 接口传参、接口返回、数据库读写、消息体字段和前端提交时间都遵循同一约定
- 不要默认按本地时区拼接、存储或展示给其他系统
- 如果业务明确要求展示本地时区，仅在展示层做转换，底层传输和存储仍优先保持 0 时区约定
- 前端时间交互优先使用 `LocalDateTime` 语义，可传递毫秒时间戳，默认按 0 时区处理
