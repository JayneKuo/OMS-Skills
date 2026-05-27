---
name: outline-notebook
description: 与 Item Notebook (Outline 知识库) 交互 — 搜索、阅读、创建、更新文档，管理集合、评论、分享、权限、附件、用户、回收站等。当用户提到 notebook、wiki、知识库、文档或任何 Outline 相关操作时使用。
---

# Outline Notebook

管理 Item Notebook 知识库（私有化部署的 Outline）。

## 连接信息

- **`OUTLINE_API_URL`** — 环境变量，默认值 `https://notebook.item.com/api`，一般不用设置
- **`OUTLINE_API_KEY`** — 环境变量，必须设置，API 密钥以 `ol_api_` 开头
- **认证方式：** 请求头 `Authorization: Bearer $OUTLINE_API_KEY`

## API 协议

- 所有端点均为 **POST** 请求
- 请求体为 **JSON** 格式
- 端点格式：`{Base URL}/{资源}.{操作}`，如 `https://notebook.item.com/api/documents.search`

## 操作路由

根据用户意图，加载对应的参考文件获取端点和参数详情：

| 用户想要... | 参考文件 |
|---|---|
| 搜索文档、查找信息 | [references/documents.md](references/documents.md) |
| 阅读、创建、更新、移动、归档、删除或模板化文档 | [references/documents.md](references/documents.md) |
| 列出最近文档、草稿、最近浏览、导入导出 | [references/documents.md](references/documents.md) |
| 浏览集合、查看文档树、创建/导出集合 | [references/collections.md](references/collections.md) |
| 查看、添加、回复或删除评论 | [references/comments.md](references/comments.md) |
| 列出用户、分组、更新个人资料、查看认证配置 | [references/users.md](references/users.md) |
| 添加/移除文档的用户或分组访问权限 | [references/permissions.md](references/permissions.md) |
| 创建、查看或撤销公开分享链接 | [references/shares.md](references/shares.md) |
| 上传、下载或删除文件附件 | [references/attachments.md](references/attachments.md) |
| 恢复已删除文档、查看归档文档、清空回收站 | [references/trash.md](references/trash.md) |
| 查看活动日志、审计记录 | [references/events.md](references/events.md) |
| 查看文档版本历史 | [references/revisions.md](references/revisions.md) |
| 收藏/取消收藏文档 | [references/stars.md](references/stars.md) |

## 显示规范

- 文档链接格式：`https://notebook.item.com{document.url}`
- 列表使用表格展示，层级结构使用树形格式
- 文档信息应展示：标题、所属集合、作者、最后更新时间
- 执行破坏性操作（删除、清空回收站等）前必须先与用户确认
