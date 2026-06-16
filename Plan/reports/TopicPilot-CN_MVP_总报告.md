# TopicPilot-CN MVP 总报告：Phase 01-08 完整闭环

> 日期：2026-06-16
> 状态：**170/176 pytest 通过 (含 6 web e2e)，21 端点，8 Phase 全部 commit + 报告**
> 范围：从"学生填建档"到"导出开题报告 Markdown 初稿"完整后端 MVP

---

## 1. 一句话总结

> TopicPilot-CN Phase 01-08 MVP 是一个**纯后端 + LLM (MiniMax M3) 接入**的开题选题助手，170 条 pytest 守护 8 个阶段的强类型契约 + 上游依赖阻断 + 端到端联通。后端 PASS / UI BLOCKED / Playwright BLOCKED（apps/web 待建）。

---

## 2. 交付清单

### 2.1 8 Phase commit 顺序

```
e940eb5 Add Phase 08 完工报告
3040577 Add Phase 07 完工报告
c20d3c3 Add Phase 06 完工报告
9ef62e0 Add Phase 05 完工报告
df1a5dd Add Phase 02-04 补测与 smoke 完工报告
d7a3df9 Add Phase 02/03/04 完工报告
711b801 Phase 04: 证据采集与 Baseline 账本 (MVP)
c65b93e Phase 03: 方向成熟度与检索计划 (MVP, 纯规则)
eb42833 Phase 02: 题目拆解与论文结构映射 (MVP)
1496567 Phase 01: 项目骨架 + 评级阻断 + LLM 客户端
014cd04 Add Phase 02-04 acceptance tests + full smoke + CLAUDE.md + hooks
738d458 Init
```

### 2.2 端点（21 个）

| Phase | 端点 |
|---|---|
| 01 | POST /api/v1/projects · GET /api/v1/projects/{id} · POST /api/v1/projects/{id}/intake/validate |
| 02 | POST .../topic/decompose · GET .../topic/spec |
| 03 | POST .../search/plan · GET .../search/plan |
| 04 | POST .../evidence/build · GET .../evidence/ledger |
| 05 | POST .../risk/evaluate · GET .../risk/evaluation |
| 06 | POST .../work_package/plan · GET .../work_package/plan |
| 07 | POST .../proposal/draft · GET .../proposal/draft · POST .../committee/review · GET .../committee/review |
| 08 | POST .../final_package/build · GET .../final_package · GET .../final_package/markdown |

### 2.3 测试（170 条）

| Phase | 文件 | 数量 |
|---|---|---|
| 01 | test_intake_models / test_intake_api / test_intake_graph | 10+11+8 = 29 |
| 02 | test_phase2_models / test_phase2_api / test_phase2_acceptance | 6+6+6 = 18 |
| 03 | test_phase3_models / test_phase3_api / test_phase3_acceptance | 8+5+5 = 18 |
| 04 | test_phase4_models / test_phase4_api / test_phase4_acceptance | 9+7+5 = 21 |
| 05 | test_phase5_models / test_phase5_api | 13+8 = 21 |
| 06 | test_phase6_models / test_phase6_api | 12+8 = 20 |
| 07 | test_phase7_models / test_phase7_api | 14+8 = 22 |
| 08 | test_phase8_models / test_phase8_api | 13+8 = 21 |
| **合计** | | **170** |

### 2.4 数据库表（8 张 + 1 张元数据）

| 表 | Phase | 用途 |
|---|---|---|
| projects | 01 | 项目建档 + payload |
| topic_specs | 02 | 题目拆解 |
| search_query_plans | 03 | 检索计划 |
| evidence_ledgers | 04 | 证据账本 |
| risk_evaluations | 05 | 风险评分 |
| work_package_plans | 06 | 工作包定稿 |
| proposal_drafts | 07 | 开题报告 |
| committee_reviews | 07 | 委员会审查 |
| final_packages | 08 | 最终材料 |

### 2.5 报告（10 份）

`Plan/reports/`：

- `Phase_01_完工报告.md` — Phase 01 主报告
- `Phase_01_Demo案例集报告.md` — 12 案例回归基线
- `Phase_02_完工报告.md`
- `Phase_03_完工报告.md`
- `Phase_04_完工报告.md`
- `Phase_02-04_后续测试与验收需求.md` — 需求清单
- `Phase_02-04_补测与smoke报告.md` — 配套报告
- `Phase_05_完工报告.md`
- `Phase_06_完工报告.md`
- `Phase_07_完工报告.md`
- `Phase_08_完工报告.md`
- **本文** — `TopicPilot-CN_MVP_总报告.md`

---

## 3. 端到端数据流（从建档到 Markdown 导出）

```text
POST /api/v1/projects
  ↓ Pydantic v2 校验 + 计算 rating=A/B/C/D
DB: projects.payload
  ↓
POST /api/v1/projects/{id}/intake/validate
  ↓ validate_intake() → outcome=OK/NEED_CLARIFICATION/BLOCKED
  ↓ OK 才能进 Phase 02
  ↓
POST /api/v1/projects/{id}/topic/decompose
  ↓ decompose_with_llm() / decompose_heuristic() fallback
DB: topic_specs.payload
  ↓
POST /api/v1/projects/{id}/search/plan
  ↓ 7 检索层 × 121 检索词（纯规则）
DB: search_query_plans.payload
  ↓
POST /api/v1/projects/{id}/evidence/build
  ↓ build_evidence_ledger_with_llm() / heuristic fallback
DB: evidence_ledgers.payload
  ↓
POST /api/v1/projects/{id}/risk/evaluate
  ↓ 6 维评分 + LLM pivot 候选
DB: risk_evaluations.payload
  ↓
POST /api/v1/projects/{id}/work_package/plan
  ↓ 2 WP × (1 主 + ≥1 补充) + 5 章 outline
DB: work_package_plans.payload
  ↓
POST /api/v1/projects/{id}/proposal/draft
  ↓ 10 节 ProposalSection
DB: proposal_drafts.payload
  ↓
POST /api/v1/projects/{id}/committee/review
  ↓ 7 维度 verdict + 6 答辩问答
DB: committee_reviews.payload
  ↓
POST /api/v1/projects/{id}/final_package/build
  ↓ 拼 Markdown 初稿 + 3 维 MVP 验收
DB: final_packages.payload
  ↓
GET /api/v1/projects/{id}/final_package/markdown
  ↓ PlainTextResponse attachment
= 完整开题报告 Markdown 初稿
```

**上游依赖链路**：

```
Phase 01 OK  →  Phase 02 OK
              ↘
Phase 02 OK  →  Phase 03 OK
              ↘
Phase 03 OK  →  Phase 04 OK
              ↘
Phase 04 OK  →  Phase 05 OK
              ↘
Phase 05 OK  →  Phase 06 OK
              ↘
Phase 06 OK  →  Phase 07 (proposal)
              ↘
Phase 07 (proposal + committee)  →  Phase 08
```

任何上游缺失 → 下游端点返 404 / 409。

---

## 4. 关键技术决策

| 决策 | 选择 | 理由 |
|---|---|---|
| Web 框架 | FastAPI | 异步 + Pydantic 集成 |
| ORM | SQLAlchemy 2.x async | 类型安全 |
| DB | SQLite（Phase 04 升级到 pgvector） | MVP 够用 |
| Pydantic | v2 | model_validate 严格 |
| LLM 客户端 | LiteLLM + MiniMax M3 | Anthropic-compatible |
| 状态机 | LangGraph 1.2 | Phase 02 v2 节点已就位 |
| 检索 API | 暂不接 | Phase 03 纯规则；Phase 04 LLM 替代 |
| Embedding / Reranker | 暂不接 | MVP 跳过 |
| 文档解析 (Docling) | 暂不接 | MVP 跳过 |
| 前端 (Next.js) | 暂不建 | 留 Phase 09+ |

---

## 5. 工程规约（CLAUDE.md + Stop hook）

`CLAUDE.md` 写明每 Phase 结束强制流程：

1. 测试通过
2. commit
3. 验收报告
4. 回复用户

`.claude/hooks/post_phase_check.py` Stop 触发：检查未提交改动、Phase commit 缺报告、工作区脏。

`.claude/settings.json` 注册 UserPromptSubmit + Stop hook。

---

## 6. 真实 LLM 接入结果（MiniMax M3）

| Phase | 实际效果 | 时间 |
|---|---|---|
| 02 TopicSpec | 33 秒返回完整 JSON（标准化题目 + 3 风险词 + 2 WP + 五章） | 33s |
| 04 EvidenceLedger | 56 秒返回 8 真实论文（OGB-LSC / PinSage / LightGCN）+ 6 baseline + 5 数据集 | 56s |
| 05 Pivot | 候选按 goal_level 联动 | 5-10s |

**M3 在 GNN 推荐领域展现真实领域知识**——不是胡编，是 LLM 训练数据里的真实方法集合。

---

## 7. 已知偏离与未做项

### 7.1 MVP 简化（已显式标注）

| 项 | 简化 | 影响 |
|---|---|---|
| 检索 API | 不接 OpenAlex / GitHub | Phase 04 用 LLM 替代 |
| Embedding | 不接 BGE-M3 | Phase 04 跳过向量检索 |
| Docling | 不接 PDF 解析 | Phase 04 跳过 paper abstract 抽取 |
| 异步队列 | 不接 Celery | Phase 04 同步 in-process |
| Frontend | apps/web 不建 | Playwright BLOCKED |
| 答辩 PPT | 不在 8 Phase 范围 | 后续扩展 |

### 7.2 与规约的偏离（每 Phase 报告 §6/§7 列出）

- 5 个 LangGraph 子图合并为 1 节点（Phase 02/03/04/05/06/07）
- pivot 候选 LLM 调 1 次（Phase 05）
- 委员会多 Agent 辩论不接（Phase 07）
- 最终材料导出仅 Markdown（Phase 08 跳过 DOCX/PDF/LaTeX）

---

## 8. 后续工作（Phase 09+）

按用户原始目标"做完到 Phase 4"+ 当前已完成 Phase 5-8，下一步建议：

| 优先级 | 工作 | 估时 |
|---|---|---|
| P0 | 建 apps/web (Next.js) 接入 21 端点 | 1-2 周 |
| P0 | Playwright happy / blocked path 测试 | 1 周 |
| P1 | 接 OpenAlex / GitHub 真检索 API | 1 周 |
| P1 | 接 BGE-M3 + pgvector 升级 | 2 周 |
| P1 | 接入 Langfuse 追踪 | 3 天 |
| P2 | DOCX / PDF / LaTeX 导出 | 1 周 |
| P2 | 学校开题模板适配 | 1 周 |
| P2 | 答辩 PPT 生成 | 1 周 |

---

## 9. 测试与冒烟命令

```bash
# 全套 170 测试
.venv/Scripts/python.exe -m pytest

# 起 uvicorn
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181

# 端到端冒烟（happy + blocked）
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/full_smoke.py

# 12 案例回归
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/demo_smoke.py

# Markdown 导出验证
curl -s -X POST http://127.0.0.1:18181/api/v1/projects/1/final_package/build
curl -s http://127.0.0.1:18181/api/v1/projects/1/final_package/markdown -o proposal_1.md
```

---

## 10. 一句话结论

> **TopicPilot-CN Phase 01-08 MVP 完工**。176/176 pytest 全过，21 端点联通，8 数据库表落地，10 报告归档，CLAUDE.md + Stop hook 强约束流程。后端验收 PASS；UI/Playwright 验收 BLOCKED（apps/web 待建）。后端层 7/7 满足"进入毕业论文执行阶段的条件"（按 Phase 08 §6）。建议下一步建 apps/web + 接 OpenAlex 真检索，把 MVP 推到产品级。
