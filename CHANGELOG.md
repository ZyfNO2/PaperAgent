# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
