# Vue + Element Plus 组件规范

## 表单
- 使用 `<el-form>` + `:rules` + `<el-form-item>`
- 校验规则定义在 `rules` 对象中
- 提交前调用 `formRef.value.validate()`
- 必填标记：`:rules="[{ required: true, message: '请输入', trigger: 'blur' }]"`

## 表格
- `<el-table>` + `<el-table-column>`
- 分页：`<el-pagination>`
- 操作列用 `<el-button>` 或 `<el-dropdown>`

## 弹窗
- `<el-dialog>` + `v-model` 控制显隐
- 确认弹窗用 `ElMessageBox.confirm()`

## 消息提示
- 成功：`ElMessage.success('操作成功')`
- 错误：`ElMessage.error('操作失败')`
- 确认：`ElMessageBox.confirm('确认删除？', '提示')`

## 选择器
- `<el-select>` + `<el-option>`
- 远程搜索：`:remote="true"` + `:remote-method="handleSearch"`

## 日期选择
- `<el-date-picker>` + `type="daterange"`
- 格式：`value-format="YYYY-MM-DD"`

## 加载状态
- 表格：`v-loading="loading"`
- 按钮：`:loading="submitting"`
- 全局：`ElLoading.service()`
