# PaperAgent Session 25 SOP：双栏候选资料工作台 MVP

> 日期：2026-06-21  
> 前置：Session 24 CandidateResource 已完成。  
> 本轮目标：实现用户灵感中的双栏工作台：左边是用户想用的资料，右边是系统搜到的候选资料。

---

## 1. 目标

```text
把 S24 的候选资源卡组织成一个可操作工作台：
左栏 SelectedResource；
右栏 CandidateResource；
用户可以把候选加入左栏，也可以从左栏移除。
```

本轮只做资料编排，不做证据晋升。

---

## 2. 数据边界

```text
CandidateResource：系统候选；
SelectedResource：用户选中；
Evidence：已验证证据；
```

硬规则：

```text
SelectedResource != Evidence
加入左栏不等于进入证据链；
移除左栏不删除原始 Candidate；
左栏资料不能直接支持报告结论。
```

---

## 3. 建议新增模型

```text
SelectedResource
  selected_id
  candidate_id
  kind
  title
  url
  source
  selected_reason
  user_note
  selected_at
  verification_status: unchecked | url_verified | failed | partial
  evidence_status: not_promoted | eligible | promoted | rejected
```

后端文件：

```text
apps/api/app/schemas_workspace.py
apps/api/app/services/workspace_board.py
apps/api/tests/test_session25_workspace_board.py
```

前端文件：

```text
apps/web/workspace_board.js
apps/web/e2e/test_one_topic_session25_workspace_board.py
```

---

## 4. UI 要求

双栏布局：

```text
左栏：已选资料
右栏：候选资料
顶部：筛选 paper / dataset / repo / benchmark
底部：当前选题资料覆盖度摘要
抽屉：URL、关键词、Trace、候选来源
```

基础动作：

```text
add_to_selected
remove_from_selected
mark_core
mark_needs_review
open_candidate_drawer
```

---

## 5. 覆盖度摘要

展示：

```text
已选论文数量；
已选数据集数量；
已选工程数量；
是否至少有 1 个数据集；
是否至少有 1 个 baseline / repo；
是否存在 url_unverified；
是否存在 needs_review。
```

---

## 6. 测试

后端：

```text
1. Candidate 可加入 Selected；
2. 重复加入同一 Candidate 幂等；
3. Selected 可移除；
4. mark_core 只改变 selected 状态；
5. Selected 不含 support_level；
6. Selected 不写 Evidence；
7. coverage summary 计算正确；
8. S24 Candidate schema 不回退。
```

Playwright：

```text
S25-PW-1：双栏工作台可打开；
S25-PW-2：右栏显示 S24 候选；
S25-PW-3：点击加入后左栏出现资料；
S25-PW-4：左栏移除后右栏候选仍存在；
S25-PW-5：mark_core 可见；
S25-PW-6：coverage summary 更新；
S25-PW-7：加入左栏不生成 EvidenceRef；
S25-PW-8：S21-S24 主流程不回退。
```

---

## 7. 验收标准

```text
1. 双栏工作台完成；
2. Candidate 和 Selected 边界清晰；
3. 用户能加入、移除、标核心、标复核；
4. 覆盖度摘要可见；
5. Trace 或 eventBuffer 记录用户选择；
6. 不写 Evidence；
7. 后端测试通过；
8. Playwright 通过；
9. S17/S21-S24 不回退。
```

---

## 8. 完工报告

```text
Plan/reports/Session_25_WorkspaceBoard_SelectedResources_验收报告.md
```

