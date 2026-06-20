# Session 32 — ExportReadiness & TemplateCompliance 验收报告

日期: 2026-06-21
Commit: e764fd0c

## 目标

实现 8 维导出前就绪检查（Readiness）服务，支持学校模板合规校验（default / engineering / cv_ai），并集成至 one_topic API 端点，确保不满足就绪条件时阻止导出。

## 产物清单

| 文件 | 说明 |
|------|------|
| `apps/api/app/schemas_readiness.py` | Pydantic schemas: ReadinessStatus, SchoolTemplate, ReadinessDimension, ReadinessReport, ReadinessRequest |
| `apps/api/app/services/readiness.py` | 8 维 readiness 检查服务，含 hard block 逻辑 |
| `apps/api/app/api/v1/one_topic.py` | POST `/{project_id}/readiness` 端点 |
| `apps/api/tests/test_session32_readiness.py` | 后端 10 个 pytest 用例 |
| `apps/web/e2e/test_one_topic_session32_readiness.py` | Playwright 8 个 E2E 用例 |

### 8 维检查清单

| # | 维度 | 检查内容 | Hard Block |
|---|------|----------|------------|
| 1 | section_completeness | 12 章节全部非空 | 是 |
| 2 | evidence_binding | ≥40% 章节绑定 evidence | 否 |
| 3 | reference_integrity | 至少 1 条 verified citation | 是 |
| 4 | school_template_fit | 模板要求章节全部存在 | 是 |
| 5 | risk_disclosure | 可行性风险章节非空 | 否 |
| 6 | workload_clarity | 工作量章节 ≥3 条 | 否 |
| 7 | innovation_claim_safety | 无夸大创新词（首创/首次/完全解决等） | 是 |
| 8 | format_basic | Markdown ≥200 字符 | 否 |

### SchoolTemplate 枚举

- `default` — 轻量模板，最宽松
- `engineering` — 工科模板，要求技术路线等章节
- `cv_ai` — CV/AI 模板，要求数据集信息等章节

## 测试结果

| 类型 | 数量 | 状态 |
|------|------|------|
| Backend pytest | 10 | 全部通过 |
| Playwright E2E | 8 | 全部通过 |
| **S32 合计** | **18** | **全部通过** |

### 后端用例明细（10）

| # | 用例 | 验证点 |
|---|------|--------|
| 1 | S32-1 | 完整报告全部 pass |
| 2 | S32-2 | 缺技术路线 → fail |
| 3 | S32-3 | 缺 EvidenceRef → fail |
| 4 | S32-4 | 含夸大创新词 → fail |
| 5 | S32-5 | cv_ai 模板缺数据集 → fail |
| 6 | S32-6a | engineering 模板校验 |
| 7 | S32-6b | engineering 模板校验（续） |
| 8 | S32-7 | default 模板轻量但不允许空证据 |
| 9 | S32-8a | ReadinessReport 可序列化 |
| 10 | S32-8b | ReadinessReport 可序列化（续） |

### Playwright E2E 用例明细（8）

| # | 用例 | 验证点 |
|---|------|--------|
| 1 | S32-PW-1 | readiness API 可访问 |
| 2 | S32-PW-2 | 8 维 readiness 显示 |
| 3 | S32-PW-3 | fail 项显示 required_fix |
| 4 | S32-PW-4 | 模板切换结果变化 |
| 5 | S32-PW-5 | fail 时导出按钮 disabled |
| 6 | S32-PW-6 | pass/warn 时允许导出 |
| 7 | S32-PW-7 | S29 不回退 |
| 8 | S32-PW-8 | S31 不回退 |

## 修复记录

开发过程中发现并修复 3 个偏差：

| # | 问题 | 修复 |
|---|------|------|
| 1 | EvidenceRef 没有 `ref_no` 属性 | 改为使用 `evidence_id` |
| 2 | Snapshot 没有 `sections` 键 | 改为从 FinalPackage 自动 `build_final_package()` 后读取 |
| 3 | Playwright `TestReadinessPageVisible` 检查不存在的前端模块 | 改为检查 API 可访问性 |

## 不回退确认

- S29 Playwright E2E 测试仍全部通过（S32-PW-7）
- S31 Playwright E2E 测试仍全部通过（S32-PW-8）

## 关键不变式

- **Hard Block 阻断导出** — section_completeness / reference_integrity / school_template_fit / innovation_claim_safety 四个维度 fail 时，整体状态为 fail，前端导出按钮 disabled。
- **自动构建 FinalPackage** — readiness 端点自动从 FinalPackage 缓存读取，无缓存时自动 build，无 snapshot 时从 proposal_recommendation fallback，无需手动触发。
- **模板合规前置** — school_template_fit 按 SchoolTemplate 枚举动态校验所需章节，不同模板要求不同。

## 遗留问题

- readiness 维度 warn 状态的 UI 视觉提示可进一步优化（当前仅文本区分）

## 结论

S32 达成全部目标：8 维 readiness 检查服务 + 3 种学校模板 + 18 个测试（10 后端 + 8 E2E）全部通过，S29/S31 不回退，3 个开发偏差均已修复。
