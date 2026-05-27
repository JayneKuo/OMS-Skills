# Vue + Element Plus Store 规范

## 目录结构
```
src/stores/
  ├── useAppStore.ts          # 应用状态（主题、侧边栏、loading）
  ├── usePrincipalStore.ts    # 认证主体（当前用户、token）
  ├── user.ts                 # 用户信息
  ├── app-theme.ts            # 主题
  ├── ele-plus-i18n.ts        # Element Plus 国际化
  ├── area-code/              # 区号模块
  ├── coupon/                 # 优惠券模块
  ├── permission/             # 权限模块
  └── user-management/        # 用户管理模块
```

## 标准 Pinia defineStore（推荐）
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useXxxStore = defineStore('xxx', () => {
  // 状态
  const list = ref<XxxItem[]>([])
  const loading = ref(false)

  // 计算属性
  const total = computed(() => list.value.length)

  // 方法
  async function loadData(params = {}) {
    loading.value = true
    try {
      const result = await getXxxList(params)
      list.value = result.list ?? []
    } catch (e) {
      console.error('Failed to load data:', e)
    } finally {
      loading.value = false
    }
  }

  function $reset() {
    list.value = []
    loading.value = false
  }

  return { list, loading, total, loadData, $reset }
})
```

## 规范
- 使用 Composition API 风格的 `defineStore`
- 文件名 camelCase：`useXxxStore.ts` 或 kebab-case：`xxx-store.ts`（以项目已有风格为准）
- 导出 `useXxxStore`
- 必须提供 `$reset()`，登出时清理状态
- 异步操作用 `loading` ref 跟踪
- 错误处理 try/catch + `console.error`

## 缓存策略
- 持久化用 `cache`（`@/utils/cache`），前缀 `portal-admin-web/`
- 会话级缓存用 `session`（同模块导出）
- 缓存 key 常量在 `src/constants/cache-key.ts`
- 缓存支持过期时间：`cache.setItem(key, value, { expiredAt: Date.now() + ms })`

## 常用 Store
- `useAppStore()` — 主题切换、侧边栏、全局 loading
- `usePrincipalStore()` — 当前用户、token、登录/登出
- `usePrincipalStore().isSignedIn` — 是否已登录
- `usePrincipalStore().isAdmin` — 是否管理员

## 注意
- Store 中不要直接操作 DOM（主题切换除外，通过 `document.documentElement.classList` 操作）
- 不要静默吞掉错误
- localStorage 操作建议通过 `cache` 工具类，保持前缀一致
