# Vue + Element Plus 样式规范

## 技术栈
- SCSS + Tailwind CSS（`@apply` 混用）
- CSS 变量主题系统
- Element Plus 主题覆盖

## 主题系统
- 亮色/暗色通过 `useAppStore().toggleTheme()` 切换
- 暗色模式通过 `document.documentElement.classList.add('dark')` 激活
- 主题名通过 `.item-purple` 等类名控制
- 颜色统一用 CSS 变量，不要硬编码：
  ```scss
  color: var(--text-color);
  background-color: var(--bg-color);
  border-color: var(--border-color);
  ```

## CSS 变量（src/styles/global.scss）
```scss
--primary-color: #6B4EFF;
--primary-light: #8A63BE;
--dark-bg: #1A1B23;
--darker-bg: #15161C;
--card-bg: #1E1F27;
--text-color: #E8E8E8;
--text-secondary: rgba(255, 255, 255, 0.6);
--border-color: #CECECE;
```

## SCSS 变量（src/styles/variables.scss）
- 布局：`$header-height`、`$sidebar-width`、`$sidebar-collapsed-width`
- 断点：`$xs`、`$sm`、`$md`、`$lg`、`$xl`
- z-index 层级：`$z-index-normal` ~ `$z-index-tooltip`
- 阴影：`$box-shadow-base`、`$box-shadow-light`

## 样式文件结构
```
src/styles/
  ├── global.scss                    # 全局样式 + CSS 变量
  ├── variables.scss                 # SCSS 变量
  ├── element-plus-theme.scss        # Element Plus 主题覆盖
  ├── element-plus-reset-light.scss  # 亮色模式重置
  ├── element-plus-reset-dark.scss   # 暗色模式重置
  ├── fonts.scss                     # 字体定义
  ├── mixins.scss                    # SCSS mixins
  ├── themes.scss                    # 主题定义
  └── design-system/                 # 设计系统 token
```

## Tailwind + SCSS 混用
- 布局优先 Tailwind：`@apply flex items-center gap-2 px-4 py-2`
- 复杂样式用 SCSS：嵌套、变量、mixin
- Element Plus 覆盖用 SCSS + CSS 变量

## scoped 样式
- `<style lang="scss" scoped>` 用于组件私有样式
- 穿透 Element Plus 子组件：`:deep(.el-xxx)`
- 全局样式放 `src/styles/` 目录

## Element Plus 样式覆盖
```scss
// 通过 CSS 变量覆盖
:root {
  --el-color-primary: var(--primary-color);
}

// 通过 :deep 穿透
:deep(.el-select-dropdown__item) {
  color: var(--text-color);
}

// 暗色模式特殊处理
.item-purple.dark .el-xxx {
  background-color: rgba(27, 28, 35, 1);
}
```

## 常用样式模式
- 页面导航栏：`.page-navbar`（sticky + backdrop-filter）
- 搜索表单：`.search-form`
- 表格表单：`.table-from`
- 自定义滚动条：`::-webkit-scrollbar` 已全局定义

## 注意
- 避免 `!important`，优先通过提高选择器优先级解决
- 不要用内联 style 做主题色
- 暗色模式样式用 `.dark` 或 `.item-purple.dark` 前缀
