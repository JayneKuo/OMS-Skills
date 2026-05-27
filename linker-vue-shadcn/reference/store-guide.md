# Vue + shadcn-vue Store 规范

## 目录结构
```
src/app/stores/
  ├── app-theme.ts          # 主题
  ├── tenant-store.ts       # 租户
  ├── principal.ts          # 认证主体（当前用户）
  ├── user-info.ts          # 用户信息
  ├── rbac/                 # RBAC（index.ts barrel export）
  ├── yms/                  # YMS 模块
  ├── tms/                  # TMS 模块
  ├── client-portal/        # Client Portal 模块
  └── wms/                  # WMS 模块
```

## 两种模式

### 模式一：Class + defineStore（需要 inject('api')）
```typescript
import { define } from '@utils/define-store';
import { inject, ref } from 'vue';
import type { IHttp } from '@utils/http';

class XxxStore {
  static create() {
    return define(() => {
      const api = inject<IHttp>('api');
      const data = ref<XxxItem[]>([]);
      const loading = ref(false);

      async function loadData() {
        loading.value = true;
        try {
          const { data: result } = await api!.get<XxxItem[]>('/api/xxx');
          data.value = result;
        } finally {
          loading.value = false;
        }
      }

      function $reset() {
        data.value = [];
        loading.value = false;
      }

      return { data, loading, loadData, $reset };
    })();
  }
}

function useXxxStore() {
  return XxxStore.create();
}
export { useXxxStore };
```

### 模式二：标准 Pinia defineStore（推荐新建）
```typescript
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useXxxStore = defineStore('xxx-store', () => {
  const data = ref<string[]>([]);

  async function loadData() {
    if (data.value.length) return; // 已有数据跳过
    // ...
  }

  function $reset() {
    data.value = [];
  }

  return { data, loadData, $reset };
});
```

## 规范
- 新建 store 优先模式二，更简洁
- 需要 `inject('api')` 的用模式一
- 文件名 kebab-case：`yms-bridge-store.ts`
- 导出 `useXxxStore`
- 必须提供 `$reset()`，登出时清理状态
- 异步操作用 `loading` ref 跟踪
- 错误处理 try/catch + `console.error`

## 缓存策略
- Store 内部判断已有数据则跳过请求
- 跨页面共享数据放 Pinia store，不放 composable 局部 ref
- 持久化用 `cache`（`@utils/cache`），自动加 `item-client-web/` 前缀
- 缓存 key 常量在 `src/app/constants/cache-key.ts`

## 常用 Store
- `useAppTheme()` — 主题（`mode`、`toggle_mode()`）
- `useTenantStore()` — 租户（`currentTenant`、`switchTenant()`）
- `usePrincipal()` — 当前用户（`get_subject()`、`user_permissions`、`is_admin`）
- `useUserInfo()` — 用户详情（`load()`、`userInfo`）
- `usePermissionStore()` — 权限（`allPermissions`、`fetchPermissions()`）

## 注意
- Store 中不要直接操作 DOM
- 不要静默吞掉错误
