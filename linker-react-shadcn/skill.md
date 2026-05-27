# Linker React + shadcn/ui 前端开发技能

## 概述
本技能集覆盖 Linker OMS 前端项目的核心开发规范与模式。
技术栈：React 19 + TypeScript + TanStack Router/Query/Table + Zustand + shadcn/ui + Tailwind CSS + react-i18next + Vite

## 技能索引

| 技能领域 | 参考文档 | 说明 |
|----------|----------|------|
| 组件开发 | [component-guide.md](./reference/component-guide.md) | 组件声明、Props、组合模式、Hooks、表单、表格、性能优化 |
| 数据与 API | [api-guide.md](./reference/api-guide.md) | HTTP 客户端、React Query、并行请求、Blob 下载、错误处理 |
| 状态管理 | [store-guide.md](./reference/store-guide.md) | Zustand Store、Context Provider、选型指南 |
| 样式与规范 | [style-guide.md](./reference/style-guide.md) | Tailwind CSS、shadcn/ui、命名规范 |
| 路由与导航 | [routing-guide.md](./reference/routing-guide.md) | TanStack Router、文件路由、导航、菜单配置、错误页面 |
| 国际化 | [i18n-guide.md](./reference/i18n-guide.md) | react-i18next、翻译文件、RTL 支持、语言切换 |
| 认证与权限 | [auth-guide.md](./reference/auth-guide.md) | OAuth 2.0、Token 管理、权限检查、多租户 |
| 功能脚手架 | [feature-scaffold-guide.md](./reference/feature-scaffold-guide.md) | 新建功能模块步骤、目录结构、列表页/详情页模板 |
| 测试 | [testing-guide.md](./reference/testing-guide.md) | Vitest、React Testing Library、Mock 模式、代码质量检查 |
| 工具函数 | [utils-guide.md](./reference/utils-guide.md) | 日期、Cookie、环境检测、日志、货币、错误处理 |

## 文件组织速查

```
src/components/              → 跨功能共享组件
src/components/ui/           → shadcn 生成（禁止修改）
src/components/common/       → 通用业务组件（PageHeader、StatusTag）
src/components/data-table/   → 表格相关组件（筛选、分页、工具栏）
src/components/layout/       → 布局壳（Main、AuthenticatedLayout）
src/features/xxx/            → 功能入口（index.tsx、detail.tsx、config.tsx）
src/features/xxx/components/ → 功能专属子组件
src/hooks/                   → 通用自定义 Hook
src/context/                 → Context Provider
src/stores/                  → Zustand 全局 Store
src/lib/api/                 → API 端点（按功能模块）
src/lib/utils/               → 工具函数
src/lib/schemas/             → Zod 校验 Schema
src/lib/types/               → TypeScript 类型定义
src/locales/                 → i18n 翻译文件
src/config/                  → 共享配置
```

## 开发 Checklist

- [ ] 使用 `function` 声明 + 命名导出
- [ ] Props 用 `interface` 定义，命名为 `XxxProps`
- [ ] 所有用户可见文本用 `t()` 包裹
- [ ] 使用 `cn()` 合并条件样式
- [ ] 传给子组件的回调用 `useCallback` 包裹
- [ ] 复杂计算用 `useMemo` 缓存
- [ ] Dialog 使用 `open` + `onOpenChange` 受控模式
- [ ] API 调用使用 React Query 或 ProTable
- [ ] 错误处理使用 try-catch + toast
- [ ] 文件名使用 kebab-case
- [ ] 不修改 `src/components/ui/` 下的文件
- [ ] 不手动排序 import（Prettier 自动处理）
- [ ] 提交前运行 `pnpm lint` + `pnpm format` + `pnpm i18n:check-hardcoded`
