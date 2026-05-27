# batch-reallocation API mapping

## Query and analysis phase

### 1. Resolve order identifier
- `POST /app-api/tracking-assistant/search-order-no`
- 用途：把输入标识解析成标准 `orderNo`

### 2. Load sale order
- `GET /app-api/sale-order/{orderNo}`
- 用途：获取订单状态、订单行、SKU 数量、Hold 信息

### 3. Load order logs
- `GET /app-api/orderLog/list`
- 参数：`omsOrderNo`, `merchantNo`
- 用途：补充 exception / 业务备注摘要

### 4. Recover eligibility check
- `GET /app-api/dispatch/recover/check/{orderNo}`
- 用途：检查订单是否允许 recover

### 5. Recover query details
- `GET /app-api/dispatch/recover/query/{orderNo}`
- 用途：获取 recoverable 结果与附加信息

## Execution phase

### 6. Release hold
- `POST /app-api/order-hold/release`
- 参数：`orderNo`
- 用途：On Hold 订单执行 recover 前先释放 hold

### 7. Recover whole order
- `POST /app-api/dispatch/recover/dispatch`
- Body: `{ "orderNo": "SO..." }`
- 用途：整单重新分仓

### 8. Recover partial order by SKU
- `POST /app-api/dispatch/recover/dispatch/part`
- Body: `{ "orderNo": "SO...", "skus": ["SKU-A"] }`
- 用途：只对未履约 SKU 重新分仓

## Runtime headers
- `Authorization: Bearer <token>`
- `x-tenant-id: <tenant>`
- `locale: zh-CN`
- 执行动作额外需要：`USER: <session user>`

## Safety rules
- 只允许处理 `unfulfilled_qty != 0` 的 SKU
- `On Hold` 场景必须先 release，再 recover
- 执行前重新读取订单，发现状态漂移则跳过并标记 `stale_state`
- 所有执行都必须来自用户表单确认后的结构化请求
