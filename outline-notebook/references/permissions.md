# 文档权限 API 参考

管理文档级别的用户/分组访问权限。

## documents.add_user — 添加用户访问权限

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| userId | 是 | 用户 ID |
| permission | 否 | `"read"` / `"read_write"`，默认 `"read_write"` |

## documents.remove_user — 移除用户访问权限

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| userId | 是 | 用户 ID |

## documents.add_group — 添加分组访问权限

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| groupId | 是 | 分组 ID |
| permission | 否 | `"read"` / `"read_write"`，默认 `"read_write"` |

## documents.remove_group — 移除分组访问权限

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 文档 ID |
| groupId | 是 | 分组 ID |

## 注意事项

- 如果用户提供的是名称而非 ID，先通过 `users.list` 或 `groups.list` 查找
- 执行权限变更前需与用户确认
