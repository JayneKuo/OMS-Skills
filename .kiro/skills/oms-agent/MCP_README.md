# OMS Agent MCP Server

统一暴露 OMS 查询和装箱计算能力的 MCP Server。
把这个 skill 导入到任何项目后，配置 MCP 即可让 AI 助手调用真实 OMS 能力。

## 暴露的 Tools

| Tool | 说明 | 输入 |
|------|------|------|
| oms_query | OMS 全域查询 | identifier(订单号等), intent(查询意图), force_refresh |
| oms_batch_query | 批量订单统计/列表 | query_type, status_filter, page_no, page_size |
| cartonize | 装箱计算 | input_json(装箱输入 JSON) |
| validate_cartonization | 装箱结果验证 | input_json, result_json |

## 导入到其他项目

1. 把整个 `.kiro/skills/` 目录复制到目标项目
2. 确保目标项目也有 `cartonization_engine/` 目录（装箱引擎）
3. 在目标项目的 `.kiro/settings/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "oms-agent": {
      "command": "python",
      "args": [".kiro/skills/oms-agent/mcp_server.py"]
    }
  }
}
```

4. 安装依赖：`pip install mcp pydantic requests`

## 直接运行测试

```bash
python .kiro/skills/oms-agent/mcp_server.py
```

## 目录结构

导出时需要包含的完整目录：

```
.kiro/skills/
├── oms-agent/           # Agent 编排层 + MCP Server
│   ├── mcp_server.py    # MCP Server 入口（导出必需）
│   ├── SKILL_REGISTRY.md
│   ├── WORKFLOWS.md
│   ├── SYSTEM_PROMPT.md
│   ├── OUTPUT_POLICY.md
│   └── README.md
│
├── oms-query/           # OMS 全域查询 Skill
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── query_oms.py
│   │   └── oms_query_engine/   # 查询引擎包
│   └── references/
│
└── cartonization/       # 装箱计算 Skill
    ├── SKILL.md
    ├── scripts/
    └── references/

cartonization_engine/    # 装箱引擎包（项目根目录）
```
