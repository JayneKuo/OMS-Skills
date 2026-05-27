# 组件开发指南

## 1. 组件创建与声明

### 1.1 函数式组件
所有组件使用 `function` 关键字 + 命名导出，禁止 class 组件和默认导出：

```tsx
// ✅ 推荐
export function OrderList({ filters }: OrderListProps) {
  return <div>...</div>;
}

// ❌ 避免
export default ({ filters }) => <div>...</div>;
```

### 1.2 Props 类型定义
使用 `interface` 定义，命名为 `组件名Props`。可扩展原生 HTML 属性：

```tsx
// 基础 Props
interface StatusTagProps {
  status?: string;
  label: string;
}

// 扩展原生属性
interface PageHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title: string | React.ReactNode;
  description?: string | React.ReactNode;
  action?: React.ReactNode;
}

// 泛型 Props
interface ProTableProps<T> {
  queryKey: string[];
  columns: ColumnDef<T>[];
  request: (params: RequestParams) => Promise<{ data: { list: T[]; total: number } }>;
}
```

### 1.3 Props 默认值
直接在解构中设置，不使用 `defaultProps`：

```tsx
export function Loading({ className, fullScreen = true }: LoadingProps) { ... }
export function DatePicker({ placeholder = "Pick a date", disabled = false }: DatePickerProps) { ... }
```

### 1.4 children 与插槽模式
通过 `children` 或命名 props 实现内容分发：

```tsx
interface PageHeaderProps {
  title: string | React.ReactNode;
  action?: React.ReactNode;       // 命名插槽：操作区
  children?: React.ReactNode;     // 默认插槽（优先于 action）
}

export function PageHeader({ title, action, children }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <h1>{title}</h1>
      {children ?? action}
    </div>
  );
}
```

---

## 2. 组件组合模式

### 2.1 页面布局模式
页面级组件统一使用 `Main` 容器 + `PageHeader`：

```tsx
import { Main } from "@/components/layout/main";
import { PageHeader } from "@/components/common/page-header";

export function OrderListPage() {
  const { t } = useTranslation("order");
  return (
    <Main className="flex flex-1 flex-col gap-4">
      <PageHeader title={t("title")} description={t("desc")} action={<Button>{t("export")}</Button>} />
      <ProTable columns={columns} request={fetchData} />
    </Main>
  );
}
```

### 2.2 受控弹窗模式
所有 Dialog/Drawer 使用 `open` + `onOpenChange` 受控：

```tsx
interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  desc: string | React.JSX.Element;
  handleConfirm: () => void;
  isLoading?: boolean;
  destructive?: boolean;
}

const [dialogOpen, setDialogOpen] = useState(false);
<ConfirmDialog open={dialogOpen} onOpenChange={setDialogOpen} title="确认" desc="不可撤销" handleConfirm={handleDelete} />
```

### 2.3 回调刷新模式
子组件操作完成后通过 `onSuccess` 通知父组件刷新：

```tsx
interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const handleSuccess = () => queryClient.invalidateQueries({ queryKey: ["order-table"] });
<ImportDialog open={open} onOpenChange={setOpen} onSuccess={handleSuccess} />
```

### 2.4 条件渲染
使用 `&&` 和三元，避免深层嵌套：

```tsx
{isLoading && <Loading />}
{error ? <ErrorState message={error.message} /> : <DataTable data={data} />}
```

---

## 3. Hooks 技能

### 3.1 状态管理选型

| 场景 | 方案 | 示例 |
|------|------|------|
| 组件内 UI 状态 | `useState` | 弹窗开关、loading、表单输入 |
| 跨组件全局状态 | Zustand store | 认证、租户、字典缓存 |
| 应用级配置 | React Context | 主题 `useTheme()`、语言 `useLocale()` |
| 服务端数据 | React Query | `useQuery`、`useMutation` |
| URL 同步状态 | `useTableUrlState` | 分页、筛选条件 |

### 3.2 常用 Hook 速查

```tsx
const [isOpen, setIsOpen] = useState(false);
const [dialogType, setDialogType] = useDialogState<"approve" | "reject">();
const orderedColumns = useMemo(() => columnOrder.map(id => columnMap.get(id)).filter(Boolean), [columnOrder, columnMap]);
const handleClick = useCallback((row: OrderItem) => { navigate({ to: "/detail/$id", params: { id: row.id } }); }, [navigate]);
useEffect(() => { fetchDetail(); }, [orderId]);
const timerRef = useRef<number | undefined>(undefined);
```

### 3.3 自定义 Hook 规范
- 文件名：`use-hook-name.ts`（kebab-case）
- 通用 Hook → `src/hooks/`，功能专属 → 功能目录内
- 必须以 `use` 开头，添加 JSDoc 注释

```tsx
/**
 * 检测当前是否为移动端视口
 * @example const isMobile = useIsMobile();
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState<boolean | undefined>(undefined);
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 767px)");
    const onChange = () => setIsMobile(window.innerWidth < 768);
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < 768);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return !!isMobile;
}
```

### 3.4 useTableUrlState - 表格 URL 状态同步

```tsx
const { globalFilter, onGlobalFilterChange, columnFilters, onColumnFiltersChange, pagination, onPaginationChange } =
  useTableUrlState({
    search: router.search,
    navigate: router.navigate,
    pagination: { pageKey: "page", pageSizeKey: "pageSize" },
    columnFilters: [{ columnId: "status", searchKey: "status", type: "array" }],
  });
```

---

## 4. 表单技能

### 4.1 React Hook Form + Zod

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  name: z.string().min(1, "名称不能为空"),
  email: z.string().email("邮箱格式不正确"),
  status: z.enum(["active", "inactive"]),
});
type FormValues = z.infer<typeof schema>;

export function CreateForm({ onSubmit }: { onSubmit: (data: FormValues) => void }) {
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Input {...register("name")} />
      {errors.name && <span className="text-destructive text-sm">{errors.name.message}</span>}
    </form>
  );
}
```

Schema 文件放在 `src/lib/schemas/` 或功能目录内。

---

## 5. 数据表格技能

### 5.1 ProTable 完整用法

```tsx
<ProTable<OrderItem>
  queryKey={["order-table", searchValue, activeFilters, isArchived]}
  request={async (params) => {
    const apiParams = { pageNo: params.pageNo || 1, pageSize: params.pageSize || 10 };
    const res = await getOrderListApi(apiParams);
    return { data: { list: res?.data?.records || [], total: res?.data?.total || 0 }, success: true };
  }}
  columns={orderedColumns}
  rowKey="id"
  rowSelection={true}
/>
```

### 5.2 列定义模式
列定义放在 `components/xxx-columns.tsx`，使用自定义 Hook 返回：

```tsx
export function useOrderColumns(options: {
  onAirbillClick: (row: OrderItem) => void;
  statusEnumList: any[];
}): ColumnDef<OrderItem>[] {
  return [
    { id: "airbillNo", header: "AIRBILL NO", cell: ({ row }) => (
      <button onClick={() => options.onAirbillClick(row.original)} className="text-primary hover:underline">
        {row.original.airbillNo}
      </button>
    )},
    { id: "status", header: "STATUS", cell: ({ row }) => {
      const name = options.statusEnumList.find(i => i.enumData === row.original.status)?.name;
      return <StatusTag status={row.original.status} label={name} />;
    }},
  ];
}
```

### 5.3 筛选配置模式

```tsx
export function getFilterConfigs(t: TFunction, options: FilterOptions): FilterConfig[] {
  return [
    { id: "status", label: "STATUS", type: "multiple", options: options.statusList.map(i => ({ label: i.name, value: i.enumData })) },
    { id: "customerName", label: "CUSTOMER", type: "multiple", optionsApi: getCustomerListApi, isPagination: true },
  ];
}
```

### 5.4 批量操作模式

```tsx
const handleBulkAction = (type: OperationType) => {
  if (selectedRows.length === 0) { toast.error("请选择至少一行"); return; }
  if (blockedStatuses.includes(selectedRows[0].status)) { toast.error("当前状态不允许此操作"); return; }
  setOperationType(type);
  setDialogOpen(true);
};
```

---

## 6. 性能优化

### 6.1 Memo 使用时机

| Hook | 使用场景 | 不需要的场景 |
|------|----------|-------------|
| `useMemo` | 复杂计算、大数组过滤排序、对象/数组作为子组件 props | 简单计算、原始值 |
| `useCallback` | 回调传给子组件、回调作为 useEffect 依赖 | 仅在当前组件使用的回调 |
| `React.memo` | 频繁重渲染的纯展示组件 | 大多数组件不需要 |

### 6.2 避免不必要的重渲染

```tsx
// ✅ 稳定引用
const filterConfigs = useMemo(() => getFilterConfigs(t, options), [t, options]);
const handleClick = useCallback((id: string) => navigate({ to: id }), [navigate]);

// ❌ 每次渲染创建新对象
<Child config={{ key: "value" }} onClick={() => doSomething()} />
```

### 6.3 代码分割
TanStack Router 自动按路由分割，无需手动配置。

### 6.4 React Query 缓存
数据按 `queryKey` 缓存，操作后手动失效：

```tsx
queryClient.invalidateQueries({ queryKey: ["order-table"] });
```
