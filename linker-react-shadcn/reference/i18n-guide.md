# 国际化（i18n）指南

## 1. 技术方案

基于 `react-i18next` + `i18next-browser-languagedetector`，翻译资源通过 API 动态加载。

支持语言：
- `en-US` - English
- `zh-CN` - 简体中文
- `zh-Hant` - 繁體中文
- `ko-KR` - 한국어
- `es-ES` - Español
- `ar` - العربية（RTL）
- `ja-JP` - 日本語

---

## 2. 基本用法

### 2.1 组件内使用

```tsx
import { useTranslation } from "react-i18next";

export function OrderList() {
  const { t } = useTranslation(); // 默认命名空间 "translation"

  return (
    <div>
      <h1>{t("layout.menus.salesOrder")}</h1>
      <p>{t("common.noData", { defaultValue: "No data available" })}</p>
      <Button>{t("common.button.confirm")}</Button>
      <Button variant="outline">{t("common.button.cancel")}</Button>
    </div>
  );
}
```

### 2.2 带参数的翻译

```tsx
// JSON: "welcome": "Hello, {{name}}"
t("welcome", { name: "张三" }); // "Hello, 张三"

// 带默认值（翻译缺失时的回退）
t("newFeature.title", { defaultValue: "New Feature" });
```

### 2.3 组件外使用

```tsx
import i18n from "@/locales";

// 直接调用
i18n.t("common.button.confirm");

// 切换语言
i18n.changeLanguage("zh-CN");
```

---

## 3. 翻译文件组织

### 3.1 目录结构

```
src/locales/
├── index.ts              # i18n 初始化配置
├── en/                   # 英文
│   ├── common.json       # 通用文本（按钮、状态、提示）
│   ├── layout.json       # 布局相关（菜单、头部、侧边栏）
│   ├── errors.json       # 错误页面文本
│   ├── dashboard.json    # 仪表盘功能
│   ├── table.json        # 表格通用文本
│   └── [功能].json       # 各功能模块翻译
├── zh-CN/                # 简体中文（结构同上）
├── zh-TW/                # 繁体中文
├── ar/                   # 阿拉伯语
├── es/                   # 西班牙语
├── ja/                   # 日语
└── ko/                   # 韩语
```

### 3.2 翻译文件格式
JSON 格式，key 按字母排序，支持嵌套：

```json
{
  "button": {
    "cancel": "Cancel",
    "confirm": "Confirm",
    "delete": "Delete",
    "save": "Save"
  },
  "noData": "No data available",
  "status": {
    "active": "Active",
    "inactive": "Inactive"
  }
}
```

---

## 4. 翻译 key 命名规范

| 场景 | 格式 | 示例 |
|------|------|------|
| 菜单标题 | `layout.menus.xxx` | `layout.menus.salesOrder` |
| 通用按钮 | `common.button.xxx` | `common.button.confirm` |
| 错误页面 | `errors.{code}.title/description` | `errors.404.title` |
| 功能模块 | `{namespace}.{key}` | `dashboard.totalOrders` |
| 表格通用 | `table.xxx` | `table.noResults` |

---

## 5. RTL 支持

阿拉伯语（`ar`）自动启用 RTL 布局：

```tsx
// LocaleProvider 自动检测并设置方向
const isRTL = RTL_LOCALES.includes(resolvedLocale);
setDir(isRTL ? "rtl" : "ltr");

// 组件中使用方向感知的 Tailwind 类
<div className="ms-4">  {/* margin-start，RTL 时变为 margin-right */}
<CalendarIcon className="ms-auto" />
```

---

## 6. 语言切换

通过 `LocaleProvider` 提供的 `useLocale()` Hook：

```tsx
import { useLocale } from "@/context/locale-provider";

const { locale, setLocale, resolvedLocale } = useLocale();

// 切换语言（会触发页面刷新）
setLocale("zh-CN");

// 跟随系统
setLocale("system");
```

语言偏好存储在 Cookie `i18nextLng` 中，有效期 1 年。

---

## 7. 开发规则

1. 所有用户可见文本必须用 `t()` 包裹，禁止硬编码
2. 新增翻译 key 时，至少更新 `en/` 目录，其他语言可后续补充
3. key 在 JSON 文件中按字母排序
4. 提交前运行检查命令：

```bash
pnpm i18n:check-hardcoded   # 检查硬编码字符串
pnpm i18n:check-missing     # 检查缺失翻译
```

5. 菜单标题使用 `layout.menus.xxx` 格式
6. 使用 `defaultValue` 参数作为翻译缺失时的回退
