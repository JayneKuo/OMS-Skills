# 集合 API 参考

## collections.list — 列出所有集合

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |

## collections.info — 获取集合详情

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 集合 ID |

## collections.documents — 文档层级树

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 集合 ID |

返回嵌套的文档树形结构，展示建议：
```
├── 文档 A
│   ├── 子文档 1
│   └── 子文档 2
└── 文档 B
```

## collections.create — 创建集合

| 参数 | 必填 | 说明 |
|------|------|------|
| name | 是 | 集合名称 |
| description | 否 | 描述 |
| permission | 否 | `"read"` / `"read_write"` / `null`（私有） |
| sharing | 否 | 是否允许分享 |
| icon | 否 | 图标名称 |
| color | 否 | 颜色代码，如 `"#0366D6"` |

## collections.export — 导出集合

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 集合 ID |
| format | 否 | `"outline-markdown"` / `"html"` / `"json"` |

触发后台文件操作。

## collections.export_all — 导出所有集合

| 参数 | 必填 | 说明 |
|------|------|------|
| format | 否 | `"outline-markdown"` / `"html"` / `"json"` |
