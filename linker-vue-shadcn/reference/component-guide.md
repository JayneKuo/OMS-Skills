# Vue + shadcn-vue 组件规范

## 目录结构
- 页面：`src/app/views/{模块}/index.vue`，子组件放 `components/` 子目录
- 全局共享：`src/app/components/global/`（page-container.vue、content-area.vue）
- UI 基础：`src/app/components/ui/`（shadcn-vue 组件）
- 业务组件：`src/app/components/`（如 rbac/、wms-common-widget/）

## 页面布局
- 列表页使用 `<page-container>` + `<content-area>` 包裹
- `page-container` props：`title`、`size="full"`、`padded`、`background="default"`
- `content-area` props：`background="transparent"`、`show-filters`
- 搜索栏放 `<template #filters>`，操作按钮放 `<template #actions>`

## SFC 规范
```vue
<template>
  <!-- 模板 -->
</template>

<script setup lang="ts">
// 1. Vue 核心（ref, computed, onMounted）
// 2. 第三方库（useI18n, lucide 图标）
// 3. UI 组件（Button, Card, Input）
// 4. Store / API / 工具
// 5. 类型导入
// 6. 响应式状态
// 7. 计算属性
// 8. 方法
// 9. 生命周期
</script>

<style lang="scss" scoped>
/* 样式 */
</style>
```

## 表单
- vee-validate + yup + shadcn Form 组件
- 结构：`<Form>` → `<FormField v-slot="{ componentField, errorMessage }">` → `<FormItem>` → `<FormLabel>` + `<FormControl>` + `<FormMessage>`
- 校验在失去焦点时自动触发
- 必填标记：`<span class="text-destructive">*</span>`
- 错误边框：`:class="{ 'border-destructive': errorMessage }"`
- yup schema 示例：
```typescript
const validationSchema = toTypedSchema(
  yup.object({
    name: yup.string().required('请输入名称'),
    email: yup.string().required('请输入邮箱').email('邮箱格式不正确'),
    status: yup.string().oneOf(['active', 'inactive']).required(),
  }),
);
```

## 弹窗
- shadcn Dialog 组件
- 背景色：`bg-card text-card-foreground border-border`
- 结构：`DialogContent` → `DialogHeader` + 内容 + `DialogFooter`
- 通过 `v-model:open` 或 `v-model:visible` 控制显隐

## 表格
- shadcn Table 或 UnisTable
- 分页：`SystemPagination` 组件
- 操作列：`DropdownMenu`

## Checkbox 注意事项
- reka-ui 的 Checkbox 在受控模式下有 bug，`checked` prop 更新不反映到 UI
- 解决方案：用原生 `<button role="checkbox">` + lucide 图标（Check / Minus）
- 三态：选中（Check 图标 + bg-primary）、半选（Minus 图标 + bg-primary）、未选（空）
- 参考实现：
```vue
<button
  type="button" role="checkbox"
  :aria-checked="state === 'partial' ? 'mixed' : state === 'all'"
  class="h-4 w-4 shrink-0 rounded-sm border border-primary flex items-center justify-center"
  :class="state !== 'none' ? 'bg-primary text-primary-foreground' : ''"
  @click.stop="onCheck"
>
  <Check v-if="state === 'all'" class="h-3 w-3" />
  <Minus v-else-if="state === 'partial'" class="h-3 w-3" />
</button>
```

## 国际化
```typescript
const { t } = useI18n();
const safeT = createSafeTranslate('module-name', t);
safeT('title')  // → t('module-name.title')
// 动态插值必须用原始 t() + 完整 key
t('module-name.deleteDialog.confirmMessage', { roleName: 'Admin' })
```
