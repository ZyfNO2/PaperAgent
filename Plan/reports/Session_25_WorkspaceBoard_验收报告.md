# Session 25 — WorkspaceBoard 双栏工作台 验收报告

日期: 2026-06-21
Commit: c192ecc0

## 概要

S25 完成 WorkspaceBoard 双栏工作台，含 schema 定义、frontend module、backend 20 tests + Playwright 8 e2e tests。

## 产物清单

| 文件 | 说明 |
|------|------|
| `apps/api/app/schemas_workspace.py` | Pydantic schemas: `SelectedResource`, `WorkspaceBoard`, `CoverageSummary`; CRUD 辅助函数 |
| `apps/web/workspace_board.js` | 前端模块 `window.WorkspaceBoard`，双栏工作台 UI 逻辑 |
| `apps/api/tests/test_session25_workspace_board.py` | 后端 20 个 pytest 用例，覆盖 schema 验证、CRUD、CoverageSummary |
| `apps/web/e2e/test_one_topic_session25_workspace_board.py` | Playwright 8 个 e2e 用例，覆盖 UI 交互、双栏布局、toggle 行为 |

## 测试结果

| 类型 | 数量 | 状态 |
|------|------|------|
| Backend pytest | 20 | 全部通过 |
| Playwright e2e | 8 | 全部通过 |
| **合计** | **28** | **全部通过** |

## 关键不变式

- **SelectedResource ≠ Evidence** — 将资源添加到工作台左栏（SelectedResource）不会自动创建 Evidence；Evidence 仅通过 Phase 04 证据链路径生成。
- **mark_core ≠ mark_for_review** — 两个独立 toggle，语义互不干扰；mark_core 标记核心文献，mark_for_review 标记待复核项。

## 不回退确认

- S21 (Step Deck UI) — 仍绿
- S22 — 仍绿
- S23 — 仍绿
- S24 — 仍绿

无回归。
