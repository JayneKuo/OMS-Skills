# Vue + Element Plus API 规范

## 目录结构
- API 服务文件放 `src/services/{模块名}.service.ts`
- 公共 API 工具放 `src/utils/api.ts`
- HTTP 封装放 `src/utils/http/`

## HTTP 封装架构
```
useApi() (src/utils/api.ts)
  └── HttpProxy (内部单例)
       └── HttpApi (src/utils/http/api.ts)
            └── HttpBase (src/utils/http/http-base.ts)
                 └── axios
```

- `useApi()` 返回带 token 自动注入、全局异常处理的 HTTP 单例
- 返回类型为 `IHttpResponse<T>`，即 `{ data: { code: number; data: T; msg: string }; status: number }`
- 业务 code 码（`code: 0 || 200` 成功）不会被自动处理
- 401/403/token 异常会自动跳转登录页

## 文件模板
```typescript
import api from './api'
import type { XxxItem, XxxListResponse, XxxQueryParams } from '../stores/xxx/type'

/** 获取列表 */
export const getXxxList = async (params: XxxQueryParams = {}) => {
  const { data } = await api.get<any>('/v1/admin/xxx/list', params)
  return data.data as XxxListResponse
}

/** 新增/保存 */
export const saveXxx = async (payload: Omit<XxxItem, 'id'>) => {
  const { data } = await api.post<any>('/v1/admin/xxx/save', payload)
  return data
}

/** 删除 */
export const deleteXxx = async (id: number) => {
  const { data } = await api.post<any>('/v1/admin/xxx/delete', { id })
  return data
}

export default { getXxxList, saveXxx, deleteXxx }
```

## 响应处理
- 后端返回 `{ code: number, data: T, msg?: string }`
- `code === 0 || code === 200` 表示成功
- 列表接口返回 `data.data` 解包后使用
- 错误由 `afterReturning` 全局拦截处理

## HTTP 方法
- `api.get<T>(url, params)` — GET 请求
- `api.post<T>(url, body)` — POST 请求
- `api.put<T>(url, body)` — PUT 请求
- `api.delete<T>(url, params)` — DELETE 请求
- `api.patch<T>(url, body)` — PATCH 请求

## IAM 接口
- `linker-client-portal` 路径自动注入 `Authorization: Bearer {iam_token}`
- IAM token 从 `usePrincipalStore().iamToken` 获取

## 注意事项
- 类型定义放 `src/stores/{模块}/type.ts`，service 文件引用
- 不要在 service 文件中引入 Vue 响应式（ref/reactive），保持纯函数
- 导入统一用 `import api from './api'`（单例）
- 后端未就绪时用 `setTimeout` mock，加 `// TODO: 后端接口就绪后替换` 注释
- 请求头自动携带 `token` 和 `x-language`
