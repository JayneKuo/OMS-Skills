# 版本历史 API 参考

## revisions.list — 列出文档修订版本

| 参数 | 必填 | 说明 |
|------|------|------|
| documentId | 是 | 文档 ID |
| limit | 否 | 返回数量 |

## revisions.info — 获取特定版本

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 版本 ID |

`text` 字段包含该时间点的完整文档内容。

## 恢复到历史版本

1. 通过 `revisions.info` 获取目标版本内容
2. 通过 `documents.update` 用该内容更新文档

恢复前需与用户确认。
