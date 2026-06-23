# PaperAgent Session 20 SOP：维护版收束与 v0.1 Release Candidate

> 日期：2026-06-19  
> 阶段定位：Session 18-19 完成诊断性与报告模板后，本轮做版本收束，不再扩展功能。  
> 本轮目标：形成可长期维护、可展示、可复盘的 v0.1 Release Candidate。

---

## 1. 低风险判断

Session 20 是当前低风险连续链路的终点。

判断：

```text
在不做中间人工审查的情况下，建议最多连续做到 Session 20；
Session 21 之后必须重新审查方向。
```

原因：

```text
S18 是错误与诊断；
S19 是 Markdown 模板；
S20 是发布收束；
三者不应改变核心证据链。

超过 S20 后通常会进入新功能：RAG、DOCX、模板精排、部署、用户系统、CI/CD 等，
这些会改变架构或产品边界，应先重新审查。
```

---

## 2. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不新增功能 | RC 阶段只收束 |
| 不重构核心流程 | 避免临近发布引入风险 |
| 不改证据规则 | 保持 S17 baseline 有效 |
| 不接新外部服务 | 避免发布不稳定 |
| 不做大规模 UI 改版 | 只做文档与维护材料 |

---

## 3. 核心交付

新增 / 更新：

```text
CHANGELOG.md
VERSION
docs/project/Roadmap.md
docs/project/Known_Limitations.md
docs/project/Release_Checklist.md
docs/project/Architecture_Overview.md
Plan/reports/Session_20_Release_Candidate_验收报告.md
```

可选：

```text
docs/project/API_Index.md
docs/project/Data_Privacy.md
```

---

## 4. VERSION

新增：

```text
VERSION
```

内容：

```text
0.1.0-rc1
```

规则：

```text
0.1.0-rc1：当前 release candidate；
0.1.0：人工验收后正式标记；
0.1.1：只修 bug；
0.2.0：新增较大能力。
```

---

## 5. CHANGELOG

新增：

```text
CHANGELOG.md
```

按 Session 汇总：

```text
## [0.1.0-rc1] - 2026-06-19

### Added
- Evidence workbench
- URL verification
- Trace persistence
- Report quality review
- Skill registry
- Multi-source retrieval
- Material card intake
- Demo baseline
- Error observability
- Opening report templates

### Changed
- README and demo docs
- Frontend empty/error states

### Security / Compliance
- rejected / pending / failed evidence constraints
- no paid database bypass
- no user file upload to third party
```

---

## 6. Known Limitations

新增：

```text
docs/project/Known_Limitations.md
```

必须包含：

```text
1. 不生成完整毕业论文正文；
2. 不做 DOCX / PPT 精排；
3. 不做全文向量库；
4. 不做 OCR；
5. 不做视频解析；
6. Semantic Scholar / Kaggle 仍可选 / 占位；
7. 外部 API 真实网络不稳定；
8. Demo baseline 是结构合同，不是自然语言黄金答案；
9. LLM 路径可降级到 heuristic。
```

---

## 7. Roadmap

新增：

```text
docs/project/Roadmap.md
```

内容：

```text
v0.1：开题证据工作台 MVP；
v0.2：可选学校模板 / DOCX 导出；
v0.3：轻量全文片段检索；
v0.4：更强资料解析；
v1.0：稳定多项目管理与部署。
```

每个版本必须写边界：

```text
仍不自动代写论文；
仍不伪造引用；
仍保留用户确认。
```

---

## 8. Architecture Overview

新增：

```text
docs/project/Architecture_Overview.md
```

包含：

```text
前端；
FastAPI；
Evidence Ledger；
Retrieval；
Verification；
Trace Store；
FinalPackage；
ReportQuality；
Materials；
Skill Registry；
Demo Baseline。
```

建议图：

```text
Input Topic
→ Retrieval / Materials
→ Evidence Ledger
→ Verification
→ EvidenceRef
→ FinalPackage
→ ReportQuality
→ Demo Baseline
```

---

## 9. Release Checklist

新增：

```text
docs/project/Release_Checklist.md
```

必须包含：

```text
1. README 可读；
2. Runbook 可启动；
3. Demo Script 可跑；
4. S17 baseline 通过；
5. 后端全量测试通过；
6. Playwright 主路径通过；
7. Known Limitations 完整；
8. Scope / Compliance 完整；
9. VERSION 已更新；
10. CHANGELOG 已更新；
11. .runtime 不纳入版本；
12. 无敏感 key / 用户文件。
```

---

## 10. 测试要求

新增：

```text
apps/api/tests/test_session20_release_candidate.py
```

覆盖：

```text
1. VERSION 存在且格式正确；
2. CHANGELOG 存在且含 0.1.0-rc1；
3. Known_Limitations 存在；
4. Release_Checklist 存在；
5. Roadmap 存在；
6. Architecture_Overview 存在；
7. Scope_And_Compliance 仍存在；
8. S17 baseline 文件仍存在；
9. README 含项目边界；
10. 不存在明显 secret 占位泄露。
```

回归：

```text
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py apps/api/tests/test_session20_release_candidate.py -v
```

建议全量：

```text
.venv/Scripts/python.exe -m pytest apps/api/tests -q
```

Playwright：

```text
至少重跑 apps/web/e2e/test_one_topic_session17_demo_baseline.py
```

---

## 11. 验收标准

通过条件：

```text
1. VERSION 存在；
2. CHANGELOG 存在；
3. Roadmap 存在；
4. Known Limitations 存在；
5. Release Checklist 存在；
6. Architecture Overview 存在；
7. README / Demo / Runbook 没有过期路径；
8. S17 baseline 通过；
9. 后端 release 测试通过；
10. Playwright 主路径通过或报告说明；
11. 无新增功能；
12. 无证据规则变化；
13. 新增 Session20 验收报告。
```

---

## 12. 完工报告要求

完成后新增：

```text
Plan/reports/Session_20_Release_Candidate_验收报告.md
```

报告必须写：

```text
版本号；
新增维护文档；
测试结果；
S17 baseline 是否通过；
是否新增功能；
是否改变证据规则；
已知限制；
下一阶段必须审查的方向。
```

---

## 13. Session 21 之后必须重新审查

建议不要直接继续做。

需要重新决策的方向：

```text
1. DOCX 导出；
2. 全文片段检索 / RAG；
3. 学校模板精排；
4. 部署 / 用户系统；
5. 多项目管理；
6. 更复杂 Agent 审核；
7. 论文正文阶段。
```

这些方向都会改变产品边界或架构复杂度，必须单独评估。

