---
name: security-review
description: >
  安全审查，检查认证授权、输入验证、敏感数据处理、API 安全等。
  当用户要求 "安全审查"、"security review"、"检查安全"、添加认证、处理用户输入、创建 API 接口时触发。
license: MIT
metadata:
  author: dev-team
  version: 1.0.0
  category: security
---

# Security Review

## Instructions

### 检查清单

1. **认证与授权**
   - 密码是否使用 bcrypt/argon2 哈希存储
   - JWT token 是否设置合理的过期时间
   - API 接口是否有权限校验
   - 是否存在越权访问风险（IDOR）

2. **输入验证**
   - 所有用户输入是否经过验证和清洗
   - SQL 查询是否使用参数化查询
   - 是否防范 XSS（输出编码）
   - 文件上传是否限制类型和大小

3. **敏感数据**
   - 密钥/密码是否硬编码在代码中
   - 日志中是否泄露敏感信息
   - API 响应是否返回了不必要的敏感字段
   - 数据传输是否使用 HTTPS

4. **依赖安全**
   - 是否存在已知漏洞的依赖（CVE）
   - 依赖版本是否锁定

5. **错误处理**
   - 错误信息是否泄露系统内部细节
   - 是否有统一的错误处理机制

## Output Format

```
## 安全审查报告

### 风险等级：[HIGH / MEDIUM / LOW]

### 发现
#### CRITICAL
- [问题] → [修复建议 + 代码示例]

#### WARNING
- [问题] → [修复建议]

#### INFO
- [建议改进项]

### 合规检查
- [ ] OWASP Top 10 覆盖
- [ ] 输入验证完整
- [ ] 认证授权正确
- [ ] 敏感数据保护
```
