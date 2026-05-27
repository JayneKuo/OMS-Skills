---
name: Vue + shadcn-vue 规范
version: 1.0.0
description: Vue 3 + shadcn-vue 技术栈的开发规范总览，涵盖组件、API、Store、样式、路径别名、权限体系、主题系统等。适用于shadcn-vue 项目。
---

# Linker Vue + shadcn-vue 开发规范

## 代码风格
- 2 空格缩进，单引号，分号，100 字符行宽
- Prettier：`useTabs: false, tabWidth: 2, printWidth: 100, singleQuote: true, trailingComma: 'es5', semi: true`
- ESLint：`eslint:recommended` + 框架对应插件
- 文件命名：组件支持 PascalCase（`UserCard.vue`）或 kebab-case（`user-card.vue`），以当前项目已有代码风格为准；工具函数统一 kebab-case

## Git 提交规范
- commit message 必须包含 ticket 号：`{前缀}-{数字}`
- 支持前缀：WISE2018、REPORT、LITE、LM、ASSET、TRF、RMS、GIS、CP、CRM、DTS
- 示例：`CP-9703 feat: add role management page`、`DTS-9699 feat: add yms iframe pages`

## 技术栈
- Vue 3 + TypeScript + Vite
- 组件库：shadcn-vue（基于 reka-ui）
- 状态管理：Pinia
- 路由：Vue Router 4
- 表单校验：vee-validate + yup + shadcn Form
- 样式：Tailwind CSS + SCSS
- 图标：lucide-vue-next
- composable 命名：`useFoo.ts`

## 路径别名
- `@/` → `src/app/`
- `@views/` → `src/app/views/`
- `@components/` → `src/app/components/`
- `@stores/` → `src/app/stores/`
- `@utils/` → `src/app/utils/`
- `@services/` → `src/app/services/`
- `@constants/` → `src/app/constants/`
- `@apis/` → `src/app/apis/`
- `@assets/` → `src/assets/`
- `@models/` → `src/app/models/`

## 缓存工具
- 使用 `cache`（`@utils/cache`），自动加 `item-client-web/` 前缀
- 缓存 key 常量在 `src/app/constants/cache-key.ts`
- 示例：`await cache.getItem<string>('i18n-locale')` → 实际读 `item-client-web/i18n-locale`

## 权限体系
- 路由 meta 的 `permissions` 字段控制菜单显示
- `router.ts` 的 `specialRoutePermissions` 映射表控制路由访问
- 两处权限字符串必须一致
- 格式：`module:action:subaction`（如 `location:status:view`）
- 管理员（`is_admin`）和通配符（`*`）直接放行

## 主题系统
- `useAppTheme()` store 管理
- `appTheme.mode` — `'dark'` 或 `'light'`
- 切换：`toggle_mode()` / `use_dark_mode()` / `use_light_mode()`

## 组件开发
详见 [component-guide](./reference/component-guide.md)

## API 开发
详见 [api-guide](./reference/api-guide.md)

## 状态管理
详见 [store-guide](./reference/store-guide.md)

## 样式规范
详见 [style-guide](./reference/style-guide.md)
