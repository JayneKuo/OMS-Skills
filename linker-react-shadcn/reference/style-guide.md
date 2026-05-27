# 样式与规范指南

## 1. Tailwind CSS 常用模式

```tsx
// 响应式布局（移动优先）
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

// Flex 布局
<div className="flex items-center justify-between gap-2">

// 条件样式（cn 工具函数 = clsx + tailwind-merge）
import { cn } from "@/lib/utils";
<div className={cn("rounded-lg border p-4", isActive && "border-primary", className)}>

// data 属性驱动样式
<Button data-empty={!selected} className="data-[empty=true]:text-muted-foreground">

// 暗色模式
<div className="bg-background text-foreground dark:bg-slate-950">

// 动画
<Loader2 className="size-10 animate-spin text-primary" />
```

---

## 2. shadcn/ui 使用规则

- `src/components/ui/` 由 shadcn CLI 生成，禁止手动修改
- 通过 `className` 覆盖样式，用 `cn()` 合并
- 使用 `variant` 和 `size` props 控制变体

```tsx
<Button variant="destructive" size="sm">删除</Button>
<Badge variant="outline" className="border text-success bg-success-light">成功</Badge>
<Dialog open={open} onOpenChange={onOpenChange}>
  <DialogContent><DialogHeader><DialogTitle>标题</DialogTitle></DialogHeader></DialogContent>
</Dialog>
```

---

## 3. 国际化（i18n）

### 3.1 基本用法

```tsx
import { useTranslation } from "react-i18next";

export function MyComponent() {
  const { t } = useTranslation("namespace");
  return (
    <div>
      <h1>{t("title")}</h1>
      <p>{t("description", { defaultValue: "默认文本" })}</p>
      <Button>{t("common.button.confirm")}</Button>
    </div>
  );
}
```

### 3.2 翻译文件
位于 `src/locales/<lang>/<namespace>.json`，key 按字母排序：

```json
{ "actions": "Actions", "description": "Manage orders", "title": "Orders" }
```

### 3.3 规则
- 所有用户可见文本必须用 `t()` 包裹
- 提交前运行 `pnpm i18n:check-hardcoded` 检查遗漏
- 运行 `pnpm i18n:check-missing` 检查缺失翻译

---

## 4. 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件/目录 | kebab-case | `order-columns.tsx`、`small-parcel/` |
| React 组件 | PascalCase | `OrderList`、`StatusTag` |
| Hook 文件 | `use-xxx.ts` | `use-dialog-state.tsx` |
| 变量/函数 | camelCase | `orderData`、`handleSubmit` |
| 常量 | UPPER_SNAKE_CASE | `APP_CACHE_PREFIX` |
| 类型/接口 | PascalCase | `OrderItem`、`AuthState` |
| API 函数 | `getXxxApi`/`postXxxApi` | `getOrderListApi` |
| Store | `useXxxStore` | `useAuthStore` |
| 翻译 key | `namespace.keyPath` | `smallParcel.title` |

---

## 5. 工具函数

### 5.1 核心工具

```tsx
// cn() - 条件类名合并（clsx + tailwind-merge）
import { cn } from "@/lib/utils";
cn("base", isActive && "active", className);

// sleep() - 延迟
await sleep(1000);

// getPageNumbers() - 分页页码生成（带省略号）
getPageNumbers(5, 20); // [1, "...", 4, 5, 6, "...", 20]
```

### 5.2 日期工具（src/lib/utils/date-utils.ts）
基于 dayjs，固定时区为 America/Los_Angeles：

```tsx
import { formattedTime12Hour, everyTimeToTimeZone, CST_TIME_ZONE } from "@/lib/utils/date-utils";

formattedTime12Hour(timestamp, "MM/DD/YYYY hh:mm:ss A", CST_TIME_ZONE);
everyTimeToTimeZone("01/15/2025 02:30:00 PM");
```

### 5.3 Cookie 工具（src/lib/cookies.ts）

```tsx
import { getCookie, setCookie, removeCookie } from "@/lib/cookies";
setCookie("key", "value", 60 * 60 * 24 * 365); // 1 年
const val = getCookie("key");
removeCookie("key");
```

### 5.4 环境检测（src/lib/env.ts）

```tsx
import { isLocalhostEnv, isDevelopmentEnv, isStagingEnv, isProductionEnv, getCurrentEnv } from "@/lib/env";
if (isProductionEnv()) { /* 生产环境逻辑 */ }
```

### 5.5 日志工具（src/lib/logger.ts）

```tsx
import { createLogger } from "@/lib/logger";
const log = createLogger("OrderService");
log.info("订单创建成功", orderId);
log.error("创建失败", error);
```

### 5.6 货币工具（src/lib/utils/currency.ts）

```tsx
import { getCurrencyIcon } from "@/lib/utils/currency";
getCurrencyIcon("USD"); // "$"
getCurrencyIcon("EUR"); // "€"
```
