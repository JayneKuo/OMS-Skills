# 团队工作流知识

## Sprint 管理

- 固定**两周一个迭代**
- BA 级看板：`boardId=127`（`rapidView=127`）
- PM 级看板：`boardId=101`（`rapidView=101`）

## 任务类型使用规范

- 主要使用 **Story**，极少创建 Bug 或 Task
- 大任务需拆分为 **Sub-task**
- 相关需求归属到 **Epic** 下管理

## 任务分配流程

1. 评审会上研发根据兴趣/分工主动认领
2. 若无人认领 → TL 指定
3. 若 TL 未指定 → PM 直接指派给 TL 进行二次分配
4. 每个研发有固定负责模块

## PO Review 流程

- PO Review 在 **Stage（预发）环境**进行
- 通过 → 标记 `PO Review Pass`
- 不通过 → 标记 `PO Review Failed`，在评论区写明具体问题

## 开发完成交付检查清单

1. 将 Issue assign 给 QA
2. 确认 Developer 字段（`customfield_11103`）是自己
3. 确认 Sprint 已设置
4. 在 commit url（`customfield_10805`）或评论中备注做了什么

## 角色操作指南

### PM
- 关注 Big picture：所有项目完成度、优先级、是否 assign 到人
- Epic 管理：把相关需求 assign 到同一 Epic 下
- Sprint 进度：全局视角评估，推荐 `boardId=101`

### BA
- 需求创建：先在外部文档写好规格，复制到 Jira Description
- PO Review：在 Stage 环境验收，检查是否符合需求文档
- 反馈问题：不通过时在评论区写明具体错误
- 推荐看板：`boardId=127`

### Dev
1. 查看当前 Sprint 分配给自己的任务
2. 迭代结束前确认工时是否充足
3. 每日检查有没有新 ticket 分到自己
4. 大任务创建 Sub-task 分步完成
5. 开发完成：assign 给 QA → 确认 Developer 是自己 → 确认 Sprint → commit 备注
6. 查问题类任务：查完后 assign 回反馈人

## 已知注意事项

- Sub-task 状态**不会自动联动**到 Parent Ticket，需手动维护
