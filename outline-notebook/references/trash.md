# 回收站与归档 API 参考

## documents.deleted — 列出已删除文档

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |
| sort | 否 | 如 `"deletedAt"` |
| direction | 否 | `"ASC"` / `"DESC"` |

## documents.archived — 列出已归档文档

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |

## documents.restore — 恢复文档

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| collectionId | 否 | 恢复到指定集合 |
| revisionId | 否 | 恢复到特定版本 |

## documents.empty_trash — 清空回收站

无需参数。**此操作不可逆**，执行前必须先列出回收站内容并与用户确认。
