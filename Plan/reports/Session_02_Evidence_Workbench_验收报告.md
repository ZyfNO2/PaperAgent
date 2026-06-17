# Session 2 验收报告: 证据工作台 UI + 审核状态机

> 验收时间: 2026-06-17
> 阶段: Session 2 (按 SOP §5 + §12.2)
> Commit: <待 commit>

---

## 1. 范围

按改造计划 SOP §5 + §12.2:
- **新页面 #page-evidence**: 顶部 tab 切换 (一题分析 / 证据工作台)
- **三栏证据池**: papers / datasets / repos, 每条带 6 档状态按钮 (pending/accepted/core/background/rejected/needs_check) + 删除
- **3 个手动加弹窗**: 论文 / 数据集 / 工程, 走 Session 1 6 个端点
- **池摘要 cells**: 总数 / 已接受 / 核心 / 已拒绝 实时计数
- **tab badge**: 证据总数显示在 tab 角标

## 2. 文件清单

| 路径 | 行数 | 说明 |
|---|---|---|
| `apps/web/index.html` | +110 | tab nav + page-evidence 区块 + 3 弹窗 |
| `apps/web/styles.css` | +103 | .tab / .evidence-* / .modal CSS |
| `apps/web/app.js` | +250 | switchTab + renderEvidence + patchReview + 3 modal handlers |
| `apps/web/e2e/test_one_topic_evidence_workbench.py` | 195 | 9 个 e2e 用例 |
| `apps/api/app/services/evidence.py` | 3 行修改 | evidence_id 加 project 短哈希 (避免跨 project 冲突) |

**总: 5 文件, 661 行新增**

## 3. 关键修复 (Session 2 调试时发现)

| Bug | 原因 | 修法 |
|---|---|---|
| PATCH 改对了 project 但前端 summary 不变 | `auto_paper_001` 这种固定 eid 在多个 project 间冲突, `update_review` 错改到老的 project | evidence_id 加 `project_id[:6]` 前缀, 全局唯一 |
| modal hidden 仍拦截点击 | `.modal { display: flex }` 覆盖了 `hidden` 属性 | 加 `.modal[hidden] { display: none }` |
| e2e 9/9 fail at 第一次 | 4 个 python 进程残留 (旧 dev_server / uvicorn), 18181 端口占用 | taskkill //F //IM python.exe + 重启 |

## 4. 测试结果

```text
apps/web/e2e/test_one_topic_evidence_workbench.py (9 用例)
  test_evidence_tab_visible_after_analyze ........ PASSED
  test_summary_cells_match_lists ................. PASSED
  test_patch_review_button_changes_status ....... PASSED
  test_reject_button_marks_rejected ............. PASSED
  test_manual_add_paper_modal ................... PASSED
  test_manual_add_paper_dedup_by_doi ............ PASSED
  test_delete_button_confirms_and_removes ....... PASSED
  test_dataset_modal_add ........................ PASSED
  test_repo_modal_add ........................... PASSED
                                          9 passed in 71.29s

apps/api/tests/test_evidence_api.py (回归) ... 11 passed in 0.27s
                                       =============
                                       20 passed 总计
```

## 5. 修了哪些 bug (相对老 UI)

| 旧 | 新 |
|---|---|
| 一键到底, 不能改 | 证据工作台手动加 / 接受 / 拒绝 / 删除 |
| 不知道数据从哪来 | 卡片带 source_mode 标签 (auto / 手动) |
| 接受/拒绝无 UI | 6 档状态按钮 (pending/accepted/core/background/rejected/needs_check) |
| 多 project 证据 ID 冲突 | evidence_id 加 project 短哈希, 全局唯一 |
| 没 evidence 计数 | 6 个池摘要 cells 实时更新 + tab 角标 |

## 6. 下一 session

Session 3: Human Gate 1-2 (关键词 / 检索计划). 关键词拆解后给用户编辑机会 (删错词, 加新词, 重拆). 检索计划确认后才发 arXiv.
