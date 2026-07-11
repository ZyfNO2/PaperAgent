# PaperAgent Re4.7：全链路验收、观测与文档收口 SOP

> **承接**：Re4.6 前端深度整合与多文档 RAG 已完成（531 tests，7 结构化报告组件，多 PDF 合并索引，端到端 case re46-e2e 52 chunks 21 nodes）。
>
> **本 SOP 覆盖 Day 7 全部任务**：全链路端到端验收（一次跑通 Re4.1–4.6 全部特性）、
> 代码清理（ruff 全项目修复、死代码清除、临时文件清理）、
> 项目文档全面更新（CODELY.md / README.md / Runbook）、
> 最终回归套件、Re4.0 版本收口 CHANGELOG。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **模型**：DeepSeek v4 flash（via OpenCode proxy，`https://opencode.ai/go`）。

---

## 0. 当前事实基线（已验证）

### Re4.1–4.6 交付物清单

| Day | SOP | 核心交付 | 测试数 |
|---|---|---|---|
| Re4.1 | 工程控制面与安全收口 | case_id 安全校验、SourcePolicy、CORS 环境化、StageContract v1、RunState + atomic_write_json | +37 |
| Re4.2 | 前端基线与人性化主流程 | React+Vite shell（首页+工作台+RAG 占位）、SSE 封装、节点人话映射、Playwright 截图 | +8 |
| Re4.3 | 创新点叙事工作包可追溯升级 | InnovationPoint/NarrativeRevision/WorkPackage schema、binding validator、依赖 DAG、修订历史+diff | +49 |
| Re4.4 | ACP 最小能力层 | 14 能力声明、REST+JSON Schema、读写权限控制、调用示例、RunLedger 接入 | +17 |
| Re4.5 | 全文入库与 RAG 检索 | PDF 提取、500/100 分块、TF-IDF 索引、余弦检索、LLM 问答+引用、知识图谱 | +30 |
| Re4.6 | 前端深度整合与多文档 RAG | 7 结构化报告组件、Workbench RAG 整合、merge_index 多文档、首页增强 | +4 |
| **合计** | | | **531** |

### 当前指标

| 指标 | 值 | 目标 |
|---|---|---|
| pytest collected | 531 | ≥ 531（不退化） |
| pytest errors | 0 | 0 |
| ruff `apps/api/app` | 19 (18 E402 + 1 E702) | ≤ 19（不新增） |
| ruff 全项目 `.` | 65 (39 E402 + 13 E701 + 8 F401 + 3 F841 + 1 E702 + 1 E741) | 修复可修复的 F401 + F841 |
| npm build | 52 modules, 240KB JS | 零 TS error |
| 端到端 case | re46-e2e: 2 PDFs, 52 chunks, 21 KG nodes | 全链路验收 |

### 需要更新的文档

| 文档 | 当前状态 | 需要更新 |
|---|---|---|
| `CODELY.md` | 描述 Re1.3 旧架构，无 ACP/RAG/React/SourcePolicy | 全面重写为 Re4.0 架构 |
| `README.md` | Session 09–15 历史描述，无 React 前端 / ACP | 追加 Re4 新能力段落 + 启动方式 |
| `docs/deployment/Local_Runbook.md` | Re4.1 已重写 | 追加 ACP / RAG / React dev server 说明 |
| `CHANGELOG.md` | Re4.4 为最新条目 | 追加 Re4.5–4.7 条目 |
| `pytest.ini` | markers 部分已更新 | 确认 testpaths 正确 |
| `.env.example` | Re4.1 已更新 | 确认 DeepSeek proxy 配置正确 |

### 需要清理的项

| 项 | 位置 | 操作 |
|---|---|---|
| F401 unused-import（8 处） | 全项目 | 修复或加 `# noqa: F401` |
| F841 unused-variable（3 处） | 全项目 | 删除未用变量 |
| E741 ambiguous-variable-name（1 处） | 全项目 | 重命名变量 |
| `_archived_legacy_sessions/` conftest | 可能引用过时 skip 逻辑 | 确认不阻塞收集 |
| `tmp_re13_eval/` 测试 case | re41-verify-001 / 04d365f121bc / re43-verify-001 / re44-verify-001 / re45-test / re46-e2e | 保留（回归测试依赖）；清理其他临时目录 |

### 决策

- **Re4.7 不引入新功能**——纯粹是验收、清理和文档
- **ruff 修复范围**：只修复 F401/F841/E741（可安全修复的）；E402/E701 保持现状（已知 pattern，不影响运行）
- **CODELY.md 全面重写**：从 Re1.3 架构更新到 Re4.0 架构，反映 ACP/RAG/React/SourcePolicy/StageContract/RunState
- **端到端验收**：跑一个完整 case，覆盖 Re4.1–4.6 全部特性

---

## 1. 本轮目标

### 核心交付

1. **全链路端到端验收**：一次 case 跑通全部 Re4.1–4.6 特性
2. **ruff 全项目修复**：F401/F841/E741 修复到 0（可修复项）
3. **死代码与临时文件清理**
4. **CODELY.md 全面重写**：反映 Re4.0 架构
5. **README.md 追加 Re4 段落**
6. **Local Runbook 追加 ACP/RAG/React 说明**
7. **最终回归套件**：531+ tests 全绿 + 端到端 case
8. **CHANGELOG 收口**：Re4.5–4.7 条目 + Re4.0 release note

### 验收标准

- 端到端 case 验收清单全部通过
- `ruff check . --statistics` 的 F401/F841/E741 = 0
- `ruff check apps/api/app` ≤ 19 errors
- `pytest --collect-only` 0 errors, ≥ 531 collected
- CODELY.md 包含 ACP/RAG/React/SourcePolicy/StageContract/RunState 描述
- README.md 包含 React 前端启动方式和 ACP 能力清单
- Local Runbook 包含 ACP / RAG / React dev server 说明

### 不做

- 不引入新功能
- 不修改 graph 拓扑
- 不修改 LLM prompt
- 不升级 TF-IDF 到 embedding（未来 Re5.x）

---

## 2. Phase 设计

### Phase 1：ruff 全项目修复 — 1h

#### Fix 1.1: 修复 F401（8 处 unused-import）

```bash
cd G:\PaperAgent
# 查看全部 F401
.venv\Scripts\python.exe -m ruff check . --select F401
# 安全自动修复
.venv\Scripts\python.exe -m ruff check . --select F401 --fix
```

手动验证修复后无新破坏：
```bash
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | findstr "collected error"
```

#### Fix 1.2: 修复 F841（3 处 unused-variable）

逐个查看并手动删除未使用变量：
```bash
.venv\Scripts\python.exe -m ruff check . --select F841
```

#### Fix 1.3: 修复 E741（1 处 ambiguous-variable-name）

```bash
.venv\Scripts\python.exe -m ruff check . --select E741
# 重命名变量（如 l → line, I → index 等）
```

#### Fix 1.4: 验证 ruff 改善

```bash
.venv\Scripts\python.exe -m ruff check . --statistics
# 预期：F401=0, F841=0, E741=0；E402/E701 保持不变
.venv\Scripts\python.exe -m ruff check apps/api/app --statistics
# 预期：≤ 19 errors
```

---

### Phase 2：死代码与临时文件清理 — 30min

#### Fix 2.1: 检查并删除临时文件

```bash
# 检查根目录下的临时 Python 文件
Get-ChildItem -Path G:\PaperAgent -Filter "tmp_*.py" -File

# 检查 tmp 目录下的验证产物
Get-ChildItem -Path G:\PaperAgent\tmp_re13_eval -Directory
```

**保留**的 case 目录（回归测试依赖）：
- `re41-verify-001` — Re4.1 验证
- `04d365f121bc` — Re4.2 验证
- `re43-verify-001` — Re4.3 验证
- `re44-verify-001` — Re4.4 验证
- `re45-test` — Re4.5 验证
- `re46-e2e` — Re4.6 验证

**删除**：根目录下所有 `tmp_*.py` 临时验证脚本（如果有残留）。

#### Fix 2.2: 检查 `_archived_legacy_sessions/conftest.py`

确认归档测试的 skip 逻辑不阻塞收集：
```bash
.venv\Scripts\python.exe -m pytest apps/api/tests/_archived_legacy_sessions/ --collect-only -q 2>&1 | findstr "error"
# 预期：0 errors（可能 0 collected，因为有 skip）
```

#### Fix 2.3: 清理 `__pycache__`

```bash
Get-ChildItem -Path G:\PaperAgent -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
```

---

### Phase 3：CODELY.md 全面重写 — 2h

#### Fix 3.1: 重写 CODELY.md

**文件**：`CODELY.md`

**需要更新的章节**：

1. **Project Overview**：追加 ACP 能力层 + RAG 全文检索 + React 前端
2. **Core Pipeline**：追加 ACP → RAG → Knowledge Graph 分支
3. **Tech Stack**：追加 React+Vite+TypeScript、ACP、RAG（TF-IDF）、SourcePolicy
4. **Building and Running**：追加 React dev server、ACP 端点、RAG 使用
5. **Architecture → Directory Structure**：追加 `acp/`、`rag/`、`schemas/`、`validators/`、`web-react/`
6. **LangGraph Pipeline**：追加 Re4.3 binding validator + DAG + narrative revisions
7. **LLM Provider Routing**：更新为 DeepSeek v4 flash via OpenCode proxy
8. **API Endpoints**：追加 ACP 端点 + work-packages 端点
9. **ACP Layer**：新增章节，描述 14 能力 + 权限模型
10. **RAG Layer**：新增章节，描述 PDF→chunk→TF-IDF→retrieve→QA 流程
11. **Development Conventions**：追加 SourcePolicy、StageContract、atomic_write_json、RunLedger 约定
12. **Testing**：更新 testpaths、markers、test count

#### Fix 3.2: 更新 README.md

**文件**：`README.md`

追加 Re4 新能力段落：

```markdown
## Re4 工程升级（2026-07）

### 新增能力

- **ACP 能力层**：14 个 REST 能力，支持外部 AI 工具（Codex / Claude Code / Trae）调用
- **RAG 全文检索**：PDF 入库 → TF-IDF 分块索引 → 检索增强问答 → 知识图谱
- **React 前端**：Vite + TypeScript，首页 / 工作台 / RAG 页面，结构化报告展示
- **证据可追溯**：创新点 candidate_ids 绑定、叙事修订历史 + diff、工作包依赖 DAG
- **工程控制面**：case_id 路径安全、SourcePolicy 统一开关、StageContract v1、原子写入

### 启动方式

```bash
# 后端
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# React 前端 (dev)
cd apps/web-react && npm run dev  # http://127.0.0.1:18183

# ACP 能力清单
curl http://127.0.0.1:18181/api/v1/acp/capabilities
```
```

#### Fix 3.3: 更新 Local_Runbook.md

**文件**：`docs/deployment/Local_Runbook.md`

追加：

```markdown
## ACP 能力层

```bash
# 列出所有能力
curl http://127.0.0.1:18181/api/v1/acp/capabilities

# 调用只读能力
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"list_cases","params":{}}'

# 调用写能力（需要 write 权限）
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -H "X-ACP-Capability: write" \
  -d '{"capability":"search_literature","params":{"topic":"测试题目"}}'
```

## RAG 全文检索

```bash
# 入库 PDF
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -H "X-ACP-Capability: write" \
  -d '{"capability":"ingest_pdf","params":{"pdf_url":"https://arxiv.org/pdf/2401.17270","case_id":"my-case"}}'

# 问答
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"query_rag","params":{"question":"What datasets are used?","case_id":"my-case"}}'

# 知识图谱
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"get_knowledge_graph","params":{"case_id":"my-case"}}'
```

## React 前端 (Dev)

```bash
cd apps/web-react
npm install
npm run dev  # http://127.0.0.1:18183, proxy /api → 18181
npm run build  # 产出 dist/，挂载在 /react
```
```

---

### Phase 4：全链路端到端验收 — 2h

#### Fix 4.1: 启动后端

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
```

#### Fix 4.2: 提交全链路 Case

通过 ACP 提交一个 case，覆盖以下特性：

```bash
# 1. ACP 提交题目 (Re4.4 + Re4.1 case_id 安全)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" -H "X-ACP-Capability: write" \
  -d '{"capability":"search_literature","params":{"topic":"基于YOLO的钢材表面缺陷检测","case_id":"re47-final"}}'

# 2. 轮询状态 (Re4.1 RunState + atomic_write_json)
# 等待 done

# 3. 获取 state — 验证 Re4.3 字段
# - innovation_points[].candidate_ids (Re4.3)
# - narrative_revisions[] (Re4.3)
# - low_bar_review.binding_validation (Re4.3)
# - low_bar_review.dag (Re4.3)

# 4. 获取 work-packages — 验证 DAG (Re4.3)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"get_work_packages","params":{"case_id":"re47-final"}}'

# 5. 获取 review — 验证 evidence_critiques (Re4.3)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"get_review","params":{"case_id":"re47-final"}}'

# 6. 入库 PDF (Re4.5 + Re4.6 merge_index)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" -H "X-ACP-Capability: write" \
  -d '{"capability":"ingest_pdf","params":{"pdf_url":"https://arxiv.org/pdf/2401.17270","case_id":"re47-final"}}'

# 7. RAG 问答 (Re4.5)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"query_rag","params":{"question":"What method is used?","case_id":"re47-final"}}'

# 8. 知识图谱 (Re4.5)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"get_knowledge_graph","params":{"case_id":"re47-final"}}'

# 9. 验证 SourcePolicy (Re4.1) — trace 中 citation_expander 记录 skipped
# 10. 验证 ACP ledger (Re4.4) — acp_ledger.jsonl 有调用记录
# 11. 验证旧前端 /web/ 仍可用 (Re4.2)
```

#### Fix 4.3: 全链路验收清单

| # | 检查项 | Re版本 | 通过标准 |
|---|---|---|---|
| 1 | case_id 安全（UUID/slug） | Re4.1 | POST 不传 case_id → 自动生成 UUID hex |
| 2 | SourcePolicy 生效 | Re4.1 | trace 中 citation_expander → S2 skipped |
| 3 | atomic_write_json | Re4.1 | state.json / trace.json / evidence_graph.json 完整可读 |
| 4 | StageContract v1.1 | Re4.3 | innovation_extractor/narrative_builder/work_package 版本 1.1 |
| 5 | binding_validation | Re4.3 | low_bar_review.binding_validation 字段存在 |
| 6 | narrative_revisions | Re4.3 | ≥1 revision，有 revision_id + parent_revision_id |
| 7 | DAG | Re4.3 | /work-packages 返回 dag，有 milestones |
| 8 | evidence_critiques | Re4.3 | review_report.evidence_critiques 存在 |
| 9 | ACP 14 能力 | Re4.4 | /capabilities 返回 14 个 |
| 10 | ACP 权限控制 | Re4.4 | write 无 header → PERMISSION_DENIED |
| 11 | ACP ledger | Re4.4 | acp_ledger.jsonl 有调用记录 |
| 12 | RAG ingest_pdf | Re4.5 | 返回 n_chunks > 0 |
| 13 | RAG query_rag | Re4.5 | 返回 answer + cited_chunks |
| 14 | RAG knowledge_graph | Re4.5 | 返回 nodes (paper/dataset/method) |
| 15 | React 前端 | Re4.2 | http://127.0.0.1:18183 可访问 |
| 16 | 结构化报告 | Re4.6 | 工作台报告区非 raw JSON |
| 17 | 旧前端兼容 | Re4.2 | http://127.0.0.1:18181/web/ 仍可用 |
| 18 | health 端点 | Re4.1 | {"phase":"re40","session":"day1"} |

---

### Phase 5：最终回归测试 — 1h

#### Fix 5.1: 全量测试

```bash
cd G:\PaperAgent
# 后端全量
.venv\Scripts\python.exe -m pytest apps/api/tests -v --tb=short

# React e2e (需 Vite dev server)
cd apps\web-react && npm run dev &
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest apps/web-react/e2e -v -m "react_web"

# 全量收集
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | findstr "collected error"
```

#### Fix 5.2: 回归验收

| 检查项 | 通过标准 |
|---|---|
| pytest collected | ≥ 531 |
| pytest errors | 0 |
| pytest failures | 0（或仅 network marker 的预期 skip） |
| ruff `apps/api/app` | ≤ 19 |
| ruff `.` F401 | 0 |
| ruff `.` F841 | 0 |
| ruff `.` E741 | 0 |
| npm build | 零 TS error |
| Playwright e2e | 全部 PASS |

---

### Phase 6：CHANGELOG 收口 — 30min

#### Fix 6.1: 追加 Re4.5–4.7 条目

**文件**：`CHANGELOG.md`

在 Re4.4 条目之前追加 Re4.5 和 Re4.6 条目（如果尚未追加），然后追加 Re4.7：

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.7)

### Fixed
- ruff 全项目修复：F401 (8处) / F841 (3处) / E741 (1处) 全部清零
- 临时验证脚本清理

### Changed
- `CODELY.md`: 全面重写为 Re4.0 架构（ACP / RAG / React / SourcePolicy / StageContract / RunState）
- `README.md`: 追加 Re4 新能力段落 + React 启动方式
- `docs/deployment/Local_Runbook.md`: 追加 ACP / RAG / React dev server 说明

### Verified
- 全链路端到端验收：Re4.1–4.6 全部 18 项检查通过
- 531 tests collected, 0 errors, 0 failures
- ruff F401/F841/E741 = 0；apps/api/app ≤ 19 errors
- npm build 零 TS error；Playwright e2e 全 PASS

## [0.4.0-dev] — Re4.0 Release Summary

Re4 工程升级周期（Day 1–7）全部完成。核心交付：

| Day | 主题 | 关键产物 |
|---|---|---|
| 1 | 工程控制面 | case_id 安全、SourcePolicy、CORS、StageContract、RunState |
| 2 | 前端基线 | React+Vite shell、首页+工作台+RAG、SSE、Playwright |
| 3 | 可追溯升级 | InnovationPoint/NarrativeRevision/WorkPackage schema、binding validator、DAG |
| 4 | ACP 能力层 | 14 能力、REST+JSON Schema、读写权限、调用示例 |
| 5 | RAG 检索 | PDF 提取、TF-IDF 索引、余弦检索、LLM 问答、知识图谱 |
| 6 | 深度整合 | 7 结构化报告组件、多文档 RAG、首页增强 |
| 7 | 验收收口 | 全链路验收、ruff 修复、文档更新、531 tests 全绿 |

测试总计：531 collected, 0 errors
ACP 能力：14（10 已实现 + 1 未来）
前端：React 52 modules, 240KB JS, 8 Playwright e2e PASS
```

---

### Phase 7：Re4.0 版本标记 — 30min

#### Fix 7.1: VERSION 确认

```bash
G:\PaperAgent\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'apps/api'); from app.main import app; print('Version:', app.version)"
# 预期: 0.4.0-dev
```

#### Fix 7.2: git status 确认

```bash
cd G:\PaperAgent
git status --short
git diff --stat HEAD
```

#### Fix 7.3: 最终确认清单

```
□ pytest --collect-only → 0 errors, ≥ 531 collected
□ ruff check apps/api/app → ≤ 19 errors
□ ruff check . → F401=0, F841=0, E741=0
□ npm run build → 零 TS error
□ 端到端 case re47-final → 18 项检查全通过
□ CODELY.md → 包含 ACP/RAG/React/SourcePolicy
□ README.md → 包含 Re4 段落
□ Local_Runbook.md → 包含 ACP/RAG/React
□ CHANGELOG.md → Re4.5–4.7 + Re4.0 release summary
□ .env.example → DeepSeek proxy 配置正确
□ 无残留临时文件
```

---

## 3. 执行顺序与依赖

```
Phase 1 (ruff 修复) ─── 无依赖
    │
    ├── Phase 2 (清理) ─── 依赖 Phase 1（修复后确认无破坏）
    │
    ├── Phase 3 (文档更新) ─── 可与 Phase 1-2 并行
    │
    ├── Phase 4 (端到端验收) ─── 依赖 Phase 1-2（代码清理后跑）
    │
    ├── Phase 5 (回归测试) ─── 依赖 Phase 1-4
    │
    ├── Phase 6 (CHANGELOG) ─── 依赖 Phase 4-5（验收结果写入）
    │
    └── Phase 7 (版本标记) ─── 依赖全部完成

可并行：
- Phase 3 (文档) 与 Phase 1-2 (代码清理) 完全并行
```

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| ruff --fix 破坏 import | pytest 收集出现 ImportError | 逐个手动修复，不用 --fix |
| 端到端 case 超时 | LLM 响应慢 | 等待 5min；timeout 不阻塞验收 |
| React build 失败 | tsc 报错 | 检查 Phase 1 是否删除了必要 import |
| CODELY.md 遗漏新模块 | 审查时发现 | 对照 Phase 4 验收清单逐项确认 |
| 旧前端 /web/ 不可用 | HTTP 500 | 确认 apps/web/index.html 未被修改 |
| 历史回归 case 缺失 | 契约回归 test SKIP | 保留已有 case 目录；不删除 tmp_re13_eval |

---

## 5. 完成标准

- [ ] `ruff check .` F401=0, F841=0, E741=0
- [ ] `ruff check apps/api/app` ≤ 19 errors
- [ ] `pytest --collect-only` 0 errors, ≥ 531 collected
- [ ] `npm run build` 零 TS error
- [ ] 端到端 case 18 项检查全通过
- [ ] CODELY.md 包含 ACP/RAG/React/SourcePolicy/StageContract/RunState
- [ ] README.md 包含 Re4 新能力段落
- [ ] Local_Runbook.md 包含 ACP/RAG/React 说明
- [ ] CHANGELOG.md 包含 Re4.5–4.7 + Re4.0 release summary
- [ ] 无残留临时文件
- [ ] git status 显示所有修改文件

---

## 6. 提交清单

| 文件 | 操作 |
|---|---|
| `CODELY.md` | 全面重写 |
| `README.md` | 追加 Re4 段落 |
| `docs/deployment/Local_Runbook.md` | 追加 ACP/RAG/React 说明 |
| `CHANGELOG.md` | 追加 Re4.5–4.7 + Re4.0 summary |
| 全项目 F401/F841/E741 相关文件 | ruff --fix 或手动修复 |
| 临时文件（如有残留） | 删除 |

---

## 7. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.7)

### Fixed
- ruff 全项目修复：F401 (8处) / F841 (3处) / E741 (1处) 全部清零
- 临时验证脚本清理

### Changed
- `CODELY.md`: 全面重写为 Re4.0 架构
- `README.md`: 追加 Re4 新能力 + React 启动方式
- `Local_Runbook.md`: 追加 ACP / RAG / React dev server 说明

### Verified
- 全链路端到端验收：Re4.1–4.6 全部 18 项检查通过
- 531 tests, 0 errors, 0 failures
- ruff F401/F841/E741 = 0；apps/api/app ≤ 19
- npm build 零 TS error；Playwright 全 PASS

## Re4.0 Release Summary

7-Day 工程升级周期完成。从工程控制面到 ACP 能力层到 RAG 全文检索到前端深度整合，
PaperAgent 从单文件 vanilla JS + 松散 dict 的原型，升级为 React+TypeScript 前端 +
ACP 标准化能力层 + TF-IDF RAG + 证据可追溯 schema 的工程化系统。

531 tests | 14 ACP capabilities | 52 React modules | 7 structured report components
```
