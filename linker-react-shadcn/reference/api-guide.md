# 数据与 API 指南

## 1. HTTP 客户端

基于 Axios，位于 `src/lib/http-client.ts`，内置拦截器自动处理：
- 请求：注入 Bearer Token、租户 ID（x-tenant-id）、语言（locale）
- 响应：统一错误处理、401 自动跳转登录、业务错误码 toast

```tsx
import httpClient from "@/lib/http-client";

// API 定义（src/lib/api/ 按功能模块组织）
export const getOrderListApi = (data: any) => httpClient.post("/api/dms/app-api/package/store/list", data);
export const getOrderDetailApi = (params: any) => httpClient.get("/api/dms/app-api/package/store", { params });
```

---

## 2. React Query 集成

```tsx
// 基础查询
const { data, isLoading } = useQuery({
  queryKey: ["orders", filters],
  queryFn: () => getOrderListApi(filters),
});

// ProTable 集成（自动处理分页、加载、缓存）
<ProTable<OrderItem>
  queryKey={["order-table", filters]}
  request={async (params) => {
    const res = await getOrderListApi({ pageNo: params.pageNo, pageSize: params.pageSize });
    return { data: { list: res.data.records, total: res.data.total }, success: true };
  }}
  columns={columns}
  rowKey="id"
  rowSelection={true}
/>

// 缓存失效
const queryClient = useQueryClient();
queryClient.invalidateQueries({ queryKey: ["order-table"] });
```

### 2.1 并行请求

```tsx
const [orderRes, enumRes] = await Promise.all([
  getOrderDetailApi({ id: orderId }),
  getScanCodeEnumListApi(),
]);
```

### 2.2 Blob 下载

```tsx
const blob = await getExportApi(params);
const url = window.URL.createObjectURL(blob);
const link = document.createElement("a");
link.href = url;
link.download = `orders-${Date.now()}.xlsx`;
link.click();
```

---

## 3. 路由技能

### 3.1 TanStack Router 文件路由
路由文件位于 `src/routes/`，目录结构即路由结构：

```
src/routes/_authenticated/
├── route.tsx                        # 认证布局 + 守卫
├── logistics/
│   ├── small-parcel.tsx             # 路由包装
│   └── small-parcel/
│       ├── index.tsx                # 列表页 /logistics/small-parcel
│       └── detail.$orderId.tsx      # 详情页 /logistics/small-parcel/detail/:orderId
```

### 3.2 路由文件模板

```tsx
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated/logistics/small-parcel/")({
  beforeLoad: async ({ context }) => {
    // 预加载数据、权限检查
    // 无权限时 throw redirect({ to: "/403" })
  },
  component: SmallParcelList,
  pendingComponent: () => <Loading />,
});
```

### 3.3 导航

```tsx
import { useNavigate, Link } from "@tanstack/react-router";

// 编程式导航（带参数和搜索状态）
const navigate = useNavigate();
navigate({
  to: "/logistics/small-parcel/detail/$orderId",
  params: { orderId: row.id },
  search: { archived: true },
});

// 声明式导航
<Link to="/logistics/small-parcel" className="text-sm text-muted-foreground hover:text-foreground">
  返回列表
</Link>
```

### 3.4 认证守卫
`_authenticated/route.tsx` 统一处理：Token 校验 → 用户信息加载 → 租户/商户初始化 → i18n 预加载 → 权限检查

---

## 4. 权限技能

### 4.1 权限检查

```tsx
import { hasPermission, canAccessRoute, filterMenuByPermissions } from "@/lib/permission";

hasPermission(user.userPermissions, "linker-di:tasks"); // true/false
const visibleMenu = filterMenuByPermissions(menuData, user.userPermissions);
canAccessRoute("/workflow/flows", menuData, user.userPermissions);
```

### 4.2 管理员权限

```tsx
const canAdmin = useAuthStore((s) => s.auth.canAccessAdmin()); // userType === 0
```

### 4.3 localhost 环境
本地开发环境（`VITE_APP_ENV=localhost`）自动跳过所有权限检查。

---

## 5. 错误处理技能

### 5.1 全局错误处理
Axios 拦截器自动处理：401 跳转登录、403 提示无权限、业务错误码 toast。
组件内只需处理特定逻辑：

```tsx
const handleSubmit = async (data: FormValues) => {
  setIsLoading(true);
  try {
    await createOrderApi(data);
    toast.success(t("createSuccess"));
    onOpenChange(false);
    onSuccess();
  } catch (error) {
    // 全局拦截器已处理 toast，这里只做状态恢复
  } finally {
    setIsLoading(false);
  }
};
```

### 5.2 优雅降级

```tsx
try {
  const res = await checkFeatureApi();
  setFeatureAvailable(res.data?.enabled ?? false);
} catch {
  setFeatureAvailable(false); // 失败时降级为不可用
}
```

### 5.3 handleServerError 工具

```tsx
import { handleServerError } from "@/lib/handle-server-error";
try { await riskyOperation(); } catch (e) { handleServerError(e); }
```
