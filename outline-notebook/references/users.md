# 用户与分组 API 参考

## users.list — 列出所有用户

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |
| query | 否 | 按姓名搜索 |
| role | 否 | `"admin"` / `"member"` / `"viewer"` / `"guest"` |
| filter | 否 | `"all"` / `"invited"` / `"active"` / `"suspended"` |

## users.info — 获取用户信息

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 用户 ID |

## auth.info — 获取当前用户

无需参数，返回当前 API Key 对应的用户和团队信息。

## users.update — 更新个人资料

| 参数 | 必填 | 说明 |
|------|------|------|
| name | 否 | 新名称 |
| avatarUrl | 否 | 头像 URL |
| language | 否 | 语言代码，如 `"zh_CN"` / `"en_US"` |

## groups.list — 列出分组

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |

## auth.config — 获取认证配置

无需认证，无需参数。返回可用的认证提供者和团队信息。

## oAuthAuthentications.list — 列出 OAuth 认证

| 参数 | 必填 | 说明 |
|------|------|------|
| limit | 否 | 返回数量 |

## 展示格式建议

```
| 姓名       | 邮箱             | 角色   | 状态   | 最后活跃    |
|------------|------------------|--------|--------|-------------|
| Hao Yan    | hao.yan@item.com | member | active | 2026-03-14  |
```
