# 文档 API 参考

## documents.search — 全文搜索

| 参数 | 必填 | 说明 |
|------|------|------|
| query | 是 | 搜索关键词 |
| limit | 否 | 返回数量，默认 25 |
| collectionId | 否 | 按集合过滤 |
| dateFilter | 否 | `"day"` / `"week"` / `"month"` / `"year"` |
| statusFilter | 否 | `["published"]` / `["draft"]` / `["archived"]` |
| userId | 否 | 按作者过滤 |

返回：`data[].document`（文档对象）+ `data[].context`（匹配上下文片段）

## documents.search_titles — 标题搜索

| 参数 | 必填 | 说明 |
|------|------|------|
| query | 是 | 搜索关键词 |
| limit | 否 | 返回数量 |

仅匹配标题，速度更快。

## documents.info — 获取文档

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 二选一 | 文档 UUID |
| urlId | 二选一 | URL 中最后一个 `-` 之后的短 ID |
| shareId | 二选一 | 分享 ID |

返回：`data.text` 为完整 Markdown 内容。

## documents.list — 列出文档

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |
| collectionId | 否 | 限定集合 |
| sort | 否 | `"updatedAt"` / `"createdAt"` / `"publishedAt"` / `"title"` |
| direction | 否 | `"ASC"` / `"DESC"` |

## documents.drafts — 我的草稿

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |

## documents.viewed — 最近浏览

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |

## documents.documents — 子文档列表

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 父文档 ID |

## documents.create — 创建文档

| 参数 | 必填 | 说明 |
|------|------|------|
| title | 是 | 标题 |
| text | 否 | Markdown 内容 |
| collectionId | 是 | 目标集合 ID |
| publish | 否 | `true` 发布 / `false` 草稿，默认 true |
| parentDocumentId | 否 | 父文档 ID（创建子文档） |
| templateId | 否 | 模板 ID |

## documents.update — 更新文档

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| title | 否 | 新标题 |
| text | 否 | 新的完整内容（**替换全部**） |
| append | 否 | `true` 时追加到末尾而非替换 |
| done | 否 | `true` 释放协作编辑锁 |
| fullWidth | 否 | 切换全宽显示 |

**注意：** `text` 会替换整个文档，更新时务必传入完整内容。

## documents.move — 移动文档

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| collectionId | 是 | 目标集合 ID |

## documents.archive — 归档文档

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |

## documents.delete — 删除文档（移入回收站）

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |

## documents.templatize — 转为模板

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |

基于文档内容创建模板，原文档不受影响。

## documents.export — 导出文档

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |

返回 `data` 字段为 Markdown 内容。

## documents.import — 导入文档

此端点使用 **multipart 表单上传**（非 JSON），需要字段：
- `file` — 文件（支持 .md / .docx / .html）
- `collectionId` — 目标集合
- `publish` — `true` / `false`
