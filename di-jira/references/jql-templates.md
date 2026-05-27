# 常用 JQL 查询模板

## 按角色查询

```
# 我的当前 Sprint 任务
assignee = {username} AND sprint in openSprints() AND project = DTS

# 我作为 Developer 的任务
cf[11103] = {username} AND sprint in openSprints() AND project = DTS

# 我作为 QA 的任务
cf[11102] = {username} AND sprint in openSprints() AND project = DTS
```

## 按状态查询

```
# 当前 Sprint 未完成任务
project = DTS AND sprint in openSprints() AND status not in (Closed, Released, Canceled)

# 等待 PO Review
project = DTS AND status = "Ready for PO Review" AND sprint in openSprints()

# PO Review 不通过
project = DTS AND status = "PO Review Failed" AND sprint in openSprints()

# 测试失败需退回
project = DTS AND status = "Test Failed" AND sprint in openSprints()
```

## 按分配查询

```
# 未分配的任务
project = DTS AND assignee is EMPTY AND sprint in openSprints()

# 某人的待办
project = DTS AND assignee = {username} AND status in (New, "Planned for Sprint", Backlog)
```

## Epic 相关

```
# Epic 下所有任务
"Epic Link" = {epicKey}

# Epic 下未完成任务
"Epic Link" = {epicKey} AND status not in (Closed, Released, Canceled)
```

## 开发工时统计

**不能用 assignee，不能用 openSprints()**，详见 SKILL.md 2.11 节完整流程。

```
# 某开发当前迭代的开发工时
# 1. 先通过 Agile API 获取精确 Sprint ID
# 2. 用 Developer 字段 + 精确 Sprint ID 查询
cf[11103] = {username} AND sprint = {sprintId} AND project = DTS
# 3. 二次过滤：只保留 customfield_10005 中仅含 1 个 Sprint 的 Issue（排除历史遗留）
```

## Sprint 进度

```
# 当前 Sprint 所有任务
project = DTS AND sprint in openSprints()

# 当前 Sprint 已完成
project = DTS AND sprint in openSprints() AND status in (Released, Closed, "PO Approved")
```
