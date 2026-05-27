# DTS 项目自定义字段映射

从 Jira 实例 API 验证获取。

## 人员字段

| 字段 ID | 字段名称 | 类型 | 值格式 |
|---------|---------|------|--------|
| `customfield_11103` | Developer | multi-user picker | `[{"name": "username"}]` |
| `customfield_11000` | Developer(single) | user picker | `{"name": "username"}` |
| `customfield_11102` | QA | multi-user picker | `[{"name": "username"}]` |
| `customfield_11104` | BA | multi-user picker | `[{"name": "username"}]` |
| `customfield_10804` | Quality assurance (QA) | user picker | `{"name": "username"}` |
| `customfield_12404` | Escalated Assignee | user picker | `{"name": "username"}` |

## 工时/点数字段

| 字段 ID | 字段名称 | 类型 | 值格式 |
|---------|---------|------|--------|
| `customfield_10002` | Story Points | float | `3.0` |
| `customfield_11602` | Dev Hours | float | `8.0` |
| `customfield_11601` | Test Hours | float | `4.0` |
| `customfield_11901` | Story Points for BA | float | `2.0` |
| `customfield_12100` | Test Points | float | `1.0` |
| `customfield_12801` | Story Point for Lead | string | `"3"` |
| `customfield_12802` | Estimate SP | float | `5.0` |

## Sprint / Epic 字段

| 字段 ID | 字段名称 | 类型 | 值格式 |
|---------|---------|------|--------|
| `customfield_10005` | Sprint | gh-sprint | Sprint ID（数字） |
| `customfield_10006` | Epic Link | gh-epic-link | `"DTS-1234"` |
| `customfield_10007` | Epic Name | string | Epic 名称（创建 Epic 时） |

## 日期字段

| 字段 ID | 字段名称 | 值格式 |
|---------|---------|--------|
| `customfield_12800` | Start Date | `"YYYY-MM-DD"` |
| `customfield_11701` | Expected Testing Time | `"YYYY-MM-DD"` |

## 其他字段

| 字段 ID | 字段名称 | 类型 | 值格式 |
|---------|---------|------|--------|
| `customfield_10805` | commit url | string | URL 字符串 |
| `customfield_12201` | Pending | select | `{"value": "选项值"}` |
| `customfield_12300` | Demand Type | select | `{"value": "选项值"}` |
| `customfield_12402` | Code Change | - | - |
| `customfield_12622` | Bug Responsible | - | - |
| `customfield_12623` | Severity | - | - |
| `customfield_10700` | url | string | URL 字符串 |
| `customfield_11801` | Function | string | 功能模块名 |
| `customfield_10000` | Flagged | multi-checkbox | - |

## 常见更新示例

```json
// 指派人
{"fields": {"assignee": {"name": "username"}}}

// Developer（多选）
{"fields": {"customfield_11103": [{"name": "dev1"}, {"name": "dev2"}]}}

// QA（多选）
{"fields": {"customfield_11102": [{"name": "qa1"}]}}

// Story Points
{"fields": {"customfield_10002": 5.0}}

// 优先级
{"fields": {"priority": {"name": "Major"}}}

// Epic Link
{"fields": {"customfield_10006": "DTS-1234"}}
```

## 状态列表

### To Do
| ID | 名称 |
|----|------|
| 1 | New |
| 10100 | Pending |
| 11200 | Backlog |
| 11800 | Requirement Ready |

### In Progress
| ID | 名称 |
|----|------|
| 10807 | Planned for Sprint |
| 3 | In Dev |
| 10810 | Work in progress |
| 11700 | In Progress |
| 11005 | Dev Completed |
| 11006 | Released to Staging |
| 11007 | QA Testing |
| 10614 | Testing |
| 11100 | Ready to Test |
| 11101 | Test Failed |
| 11600 | Ready for PO Review |
| 11601 | PO Review Failed |
| 11602 | PO Review Pass |

### Done
| ID | 名称 |
|----|------|
| 11009 | PO Review |
| 11011 | PO Approved |
| 11010 | Released |
| 6 | Closed |
| 10808 | Canceled |
