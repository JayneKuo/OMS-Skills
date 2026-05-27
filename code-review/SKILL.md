---
name: code-review
description: >
  审查代码变更，检查安全漏洞、错误处理、代码复杂度、命名规范和性能问题。
  当用户要求 "review PR"、"审查代码"、"review diff"、"代码审查" 时触发。
license: MIT
metadata:
  author: dev-team
  version: 1.0.0
  category: developer-tools
---

# Code Review

## Instructions

1. 阅读完整的 diff 或代码文件
2. 检查 OWASP Top 10 安全漏洞（SQL 注入、XSS、CSRF 等）
3. 评估错误处理是否完善
4. 评估代码复杂度和可读性
5. 检查命名规范和代码风格一致性
6. 查找性能问题（N+1 查询、不必要的循环、内存泄漏等）
7. 检查输入验证和边界条件

## Output Format

```
## 审查总结
[一句话总结]

## 发现
### CRITICAL
- [文件:行号] 问题描述
  修复建议：[代码示例]

### WARNING
- [文件:行号] 问题描述
  修复建议：[代码示例]

### SUGGESTION
- [文件:行号] 问题描述
  修复建议：[代码示例]

## 优秀实践
- [值得肯定的代码模式]
```
