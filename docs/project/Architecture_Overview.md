# Architecture Overview

> v0.1.0-rc1 系统架构概览.

## 1. 整体数据流

```text
Input Topic
   ↓
Retrieval / Materials  ─→  全文资料 / 图片 / PDF / 网页卡片 (Session 15)
   ↓
Evidence Ledger       ─→  三类证据 (paper / dataset / baseline)
   ↓
Verification          ─→  URL 验证 + 多源交叉 (Session 10)
   ↓
EvidenceRef           ─→  统一证据引用结构 (Session 7)
   ↓
Feasibility           ─→  GO / NARROW / PIVOT / PARK / STOP 5 档
   ↓
Proposal Recommendation ─→  推荐题目 + 工作包 + 退化路线
   ↓
Light Review          ─→  5 维轻审核 (覆盖度 / 风险 / 完备性 / ...)
   ↓
FinalPackage          ─→  Markdown 开题报告 + 引用清单 (Session 8)
   ↓
ReportQuality         ─→  质量评分 + 不支持声明标注 (Session 12)
   ↓
Demo Baseline         ─→  结构合同冒烟测试 (Session 17)
```

## 2. 层次

### 2.1 前端 (apps/web/)

- **HTML 骨架**: `index.html` (单页 + section 折叠)
- **样式**: `styles.css` (浅色 / 暗色, 响应式)
- **逻辑**: `app.js` (vanilla JS, 无框架)
- **e2e 测试**: `e2e/test_one_topic_*.py` (Playwright)

关键模块:
- `state` 全局状态 (project_id, finalPackage, workspaceBoard, ...)
- `buildReport()` / `renderReportSummary()` 报告渲染
- `loadWorkspaceBoard()` 双栏工作台
- `submitHumanGate()` Human Gate 1/2 提交
- `applyTraceReplay()` Trace 回放

### 2.2 后端 (apps/api/app/)

```
app/
├── main.py                    # FastAPI 入口 + lifespan
├── errors.py                  # AppError + 错误码 (Session 18)
├── schemas.py                 # Pydantic v2 schemas
├── api/v1/
│   └── one_topic.py           # /one-topic/* 全部端点
└── services/
    ├── topic_understanding.py # 题目理解
    ├── keyword_breakdown.py   # 关键词拆解
    ├── search_plan.py         # 检索词生成
    ├── retrieval.py           # 7 检索层
    ├── evidence.py            # Evidence Ledger (snapshot)
    ├── paper_score.py         # 论文评分
    ├── dataset_score.py       # 数据集评分
    ├── repo_score.py          # 仓库评分
    ├── feasibility.py         # 可行性判断
    ├── proposal.py            # 开题建议
    ├── light_review.py        # 轻审核
    ├── final_package.py       # Markdown 报告生成
    ├── report_templates.py    # 模板系统 (Session 19)
    ├── report_quality.py      # 报告质量检查
    ├── verification.py        # URL 验证
    ├── trace_store.py         # JSONL Trace
    ├── workspace.py           # 双栏工作台
    ├── skills.py              # 内部 Skill Registry (Session 13)
    ├── materials.py           # 资料卡片 (Session 15)
    ├── demo_baseline.py       # Demo baseline (Session 17)
    ├── health.py              # /health 端点
    ├── llm.py                 # LLM 客户端 + heuristic fallback
    └── ...
```

### 2.3 端点索引 (one_topic)

| Method | Path | 用途 | Session |
| --- | --- | --- | --- |
| POST | `/analyze` | 题目分析 (主入口) | 1 |
| GET | `/analyze/{project_id}` | 重读分析结果 | 1 |
| GET | `/health` | 健康检查 | 18 |
| GET | `/health/details` | 详细健康 (LLM / evidence / trace) | 18 |
| POST | `/analyze/{project_id}/gate/keywords` | Human Gate 1 提交 | 3 |
| POST | `/analyze/{project_id}/gate/search` | Human Gate 2 提交 | 3 |
| GET | `/analyze/{project_id}/workspace/board` | 双栏工作台 | 9 |
| PATCH | `/analyze/{project_id}/workspace/item` | 移动证据 | 9 |
| POST | `/analyze/{project_id}/evidence/upload` | 上传 PDF/图片 | 15 |
| POST | `/analyze/{project_id}/final-package/build` | 生成报告 | 8 |
| GET | `/analyze/{project_id}/final-package` | 报告摘要 | 8 |
| GET | `/analyze/{project_id}/final-package/markdown` | 下载 Markdown | 8 |
| GET | `/one-topic/report/templates` | 模板列表 | 19 |

### 2.4 持久化

| 存储 | 路径 | 用途 |
| --- | --- | --- |
| Snapshot | `.runtime/snapshots/{project_id}.json` | Evidence Ledger 持久化 |
| Trace | `.runtime/traces/{project_id}.jsonl` | JSONL Trace |
| Log | `.runtime/logs/*.log` | 结构化日志 |
| FinalPackage | `.runtime/final_packages/{project_id}.json` | 报告缓存 |

`.runtime/` 不入 git, 仅本地调试.

### 2.5 外部依赖

| 库 | 用途 | 状态 |
| --- | --- | --- |
| FastAPI | Web 框架 | 必须 |
| Pydantic v2 | Schema 校验 | 必须 |
| arXiv API | 论文检索 | 可选 (失败 fallback heuristic) |
| Semantic Scholar | 论文 metadata | 可选 (占位) |
| Kaggle | 数据集列表 | 可选 (占位) |
| LLM (MINIMAX) | 增强生成 | 可选 (失败 fallback heuristic) |

**所有外部依赖失败均不阻塞服务**.

## 3. 关键不变式

1. **每个阶段端点必须被前阶段 409 拦截**
   - D 评级 → Phase 02 拒; 无 TopicSpec → Phase 03 拒; 无 SearchQueryPlan → Phase 04 拒
2. **LLM 路径必须配 heuristic fallback**
3. **凭据从 `.env` 读取, `.env` 不入 git**
4. **pytest 总数每次 commit 增长**
5. **rejected / pending / failed 证据不进入 FinalPackage 引用清单 (除非显式 include_rejected_as_appendix)**
6. **Trace 必须 JSONL 持久化, 可 replay**

## 4. 端到端 smoke

```bash
# 1. 起后端
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 2. 起前端
.venv/Scripts/python.exe apps/web/dev_server.py

# 3. 跑 demo
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/demo_smoke.py

# 4. 跑全量 Phase 01-04
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/full_smoke.py

# 5. 跑测试
.venv/Scripts/python.exe -m pytest
```

## 5. 不在 v0.1 范围

- 全文向量库 / RAG (v0.3)
- DOCX 精排 (v0.2)
- OCR / 视频解析 (v0.4)
- 用户系统 / 多租户 (v1.0)
- CI/CD / 自动部署 (v1.0)
- 论文正文代写 (永不做)

详见 `Roadmap.md` 与 `Known_Limitations.md`.
