# 附件 API 参考

## attachments.create — 创建附件（获取上传 URL）

| 参数 | 必填 | 说明 |
|------|------|------|
| name | 是 | 文件名 |
| size | 是 | 文件大小（字节） |
| contentType | 是 | MIME 类型 |
| documentId | 否 | 关联的文档 ID |

返回 `uploadUrl`（签名上传地址）和 `attachment.url`（附件引用地址）。

上传为两步操作：
1. 调用此端点获取签名 URL
2. 用 **PUT** 请求将文件上传到该 URL

## attachments.redirect — 获取附件访问 URL

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 附件 ID |

返回临时签名 URL。

## attachments.delete — 删除附件

| 参数 | 必填 | 说明 |
|------|------|------|
| id | 是 | 附件 ID |

## 常见 MIME 类型

| 扩展名 | MIME 类型 |
|--------|----------|
| .txt | text/plain |
| .pdf | application/pdf |
| .png | image/png |
| .jpg | image/jpeg |
| .zip | application/zip |
| .xlsx | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| .docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document |
