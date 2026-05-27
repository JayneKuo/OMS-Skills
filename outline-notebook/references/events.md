# 活动日志 API 参考

## events.list — 列出事件

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |
| name | 否 | 事件类型过滤（见下方） |
| documentId | 否 | 指定文档的事件 |
| collectionId | 否 | 指定集合的事件 |
| userId | 否 | 指定用户的事件 |
| auditLog | 否 | `true` 包含详细审计信息 |
| sort | 否 | 如 `"createdAt"` |
| direction | 否 | `"ASC"` / `"DESC"` |

## 常见事件类型

| 事件名 | 说明 |
|--------|------|
| documents.create | 文档已创建 |
| documents.update | 文档已编辑 |
| documents.delete | 文档已删除 |
| documents.publish | 文档已发布 |
| documents.archive | 文档已归档 |
| documents.move | 文档已移动 |
| collections.create | 集合已创建 |
| users.signin | 用户已登录 |
| revisions.create | 新版本已保存 |
