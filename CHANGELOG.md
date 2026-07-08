# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
