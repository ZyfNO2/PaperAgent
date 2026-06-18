# PaperAgent 后续 Session 路线图与参考资料索引

> 日期：2026-06-18  
> 目的：在 Session 08 已完成开题报告 Markdown 导出后，规划后续多个 Session 的路径、边界、最终结果和参考资料索引。  
> 原则：近期 Session 详细，远期 Session 简化；始终围绕“交互式证据工作台”，不要过早跳到完整论文写作系统。

---

## 1. 当前已完成到哪里

最新报告：

```text
Plan/reports/Session_08_FinalPackage_Markdown_验收报告.md
```

当前能力：

```text
输入题目
→ 关键词拆解
→ 证据检索
→ 手动证据加入
→ 证据评分
→ EvidenceRef 证据追溯
→ Pivot / 工作包
→ 开题报告 Markdown 导出
```

短期闭环已经打通。下一阶段应提升“证据工作台”的使用体验和资料摄入能力。

---

## 2. 后续总体边界

### 2.1 近期边界

近期只做：

```text
证据工作台
资料卡片化
多源轻验证
Trace 持久化
报告质量检查
```

近期不做：

```text
完整毕业论文正文自动写作
DOCX / PPT 高级排版
PDF 全文 RAG
多 Agent 委员会复杂对话
Skill Marketplace 批量安装
自动实验执行
```

---

### 2.2 最终结果

阶段性最终结果应是：

> 一个面向中国研究生开题/选题的交互式证据工作台。用户输入题目后，可以把导师论文、系统检索论文、数据集、GitHub 工程和网页材料整理成证据卡片，经过人工审核后生成可追溯证据来源的开题报告 Markdown。

不是：

```text
全自动写完整毕业论文
全自动跑实验
自动替学生做学术判断
```

---

## 3. Session 路线图

### Session 09：双栏证据工作台 + Agent Card Intake

详细 SOP：

```text
Plan/PaperAgent_Session09_双栏证据工作台与Agent卡片导入SOP.md
```

目标：

```text
左侧放用户希望使用的证据；
右侧放系统检索到的候选证据；
用户可以把 URL / 文字描述交给 Agent，生成 pending EvidenceCard。
```

关键交付：

```text
workspace_lane 字段；
EvidenceWorkspaceBoard；
GET /workspace/board；
PATCH /workspace/item；
POST /cards/intake；
双栏 UI；
Agent 卡片导入面板。
```

验收：

```text
用户能移动卡片；
用户能标核心；
GitHub / arXiv / HuggingFace / Kaggle URL 能生成待确认卡片；
workspace_lane 能影响 EvidenceRef 优先级；
Markdown 导出不回退。
```

---

### Session 10：多源轻验证与 URL Verified

目标：

```text
让卡片不是只“看起来像证据”，而是至少做轻量来源验证。
```

范围：

```text
OpenAlex / arXiv / GitHub / HuggingFace / Kaggle URL 轻验证；
url_verified 字段落地；
extraction_confidence 接入 EvidenceRef；
Card Intake 生成 warnings；
低置信卡片不能进入 supports。
```

建议 API：

```text
POST /api/v1/one-topic/{project_id}/evidence/verify
POST /api/v1/one-topic/{project_id}/cards/intake/verify
GET  /api/v1/one-topic/{project_id}/evidence/verification-summary
```

参考：

```text
ResearchMCP：OpenAlex 检索与 paper fetcher 分层
DatasetResearch：gated check_exist
idea-evaluation-pipeline：未验证标 [UNVERIFIED]
ResearchRubrics：confidence 字段
```

边界：

```text
只做 URL / 元数据验证；
不做全文下载；
不绕过付费数据库；
不做复杂爬虫。
```

---

### Session 11：Trace 持久化与操作回放

目标：

```text
把用户如何修改关键词、移动证据、拒绝证据、选择 Pivot、生成报告的过程保存下来。
```

范围：

```text
Trace 从 in-memory 改为 jsonl 或本地轻量存储；
每个 project 有操作历史；
前端显示关键操作；
报告附“关键决策记录”。
```

参考：

```text
ARIS：failed ideas 永不剪枝；
research-companion：research-evaluations/YYYY-MM-DD-<slug>.md；
AutoResearchClaw：TransitionEvent / StageStatus。
```

边界：

```text
不做完整 Research Wiki；
不做跨项目推荐；
只保证当前 project 可回放。
```

---

### Session 12：报告质量检查与低门槛委员会复核

目标：

```text
对开题报告 Markdown 做结构、证据、风险和答辩问题的复核。
```

范围：

```text
检查每节是否有证据；
检查创新点是否过度宣传；
检查数据集/baseline 是否支撑工作包；
生成修改清单；
给出低门槛开题委员会 verdict。
```

参考：

```text
ResearchRubrics：rubric + confidence；
Idea2Proposal：多维评审；
Professor_skill：每条结论附证据；
nsfc-agent-skills：正反清单和合规表达。
```

边界：

```text
不做复杂多 Agent 辩论；
不模拟真实导师人格；
只做规则 + LLM 的轻复核。
```

---

### Session 13：内部科研 Skill Registry 最小版

目标：

```text
把已有 4 个内部 skill 从“文档”变成可注册、可索引、可被流程调用的能力说明。
```

现有 skill：

```text
skills/research/paper-card/SKILL.md
skills/dataset/dataset-validation/SKILL.md
skills/engineering/github-baseline/SKILL.md
skills/evidence/evidence-ledger/SKILL.md
```

范围：

```text
SkillRegistry；
skill metadata；
输入/输出 schema；
安全状态 reviewed/adapted/enabled；
在 Card Intake / EvidenceRef / FinalPackage 中引用 skill 名称。
```

边界：

```text
不下载第三方 skill；
不执行外部 shell；
不做 marketplace。
```

---

### Session 14：多源检索增强

目标：

```text
让系统候选证据来源从 arXiv/启发式扩展到 OpenAlex、Semantic Scholar、GitHub、HuggingFace 等。
```

范围：

```text
OpenAlex paper search；
GitHub repo search；
HuggingFace dataset search；
统一 Candidate Normalization；
统一 Dedup；
score + verification。
```

参考：

```text
ResearchMCP；
DatasetResearch；
Agent Research Skills；
Claude Scholar。
```

边界：

```text
先做 API 可用性与 fallback；
不追求召回率极致；
不做付费数据库爬取。
```

---

### Session 15：全文资料与图片/PDF 卡片化

目标：

```text
把 Card Intake 从 URL/文字扩展到截图、图片、PDF 片段。
```

范围：

```text
图片上传；
截图备注；
PDF 片段元数据；
用户确认后生成 PaperCard / DatasetCard / NoteCard。
```

参考：

```text
PaperQA2 思路；
RAG_Research_Paper_Gap_Finder；
doc-to-markdown / PDF 解析能力。
```

边界：

```text
不立刻做全文向量库；
先只做摘要级卡片；
所有 OCR/解析结果必须 pending，用户确认后才入证据链。
```

---

### Session 16+：维护与作品化

目标：

```text
把 MVP 做成稳定可展示项目。
```

范围：

```text
README；
Demo 样例；
测试矩阵；
错误提示；
开发文档；
部署说明；
合规声明；
简历项目描述。
```

边界：

```text
不继续无限扩功能；
优先稳定、可验收、可展示。
```

---

## 4. 参考资料索引

### 4.1 工作区核心报告

| 文件 | 用途 |
|---|---|
| `Plan/reports/Session_08_FinalPackage_Markdown_验收报告.md` | 当前最新状态，确认 Markdown 导出已完成 |
| `Plan/reports/Session_07_EvidenceRef_验收报告.md` | EvidenceRef 规则、coverage、用户复核 |
| `Plan/reports/Session_05_Evidence_Scoring_验收报告.md` | 证据评分、去重、score summary |
| `Plan/reports/Session_06_LLM_Path_Activation_验收报告.md` | LLM 路径、rerank、recommend、review |
| `Plan/reports/PINN_数字孪生_诊断报告.md` | 特定题目问题诊断和修复方向 |

---

### 4.2 工作区核心规划文档

| 文件 | 用途 |
|---|---|
| `Plan/Faraway/PaperAgent_交互式证据工作台改造计划书与SOP.md` | 总主线：证据工作台、人机交互、证据审核 |
| `Plan/Faraway/8Phase详解.md` | 8 Phase 输入/输出/测试结构 |
| `Plan/Faraway/Agent化路线.md` | 后续 Agent 化方向，注意近期不要过度提前实现 |
| `Plan/Faraway/参考项目调研.md` | 15 个参考仓库的 trick 和落地启示 |
| `Plan/Faraway/PaperAgent_科研Skill下载链接汇总.md` | skill 来源、内置规范和安全边界 |
| `Plan/毕业论文合集知识总结.md` | 毕业论文工作流与开题/论文方法总结 |

---

### 4.3 当前关键代码路径

| 路径 | 用途 |
|---|---|
| `apps/api/app/schemas.py` | OneTopic 响应模型、EvidenceRef、FinalPackage 模型 |
| `apps/api/app/schemas_evidence.py` | EvidenceItem 和证据池模型 |
| `apps/api/app/services/evidence.py` | 证据存储、手动添加、审核、snapshot、final_package 缓存 |
| `apps/api/app/services/evidence_refs.py` | EvidenceRef 选择、优先级、coverage |
| `apps/api/app/services/final_package.py` | Markdown 开题报告构建 |
| `apps/api/app/services/scoring.py` | Paper/Dataset/Repo 评分 |
| `apps/api/app/services/one_topic.py` | 主流程：拆题、检索、可行性、Pivot、推荐、审核 |
| `apps/api/app/services/keyword_search_assistant.py` | LLM 搜索助手 |
| `apps/api/app/services/llm.py` | LLM JSON 调用 helper |
| `apps/api/app/api/v1/one_topic.py` | OneTopic API 路由 |
| `apps/web/app.js` | 前端主逻辑 |
| `apps/web/index.html` | 前端结构 |
| `apps/web/styles.css` | 前端样式 |

---

### 4.4 当前测试路径

| 路径 | 用途 |
|---|---|
| `apps/api/tests/test_session8_final_package.py` | Markdown 导出后端测试 |
| `apps/web/e2e/test_one_topic_session8_final_package.py` | Markdown 导出 Playwright |
| `apps/api/tests/test_session7_evidence_refs.py` | EvidenceRef 后端测试 |
| `apps/web/e2e/test_one_topic_session7_evidence_refs.py` | EvidenceRef 前端测试 |
| `apps/api/tests/test_session5_evidence_scoring.py` | 证据评分测试 |
| `apps/web/e2e/test_one_topic_session5_scoring.py` | 证据评分 UI 测试 |

---

### 4.5 当前内部 Skill

| Skill | 路径 | 用途 |
|---|---|---|
| paper-card | `skills/research/paper-card/SKILL.md` | 论文卡片、论文评分、论文分类 |
| dataset-validation | `skills/dataset/dataset-validation/SKILL.md` | 数据集可用性检查 |
| github-baseline | `skills/engineering/github-baseline/SKILL.md` | GitHub baseline 与复现风险 |
| evidence-ledger | `skills/evidence/evidence-ledger/SKILL.md` | 证据账本、证据状态、证据追溯 |

---

### 4.6 参考仓库索引

| 仓库 / 项目 | 链接 | 主要借鉴点 |
|---|---|---|
| ResearchAgent | https://github.com/JinheonBaek/ResearchAgent | 文献驱动的问题/方法/实验迭代 |
| IRIS | https://github.com/Anikethh/IRIS-Interactive-Research-Ideation-System | 交互式 idea 探索、细粒度反馈 |
| Idea2Proposal | https://github.com/NuoJohnChen/Idea2Proposal | 多维评审、YAML-driven agent |
| research-companion | https://github.com/andrehuang/research-companion | idea critic、PURSUE/REFINE/KILL |
| idea-evaluation-pipeline | https://github.com/alejandroll10/idea-evaluation-pipeline | 评估-复核-转向闭环、强制 URL 引用 |
| DatasetResearch | https://github.com/GAIR-NLP/DatasetResearch | 数据集发现、gated check、dry-run |
| ResearchMCP | https://github.com/DaniManas/ResearchMCP | OpenAlex 检索、MCP paper tools |
| RAG Gap Finder | https://github.com/bistadinank/RAG_Research_Paper_Gap_Finder | section-aware chunk、gap 检索 |
| ARIS | https://github.com/wanshuiyin/auto-claude-code-research-in-sleep | Research Wiki、query_pack、失败想法保留 |
| AutoResearchClaw | https://github.com/aiming-lab/AutoResearchClaw | 状态机、HITL gate、pivot rollback |
| ResearchRubrics | https://github.com/scaleapi/researchrubrics | rubric、confidence、合规评分 |
| academic-ai-prompt | https://github.com/bohyy/academic-ai-prompt | 中文开题/写作 prompt、槽位化 |
| thesis_work_flow | https://github.com/bikeread/thesis_work_flow | 开题到论文的 Dify 工作流 |
| Professor_skill | https://github.com/Azurboy/Professor_skill | 证据链式导师/委员会模拟 |
| nsfc-agent-skills | https://github.com/njzjz/nsfc-agent-skills | 合规、正反清单、政策对齐 |

---

### 4.7 外部 Skill / 市场索引

| 名称 | 链接 | 用途 |
|---|---|---|
| Academic Research Skills | https://github.com/imbad0202/academic-research-skills | 文献、引用、写作 |
| Agent Research Skills | https://github.com/lingzhi227/agent-research-skills | 研究生命周期、GitHub 研究 |
| Deep Research Skills | https://github.com/Weizhena/Deep-Research-skills | 分阶段 deep research |
| Claude Scholar | https://github.com/Galaxy-Dawn/claude-scholar | question-evidence-experiment-claim |
| Research Paper Writing Skills | https://github.com/Master-cai/Research-Paper-Writing-Skills | ML/CV/NLP 写作规范 |
| Scientific Agent Skills | https://github.com/K-Dense-AI/scientific-agent-skills | 科研数据库和分析 |
| Academic Paper Skills | https://github.com/lishix520/academic-paper-skills | 论文规划与写作检查 |
| paper-craft-skills | https://github.com/zsyggg/paper-craft-skills | 图、PPT、论文可视化 |
| SkillsLLM | https://skillsllm.com/ | Skill 市场索引 |
| MCPMarket Skills | https://mcpmarket.com/tools/skills | MCP / Skill 搜索 |

---

## 5. 维护原则

后续每个 Session 都必须满足：

```text
1. 先读最新 report；
2. 不跳过 Evidence Ledger；
3. 任何结论必须可追溯 evidence_id；
4. 用户确认优先于 LLM 自动判断；
5. rejected 不得正向引用；
6. pending / assistant_intake 不得直接 supports；
7. Playwright 要覆盖主路径；
8. 每轮都写 Plan/reports/Session_xx_*.md。
```

---

## 6. 简易路径总览

```text
Session 09
双栏证据工作台 + Agent Card Intake

Session 10
多源轻验证 + url_verified + confidence

Session 11
Trace 持久化 + 操作回放

Session 12
报告质量检查 + 低门槛委员会复核

Session 13
内部 Skill Registry 最小版

Session 14
多源检索增强

Session 15
图片/PDF/网页资料卡片化

Session 16+
作品化、部署、README、Demo、测试矩阵、合规声明
```

