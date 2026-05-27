# 认证与权限指南

## 1. 认证流程

基于 OAuth 2.0 授权码模式，通过 IAM 服务实现：

```
用户访问 → 检查 Token → 无效 → 跳转 IAM 登录页
                        → 有效 → 加载用户信息 → 初始化租户/商户 → 进入应用
IAM 登录成功 → 回调 /auth-code → 用 code 换 token → 存储 Cookie → 跳回原页面
```

### 1.1 IAM 配置
位于 `src/config/iam.config.ts`，所有配置从环境变量读取：

```tsx
import IamConfig from "@/config/iam.config";

IamConfig.clientId;           // OAuth Client ID
IamConfig.authorizeEndpoint;  // 授权端点
IamConfig.getAuthorizeUrl();  // 构建完整授权 URL
IamConfig.getRedirectUrl();   // 回调地址
IamConfig.getLogoutUrl(token); // 登出 URL
```

### 1.2 Token 管理
Token 存储在 Cookie 中，通过 `useAuthStore` 管理：

```tsx
import { useAuthStore } from "@/stores/auth-store";

// 设置 Token
useAuthStore.getState().auth.setAccessToken(token);

// 获取 Token（组件外，如拦截器中）
const token = useAuthStore.getState().auth.accessToken;

// 清除认证状态
useAuthStore.getState().auth.reset();
```

### 1.3 自动注入
HTTP 拦截器自动在请求头注入：
- `Authorization: Bearer {token}` - 认证令牌
- `x-tenant-id: {tenantCode}` - 租户标识
- `locale: {language}` - 语言偏好

---

## 2. 权限系统

### 2.1 权限模型
用户权限来自 IAM，格式为 `app:resource`：

```tsx
interface UserPermission {
  id: string;
  name: string;      // 权限标识，如 "linker-oms:sales-order"
  parentId: string;
  title: string;
  app: string;
  externalInfo: Record<string, unknown>;
}
```

### 2.2 权限检查 API

```tsx
import { hasPermission, canAccessRoute, filterMenuByPermissions } from "@/lib/permission";

// 检查单个权限
hasPermission(user.userPermissions, "linker-oms:sales-order"); // true/false

// 过滤菜单树（自动递归，无可见子项的父菜单也会隐藏）
const visibleMenu = filterMenuByPermissions(menuData, user.userPermissions);

// 检查路由访问权限
canAccessRoute("/sales-orders", menuData, user.userPermissions);
```

### 2.3 权限规则
- 未配置 `permission` → 默认公共访问
- `permission: "*"` → 显式公共访问
- `permission: "linker-oms:xxx"` → 需要对应权限
- localhost 环境 → 自动跳过所有权限检查

### 2.4 管理员权限

```tsx
// userType === 0 为超级管理员
const canAdmin = useAuthStore((s) => s.auth.canAccessAdmin());
```

---

## 3. 多租户

### 3.1 租户切换

```tsx
import { useTenantStore } from "@/stores/tenant-store";

const { getCurrentTenant, getCurrentTenantCode, setCurrentTenant } = useTenantStore.getState();

// 切换租户
setCurrentTenant(newTenant);
```

### 3.2 商户切换

```tsx
import { useMerchantStore } from "@/stores/merchant-store";

const { getCurrentMerchant, setCurrentMerchant } = useMerchantStore.getState();
```

租户/商户信息在认证守卫中初始化，切换后会刷新页面数据。

---

## 4. 环境检测

```tsx
import { isLocalhostEnv, isDevelopmentEnv, isStagingEnv, isProductionEnv } from "@/lib/env";

// localhost 环境跳过权限检查
if (isLocalhostEnv()) { /* 本地开发，权限全开 */ }

// 生产环境特殊处理
if (isProductionEnv()) { /* 生产环境逻辑 */ }
```

环境由 `VITE_APP_ENV` 环境变量控制：`localhost` | `development` | `staging` | `production`
