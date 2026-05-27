# Vue + Element Plus 路由规范

## 路由文件
- 路由定义：`src/router/index.ts`
- 布局组件：`src/layouts/AdminLayout.vue`（后台管理）、`src/layouts/DefaultLayout.vue`

## 路由结构
```typescript
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/home' },
  {
    path: '/login',
    name: 'login',
    component: () => import('../pages/login/index.vue'),
    meta: { title: 'login.SignIn', hidden: true, requiresAuth: false }
  },
  {
    path: '/',
    component: AdminLayout,
    children: [
      // 所有后台页面作为 AdminLayout 的子路由
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'not-found', ... }
]
```

## 路由 Meta 类型
```typescript
interface RouteMeta {
  title?: string;           // 页面标题（国际化 key）
  icon?: string;            // 菜单图标（HTML 字符串）
  hidden?: boolean;         // 是否在菜单中隐藏
  keepAlive?: boolean;      // 是否缓存组件
  needCheckIsAdmin?: boolean; // 是否需要管理员权限
  requiresAuth?: boolean;   // 是否需要登录
}
```

## 添加新页面
1. 在 `src/pages/{模块}/` 下创建页面组件
2. 在 `src/router/index.ts` 的 `AdminLayout.children` 中添加路由
3. `meta.title` 使用国际化 key（如 `'menus.xxx'`）
4. `meta.requiresAuth: true` 需要登录的页面
5. 子页面（如创建/编辑）设置 `meta.hidden: true` 不显示在菜单

## 路由示例
```typescript
{
  path: 'module-name',
  name: 'module-name',
  meta: {
    title: 'menus.moduleName',
    icon: '<span class="material-icons-outlined">icon_name</span>',
    requiresAuth: true
  },
  children: [
    {
      path: 'list',
      name: 'module-list',
      component: () => import('@/pages/module-name/index.vue'),
      meta: { title: 'menus.moduleList', requiresAuth: true }
    },
    {
      path: 'create',
      name: 'module-create',
      component: () => import('@/pages/module-name/create.vue'),
      meta: { title: 'module.create', hidden: true, requiresAuth: true }
    },
    {
      path: 'edit/:id',
      name: 'module-edit',
      component: () => import('@/pages/module-name/create.vue'),
      meta: { title: 'module.edit', hidden: true, requiresAuth: true }
    }
  ]
}
```

## 路由守卫
- 全局前置守卫已配置：
  - 未登录 → 尝试从 cache 恢复 → 失败则跳转 `/login`
  - 已登录访问 `/login` → 重定向到 `/home`
- token 判断：`usePrincipalStore().isSignedIn` + `cache.getItem(CK_TOKEN)`

## 菜单生成
- `generateMenu()` 从路由配置自动生成菜单
- 过滤 `meta.hidden: true` 的路由
- 支持嵌套子菜单

## 页面文件结构
```
src/pages/{模块名}/
  ├── index.vue              # 列表页
  ├── create.vue             # 新增/编辑页（复用）
  └── components/            # 页面私有组件
       ├── XxxDialog.vue
       └── XxxTable.vue
```

## 注意
- 路由懒加载：统一用 `() => import(...)` 动态导入
- 路由 name 使用 kebab-case
- 图标使用 Material Icons Outlined
