# Phase 64 T6: Frontend Candidate Role Display — 验收报告

**Task**: Session 64 T6 (Phase 64 — paper/dataset/repo 全链路)
**File**: `apps/web-react/src/features/evidence/RetrievalCandidatePanel.tsx`

## 产物

- `apps/web-react/src/features/evidence/RetrievalCandidatePanel.tsx` (改写, ~700 行)
  - 新增 `LiteratureRole` / `RoleAssignment` / `ModuleMatrix` 类型, 对齐后端 orchestrator 输出
  - 新增 `Tabs` 复用组件 (`apps/web-react/src/components/ui/Tabs.tsx`)
  - 新增 `ModuleMatrixView` / `DevPanel` 子组件

## 实现摘要

### 1. 按角色分组 (Role-Based Display)

```
Tabs:
  Baseline (baseline_framework + baseline_method)
  平行论文 (parallel_application_paper)
  模块论文 (module_improvement_paper)  -- + Module Matrix 表格
  数据集 (datasets + repos)
  Survey (仅当 surveyPapers > 0)        -- 综述背景, 不入主 baseline/平行
  开发者模式 (devMode 时挂上)
```

论文按 `literature_roles` (S64 T3) 自动分桶, 无角色时 fallback 到 parallel (旧行为不变).

### 2. 状态显示

- **Keep**: 主视图 (Baseline / 平行 / 模块 / 数据集 四个 tab 始终可见)
- **Quarantine / Reject**: 仅开发者模式可见, 通过 `clean_summary` 计数 + `role=irrelevant` 论文列表暴露

### 3. 开发者模式 (Developer Mode Toggle)

`retrieval-dev-toggle` 按钮 (Ghost 类), toggle 后:

| 区域 | 内容 |
|------|------|
| `retrieval-clean-summary` | `clean_summary` 计数 (keep / quarantine / reject / needs_manual) |
| `retrieval-irrelevant-section` | `role=irrelevant` 论文列表 + reason |
| `retrieval-source-trace` | 每个 source 的 status / candidate_count / duration_ms / error |
| 每张 candidate 卡片 | 额外显示 `role-badge` + `base / modules / reason` 详情行 |

### 4. 移除占位文案

`(未匹配公开数据集)` 这种占位文案只在 gap report 里出现 (`g.reason`), 主候选列表不再硬塞占位文字. 当 candidate 为空时只显示 `暂无候选`.

### 5. 模块矩阵显示 (Module Matrix)

`module_matrix.entries` 非空时, 在模块论文 tab 下面挂一张紧凑表格:

```
Base | Module A | Module B | Dataset | Metrics | Improvement
```

missing_module_types 在表格下方单行展示, 提示 "缺哪类模块".

## 向后兼容

| 旧 testId | 保留位置 |
|-----------|---------|
| `retrieval-papers` | 主视图三栏第一栏 (论文聚合) |
| `retrieval-datasets` | 主视图三栏第二栏 + 数据集 tab |
| `retrieval-repos` | 主视图三栏第三栏 + 数据集 tab |
| `retrieval-add-evidence-*` / `retrieval-reject-*` / `retrieval-retry-similar-*` | 全保留 |
| `retrieval-source-*` / `retrieval-flash` / `retrieval-error` | 全保留 |

主视图三栏 (papers / datasets / repos) 始终可见, Session 61 e2e (`test_session61_retrieval_enhancement.py`) 的 9 个 `expect(retrieval-papers).to_be_visible()` / `retrieval-datasets` / `retrieval-repos` 断言不变.

## 新增 testId

- `retrieval-dev-toggle` — 开发者模式开关
- `retrieval-role-tabs` / `tab-baseline` / `tab-parallel` / `tab-modules` / `tab-datasets` — Tabs
- `retrieval-baseline` / `retrieval-parallel` / `retrieval-modules` / `retrieval-survey` — 各角色面板
- `retrieval-role-badge-<cid>` — 角色 Badge
- `retrieval-role-detail-<cid>` — 开发者模式下角色详情行 (base / modules / reason)
- `retrieval-module-matrix` / `retrieval-module-row-<i>` / `retrieval-module-missing` — 模块矩阵
- `retrieval-dev-panel` / `retrieval-clean-summary` / `retrieval-irrelevant-section` / `retrieval-irrelevant-<cid>` / `retrieval-source-trace` — 开发者模式内部

## 验证

- `npx tsc -b` → **exit 0** (无类型错误)
- 现有 Session 61 e2e (`expect(retrieval-papers|datasets|repos).to_be_visible()`) 兼容

## 风险 / 已知边界

- **clean_summary 只是计数, 无 per-candidate reason**: 后端 orchestrator 只暴露 `clean_summary: dict[str, int]`, 没暴露 per-candidate clean reasons. 当前 dev 面板只能展示 `role=irrelevant` 的论文 + reason, quarantine/reject 候选只有总数. 后续若后端把 `clean_results` 透传到 RetrievalRun, dev 面板再加 per-candidate 行. ponytail: 当前 minimum viable, 升级路径清晰.
- **survey tab 始终挂在尾部**: 当 `surveyPapers.length === 0` 时不挂 tab, 不显示空 tab.
- **survey 仅背景**: 不入 baseline/平行桶, 但用户仍可点 tab 查看 / 标记不相关 / 加入证据. 设计取舍: 让 survey 单独可见避免污染主视图.

## Files Modified

- `apps/web-react/src/features/evidence/RetrievalCandidatePanel.tsx` (改写)