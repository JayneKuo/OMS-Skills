# Vue + shadcn-vue 样式规范

## 技术栈
- Tailwind CSS + SCSS
- CSS 变量主题系统（`hsl(var(--primary))`）
- shadcn-vue 设计令牌

## 主题
- 亮色/暗色通过 `useAppTheme()` 切换
- 颜色用 CSS 变量类名：`text-primary`、`bg-card`、`border-border`、`text-muted-foreground`、`text-destructive`
- 不要硬编码颜色值

## 布局
- 优先 Tailwind 工具类：`flex`、`grid`、`gap-*`、`p-*`、`m-*`
- 响应式前缀：`sm:`、`md:`、`lg:`
- 滚动容器三件套：`overflow-y-auto` + `flex-1` + `min-h-0`

## scoped 样式
- `<style lang="scss" scoped>` 用于组件私有样式
- 穿透子组件：`:deep(.class)`
- 影响祖先元素：非 scoped `<style>` + `:has()` 选择器做作用域隔离
  ```scss
  // 只在当前页面生效，离开后自动失效
  .main-content:has(.my-page-class) {
    overflow: hidden;
  }
  ```

## 常用样式模式
- 弹窗背景：`bg-card text-card-foreground border-border`
- 必填标记：`<span class="text-destructive">*</span>`
- 错误边框：`:class="{ 'border-destructive': errorMessage }"`
- 禁用状态：`disabled:cursor-not-allowed disabled:opacity-50`
- 悬停效果：`hover:bg-muted/50 transition-colors`

## 注意
- 不要用 `!important`
- 不要用内联 style 做主题色
- 不要用 Element Plus 的样式类（项目已迁移到 shadcn-vue）
