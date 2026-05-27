# 测试指南

## 1. 测试方案

- 测试框架：Vitest + React Testing Library
- 测试文件位置：`src/features/xxx/__tests__/`
- 文件命名：`xxx.test.tsx` 或 `xxx.spec.tsx`

---

## 2. 测试文件结构

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MyComponent } from "../index";

// Mock API
vi.mock("@/lib/api/my-feature", () => ({
  getMyFeatureListApi: vi.fn().mockResolvedValue({
    data: { records: [{ id: "1", name: "测试" }], total: 1 },
  }),
}));

describe("MyComponent", () => {
  it("应该渲染标题", () => {
    render(<MyComponent />);
    expect(screen.getByText("标题")).toBeInTheDocument();
  });

  it("应该处理点击事件", async () => {
    const onAction = vi.fn();
    render(<MyComponent onAction={onAction} />);
    fireEvent.click(screen.getByRole("button", { name: "操作" }));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("应该加载并显示数据", async () => {
    render(<MyComponent />);
    await waitFor(() => {
      expect(screen.getByText("测试")).toBeInTheDocument();
    });
  });
});
```

---

## 3. 测试原则

### 3.1 测什么
- 用户交互行为（点击、输入、提交）
- 条件渲染逻辑（loading、error、empty 状态）
- 表单验证（必填、格式校验）
- 关键业务逻辑（状态流转、权限判断）

### 3.2 不测什么
- shadcn/ui 组件内部实现
- 第三方库的行为
- 纯样式（Tailwind 类名）
- 实现细节（内部 state 值）

### 3.3 测试风格
- 以用户视角编写测试（查找元素用 `getByRole`、`getByText`）
- 避免测试实现细节
- 每个测试只验证一个行为
- 使用 `describe` 分组，`it` 描述行为

---

## 4. Mock 模式

### 4.1 Mock API

```tsx
vi.mock("@/lib/http-client", () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));
```

### 4.2 Mock Hook

```tsx
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, ...props }: any) => <a {...props}>{children}</a>,
}));
```

### 4.3 Mock Store

```tsx
vi.mock("@/stores/auth-store", () => ({
  useAuthStore: vi.fn((selector) =>
    selector({ auth: { user: { id: "1", userName: "test" }, canAccessAdmin: () => true } })
  ),
}));
```

---

## 5. 运行测试

```bash
# 单次运行所有测试
pnpm vitest --run

# 运行指定文件
pnpm vitest --run src/features/my-feature/__tests__/index.test.tsx

# 监听模式（开发时使用）
pnpm vitest
```

---

## 6. 代码质量检查

测试之外，日常开发依赖以下检查保证质量：

```bash
pnpm lint              # ESLint 检查
pnpm format:check      # Prettier 格式检查
pnpm format            # 自动格式化
pnpm build             # TypeScript 类型检查 + 构建
pnpm knip              # 检查未使用的导出
pnpm i18n:check-hardcoded  # 检查硬编码字符串
```

---

## 7. PR 提交前 Checklist

- [ ] `pnpm lint` 无错误
- [ ] `pnpm format` 已格式化
- [ ] `pnpm build` 构建通过
- [ ] `pnpm i18n:check-hardcoded` 无硬编码
- [ ] `pnpm knip` 无未使用导出
- [ ] UI 变更附带截图
- [ ] 手动测试关键路径
