# 路由与导航指南

## 1. TanStack Router 文件路由

路由文件位于 `src/routes/`，目录结构即路由结构。使用 `_authenticated` 前缀表示需要认证的路由。

```
src/routes/
├── __root.tsx                       # 根路由
├── _authenticated/
│   ├── route.tsx                    # 认证布局 + 守卫（Token、用户、租户、i18n）
│   ├── logistics/
│   │   ├── small-parcel.tsx         # 路由包装（layout route）
│   │   └── small-parcel/
│   │       ├── index.tsx            # 列表页 → /logistics/small-parcel
│   │       └── detail.$orderId.tsx  # 详情页 → /logistics/small-parcel/detail/:orderId
│   └── [其他功能模块]/
├── auth-code.tsx                    # OAuth 回调页
└── sign-in.tsx                      # 登录页
```

---

## 2. 路由文件模板

### 2.1 基础路由

```tsx
import { createFileRoute } from "@tanstack/react-router";
import { SmallParcelList } from "@/features/logistics/small-parcel";
import { Loading } from "@/components/loading";

export const Route = createFileRoute("/_authenticated/logistics/small-parcel/")({
  component: SmallParcelList,
  pendingComponent: () => <Loading />,
});
```

### 2.2 带预加载和权限检查的路由

```tsx
export const Route = createFileRoute("/_authenticated/logistics/small-parcel/")({
  beforeLoad: async ({ context }) => {
    // 预加载数据
    await queryClient.ensureQueryData({ queryKey: ["enums"], queryFn: fetchEnums });
    // 权限检查（无权限时抛出重定向）
    if (!hasPermission(context.user.permissions, "linker-oms:small-parcel")) {
      throw redirect({ to: "/403" });
    }
  },
  component: SmallParcelList,
  pendingComponent: () => <Loading />,
});
```

### 2.3 带动态参数的路由
文件名中 `$paramName` 表示动态参数：

```tsx
// 文件：detail.$orderId.tsx
export const Route = createFileRoute("/_authenticated/logistics/small-parcel/detail/$orderId")({
  component: OrderDetail,
});

// 组件内获取参数
const { orderId } = Route.useParams();
```

---

## 3. 导航方式

### 3.1 编程式导航

```tsx
import { useNavigate } from "@tanstack/react-router";

const navigate = useNavigate();

// 基础导航
navigate({ to: "/logistics/small-parcel" });

// 带路由参数
navigate({ to: "/logistics/small-parcel/detail/$orderId", params: { orderId: row.id } });

// 带搜索参数（URL query）
navigate({ to: "/logistics/small-parcel", search: { status: "active", page: 2 } });

// 组合使用
navigate({
  to: "/logistics/small-parcel/detail/$orderId",
  params: { orderId: row.id },
  search: isArchived ? { archived: true } : {},
});
```

### 3.2 声明式导航

```tsx
import { Link } from "@tanstack/react-router";

// 基础链接
<Link to="/logistics/small-parcel">返回列表</Link>

// 带样式的返回链接
<Link to="/logistics/small-parcel" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
  <ArrowLeft className="h-4 w-4" /> 返回
</Link>

// 带参数
<Link to="/logistics/small-parcel/detail/$orderId" params={{ orderId: row.id }}>
  {row.airbillNo}
</Link>
```

### 3.3 浏览器历史导航

```tsx
const { history } = useRouter();
history.go(-1); // 返回上一页
```

---

## 4. 认证守卫

`_authenticated/route.tsx` 统一处理认证流程：

1. Token 校验 → 无效则跳转登录
2. 用户信息加载 → 从 IAM 获取用户数据
3. 租户/商户初始化 → 设置多租户上下文
4. i18n 数据预加载 → 加载翻译资源
5. 权限检查 → 过滤菜单、校验路由访问权限

---

## 5. 菜单配置

菜单定义在 `src/config/menu.config.ts`，类型在 `src/config/menu.types.ts`：

```tsx
// 菜单项类型
type NavItem = {
  title: string;           // 翻译 key，如 "layout.menus.salesOrder"
  url?: string;            // 路由路径
  icon?: React.ElementType; // lucide-react 图标
  permission?: string;     // 权限标识符（不配置则公共访问）
  visible?: () => boolean; // 动态可见性
  items?: NavItem[];       // 子菜单
};

// 菜单配置示例
{
  title: "layout.menus.logistics",
  icon: Truck,
  permission: "linker-oms:logistics",
  items: [
    { title: "layout.menus.smallParcel", url: "/logistics/small-parcel", icon: Package, permission: "linker-oms:small-parcel" },
  ],
}
```

---

## 6. 错误页面

错误页面位于 `src/features/errors/`，统一模式：

```tsx
export function ForbiddenError() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { history } = useRouter();
  return (
    <div className="h-svh">
      <div className="m-auto flex h-full w-full flex-col items-center justify-center gap-2">
        <h1 className="text-[7rem] leading-tight font-bold">403</h1>
        <span className="font-medium">{t("errors.403.title", { defaultValue: "Access denied" })}</span>
        <p className="text-muted-foreground text-center">{t("errors.403.description")}</p>
        <div className="mt-6 flex gap-4">
          <Button variant="outline" onClick={() => history.go(-1)}>返回</Button>
          <Button onClick={() => navigate({ to: "/" })}>回到首页</Button>
        </div>
      </div>
    </div>
  );
}
```

现有错误页：`forbidden.tsx`(403)、`not-found-error.tsx`(404)、`unauthorized-error.tsx`(401)、`general-error.tsx`(500)、`maintenance-error.tsx`
