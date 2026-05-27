---
name: Vue + Element Plus 规范
version: 1.0.0
description: Vue 3 + Element Plus 技术栈的开发规范总览，涵盖组件、API、Store、样式、路由等子规范索引。适用于Element Plus 项目。
---

# Linker Vue + Element Plus 开发规范

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
- 组件库：Element Plus
- 状态管理：Pinia
- 路由：Vue Router 4
- 表单校验：Element Plus 内置 Form 校验（rules）
- 样式：SCSS + Tailwind CSS + Element Plus 主题变量
- 图标：Material Icons Outlined + @element-plus/icons-vue
- HTTP：axios（封装为 HttpApi）
- 缓存：localStorage / sessionStorage（WebStorageCache 封装）

## 组件开发
详见 [component-guide](./reference/component-guide.md)

## API 开发
详见 [api-guide](./reference/api-guide.md)

## 状态管理
详见 [store-guide](./reference/store-guide.md)

## 样式规范
详见 [style-guide](./reference/style-guide.md)

## 路由规范
详见 [router-guide](./reference/router-guide.md)
