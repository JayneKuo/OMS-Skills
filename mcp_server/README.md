# OMS Agent MCP Server

统一暴露 OMS 查询和装箱计算能力的 MCP Server。

## Tools

| Tool | 说明 |
|------|------|
| oms_query | OMS 全域查询（订单/库存/仓库/规则/发运/集成中心） |
| oms_batch_query | 批量订单统计和列表查询 |
| cartonize | 装箱计算 |
| validate_cartonization | 装箱结果验证 |

## 使用方式

### 在 Kiro 中使用

已配置在 `.kiro/settings/mcp.json`，Kiro 会自动连接。

### 在其他 MCP 客户端中使用

```json
{
  "mcpServers": {
    "oms-agent": {
      "command": "python",
      "args": ["mcp_server/oms_agent_server.py"]
    }
  }
}
```

### 直接运行

```bash
python mcp_server/oms_agent_server.py
```

## 依赖

```bash
pip install mcp pydantic requests
```
