---
name: skillpull
description: "Manage AI agent skills across projects using skillpull CLI. Use when user asks to install/update/remove/list/push skills, configure skill repos, set up .skillpullrc, sync skills to Claude/Codex/Kiro/Cursor, or mentions \"skillpull\". Covers: init, pull, push, update, search, alias, registry, remove, and multi-target deployment."
license: MIT
allowed-tools: Bash
---

# skillpull — AI Agent Skill 管理工具

## 概述

skillpull 是一个 CLI 工具，用于从 Git 仓库同步 AI agent skills 到项目中。支持 Claude Code、Codex、Kiro、Cursor 四种目标。

## 核心概念

### Skill 仓库结构

```
shared-agent/                    # Git 仓库根目录
├── skills/                      # 通用 skills（所有项目共享）
│   ├── code-review/
│   │   └── SKILL.md             # skill 定义文件（必须）
│   ├── linker-react-shadcn/
│   │   ├── skill.md             # SKILL.md 或 skill.md 均可
│   │   └── reference/           # 可选：参考文档目录
│   │       ├── component-guide.md
│   │       └── api-guide.md
│   └── tdd-workflow/
│       └── SKILL.md
├── client-portal/               # 项目专属 skills（仅该项目使用）
│   ├── db/
│   │   └── SKILL.md
│   └── item-dev-workflow/
│       ├── SKILL.md
│       └── references/
├── linker-pom/                  # 另一个项目的专属 skills
│   └── db/
│       ├── SKILL.md
│       ├── connection.md
│       └── schema/
└── livechat/                    # livechat 项目专属 skills
    └── item-dev-workflow/
        ├── SKILL.md
        └── references/
```

### SKILL.md 格式

```markdown
---
name: skill-name
version: 1.0.0                   # 可选
description: "触发条件和功能描述"
license: MIT                     # 可选
metadata:                        # 可选
  author: dev-team
allowed-tools: Bash              # 可选
---

# Skill 标题

skill 内容...
```

### 配置层级

```
CLI flags > .skillpullrc (项目级) > ~/.config/skillpull/config.json (全局)
```

- 全局配置：`~/.config/skillpull/config.json` — registry、aliases
- 项目配置：`.skillpullrc` — project name、可选 registry override

### .skillpullrc 格式

```json
{"registry":"","project":"client-portal"}
```

- `registry`: 留空则使用全局 registry；填写则覆盖全局
- `project`: 对应 skill 仓库中的项目子目录名，拉取时会同时获取 `skills/`（通用）和 `<project>/`（专属）下的 skills

### 安装目标

| Target | 目录 | 说明 |
|--------|------|------|
| `--claude` | `.claude/skills/` | Claude Code（默认） |
| `--codex` | `.codex/skills/` | OpenAI Codex CLI |
| `--kiro` | `.kiro/skills/` | Kiro |
| `--cursor` | `.cursor/rules/` | Cursor（自动转换为 .mdc） |
| `--all` | 以上全部 | 一次安装到所有目标 |

## 命令参考

### 初始化

```bash
# 全局初始化（设置默认 skill 仓库）
skillpull init --global

# 项目初始化（创建 .skillpullrc）
cd /path/to/project
skillpull init
# 交互式输入：project name → 对应 skill 仓库中的子目录名
# 交互式输入：registry override → 留空使用全局

# 设置默认 registry（非交互式）
skillpull registry git@github.com:org/shared-agent.git
```

### 拉取 Skills

```bash
# 拉取所有 skills 到默认目标（claude）
skillpull

# 拉取到所有目标
skillpull --all

# 强制覆盖已有 skills
skillpull --all -f

# 从指定源拉取
skillpull git@github.com:org/shared-agent.git --all

# 拉取单个 skill（指定目标）
skillpull code-review --claude
skillpull tdd-workflow --codex
skillpull linker-react-shadcn --kiro

# 拉取单个 skill 到所有目标
skillpull code-review --all

# 指定 project（覆盖 .skillpullrc）
skillpull --project livechat --all

# 指定分支/tag
skillpull --branch develop --all

# 组合使用：从特定分支拉取特定项目的 skills
skillpull --branch develop --project livechat --all
skillpull --branch feature/new-workflow --project client-portal --claude
skillpull --branch v2.0 --project linker-pom --codex

# 预览不实际安装
skillpull --dry-run

# GitHub shortname
skillpull user/repo --all

# 使用 alias
skillpull @work --all
```

### 查看与搜索

```bash
# 列出远程仓库中可用的 skills
skillpull list
skillpull list git@github.com:org/shared-agent.git

# 查看已安装的 skills
skillpull installed
skillpull installed --global

# 搜索 GitHub 上的 skill 仓库
skillpull search coding-standards
```

### 更新与删除

```bash
# 更新所有已安装的 skills
skillpull update

# 删除单个 skill
skillpull remove code-review
skillpull remove code-review --global

# 完全卸载 skillpull 配置
skillpull uninstall
```

### Alias 管理

```bash
# 添加别名
skillpull alias add work git@github.com:org/shared-agent.git

# 列出别名
skillpull alias list

# 删除别名
skillpull alias rm work

# 使用别名拉取
skillpull @work --all
skillpull @work code-review --claude
```

### 推送 Skills

```bash
# 推送所有本地 skills 到远程仓库（需要写权限）
skillpull push
skillpull push git@github.com:org/agent-skills.git

# 推送单个 skill（语法：skillpull push [repo] [skill-name]）
skillpull push my-skill                              # 使用默认 registry
skillpull push git@github.com:org/agent-skills.git my-skill
skillpull push @work code-review                     # 使用 alias
```

## 工作流

### 新项目接入

```bash
# 1. 确保全局 registry 已设置
skillpull registry git@github.com:org/shared-agent.git

# 2. 进入项目目录，初始化
cd /path/to/my-project
skillpull init
# 输入 project name（对应 shared-agent 中的子目录名）

# 3. 拉取 skills
skillpull --all -f

# 4. 验证
skillpull installed
```

### 批量初始化多个项目

```bash
# 非交互式：直接创建 .skillpullrc
echo '{"registry":"","project":"client-portal"}' > /path/to/project/.skillpullrc

# 或用 printf 模拟交互
cd /path/to/project && printf "client-portal\n\n" | skillpull init
```

### 日常更新

```bash
# 在项目目录下
skillpull update

# 或强制重新拉取
skillpull --all -f
```

## 团队 Skill 仓库约定

### 添加通用 skill

在 `skills/` 目录下创建子目录，包含 `SKILL.md`：

```bash
skills/
└── my-new-skill/
    ├── SKILL.md          # 必须
    └── reference/        # 可选：参考文档
```

### 添加项目专属 skill

在项目子目录下创建：

```bash
my-project/
└── db/
    ├── SKILL.md
    └── schema/
```

### Skill 命名规范

- 目录名用 kebab-case
- SKILL.md 中的 `name` 字段用 kebab-case
- `description` 要包含触发条件（TRIGGER when）

## 注意事项

- `skillpull init` 是交互式命令，自动化时用 `printf` 管道输入或直接写 `.skillpullrc`
- `--all` 会安装到 claude/codex/kiro/cursor 四个目标
- `-f` (force) 覆盖已有 skills，日常更新建议带上
- Cursor 目标会自动将 SKILL.md 转换为 .mdc 格式
- `reference/` 目录下的文件会随 skill 一起安装
- 全局 skills 安装在 `~/.claude/skills/`（用 `--global`）
- 项目 skills 安装在 `.claude/skills/`（默认）
