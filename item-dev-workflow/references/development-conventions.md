# 开发与测试阶段约定

## 环境变量优先级

1. 项目根目录 `.env`
2. 当前进程环境变量

项目根目录 `.env` 为最高优先级，全局环境变量优先级第二。只有 `.env` 缺少对应变量时，才回退到全局环境变量。

如果 `.env` 和全局环境变量都缺少必需配置，明确指出缺失变量并引导补全，不要猜测默认值。

## IAM 账号变量

- `ITEM_DEV_USERNAME`：dev 环境 IAM 账号
- `ITEM_DEV_PASSWORD`：dev 环境 IAM 密码
- `ITEM_STAGING_USERNAME`：staging 环境 IAM 账号
- `ITEM_STAGING_PASSWORD`：staging 环境 IAM 密码

## 通用可选变量

- `IAM_TOKEN_URL`：直接覆盖完整登录地址
- `IAM_TOKEN_GRANT_TYPE`：默认值为 `password`
- `ITEM_TARGET_ENV`：默认登录环境，可选 `dev` 或 `staging`
- `DOC_FILE_PATH`：过程中文件的保存位置，存放不适合提交到 Git 的文档文件，例如中间产物、临时导出文件或联调过程中生成的文档；同一个需求的文档应放在该路径下同一个子目录中

## 端口与 token

- `PORT`：项目端口
- 兼容读取：`IAM_TOKEN_PORT`、`SERVER_PORT`

如果未提供 `IAM_TOKEN_URL`，按以下顺序找端口：

1. `.env` 中的 `IAM_TOKEN_PORT`
2. `.env` 中的 `SERVER_PORT`
3. `.env` 中的 `PORT`
4. `application.yml` / `application.yaml` / `application.properties` 中的 `server.port`
5. 当前进程环境变量中的 `SERVER_PORT` / `PORT`

若当前项目登录接口遵循本地服务统一入口，可按需拼接默认登录地址：

```text
http://localhost:<PORT>/iam/token
```

token 使用规则：

- 每次联调或测试需要登录态时，重新获取新的 token
- 不复用之前会话残留的 token
- 获取方式以当前项目已有登录接口、测试脚本或认证流程为准
- 如果 token 所需配置缺失，先列出缺失变量或文件，再提示用户补全

## 开发阶段环境约定

- 项目启动需要根据环境配置 active profile
- 开发和测试优先复用项目现有能力，不要重复发明轮子

## 项目启动

本项目是 Spring Boot 多模块项目，启动入口为：

```
linker-module-client-portal-biz/src/main/java/com/item/linker/module/clientportal/ClientPortalServerApplication.java
```

启动时必须指定 active profile，dev 环境使用 `bootstrap-dev.yml`，staging 环境使用 `bootstrap-staging.yml`。

IntelliJ 启动配置示例（VM options）：

```
-Dspring.profiles.active=dev
```

启动后验证服务是否就绪：

```bash
curl -s http://localhost:<PORT>/actuator/health
```

## 多租户限制机制

本项目使用框架级多租户拦截器（`TenantDatabaseInterceptor`），对数据库查询自动追加 `AND tenant_id = '当前登录租户'` 条件。

### 两个域的区别

- **Portal 域**：tenantId 从 JWT Token 中自动提取，框架强制隔离，用户只能访问自己租户的数据
- **Admin 域**：tenantId 作为请求参数显式传入，框架**不校验** tenantId，可跨租户操作

### ignore-tables 配置

如果某张表需要加入 `ignore-tables`（跳过框架租户过滤），**不要在本地 `bootstrap-dev.yml` 中配置**，应联系开发负责人在 Nacos 的 `linker-client-portal.yml` 中统一维护：

```yaml
framework:
  tenant:
    ignore-tables:
      - 表名
```

注意：`TenantDatabaseInterceptor` 的 `ignore-tables` 在启动时一次性初始化，不支持动态刷新，修改 Nacos 配置后需要重启服务才能生效。

### Admin 域跨租户查询

Admin 域查询 `cp_*` 表时，需要在 service 层用 `queryIgnoreTenant` 包裹，绕过框架租户过滤：

```java
private <T> T queryIgnoreTenant(Callable<T> callable) {
    Boolean previousIgnore = TenantContextHolder.isIgnore();
    TenantContextHolder.setIgnore(Boolean.TRUE);
    try {
        return callable.call();
    } catch (Exception e) {
        if (e instanceof RuntimeException re) throw re;
        throw new RuntimeException(e);
    } finally {
        TenantContextHolder.setIgnore(previousIgnore);
    }
}
```

## Nacos 配置

本项目配置中心使用 Nacos，启动时从 Nacos 拉取配置覆盖本地配置。

### 连接信息

| 环境 | 地址 | 用户名 | 密码 | Namespace |
|------|------|--------|------|-----------|
| dev/staging | `nacos2-dev.item.pub:8848` | `linker` | `0f2a170d3e` | `linker` |

### 主要配置文件

- `application.yml`：公共配置
- `linker-client-portal.yml`：项目主配置（数据库、IAM、租户 ignore-tables 等）
- `redis-client-portal.yml`：Redis 配置

### 读取 Nacos 配置

```bash
# 1. 获取 token
NACOS_TOKEN=$(curl -s -X POST "http://nacos2-dev.item.pub:8848/nacos/v1/auth/login" \
  -d "username=linker&password=0f2a170d3e" | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# 2. 读取配置
curl -s "http://nacos2-dev.item.pub:8848/nacos/v1/cs/configs?dataId=linker-client-portal.yml&group=DEFAULT_GROUP&tenant=linker&accessToken=${NACOS_TOKEN}"
```

### 优先级说明

`bootstrap-dev.yml` 中的配置**优先级低于** Nacos 动态配置。

## 已知踩坑
提
### 1. TenantUtils.execute 切换租户无效

**现象**：调用 `TenantUtils.execute("LT", () -> mapper.query())` 后，查询仍然用的是登录账号的租户过滤。

**原因**：`TenantSecurityWebFilter` 在请求入口检查 `TenantContextHolder` 与登录用户 tenantId 是否一致，不一致会 403。`TenantUtils.execute` 虽然切换了 `TenantContextHolder`，但框架 filter 已在请求入口设置好了，后续 SQL 执行时 `TenantContextHolder` 的值取决于 `ignore-tables` 是否命中，而不是 `execute` 的切换。

**解决**：用 `TenantContextHolder.setIgnore(true)` 完全跳过租户过滤，执行完后恢复，即 `queryIgnoreTenant` 模式。

---

### 2. IAM 创建用户报 500

**现象**：调用 IAM `POST /platform/v1/users` 返回 `210000500`。

**原因**：`client_credentials` token 在 dev 环境没有创建用户的权限，或目标租户在 IAM 里没有注册 `client-portal` appCode。

**解决**：使用有权限的账号 token（`password` grant）调用，或联系 IAM 管理员确认租户 appCode 配置。
