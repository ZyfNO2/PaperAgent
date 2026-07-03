# Hooks Mirror — opencode ↔ Claude Code 行为对照

> 与 `.claude/settings.json` 等价的 opencode 配置说明。
> 本文件供 opencode 会话加载；不替代 Claude 源，**Claude Code 仍按 `.claude/settings.json` 工作**。

## 1. 为什么有这份镜像

| 能力 | Claude Code | opencode |
| --- | --- | --- |
| `UserPromptSubmit` 提示 | `settings.json` → `echo` | 通过 `instructions:` 系统 prompt 提示 |
| `PreToolUse(Write)` 完工报告审计 | `pre_report_audit.py` | **暂未自动激活**（见下方） |
| `Stop` 自检对话完成度 | `user_completion_check.py` | **暂未自动激活**（见下方） |
| Skill 自动加载 | `~/.claude/skills/`、`~/.agents/skills/` | `~/.agents/skills/`（同左） |

## 2. 哪些 hook **不**会自动跑

opencode 的 `PreToolUse` / `Stop` 钩子机制跟 Claude Code 不同：

- 真正的等价物是 `.opencode/plugin/*.ts` 中的 `tool.execute.before` / `experimental.text.complete` 钩子。
- 本镜像**没有自动激活这两个 hook**——保留 Python 源码只是为了让会话里"看到"对应的诊断逻辑。
- 三个 Python 文件被快照在 `.opencode/hooks/`：
  - `pre_report_audit.py` — 完工报告写盘前审计
  - `user_completion_check.py` — Stop 时跑 git log + trace diff + 用户消息关键词匹配
  - `test_write_payload.py` — 前者的手工测试桩

## 3. 想要真正触发怎么办

任选其一：

### 方案 A：用 opencode plugin 复刻

在 `.opencode/plugin/` 下新建 `.ts` 文件，用 `tool.execute.before` (工具调用前) 与
`experimental.text.complete` (停止/回合结束) 钩子重新实现审计逻辑。
Python 审计脚本里的正则表达式可以原样照抄。

### 方案 B：用 shell alias 让 agent 自查

每个会话开始时把 "做完一个改动就跑 `python .opencode/hooks/pre_report_audit.py`"
作为口头约定（不强制，靠 reminder）。

### 方案 C：保持现状

靠 `CLAUDE.md` + `AGENTS.md` + `session66-66v-rewrite.md` 中的口述规范达成
"完工报告审计效果"。本选项**不依赖 hook 自动跑**，
只在 agent 把规则读到 system prompt 里时生效。

## 4. 选定的实现：方案 C

本次迁移选了方案 C：

- opencode session 自动加载 `../AGENTS.md`、`../CLAUDE.md`、本目录内的两个 rules 文件。
- 完工报告审计**不自动跑**，但被读取的 `session66-66v-rewrite.md` §3–5
  已经把"Re03 SOP §1.6 per-round delta + 3-choose-1 audit (A/B/C)"写成文字硬约束；
  agent 写盘时如漏掉会被 LLM-side self-check 抓出来。
- 不再依赖 PreToolUse/Stop 钩子——hooks 脚本作为**可手动调用的诊断工具**保留。

## 5. 用法参考

如需手工跑：

```powershell
# 完工报告审计（手工）
uv run python .opencode/hooks/pre_report_audit.py < payload.json
# 或：先写一个测试 payload
python .opencode/hooks/test_write_payload.py
```

```powershell
# Stop 时自检用户输入 vs 已交付物
uv run python .opencode/hooks/user_completion_check.py
```

## 6. 跟原 Claude 配置的差异表

| 项目 | Claude 原配置 | opencode 镜像 |
| --- | --- | --- |
| 加载位置 | 自动 | 由 `opencode.json` `instructions:` 列出 |
| 钩子自动激活 | 是 | 否（依赖规则自查） |
| 故障容忍 | 钩子崩 → session 仍继续 | 同上 |
| 用户消息提醒 | hook `echo` | 由 system prompt 内置 instruction 自带 |
