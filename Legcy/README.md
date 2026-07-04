# Legcy / 过时代码收容目录（Re1.1 起）

本目录存放 **被 Re1.1 重构淘汰的代码、脚本、报告**。它们仍被 git 追踪（在 Legcy/ 路径下），
但不再被主编排 `apps/api/app/services/agents/graph/...` 调用。

## 子目录

| 目录 | 内容 |
| --- | --- |
| `Legcy/_paperagent_legacy_root_scripts/` | 原仓库根目录的临时/调试脚本（`audit_deep.py`、`test_check_*.py`、`test_fix3_debug*.py` 等） |
| `Legcy/Plan/` | 旧 `Plan/` 根的非活跃报告与子目录。活文件（SOP、FIX-4 完工/小样例审计）仍放在 `Plan/` |
| `Legcy/Plan/reports/` | 原 `Plan/reports/`，含 Re01–Re10/FIX 系列完工、审计、SOP 文档 |

## 判定标准

- 若一个文件**仅在** `Legcy/` 或 `apps/api/app/services/Legcy/` 路径被引用，移入此目录。
- 若仍被 `apps/api/app/services/agents/`（活跃 graph）引用，**不要**移入。
- 放进 `Legcy/` 不删除、不改写内容；如需更新内容，在活跃路径下重建并引用。

## 何时清理

Re1.1 结束后：只做「保留 / 整体归档到 `archive/`」决策；禁止逐文件 review 内容。
