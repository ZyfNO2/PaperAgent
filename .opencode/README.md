# opencode ↔ Claude Code 迁移 — 项目目录布局

> 本目录 (`G:\PaperAgent\.opencode\`) 是 `G:\PaperAgent\.claude\`
> 的 **opencode 等价镜像**。
> Claude Code 源文件**未删除**——Claude 仍按原 `.claude/` 工作。

## 1. 一图看懂

```
G:\PaperAgent\
├── AGENTS.md               ┐
├── CLAUDE.md               │  Claude 也加载, opencode 也通过 instructions 加载
│                           ┘
├── .claude\                ← Claude Code 源（未动）
│   ├── settings.json           ← 3 个 hooks (UserPromptSubmit / PreToolUse / Stop)
│   ├── hooks\*.py              ← 钩子脚本
│   ├── rules\*.md              ← rules 文本
│   ├── worktrees\              ← git worktree 备份, 不动
│   └── .gitignore
│
└── .opencode\              ← opencode 镜像（本目录）
    ├── opencode.json            ← 项目级 opencode 配置
    ├── rules\                   ← opencode 加载的规则文件
    │   ├── session66-66v-rewrite.md   (镜像 .claude\rules\)
    │   └── hooks-mirror.md           (NEW — 解释镜像策略)
    ├── hooks\                   ← 镜像 .claude\hooks\，但**不自动激活**
    │   ├── README.md
    │   ├── pre_report_audit.py
    │   ├── user_completion_check.py
    │   └── test_write_payload.py
    └── .gitignore
```

## 2. opencode 加载顺序

`opencode.json` 中 `instructions: [...]` 字段控制项目级加载项：

| 路径 (相对 `.opencode/opencode.json`) | 内容 |
| --- | --- |
| `../AGENTS.md` | AI 工程协作增强规则（用户口述） |
| `../CLAUDE.md` | TopicPilot-CN 阶段开发流程约束 |
| `rules/session66-66v-rewrite.md` | S66 / S66v 智能体重写强约束 |
| `rules/hooks-mirror.md` | hooks 镜像策略说明 |
| `../.opencode/README.md` | 本文件 |

## 3. 没自动跑的事

- `pre_report_audit.py`（Claude 自动 / opencode 手动 / 或依赖 LLM 自查）
- `user_completion_check.py`（同上）
- 见 `rules/hooks-mirror.md` §3 选择的策略方案 C

## 4. 重新生成 / 删除

如需重新生成镜像：

```powershell
# 全删再重建
Remove-Item -LiteralPath "G:\PaperAgent\.opencode" -Recurse -Force
# 然后跑迁移脚本（手动流程, 见 Plan/Migration/opencode_migration.md）
```

注：当前没有自动化迁移脚本，迁移工作按本目录蓝图手工完成。
将来要做"真迁移"（删除 `.claude/`）需用户二次确认，
并先验证 Claude Code 不在日常使用中才执行。

## 5. 全局配置

`~/.config/opencode/opencode.json` 也被更新了，添加了：

- `instructions: ["~/.config/opencode/RULES.md"]`
- `references.browser-harness` 别名，对应 `~/Developer/browser-harness/SKILL.md`

详见那个文件旁边的 `RULES.md`。
