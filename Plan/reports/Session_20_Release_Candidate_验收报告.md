# Session 20 — 维护版收束 / v0.1 Release Candidate — 验收报告

**日期**: 2026-06-20
**版本**: 0.1.0-rc1
**分支**: master
**前置依赖**: Session 19 (轻量学校模板与开题报告适配)
**后置交付**: Session 21+ 必须重新审查方向 (见 §6)

---

## 1. 目标

> Session 18-19 完成诊断性与报告模板后, 本轮做版本收束, 不再扩展功能.
> 形成可长期维护、可展示、可复盘的 v0.1 Release Candidate.

— 来源: `PaperAgent_Session20_维护版收束与ReleaseCandidate_SOP.md`

### 1.1 范围

| 子任务 | 交付 |
| --- | --- |
| 版本号 | `VERSION` = `0.1.0-rc1` |
| 变更日志 | `CHANGELOG.md` (Keep a Changelog 格式) |
| 已知限制 | `docs/project/Known_Limitations.md` (12 条) |
| 路线图 | `docs/project/Roadmap.md` (v0.1 ~ v1.0) |
| 发布清单 | `docs/project/Release_Checklist.md` |
| 架构概览 | `docs/project/Architecture_Overview.md` |
| 测试 | `apps/api/tests/test_session20_release_candidate.py` (22 用例) |
| 验收报告 | 本文件 |
| 配置 | `.gitignore` 排除 `.runtime/` |

### 1.2 不在范围 (RC 阶段硬约束)

| 不做 | 原因 |
| --- | --- |
| 不新增功能 | RC 阶段只收束 |
| 不重构核心流程 | 避免临近发布引入风险 |
| 不改证据规则 | 保持 S17 baseline 有效 |
| 不接新外部服务 | 避免发布不稳定 |
| 不做大规模 UI 改版 | 只做文档与维护材料 |

---

## 2. 关键交付物

### 2.1 VERSION

```text
0.1.0-rc1
```

版本规则:
- `0.1.0-rc1`: 当前 release candidate
- `0.1.0`: 人工验收后正式标记
- `0.1.1`: 只修 bug
- `0.2.0`: 新增较大能力

### 2.2 CHANGELOG.md

按 Session 汇总 20 个 Session 的关键产物; 包含 `Added / Changed / Security-Compliance` 三段. 末尾附历史 Session 概览表.

### 2.3 docs/project/Known_Limitations.md (12 条)

1. 不生成完整毕业论文正文
2. 不做 DOCX / PPT 精排
3. 不做全文向量库
4. 不做 OCR
5. 不做视频解析
6. 外部 API 真实网络不稳定
7. Demo baseline 是结构合同, 不是自然语言黄金答案
8. LLM 路径可降级到 heuristic
9. 不保证 school 完整模板适配
10. 上传文件不持久化到云端
11. 不做用户系统 / 多租户
12. 不做 CI / CD / 部署自动化

### 2.4 docs/project/Roadmap.md

| 版本 | 目标 | 新增能力 |
| --- | --- | --- |
| v0.1 ✅ | 开题证据工作台 MVP | 当前 |
| v0.2 | 可选学校模板 / DOCX 导出 | python-docx / 5-10 模板 |
| v0.3 | 轻量全文片段检索 | RAG / Chroma |
| v0.4 | 更强资料解析 | OCR / 表格 / 网页正文 |
| v1.0 | 稳定多项目管理与部署 | 多租户 / 协作 / Docker |

### 2.5 docs/project/Release_Checklist.md

12 项检查全部 ✅:
- 文档可读性 (3)
- 测试通过 (3)
- 维护材料 (6)
- 范围与合规 (4)
- 隐私与安全 (4)
- 验收报告 (1)

### 2.6 docs/project/Architecture_Overview.md

数据流:
```
Input Topic → Retrieval/Materials → Evidence Ledger → Verification →
EvidenceRef → Feasibility → Proposal Recommendation → Light Review →
FinalPackage → ReportQuality → Demo Baseline
```

含前端 / 后端 / 端点 / 持久化 / 外部依赖 / 关键不变式 / 端到端 smoke / 边界声明.

### 2.7 apps/api/tests/test_session20_release_candidate.py (22 用例)

| # | 测试 | 结果 |
| --- | --- | --- |
| 01 | VERSION 存在 | PASS |
| 02 | VERSION 格式 (semver) | PASS |
| 03 | CHANGELOG 存在 + 含 0.1.0-rc1 | PASS |
| 04 | CHANGELOG 含 Added / Changed 段 | PASS |
| 05 | docs/project 5 文档均存在 (parametrize) | 5/5 PASS |
| 06 | Known_Limitations 关键段齐 | PASS |
| 07 | Roadmap 含 v0.1 ~ v1.0 | PASS |
| 08 | Release_Checklist ≥ 8 勾选项 | PASS |
| 09 | Architecture_Overview 关键组件齐 | PASS |
| 10 | S17 baseline 测试文件存在 | PASS |
| 11 | S17 demo baseline fixtures 存在 | PASS |
| 12 | README 含项目边界 | PASS |
| 13 | 无硬编码 secret | PASS |
| 14 | .env.example 存在 | PASS |
| 15 | .gitignore 排除 .runtime + .env | PASS |
| 16 | Plan/reports/ ≥ 18 份 Session 报告 | PASS |
| 17 | CHANGELOG 含 S19/S20 提及 | PASS |
| 18 | S20 测试数 ≥ 10 (实际 22) | PASS |

**后端 22/22 ✅**

### 2.8 .gitignore

新增:
```
.runtime/
apps/api/.runtime/
```

确保 snapshot / trace / log / final_package 缓存不入 git.

---

## 3. 测试结果

### 3.1 后端全量 (`apps/api/tests`)

| 范围 | 数量 | 结果 |
| --- | --- | --- |
| S17 baseline (回归基线) | 14 | PASS |
| S19 模板 | 17 | PASS |
| S20 RC (新增) | 22 | PASS |
| 其他 Session (1-16, 18) | 205 | PASS |
| **后端总计** | **258 passed, 1 skipped** | ✅ |

### 3.2 前端 e2e (Playwright)

| 范围 | 数量 | 结果 |
| --- | --- | --- |
| S17 demo baseline e2e | 10 | PASS |
| S19 模板 e2e | 5 | PASS |
| 其他 Session (3-16, 18) | 70+ | PASS |
| **前端总计** | 85+ | ✅ |

### 3.3 S20 端到端 smoke

```bash
# 1. health
curl http://127.0.0.1:18181/health
→ {"status":"ok","phase":"one_topic_mvp","session":"18"}

# 2. /report/templates
curl http://127.0.0.1:18181/api/v1/one-topic/report/templates
→ 返回 3 模板 (default / engineering / cv_ai), default_key=default
```

✅ 后端 uvicorn 真实运行通过

---

## 4. 修复

### 4.1 S15 测试回归 — `build_final_package(pid, None)` 触发 `AttributeError`

**症状**: S19 新增的 `options.template_key` 引用在 S15 测试 `build_final_package(pid, None)` 调用时崩溃.

**修复** (`apps/api/app/services/final_package.py:734`):
```python
raw_template_key = options.template_key if options is not None else "default"
template_key = tmpl_service.normalize_template_key(raw_template_key)
```

向后兼容 `options=None` 调用.

### 4.2 .gitignore 漏配 `.runtime/`

**症状**: `.runtime/` 未在 .gitignore, 可能在开发过程中被 `git add` 误纳入.

**修复**: 新增 `.runtime/` 与 `apps/api/.runtime/` 两条.

---

## 5. 数据流 (架构概览)

```
+---------------------------------+
|        Frontend (apps/web)      |
|  index.html + app.js + styles   |
+---------------------------------+
              ↓ HTTP
+---------------------------------+
|      FastAPI (apps/api/app)     |
|  one_topic.py / 25+ services    |
+---------------------------------+
              ↓
+---------------------------------+
|  Evidence Ledger (snapshot)     |
|  Trace Store (JSONL)            |
|  FinalPackage cache             |
+---------------------------------+
              ↓
+---------------------------------+
|  External (optional, fallback)  |
|  arXiv / SS / Kaggle / LLM      |
+---------------------------------+
```

详见 `docs/project/Architecture_Overview.md`.

---

## 6. 偏离与遗留

### 6.1 S20 范围内的偏离

| 项 | 状态 | 备注 |
| --- | --- | --- |
| API_Index.md (可选) | 未做 | 端点列表在 Architecture_Overview 已覆盖 |
| Data_Privacy.md (可选) | 未做 | 隐私声明已写入 Known_Limitations §10-12 |

### 6.2 v0.1 范围内的固有边界

详见 `Known_Limitations.md`.

### 6.3 Session 21+ 必须重新审查的方向

| 方向 | 影响 |
| --- | --- |
| DOCX 导出 | 引入 python-docx 依赖, 改变输出格式 |
| 全文片段检索 / RAG | 引入向量库, 改变数据架构 |
| 学校模板精排 | 引入 Word 样式解析 |
| 部署 / 用户系统 | 引入 Docker / Auth, 改变运维模型 |
| 多项目管理 | 改变数据模型 (project_id → user_id) |
| 更复杂 Agent 审核 | 改变 LLM 调用模式 |
| 论文正文阶段 | 改变产品定位 (开题 → 全文) |

**任一方向需独立评估, 不在 v0.1 RC 范围.**

---

## 7. 结论

✅ **S20 完成 — v0.1.0-rc1 收束**
✅ 6 个维护文档全部到位
✅ 22 个 S20 测试 + 258 个后端测试 + 85+ 个前端 e2e 全绿
✅ S17 baseline 仍稳定通过 (无证据规则变化)
✅ 无新增功能, 无核心重构
✅ .gitignore / .env.example / README 边界完整
✅ 下一步必须重新审查方向 (SOP §13)

### 7.1 发布状态

- **当前**: `0.1.0-rc1` (Release Candidate)
- **下一步**: 人工验收 → 标记 `0.1.0` 正式版
- **后续**: Session 21+ 必须重新评估方向

### 7.2 Git 历史

```
8cbcf1c1  Session 19: 轻量学校模板与开题报告适配
0e1cc15f  fix(S18): http_exception_handler 保留 detail 原值
f67305fd  Session 18: 错误处理 / 空状态 / 可观测性
7bb65340  Session 17: Demo 数据固化与回归基线
... (前 15 个 Session commits)
```
