# Release Checklist — v0.1.0-rc1

> 每次发布前, 逐项核对. 全部 ✅ 才可标记 release 完成.

## 1. 文档可读性

- [x] **README 可读** — 含项目简介 / 启动步骤 / 演示命令 / 边界声明
- [x] **Runbook 可启动** — 端口 18181 / 18182, 命令在 CLAUDE.md
- [x] **Demo Script 可跑** — `scripts/demo_smoke.py` + `scripts/full_smoke.py`

## 2. 测试通过

- [x] **S17 baseline 通过** — `apps/api/tests/test_session17_demo_baseline.py`
- [x] **后端全量测试通过** — `pytest apps/api/tests` 全绿
- [x] **Playwright 主路径通过** — `apps/web/e2e/test_one_topic_*.py` 全绿

## 3. 维护材料

- [x] **VERSION 已更新** — `0.1.0-rc1`
- [x] **CHANGELOG 已更新** — `CHANGELOG.md` 含本版本号
- [x] **Known Limitations 完整** — `docs/project/Known_Limitations.md` (12 条)
- [x] **Roadmap 已写** — `docs/project/Roadmap.md` (v0.1 ~ v1.0)
- [x] **Release Checklist 存在** — 本文件
- [x] **Architecture Overview 存在** — `docs/project/Architecture_Overview.md`

## 4. 范围与合规

- [x] **Scope_And_Compliance 完整** — `docs/project/Scope_And_Compliance.md` 未过期
- [x] **不自动代写论文** — 边界在 README / 报告抬头显式声明
- [x] **不伪造引用** — 所有 EvidenceRef 必带 url_verified
- [x] **Human Gate 保留** — Gate 1 (关键词) / Gate 2 (检索词) 不可绕过

## 5. 隐私与安全

- [x] **.runtime 不入 git** — `.gitignore` 已配
- [x] **`.env` 不入 git** — `.gitignore` 已配
- [x] **无敏感 key 泄露** — 无 `MINIMAX_API_KEY=*` 硬编码
- [x] **无第三方上传** — 用户文件仅本地解析, 不发外网

## 6. 验收报告

- [x] **Session 20 验收报告** — `Plan/reports/Session_20_Release_Candidate_验收报告.md`

---

## 不通过的处理

任一项 ⛔ 即**不发布**. 修复后回到本清单重新核对.
