# PaperAgent 后续 Session 16-20 路线图与参考资料索引

> 日期：2026-06-19  
> 背景：Session 09-15 已完成证据工作台主闭环。后续重点从“继续堆功能”切换为“作品化、稳定化、可复现、可展示”。  
> 原则：近期 Session 详细，远期 Session 简化；保持开题/选题证据工作台定位，不转向完整毕业论文自动写作。

---

## 1. 当前状态

最新验收报告：

```text
Plan/reports/Session_15_Material_Card_Intake_验收报告.md
```

当前主流程：

```text
题目输入
→ 关键词拆解
→ 多源检索
→ 证据工作台
→ 用户资料卡片化
→ URLVerified
→ Trace 持久化
→ EvidenceRef
→ FinalPackage Markdown
→ ReportQuality
```

已具备的关键能力：

```text
1. 双栏证据工作台；
2. Agent Card Intake；
3. URL / 元数据轻验证；
4. Trace jsonl 持久化；
5. 报告质量检查；
6. 内部 Skill Registry；
7. OpenAlex / arXiv / GitHub / HuggingFace 多源检索；
8. PDF / 图片 / 网页文字 / URL+描述 / 导师备注卡片化；
9. pytest + Playwright 持续验收。
```

---

## 2. 总体边界

后续优先：

```text
作品化；
Demo 固化；
测试矩阵；
部署说明；
错误提示；
轻量维护；
边界声明；
项目展示材料。
```

后续暂不做：

```text
完整毕业论文正文自动生成；
全文向量库；
大规模 PDF RAG；
视频解析；
批量图片 OCR；
多 Agent 委员会复杂辩论；
自动实验执行；
第三方 Skill Marketplace；
DOCX / PPT 高级排版。
```

最终结果：

```text
一个可运行、可演示、可测试、边界清楚的开题选题证据工作台项目。
```

---

## 3. Session 16：作品化、稳定化与 Demo 包装

详细 SOP：

```text
Plan/PaperAgent_Session16_作品化稳定化与Demo包装SOP.md
```

目标：

```text
把当前系统整理成可展示项目，而不是继续扩功能。
```

交付：

```text
README；
docs/demo/OneTopic_Demo_Script.md；
docs/demo/Demo_Cases.md；
docs/testing/Test_Matrix.md；
docs/deployment/Local_Runbook.md；
docs/project/Scope_And_Compliance.md；
docs/project/Resume_Project_Description.md；
Plan/reports/Session_16_Productization_Demo_验收报告.md。
```

验收重点：

```text
1. 外部读者能理解项目做什么；
2. 本地能按文档启动；
3. Demo 能按脚本跑通；
4. 测试矩阵能说明质量边界；
5. 项目边界声明不夸大能力；
6. 不破坏 Session 10-15 的证据规则。
```

---

## 4. Session 17：Demo 数据固化与回归基线

目标：

```text
把 1-2 个 Demo 项目固化成稳定回归基线，后续修改可以比较输出是否退化。
```

建议交付：

```text
docs/demo/baselines/yolo_steel_defect_input.json
docs/demo/baselines/yolo_steel_defect_expected.md
docs/demo/baselines/risky_topic_input.json
docs/demo/baselines/risky_topic_expected.md
apps/api/tests/test_session17_demo_baseline.py
apps/web/e2e/test_one_topic_session17_demo_baseline.py
Plan/reports/Session_17_Demo_Baseline_验收报告.md
```

近期细节：

```text
1. 固化输入题目；
2. 固化必要的 mock 外部源；
3. 固化核心证据数量；
4. 固化 FinalPackage 必备章节；
5. 固化 ReportQuality verdict 范围；
6. 固化 rejected / pending / failed 不进 supports 的断言；
7. 固化 Trace 关键 action 出现。
```

边界：

```text
不要求每次自然语言输出逐字一致；
只比较结构、关键字段、证据规则和报告章节。
```

---

## 5. Session 18：错误处理、空状态与可观测性整理

目标：

```text
让系统在外部 API 失败、无数据、上传失败、验证失败、报告质量低分时给出明确下一步。
```

建议交付：

```text
统一错误码；
前端错误提示组件；
空状态文案；
检索失败 fallback 说明；
资料上传失败说明；
ReportQuality 修改建议入口；
轻量 health endpoint；
Plan/reports/Session_18_Error_Observability_验收报告.md。
```

重点场景：

```text
OpenAlex 不可达；
GitHub 限流；
PDF 无文本层；
图片无 OCR；
没有数据集；
没有 baseline；
用户导入重复证据；
ReportQuality verdict=需修改 / 不建议。
```

边界：

```text
不引入复杂日志平台；
不做生产级监控；
只做本地 MVP 可诊断。
```

---

## 6. Session 19：轻量学校模板与开题报告适配

目标：

```text
在不做 DOCX 高级排版的前提下，提供 2-3 种 Markdown 开题报告模板。
```

建议交付：

```text
docs/templates/opening_report_default.md
docs/templates/opening_report_engineering.md
docs/templates/opening_report_cv_ai.md
FinalPackage template selector；
Plan/reports/Session_19_Report_Templates_验收报告.md。
```

模板字段：

```text
研究背景；
国内外研究现状；
研究内容；
技术路线；
创新点；
实验方案；
进度安排；
风险预案；
参考文献；
证据引用清单。
```

边界：

```text
不做学校 Word 模板精排；
不做自动格式审查；
只做 Markdown 结构适配。
```

---

## 7. Session 20：维护版收束与发布候选

目标：

```text
形成一个可长期维护的 v0.1 Release Candidate。
```

建议交付：

```text
CHANGELOG.md；
VERSION；
docs/project/Roadmap.md；
docs/project/Known_Limitations.md；
Release checklist；
Plan/reports/Session_20_Release_Candidate_验收报告.md。
```

验收：

```text
1. README / Demo / Runbook 完整；
2. 核心测试通过；
3. 已知限制明确；
4. 不再混入新的大功能；
5. 项目可用于展示、简历和后续论文阶段规划。
```

---

## 8. 参考资料索引：核心文档

| 文件 | 用途 |
|---|---|
| `Plan/Faraway/PaperAgent_交互式证据工作台改造计划书与SOP.md` | 总主线：证据工作台、人机交互、证据审核 |
| `Plan/Faraway/参考项目调研.md` | 参考项目设计启发 |
| `Plan/Faraway/Agent化路线.md` | 长期 Agent 化方向，近期只作为边界参考 |
| `Plan/Faraway/8Phase详解.md` | 早期阶段拆解与验收结构 |
| `Plan/Faraway/PaperAgent_科研Skill下载链接汇总.md` | Skill 来源与安全边界 |
| `Plan/毕业论文合集知识总结.md` | 开题/毕业论文方法论来源 |
| `Plan/PaperAgent_Session15_全文资料与图片PDF网页卡片化SOP.md` | 当前最新执行 SOP |
| `Plan/reports/Session_15_Material_Card_Intake_验收报告.md` | 当前最新验收依据 |

---

## 9. 参考资料索引：Session 报告

| 报告 | 作用 |
|---|---|
| `Plan/reports/Session_09_WorkspaceBoard_CardIntake_验收报告.md` | 双栏工作台与 Agent 卡片导入 |
| `Plan/reports/Session_10_Verification_URLVerified_验收报告.md` | URLVerified 与 supports 硬约束 |
| `Plan/reports/Session_11_Trace_Persistence_验收报告.md` | Trace 持久化与时间线 |
| `Plan/reports/Session_12_ReportQuality_Review_验收报告.md` | 报告质量检查与低门槛审核 |
| `Plan/reports/Session_13_SkillRegistry_验收报告.md` | 内部 Skill Registry |
| `Plan/reports/Session_14_MultiSource_Retrieval_验收报告.md` | 多源检索增强 |
| `Plan/reports/Session_15_Material_Card_Intake_验收报告.md` | PDF / 图片 / 网页资料卡片化 |

---

## 10. 参考资料索引：核心代码

| 路径 | 用途 |
|---|---|
| `apps/api/app/api/v1/one_topic.py` | OneTopic 主 API，含 evidence / retrieval / materials 入口 |
| `apps/api/app/api/v1/skills.py` | Skill Registry API |
| `apps/api/app/schemas.py` | 主响应模型、EvidenceRef、FinalPackage、ReportCitation |
| `apps/api/app/schemas_evidence.py` | EvidenceItem 与证据池模型 |
| `apps/api/app/schemas_retrieval.py` | RetrievalCandidate / RetrievalRun |
| `apps/api/app/schemas_materials.py` | MaterialItem / DraftEvidenceCard |
| `apps/api/app/schemas_trace.py` | TraceEvent 模型 |
| `apps/api/app/schemas_quality.py` | ReportQuality 模型 |
| `apps/api/app/services/evidence.py` | Evidence Ledger 存储与审核 |
| `apps/api/app/services/evidence_refs.py` | EvidenceRef 角色选择与 supports 约束 |
| `apps/api/app/services/verification.py` | URL / 元数据轻验证 |
| `apps/api/app/services/trace_store.py` | Trace jsonl 持久化 |
| `apps/api/app/services/report_quality.py` | 8 维报告质量审核 |
| `apps/api/app/services/final_package.py` | 开题报告 Markdown 构建 |
| `apps/api/app/services/skill_registry.py` | 内部 Skill Registry |
| `apps/api/app/services/retrieval/` | 多源检索、归一化、去重、排序 |
| `apps/api/app/services/materials/` | PDF / 图片 / 网页资料卡片化 |
| `apps/web/index.html` | 前端结构 |
| `apps/web/app.js` | 前端主交互逻辑 |
| `apps/web/styles.css` | 前端样式 |

---

## 11. 参考资料索引：测试

| 路径 | 用途 |
|---|---|
| `apps/api/tests/test_session10_verification.py` | URLVerified |
| `apps/api/tests/test_session11_trace_persistence.py` | Trace persistence |
| `apps/api/tests/test_session12_report_quality.py` | ReportQuality |
| `apps/api/tests/test_session13_skill_registry.py` | SkillRegistry |
| `apps/api/tests/test_session14_multi_source_retrieval.py` | Multi-source retrieval |
| `apps/api/tests/test_session15_material_card_intake.py` | Material card intake |
| `apps/web/e2e/test_one_topic_session10_verification.py` | Verification UI |
| `apps/web/e2e/test_one_topic_session11_trace_persistence.py` | Trace UI |
| `apps/web/e2e/test_one_topic_session12_report_quality.py` | ReportQuality UI |
| `apps/web/e2e/test_one_topic_session13_skill_registry.py` | Skill UI |
| `apps/web/e2e/test_one_topic_session14_retrieval.py` | Retrieval UI |
| `apps/web/e2e/test_one_topic_session15_material_cards.py` | Material cards UI |

---

## 12. 参考资料索引：内部 Skill

| Skill | 路径 | 当前用途 |
|---|---|---|
| paper-card | `skills/research/paper-card/SKILL.md` | 论文卡片生成、论文证据来源标记 |
| dataset-validation | `skills/dataset/dataset-validation/SKILL.md` | 数据集卡片与可用性标记 |
| github-baseline | `skills/engineering/github-baseline/SKILL.md` | GitHub baseline / repo 证据标记 |
| evidence-ledger | `skills/evidence/evidence-ledger/SKILL.md` | 证据账本、去重、审核、引用链 |
| registry | `skills/registry.json` | Skill metadata / risk / used_by |

---

## 13. 参考资料索引：外部项目

| 项目 | 链接 | 参考点 |
|---|---|---|
| ResearchAgent | https://github.com/JinheonBaek/ResearchAgent | 文献驱动的问题/方法/实验迭代 |
| IRIS | https://github.com/Anikethh/IRIS-Interactive-Research-Ideation-System | 交互式 idea 探索 |
| Idea2Proposal | https://github.com/NuoJohnChen/Idea2Proposal | 多维评审与 proposal 化 |
| research-companion | https://github.com/andrehuang/research-companion | idea critic 与研究记录 |
| idea-evaluation-pipeline | https://github.com/alejandroll10/idea-evaluation-pipeline | 强制 URL 引用与评估闭环 |
| DatasetResearch | https://github.com/GAIR-NLP/DatasetResearch | 数据集发现与 gated check |
| ResearchMCP | https://github.com/DaniManas/ResearchMCP | OpenAlex 检索与 paper tools |
| RAG Gap Finder | https://github.com/bistadinank/RAG_Research_Paper_Gap_Finder | section-aware gap 检索，后续 RAG 才参考 |
| ARIS | https://github.com/wanshuiyin/auto-claude-code-research-in-sleep | Research Wiki、query_pack、失败想法保留 |
| AutoResearchClaw | https://github.com/aiming-lab/AutoResearchClaw | 状态机、HITL gate、pivot rollback |
| ResearchRubrics | https://github.com/scaleapi/researchrubrics | rubric、confidence、合规评分 |
| thesis_work_flow | https://github.com/bikeread/thesis_work_flow | 开题到论文的工作流参考 |

---

## 14. 简易路径总览

```text
Session 16
作品化、稳定化、Demo 包装

Session 17
Demo 数据固化与回归基线

Session 18
错误处理、空状态与可观测性整理

Session 19
轻量学校模板与开题报告 Markdown 适配

Session 20
维护版收束与 v0.1 Release Candidate
```

---

## 15. 维护原则

后续每个 Session 都必须继续遵守：

```text
1. 先读最新 report；
2. 不跳过 Evidence Ledger；
3. 任何结论必须可追溯 evidence_id；
4. 用户确认优先于 LLM 自动判断；
5. rejected 不得正向引用；
6. pending / assistant_intake / unverified 不得直接 supports；
7. failed verification 不得 supports；
8. Playwright 覆盖主路径；
9. 每轮写 Plan/reports/Session_xx_*.md；
10. 新功能必须说明边界和未做项。
```

