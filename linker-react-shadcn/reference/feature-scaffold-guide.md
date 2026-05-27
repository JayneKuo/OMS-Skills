# 功能模块脚手架指南

## 1. 功能模块目录结构

每个功能模块位于 `src/features/` 下，遵循统一结构：

### 1.1 简单功能（仅列表页）

```
src/features/brand/
├── index.tsx              # 主组件（列表页）
└── components/
    └── brand-columns.tsx  # 表格列定义
```

### 1.2 标准功能（列表 + 详情）

```
src/features/logistics/small-parcel/
├── index.tsx              # 列表页
├── detail.tsx             # 详情页
├── config.tsx             # 筛选配置、搜索字段
└── components/
    ├── order-columns.tsx  # 表格列定义
    ├── order-import.tsx   # 导入弹窗
    ├── export-dialog.tsx  # 导出弹窗
    └── manual-status-dialog.tsx
```

### 1.3 复杂功能（含自定义 Hook、Schema、类型）

```
src/features/sales-order/
├── index.tsx              # 主入口
├── components/            # 子组件
├── config/                # 筛选、列配置
├── hooks/                 # 功能专属 Hook
├── schemas/               # Zod 校验 Schema
├── types/                 # TypeScript 类型
├── list/                  # 列表视图
└── map/                   # 地图视图
```

---

## 2. 新建功能模块步骤

### 步骤 1：创建功能目录和主组件

```tsx
// src/features/my-feature/index.tsx
import { useTranslation } from "react-i18next";
import { Main } from "@/components/layout/main";
import { PageHeader } from "@/components/common/page-header";

export function MyFeature() {
  const { t } = useTranslation();

  return (
    <Main className="flex flex-1 flex-col gap-4">
      <PageHeader
        title={t("layout.menus.myFeature")}
        description={t("myFeature.description", { defaultValue: "Manage my feature" })}
      />
      {/* 内容区 */}
    </Main>
  );
}
```

### 步骤 2：创建路由文件

```tsx
// src/routes/_authenticated/my-feature.tsx（layout route，可选）
import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated/my-feature")({
  component: () => <Outlet />,
});

// src/routes/_authenticated/my-feature/index.tsx
import { createFileRoute } from "@tanstack/react-router";
import { MyFeature } from "@/features/my-feature";
import { Loading } from "@/components/loading";

export const Route = createFileRoute("/_authenticated/my-feature/")({
  component: MyFeature,
  pendingComponent: () => <Loading />,
});
```

### 步骤 3：添加菜单配置

```tsx
// src/config/menu.config.ts 中添加
{
  title: "layout.menus.myFeature",
  url: "/my-feature",
  icon: SomeIcon,
  permission: "linker-oms:my-feature",
}
```

### 步骤 4：添加翻译

```json
// src/locales/en/layout.json 中添加菜单翻译
{ "menus": { "myFeature": "My Feature" } }

// src/locales/zh-CN/layout.json
{ "menus": { "myFeature": "我的功能" } }
```

### 步骤 5：添加 API

```tsx
// src/lib/api/my-feature.ts
import httpClient from "@/lib/http-client";

export const getMyFeatureListApi = (data: any) =>
  httpClient.post("/api/dms/app-api/my-feature/list", data);

export const getMyFeatureDetailApi = (params: any) =>
  httpClient.get("/api/dms/app-api/my-feature/detail", { params });
```

---

## 3. 列表页模板

标准列表页包含：搜索、筛选、表格、批量操作、弹窗。

```tsx
export function MyFeatureList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // 状态
  const [selectedRows, setSelectedRows] = useState<any[]>([]);
  const [importOpen, setImportOpen] = useState(false);

  // 列定义
  const columns = useMyFeatureColumns({
    onRowClick: (row) => navigate({ to: "/my-feature/detail/$id", params: { id: row.id } }),
  });

  // 操作成功回调
  const handleSuccess = () => queryClient.invalidateQueries({ queryKey: ["my-feature-table"] });

  return (
    <Main className="flex flex-1 flex-col gap-4">
      <PageHeader title={t("layout.menus.myFeature")} action={<Button onClick={() => setImportOpen(true)}>导入</Button>} />
      <ProTable<MyFeatureItem>
        queryKey={["my-feature-table"]}
        request={async (params) => {
          const res = await getMyFeatureListApi({ pageNo: params.pageNo, pageSize: params.pageSize });
          return { data: { list: res.data.records || [], total: res.data.total || 0 }, success: true };
        }}
        columns={columns}
        rowKey="id"
        rowSelection={true}
      />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} onSuccess={handleSuccess} />
    </Main>
  );
}
```

---

## 4. 详情页模板

```tsx
export function MyFeatureDetail() {
  const { t } = useTranslation();
  const { id } = Route.useParams();
  const [data, setData] = useState<MyFeatureItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDetail = async () => {
      setIsLoading(true);
      try {
        const res = await getMyFeatureDetailApi({ id });
        setData(res.data);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  if (isLoading) return <Loading />;

  return (
    <Main className="flex flex-1 flex-col gap-6">
      <Link to="/my-feature" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> 返回列表
      </Link>
      <PageHeader title={data?.name || ""} />
      <Tabs defaultValue="basic">
        <TabsList><TabsTrigger value="basic">基本信息</TabsTrigger></TabsList>
        <TabsContent value="basic">{/* 内容 */}</TabsContent>
      </Tabs>
    </Main>
  );
}
```

---

## 5. 功能模块 Checklist

- [ ] 创建 `src/features/xxx/index.tsx` 主组件
- [ ] 创建 `src/routes/_authenticated/xxx/index.tsx` 路由
- [ ] 在 `src/config/menu.config.ts` 添加菜单项
- [ ] 在 `src/locales/en/layout.json` 添加菜单翻译
- [ ] 在 `src/lib/api/` 添加 API 定义
- [ ] 列表页使用 `ProTable` + `PageHeader` + `Main`
- [ ] 详情页使用返回链接 + `Tabs`
- [ ] 弹窗使用 `open` + `onOpenChange` 受控模式
