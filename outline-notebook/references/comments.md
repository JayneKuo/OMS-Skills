# 评论 API 参考

评论内容使用 ProseMirror JSON 格式（`data` 字段）。

## comments.list — 列出文档评论

| 参数 | 必填 | 说明 |
|------|------|------|
| documentId | 是 | 文档 ID |
| limit | 否 | 返回数量 |

展示时应包含：作者、内容、时间戳、回复线程结构。

## comments.info — 获取单条评论

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 评论 ID |

## comments.create — 添加评论

| 参数 | 必填 | 说明 |
|------|------|------|
| documentId | 是 | 文档 ID |
| data | 是 | ProseMirror JSON 内容 |
| parentCommentId | 否 | 父评论 ID（用于回复） |

`data` 格式示例：
```json
{
  "type": "doc",
  "content": [{"type": "paragraph", "content": [{"type": "text", "text": "评论内容"}]}]
}
```

## comments.update — 更新评论

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 评论 ID |
| data | 是 | 新的 ProseMirror JSON 内容 |

## comments.delete — 删除评论

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 评论 ID |

删除父评论会同时删除其所有回复。删除前需确认。
