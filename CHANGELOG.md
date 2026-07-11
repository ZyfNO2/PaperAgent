# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.7.6-dev] - 2026-07-11 (Re7.6)

### Added
- `apps/api/scripts/run_round0.py`: Batch runner for 10 cross-domain topics via subprocess isolation
- `apps/api/scripts/run_topic_async.py`: Single-topic async runner via LangGraph streaming
- `apps/api/scripts/nv_model_compare.py`: NVIDIA multi-model comparison (7 models × verifier)
- `apps/api/scripts/re76_real_llm_test.py`: Real LLM verifier coverage test (Mistral/NV)
- `apps/api/tests/test_re7_rag_e2e.py`: RAG contract + feedback e2e tests (feedback_bar, citation_valid, fake-citation rejection, 19/20 irrelevant abstention, feedback write/read/aggregate)
- `apps/api/tests/test_re7_final_recommendation.py`: final recommendation verdict + feedback_bar tests
- `apps/api/app/services/feedback_bar.py`: `make_feedback_bar_for_final_recommendation` helper
- `apps/api/app/services/feedback_store.py`: extended `ArtifactType` with `rag_answer`, `final_recommendation`, `innovation_card`; added `list_by_artifact`
- `apps/api/app/services/rag/rag_contract.py`: Chinese instruction-injection patterns + `validate_citations_subset`
- `apps/api/tests/fixtures/generate_gold_fixtures.py`: Fixture generator script
- `apps/api/tests/fixtures/eval_R6/hidden_ood/`: 48 hidden-OOD test fixtures (4 categories)
- `apps/api/tests/fixtures/eval_R6/failure/`: 16 failure-injection fixtures
- `apps/api/tests/fixtures/eval_R6/novelty/`: 24 novelty-gold fixtures
- `apps/api/tests/fixtures/eval_R6/rag/`: 30 RAG-gold Q&A fixtures
- `apps/api/tests/fixtures/eval_H1/holdout_ids.json`: 5 holdout blind test case IDs

### Changed
- `apps/api/app/services/router/model_policy.py`: Expanded ALLOWED_MODEL_IDS with mistral-small-latest, stepfun-ai/step-3.7-flash, deepseek-ai/deepseek-v3, z-ai/glm-4.5-flash, moonshotai/kimi-k2.6, qwen/qwen3-8b, google/gemma-3-12b-it
- `apps/api/app/services/agents/graph/nodes/search_agent.py`: `_run_tool_sync` now uses `asyncio.new_event_loop()` instead of `asyncio.run()` to avoid RuntimeWarning in LangGraph async context
- `apps/api/scripts/run_round0.py`: Explicit `PYTHONPATH` in subprocess env

### Verified
- Real LLM verifier: Mistral Small 3.1 → 100% coverage (11/11), 5.0s
- NV Llama-3.1-8B → 100% coverage, 17.8s (backup provider)
- RAG e2e: 20/20 tests pass (feedback_bar + citation_valid + fake-citation rejection + 19/20 irrelevant abstention + feedback write/read/aggregate)
- final recommendation: verdict + feedback_bar tests pass
- 118 gold fixtures generated (48 OOD + 16 failure + 24 novelty + 30 RAG)
- 5 holdout blind test cases created with stratified verdict sampling

## [0.4.0-dev] - 2026-07-10 (Re4.4)

### Added
- `services/acp/`: ACP 最小能力层
  - `capabilities.py`: 14 个能力声明（8 read + 2 write + 4 declared）
  - `registry.py`: CapabilityRegistry — 注册/查找/参数校验
  - `server.py`: ACPServer — REST handler 路由 + 读写权限控制 + RunLedger 记录
  - `errors.py`: 统一错误结构（UNKNOWN_CAPABILITY / PERMISSION_DENIED / INVALID_PARAMS / NOT_IMPLEMENTED / INTERNAL_ERROR）
  - `examples.py`: Codex / Claude Code / Trae 调用示例
- `api/v1/acp.py`: ACP REST 端点（GET /capabilities, POST /invoke, GET /examples）
- `docs/project/THIRD_PARTY_NOTICES.md`: AutoResearchClaw MIT 许可证记录
- `test_re44_acp.py`: 17 个集成测试（registry + read + write + errors + declared）

### Changed
- `research.py`: 提取 10 个 `_xxx_impl` 函数供 ACP server 调用（不改变现有端点行为）
- `main.py`: 注册 acp_router

### Verified
- 端到端 case re44-verify-001 通过 ACP 层验证：提交 → 轮询 → 获取产物
- 17 个集成测试全部 PASS
- 4 个只读能力 + 2 个受控写能力通过测试
- 未知能力/越权/缺参数/未实现返回统一错误结构
- ACP 调用记录到 acp_ledger.jsonl（4 条事件）
- THIRD_PARTY_NOTICES.md 已记录 MIT 许可证

## [0.4.0-dev] - 2026-07-10 (Re4.3)

### Added
- `schemas/evidence_schema.py`: Pydantic v2 models for InnovationPoint (candidate_ids, evidence_snippets, scores),
  NarrativeRevision (revision_id, parent_revision_id, diff), WorkPackage (objective, method, deliverable, prerequisite_ids)
- `validators/binding_validator.py`: 证据链一致性验证器
  - innovation → candidate_id 绑定检查
  - work_package → evidence 绑定检查
  - narrative → innovation 引用检查
  - stale marking（上游 evidence 变化 → derived items 标记 stale）
- `validators/dependency_dag.py`: 工作包依赖 DAG 构建
  - 拓扑排序 + 循环检测 + 里程碑分层
- API endpoint `GET /{case_id}/work-packages`: 返回工作包 + DAG
- 5 个新测试文件：schema、binding validator、narrative revision、DAG、契约回归

### Changed
- `innovation_extractor.py`: prompt 追加 candidate_ids/evidence_snippets/scores 约束；validator 调用
- `narrative_builder.py`: 追加 revision history + diff 计算
- `devils_advocate_node.py`: prompt 追加 evidence_critiques；MINOR_REVISION 时传递 critique
- `content.py` (low_bar_review): 追加 binding validation + DAG 构建
- `stage_contract.py`: 3 个节点 contract 版本升级到 1.1
- `state.py`: 追加 narrative_revisions, binding_validation 字段

### Verified
- 端到端 case re43-verify-001 验证：新 schema 字段在 state/trace/work-packages 产物中存在
- innovation_points 3/3 有 candidate_ids（arXiv ID）+ novelty_score
- narrative_revisions 2 个（rev-0→rev-1，diff 存在）
- low_bar_review 包含 binding_validation + DAG
- review_report 包含 evidence_critiques（4 条指向具体 target_id）
- /work-packages API 返回 DAG（5 nodes, 1 milestone）
- 3 个历史 case 契约回归全部 PASS（向后兼容）

## [0.4.0-dev] - 2026-07-10 (Re4.2)

### Added
- `apps/web-react/`: 最小 React + Vite + TypeScript 前端 shell
  - 首页：价值主张、三步引导、两个 Demo Case 入口、历史记录
  - 工作台：题目输入、SSE 实时进度、论文列表、来源状态面板、报告折叠区
  - RAG 占位路由
  - 统一空状态、错误状态 + 中文建议、加载语义、键盘可达性
  - 人话节点名映射（24 节点 → 中文描述 + 阶段分组）
- `apps/web-react/e2e/test_re42_react_web.py`: Playwright 截图基线（home/workbench/error/report/mobile/keyboard）
- `apps/web-react/src/types/api.ts`: 完整 API 类型定义（ResearchState + SSE + SourcePolicy + Trace）
- `apps/web-react/src/lib/sse.ts`: SSE EventSource 封装（14 事件类型）
- `apps/web-react/src/lib/nodeNames.ts`: 节点内部名 → 人话映射 + 阶段分组

### Changed
- `.gitignore`: 追加 web-react node_modules/dist
- `apps/api/app/main.py`: 追加 /react 静态挂载（构建产物）
- `pytest.ini`: 追加 apps/web-react/e2e testpaths、更新 react-web marker

### Verified
- 端到端 case 前端验证：提交题目 → SSE 进度 → 报告展示完整
- 旧前端 /web/ 未受影响
- 375px 窄屏可浏览
- 键盘 Tab 导航可用
- 8 个 Playwright e2e 测试全部 PASS
- 7 张截图生成在 tmp_re42_screenshots/

## [0.4.0-dev] - 2026-07-10 (Re4.1)

### Added
- `source_policy.py`: 统一 SourcePolicy，per-source 启停/并发/退避/状态
- `run_state.py`: RunState 模型 + atomic_write_json + RunLedger
- `stage_contract.py`: StageContract v1，7 核心节点 I/O 契约
- `test_re40_case_id_security.py`: case_id 路径穿越防护测试
- `test_re40_source_policy.py`: SourcePolicy 单元测试
- `test_re40_stage_contract.py`: StageContract 注册与校验测试
- `test_re40_run_state.py`: 原子写入与 RunLedger 测试

### Changed
- `research.py`: case_id 改为服务端 UUID 或受限 slug + 路径边界校验
- `research.py`: atomic_write_json 替换直接 json.dump (state/trace/evidence_graph)
- `main.py`: CORS 从环境变量读取；VERSION 更新为 0.4.0-dev；health 端点更新
- `citation_expander.py`: 接入 SourcePolicy，禁用源零请求
- `source_ledger.py`: 补充 `skipped` 状态
- `.env.example`: 追加 SourcePolicy / CORS / TLS 配置
- `pytest.ini`: markers 更新（端口修正、React 前端标注为未实现）
- `Local_Runbook.md`: 完整重写，替换失效命令和版本号

### Archived
- `test_re04_main_entry.py` → `_archived_legacy_sessions/`
- `test_re10_reflection_search.py` → `_archived_legacy_sessions/`

### Added (Re3.9)
- PubMed E-utilities adapter (pubmed_search.py) — free, no key, 3 req/s
- _get_domain_tools in search_agent — PubMed only enabled for medical/biological domains
- PAPERAGENT_DISABLE_S2 / PAPERAGENT_DISABLE_OPENALEX env vars for search agent tool disable
- Cross-node dataset scan in innovation_extractor — scans innovation_points text for dataset names
  missed by dataset_repo_extractor, source=cross_node:innovation_extractor
- Provenance analysis script (scripts/re39_provenance_analysis.py) — 95 cases analyzed
- scripts/re39_disabled_link_run.py — Phase 5 disabled-link verification runner

### Fixed (Re3.9)
- topic_parser prompt now enforces ALL keywords MUST be in English (Re3.8 omission)
- known_dataset_names renamed to known_dataset_names_fallback with FALLBACK ONLY annotation
- Heuristic dataset source labels unified: heuristic_fallback:innovation_plan / heuristic_fallback:paper_title
- LLM dataset source labeled: llm:dataset_repo_extractor (was: paper_abstract)
- dataset_repo_extractor trace now includes used_fallback + llm_success_rate in output_summary
- Frontend timeline shows orange warning when a node used heuristic fallback

### Added (Re3.8)
- 40-paper regression: 100% PASS rate (0 failures)
- feasibility score anchoring: 9 distinct scores (was 75-clustered)
- search_agent duplicate query prevention
- devils_advocate 3-tier heuristic (ACCEPT/MINOR_REVISION/BLOCK)
- 4× BaseException→Exception residual cleanup
- citation_expander state_keys coverage

### Fixed (Re3.8)
- feasibility scoring: eliminated 75-score clustering via precise anchoring
- search_agent: LLM duplicate queries now fallback to plan queries
- devils_advocate heuristic: now returns MINOR_REVISION for thin evidence (was always ACCEPT)
- dataset_extractor: abstract/snippet range expanded 800→2000 chars
- dataset_extractor: known_dataset_names expanded with robotics/human-reconstruction/depth datasets
- scripts/re38_batch_verify.py: 50-paper verification script
- Plan/PaperAgent_Re3.8_完工报告.md
- Plan/PaperAgent_Re3.x_收官报告.md

### Fixed (Re3.8)
- 4 × except BaseException → except Exception (search_planner, targeted_repair, topic_parser, llm_router)
- Deleted obsolete ponytail comment in research_agent.py
- citation_expander state_keys verified non-empty (was only empty node in R36-003 trace)
- S1: feasibility scoring precision — vague ranges replaced with exact score anchors (85-100/75-84/60-74/40-59/0-39)
- S2: dataset_extractor abstract truncation 800→2000 + known_dataset_names expanded to 45+ across 10 domains
- S5: topic_parser prompt now forces ALL keywords in English (MUST be in English directive)
- S6: search_agent _llm_decide dedup check — duplicate tool+query triggers fallback
- S7: devils_advocate heuristic 3-tier verdict (ACCEPT/MINOR_REVISION/BLOCK based on baseline count + feasibility)

### Fixed (Re3.7)
- Removed _HEURISTIC_DOMAIN_KEYWORDS hardcoded domain map (rules.md §1)
- Removed _CN_EN_MAP hardcoded CN→EN translation map (rules.md §1)
- Removed hardcoded "deep learning survey" search suffix (rules.md §1)
- Fixed short-keyword filtering len<4 → len<2 (GAN/NLP now pass) (rules.md §1)
- Replaced domain-specific prompt examples with neutral placeholders (rules.md §10)
- Removed RE02_DATASET_WHITELIST ground-truth dataset injection (rules.md §1)
- Moved user input from system_prompt to user_prompt in baseline_classifier (CLAUDE.md §4)
- Added [OUTPUT CONTRACT] to 3 prompt files (re11_parser, re11_topic_parser, gap_repair_planner)
- Added expected= parameter to json_repair call_json
- Fixed 7 × except BaseException → except Exception (content.py + dataset_repo_extractor.py + verify.py)
- Added logger.debug to 3 × silent except Exception: pass (research_agent.py)
- Deleted duplicate _collect_stream definition in llm.py (Re3.6遗留)
- Archived _research_agent_compat.py + 3 dependent files (domain_scout_agent, re04_entry, reflection_critic_agent)
- .ruff.toml: added tmp_re24_eval to exclude list
- ruff errors: 94 → 64 (F821=0, F822=0, E722=0)

### Added (Re3.6)
- state_keys coverage: all 19 graph node files now report returned state keys in trace
- 12-paper batch regression with domain matrix coverage (3D vision, UAV, medical, AD, civil, power)

### Fixed (Re3.6)
- F821 undefined-name: 10 errors fixed (3 real bugs in eval/__init__.py, llm.py, citation_expand.py)
- F822 undefined-export: 6 errors fixed (_research_agent_compat.py __all__ noqa)
- dataset_extractor medical domain constraint strengthened (COCO rejection for medical papers)
- ruff errors: 95 → 94 (F821/F822 = 0)

### Added (Re3.5)
- Timeline debugger: draggable progress bar + node detail panel + progressive counts
- /timeline API endpoint with progressive state counts
- state_keys field in trace events (emit_trace enhanced)
- Feasibility prompt: domain-specific risk assessment (hardware/data compliance/dataset availability)
- dataset_repo_extractor: anti-false-positive rules + 11 new known dataset names
- .ruff.toml configuration with excluded directories

### Fixed (Re3.5)
- Feasibility assessor now passes domain hint to LLM prompt
- dataset_repo_extractor prompt rejects COCO/ImageNet for domain-specific papers
- Ruff errors: 466 → 95 (F841: 44→1, F401: 260→14, unsafe-fixes applied)

### Added (Re3.4)
- Selective regression: 6 problematic chapters re-tested (R34-002/038/046/066/092/033)
- P1 verification: feasibility_report keyword checks for R34-046 (hardware) and R34-033 (data/compliance)
- P1 verification: search_steps "deep learning" hardcoded check across all 6 cases
- P1 verification: research_narrative content check (all 6 cases have content)
- P1 verification: review_report.overall_verdict diversity check (2 unique verdicts)
- Completion report: `Plan/PaperAgent_Re3.4_完工报告.md`

### Fixed (Re3.4)
- final_recommendation counts verified in e2e (were 0 in Re3.3 artifacts — stale runs with old code)
- 60 legacy session tests archived to _archived_legacy_sessions/ (collection errors eliminated)
- retrieve.py dead code removed (296 lines, superseded by search_agent)
- Re3.3 SOP field name corrected (tier → verdict, _block_retry_count → devils_advocate_block_count)
- Ruff auto-fix applied to 6 core files in Re3.3 (15 errors → 0)

### Changed (Re3.4)
- pytest collection: 46 errors → 0 (348 tests collected)
- Ruff errors: 463 → 139 (legacy archive reduced count; 6 core files clean)
- R34-002 (磁瓦检测): 0 papers → 10 papers (fixed by search_agent)
- R34-038 (无人机检测): not_recommended/score=25 → feasible/score=82 (fixed)

### P1 Verification Results (Re3.4)
- **Item 11 (R34-046 hardware risk)**: ❌ FAIL — feasibility_report 未包含 "硬件"/"机械臂" 关键词；风险聚焦于数据采集
- **Item 12 (R34-033 data/compliance)**: ✅ PARTIAL — feasibility_report 含 "数据"/"数据集" (2处) 及 LIDC-IDRI；未显式提及 "合规"/"隐私"
- **Item 13 (no deep learning hardcoded)**: ✅ PASS — R34-002/038 的 "deep learning" 来自用户 topic "深度学习"，非硬编码 fallback；其余 4 case 无
- **Item 14 (verdict diversity)**: ✅ PASS — ACCEPT(4) + MINOR_REVISION(2)
- **research_narrative**: ✅ 所有 6 case 均有内容 (字段名为 singular `research_narrative`)

### Known Limitations (Re3.4)
- ruff errors 139 > 50 目标 (archived legacy 仍被扫描)
- R34-046 feasibility_report 未识别硬件/机械臂风险
- R34-033 feasibility_report 未显式提及合规/隐私 (仅 "数据"/"数据集")
- R34-066 仍 risky (多模态对抗攻击论文仅 3 篇)

### Added (Re3.0)
- React search agent: LLM-driven 8-step think-call-observe loop
- Reflection strategy switch: synonym/broaden/switch_tool for repair
- Search agent async-safe (_run_tool_sync for FastAPI BackgroundThreads)

### Added (Re3.1)
- User paper upload API (POST/GET /{case_id}/papers)
- arXiv full-text PDF retrieval + pypdf text extraction
- Crossref component type filtering in quality_filter
- Enhanced cross-adapter dedup (_dedup_key with DOI priority)
- Heuristic dataset extraction from paper titles (45+ known datasets)
- Frontend upload UI

### Added (Re3.2)
- CORE adapter registered to REGISTRY
- DataCite adapter for dataset DOI search
- search_agent expanded to 8 tools (added huggingface, core, datacite)
- rules.md restored

### Fixed (Re3.0)
- Removed hardcoded "deep learning" domain fallback
- Removed len(q) > 5 short keyword filtering (YOLO, SLAM, GAN now pass)
- Removed hardcoded domain_map
- Unified research_narrative field name (singular) across 4 files
- Fixed revision_count double increment (narrative_builder + optimization_advisor)
- recursion_limit=100 (was default 25, caused graph truncation)
- search_agent _run_tool_sync replaces asyncio.run() (no event loop crash)

### Fixed (Re3.2)
- verify.py missing import re, import json (NameError on string LLM output)
- test_re1_2_graph_nodes.py updated for search_agent (was paper_retriever)
- MAX_REPAIR_ROUNDS reads env var in targeted_repair.py (was hardcoded)
- adapters/__init__.py mojibake docstring fixed
- SearchSource Literal expanded with core, datacite, crossref

---

## [0.1.0-rc1] - 2026-06-19

> 维护版收束 / v0.1 Release Candidate.
> 自 Session 18-20 起不再扩展新功能, 仅做错误处理、报告模板、文档收束.

### Added
- Evidence workbench (双栏证据工作台 + Agent Card Intake, Session 9)
- URL verification + 多源轻验证 (Session 10)
- Trace persistence + 操作回放 (Session 11)
- Report quality review + 低门槛委员会复核 (Session 12)
- Skill registry (内部 Skill 注册表, Session 13)
- Multi-source retrieval (Semantic Scholar / Kaggle / heuristic, Session 14)
- Material card intake (全文资料 / 图片 / PDF / 网页卡片化, Session 15)
- Demo baseline + 回归基线 (Session 16-17)
- Error observability (错误码 / 空状态 / 可观测性, Session 18)
- Opening report templates (default / engineering / cv_ai, Session 19)
- 维护文档: VERSION, CHANGELOG, Roadmap, Known Limitations, Release Checklist, Architecture Overview

### Changed
- README 与 demo 文档更新 (启动步骤 / 演示脚本)
- 前端空状态 / 错误状态提示统一

### Security / Compliance
- rejected / pending / failed 证据必须用户复核
- 不绕过付费数据库 (Semantic Scholar 仅 metadata, Kaggle 仅列表)
- 不向第三方上传用户文件
- 所有 LLM 凭据从 `.env` 读取, `.env` 不入 git
- Demo baseline 是结构合同, 非自然语言黄金答案
- LLM 路径可降级到 heuristic fallback, 不挂掉服务

---

## 历史 Session 概览

| Session | 主题 | 关键产物 |
| --- | --- | --- |
| 01 | 任务建模与评级 | ProjectIntake / FastAPI 3 端点 / LangGraph |
| 02 | 题目理解 | TopicSpec + LLM 拆解 |
| 03 | 三线检索 | SearchQueryPlan + 7 检索层 |
| 04 | 证据收集 | EvidenceLedger |
| 05 | 证据评分 | PaperScore / DatasetScore / RepoScore |
| 06 | LLM 路径 | heuristic fallback + LLM 增强 |
| 07 | EvidenceRef | 证据引用 + 复核 SOP |
| 08 | FinalPackage | Markdown 报告导出 |
| 09 | 双栏工作台 | EvidenceWorkspaceBoard |
| 10 | URL 验证 | Verification status 联动 |
| 11 | Trace 持久化 | JSONL Trace |
| 12 | 报告质量 | ReportQuality + 5 维轻审核 |
| 13 | Skill Registry | 内部 Skill 调度 |
| 14 | 多源检索 | Semantic Scholar / Kaggle |
| 15 | 资料卡片化 | 图片 / PDF / 网页卡片 |
| 16 | 作品化 / Demo | Demo 包装 |
| 17 | Demo baseline | 回归基线 |
| 18 | 错误 / 观测 | AppError / 空状态 / healthz |
| 19 | 报告模板 | 3 轻量学校模板 |
| 20 | Release Candidate | 维护文档收束 |
