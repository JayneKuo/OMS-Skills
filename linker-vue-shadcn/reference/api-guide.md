# Vue + shadcn-vue API 规范

## 目录结构
- API 文件放 `src/app/api/{模块名}/index.ts`
- 按功能模块分目录：`account-management/`、`role-management/` 等

## HTTP 封装架构
```
HttpApi (src/app/utils/http/api.ts)
  └── HttpBase (src/app/utils/http/http-base.ts)
       └── AxiosHttpService (src/app/utils/http/axios-http-service.ts)
            └── axios
```

- `HttpApi` 是业务层主要使用的 HTTP 工具
- 返回类型统一为 `IHttpResponse<T>`，即 `{ code: number; data: T; msg: string }`
- axios 层处理 HTTP 状态码（非 200 自动 reject）
- 业务 code 码（如 `code: 200` 成功、`code: 600057` 业务异常）**不会**被自动处理
- 因此 API 层必须用 `ensureSuccess()` 手动检查业务 code 并解包 data

## HTTP 工具选择
- `HttpApi`（`@utils/http/api`）— 主要使用，自动注入 token、支持中间件、GET 请求缓存
- `AxiosHttpService`（`@utils/http/axios-http-service`）— 需要自定义 baseURL 时使用（如 IAM 接口）
- 方法：
  - `httpApi.get<T>(url, params)`
  - `httpApi.post<T>(url, body)`
  - `httpApi.put<T>(url, body)`
  - `httpApi.delete<T>(url, params)`

## 文件模板
```typescript
import { HttpApi } from '@utils/http/api';

const httpApi = new HttpApi('');
const BASE = '/api/xxx';

// ======================== Types ========================

export interface XxxItem {
  id: string;
}

export interface XxxListParams {
  pageNo?: number;
  pageSize?: number;
}

export interface PageResult<T> {
  list: T[];
  total: number;
}

// ======================== Helpers ========================

/**
 * 解包业务响应：检查 code 是否成功，提取 data
 * HttpApi 不会自动处理业务 code，必须手动检查
 */
function ensureSuccess<T>(response: { code: number; data: T; msg?: string }) {
  if (response.code === 0 || response.code === 200) {
    return response.data;
  }
  throw new Error(response.msg || 'Request failed');
}

function normalizePageResult<T>(payload: unknown): PageResult<T> {
  const res = (payload || {}) as Record<string, unknown>;
  const list = (res.list ?? res.records ?? []) as T[];
  return {
    list: Array.isArray(list) ? list : [],
    total: Number(res.total ?? list.length ?? 0),
  };
}

// ======================== API ========================

/** 获取列表 */
export async function getXxxList(params: XxxListParams): Promise<PageResult<XxxItem>> {
  const response = await httpApi.get<unknown>(
    `${BASE}/list`,
    params as unknown as Record<string, unknown>,
  );
  return normalizePageResult<XxxItem>(ensureSuccess(response));
}
```

## 响应处理
- 后端返回 `{ code: number, data: T, msg?: string }`
- `code === 0 || code === 200` 表示成功
- `ensureSuccess()` 统一解包，失败抛 Error
- 列表接口兼容 `data.list` / `data.records` / `data.data`

## 数据规范化
- 字段缺失给默认值：`String(r.name ?? '')`、`Number(r.count ?? 0)`
- 数组字段：`Array.isArray(x) ? x : []`

## IAM 接口
- baseURL 从 `linc.projectInfo.iamBaseUrl` 获取，兜底 `/api`
- 使用 `AxiosHttpService.create({ baseURL })` 创建独立实例
- 兼容网关包装 `{ code, data }` 和直出格式

## 注意事项
- 类型定义和 API 函数从同一个 `index.ts` 导出
- 不要在 API 文件中引入 Vue 响应式（ref/reactive），保持纯函数
- 后端未就绪时用 `setTimeout` mock，加 `// TODO: 后端接口就绪后替换` 注释
