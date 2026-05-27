# 工具函数指南

## 1. 核心工具（src/lib/utils.ts）

```tsx
import { cn, sleep, getPageNumbers } from "@/lib/utils";

// cn() - 条件类名合并（clsx + tailwind-merge）
cn("rounded-lg border", isActive && "border-primary", className);

// sleep() - 异步延迟
await sleep(1000);

// getPageNumbers() - 分页页码生成（带省略号）
getPageNumbers(5, 20); // [1, "...", 4, 5, 6, "...", 20]
getPageNumbers(1, 3);  // [1, 2, 3]
```

---

## 2. 日期工具（src/lib/utils/date-utils.ts）

基于 dayjs，默认时区 `America/Los_Angeles`，支持 CST（`America/Chicago`）。

```tsx
import {
  formattedTime12Hour,
  everyTimeToTimeZone,
  timeToLos,
  getLosNow,
  beforeTime,
  isEmptyValue,
  parseDateSafe,
  CST_TIME_ZONE,
} from "@/lib/utils/date-utils";

// 12 小时制格式化（自动转换时区）
formattedTime12Hour("2025-01-15T10:30:00Z", "MM/DD/YYYY hh:mm:ss A");
// → "01/15/2025 02:30:00 AM"（洛杉矶时间）

// CST 时区格式化（带时区缩写）
formattedTime12Hour("2025-01-15T10:30:00Z", "MM/DD/YYYY hh:mm:ss A", CST_TIME_ZONE);
// → "01/15/2025 04:30:00 AM CST"

// 将本地时间转为 UTC ISO 格式
everyTimeToTimeZone("01/15/2025 02:30:00 PM");
// → "2025-01-15T22:30:00.000Z"

// 获取洛杉矶当前时间
getLosNow(); // ISO 格式

// 日期选择器禁用函数（禁用今天之前的日期）
<Calendar disabled={(date) => beforeTime(date)} />

// 空值判断（布尔和数字不算空）
isEmptyValue(null);  // true
isEmptyValue(0);     // false
isEmptyValue(false); // false

// 安全解析日期字符串（避免时区偏移）
parseDateSafe("2025-01-15"); // new Date(2025, 0, 15) 本地时间
```

---

## 3. Cookie 工具（src/lib/cookies.ts）

```tsx
import { getCookie, setCookie, removeCookie, setIframeCookie } from "@/lib/cookies";

setCookie("key", "value", 60 * 60 * 24 * 365); // 设置，有效期 1 年
const val = getCookie("key");                    // 读取
removeCookie("key");                             // 删除

// iframe 场景（SameSite=None; Secure）
setIframeCookie("key", "value", 365);
```

---

## 4. 环境检测（src/lib/env.ts）

```tsx
import {
  isLocalhostEnv,
  isDevelopmentEnv,
  isStagingEnv,
  isProductionEnv,
  getCurrentEnv,
} from "@/lib/env";

if (isLocalhostEnv()) { /* 本地开发 */ }
if (isProductionEnv()) { /* 生产环境 */ }
getCurrentEnv(); // "localhost" | "development" | "staging" | "production"
```

---

## 5. 日志工具（src/lib/logger.ts）

```tsx
import { createLogger } from "@/lib/logger";

const log = createLogger("OrderService");
log.info("订单创建成功", orderId);
log.warn("库存不足", { sku, available });
log.error("创建失败", error);
log.debug("调试信息", data);
```

带命名空间前缀，输出格式：`[OrderService] 订单创建成功 123`

---

## 6. 货币工具（src/lib/utils/currency.ts）

```tsx
import { getCurrencyIcon, currencyList } from "@/lib/utils/currency";

getCurrencyIcon("USD"); // "$"
getCurrencyIcon("EUR"); // "€"
getCurrencyIcon("CNY"); // "¥"
getCurrencyIcon("AED"); // "د.إ"
getCurrencyIcon();      // "$"（默认）

// 完整货币列表
currencyList; // [{ value: "USD", label: "$" }, { value: "EUR", label: "€" }, ...]
```

---

## 7. 错误处理工具（src/lib/handle-server-error.ts）

```tsx
import { handleServerError } from "@/lib/handle-server-error";

try {
  await riskyOperation();
} catch (error) {
  handleServerError(error); // 自动 toast 错误信息
}
```

自动处理 Axios 错误和 204 状态码。

---

## 8. 安全工具（src/lib/utils/security.ts）

位于 `src/lib/utils/security.ts`，用于数据脱敏等安全相关操作。

---

## 9. 字典工具（src/lib/utils/dictionary-utils.ts）

用于枚举/字典数据的查找和转换。

---

## 10. 标签工具（src/lib/utils/tag-utils.ts）

用于标签相关的颜色映射和显示逻辑。
