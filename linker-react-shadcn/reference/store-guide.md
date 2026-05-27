# 状态管理指南

## 1. Zustand Store 模式

Store 位于 `src/stores/`，使用 `create` 创建：

```tsx
import { create } from "zustand";

interface AuthState {
  auth: {
    user: AuthUser | null;
    setUser: (user: AuthUser | null) => void;
    accessToken: string;
    setAccessToken: (token: string) => void;
    reset: () => void;
    canAccessAdmin: () => boolean;
  };
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  auth: {
    user: null,
    setUser: (user) => set((state) => ({ ...state, auth: { ...state.auth, user } })),
    accessToken: "",
    setAccessToken: (token) => set((state) => ({ ...state, auth: { ...state.auth, accessToken: token } })),
    reset: () => set((state) => ({ ...state, auth: { ...state.auth, user: null, accessToken: "" } })),
    canAccessAdmin: () => get().auth.user?.userType === 0,
  },
}));

// 组件内使用
const user = useAuthStore((state) => state.auth.user);

// 组件外使用（API 拦截器等）
const { auth } = useAuthStore.getState();
```

### 现有 Store 一览
- `useAuthStore` - 认证、Token、权限
- `useTenantStore` - 多租户上下文
- `useMerchantStore` - 商户上下文
- `useDictStore` - 字典/枚举缓存
- `useLocalStore` - 本地应用状态

---

## 2. Context Provider 模式

Provider 位于 `src/context/`，用于应用级配置：

```tsx
// 创建 Context + Provider + Hook 三件套
const ThemeContext = createContext<ThemeProviderState>(initialState);

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>("system");
  const resolvedTheme = useMemo(() => theme === "system" ? detectSystemTheme() : theme, [theme]);
  return <ThemeContext value={{ theme, setTheme, resolvedTheme }}>{children}</ThemeContext>;
}

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
};
```

### 现有 Provider 一览
- `ThemeProvider` → `useTheme()` - 暗色/亮色/系统主题
- `LocaleProvider` → `useLocale()` - 语言切换 + RTL
- `DirectionProvider` → `useDirection()` - 文字方向
- `SearchProvider` → `useSearch()` - 全局搜索（Cmd+K）
- `MerchantProvider` - 商户上下文
- `LayoutProvider` - 布局状态

---

## 3. Store vs Context 选择指南

| 维度 | Zustand | Context |
|------|---------|---------|
| 组件外访问 | ✅ `getState()` | ❌ 仅组件内 |
| 适用场景 | API 拦截器、路由守卫、高频更新、复杂状态 | 主题、语言、方向等纯 UI 配置 |
| 更新频率 | 高频 | 低频 |
| 嵌套方式 | 无需 Provider | 需要 Provider 包裹 |
