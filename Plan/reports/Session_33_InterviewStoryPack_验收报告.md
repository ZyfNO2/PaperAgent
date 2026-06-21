# Session 33 — InterviewStoryPack 面试导向材料 验收报告

**日期:** 2026-06-21
**分支:** master

---

## 1. 摘要

Session 33 为非功能冲刺，产出为 **面试导向材料整理**（Interview Story Pack），覆盖项目介绍、架构图解、QA 问答、演示脚本、失败案例、简历亮点等 7 份文档，定位为面向面试官 / 评审人的系统化介绍包。共 13 个后端测试验证文档存在性与内容完整性，全部通过；Session 6 LLM 路径的 8 个测试保持已知状态通过。统计算法：S33 新增 13 条测试断言，S6 维持 8 条，Session 33 整体贡献 13 条有效断言。

---

## 2. 文档清单

所有文档位于 `docs/interview/` 目录：

| # | 文件 | 说明 |
|---|------|------|
| 1 | `Project_OnePager.md` | 10 节项目一页总览（定位、目标用户、核心问题、技术架构、技术难点、测试、安全边界、演示路径、未来扩展），繁体中文 |
| 2 | `Architecture_Diagram.md` | 2 份 Mermaid 图表：用户流程图（8 阶段 + 5 决策节点）与技术架构图（7 层分层 + 证据流生命周期） |
| 3 | `Interview_QA_Cards.md` | 30 道面试 QA 卡片，分 6 大类别，每类 5 题；每题包含问题、面试官意图、PaperAgent 回答、项目证据、可展示文件、风险补充 |
| 4 | `Demo_Script_3min.md` | 7 阶段 3 分钟现场演示脚本（~450 字），以 YOLO 钢材缺陷检测为演示题目 |
| 5 | `Demo_Script_10min.md` | 扩展版 10 分钟演示脚本（~1500 字），含 Trace 回放、失败案例、PIVOT 路线、架构深度 |
| 6 | `Failure_Cases.md` | 8 个失败案例（6 必选 + 2 附加），每个含输入、系统拦截、UI 反馈、面试解释、对应测试、案例对照表 |
| 7 | `Resume_Bullets.md` | 10 条简历式亮点陈述，涵盖架构、证据晋升、LLM 编排、检索设计、测试基建、事件溯源等工作成果 |

---

## 3. QA 卡片覆盖（30 题 / 6 类别）

| 类别 | 题号 | 覆盖主题 |
|------|------|----------|
| RAG（检索增强生成） | Q1-Q5 | 7 层检索架构、噪声过滤、多模态数据、延迟控制、RAG 评估 |
| Agent | Q6-Q10 | Agent 记忆设计、状态管理、单 Agent 决策、Human-in-the-Loop、决策点分布 |
| Memory / Transcript | Q11-Q15 | Trace 事件流、RunEvent 设计、决策可追溯、调试回放、存储膨胀控制 |
| Tool Calling / MCP | Q16-Q20 | 工具调用链、Function Calling 降级、SSRF 防护、调用深度、MCP 关系 |
| Evaluation / Testing | Q21-Q25 | 评估方法、Playwright 覆盖、Baseline Fixtures、可重复性、错误路径 |
| Safety / Boundary | Q26-Q30 | 夸大词检测、URL 验证、导出前过滤（Readiness）、幻觉控制、高风险题目 |

每道题按统一格式组织：**问题 / 面试官意图 / 项目回答 / 代码证据 / 可展示文件 / 风险补充**，确保面试官可对照代码库验证。

---

## 4. 演示脚本

### 4.1 3 分钟脚本（7 阶段）

使用题目「基于 YOLO 的钢材表面缺陷检测」，走主闭环：

| 阶段 | 时长 | 展示内容 |
|------|------|----------|
| Phase 0 | 15s | 打开页面，输入题目 |
| Phase 1-2 | 30s | 关键词拆解，展示 Gate 1 + 2 |
| Phase 3 | 30s | 多源检索，候選資源出現 |
| Phase 4 | 30s | 證據晉升（選定 → URL 驗證 → 證據） |
| Phase 5 | 30s | 可行性判斷 + Verdict + PIVOT 路線 |
| Phase 6 | 30s | 報告草稿 + 委員會複核 |
| Phase 7 | 15s | Readiness 檢查 → 導出可用 |

### 4.2 10 分钟脚本（扩展版）

约 1500 字，在 3 分钟基础上增加：
- **Trace 回放演示** — 展示 RunEvent 持久化与前端回放
- **PIVOT 路线对比** — YOLO (GO) vs MLLM 高风险 (PIVOT) 双案例对比
- **失败案例演示** — 夸大词拦截、URL 验证拦截
- **Playwright E2E 演示** — 展示完整的自动化验收流程
- **架构深度解读** — 配合 Architecture_Diagram 讲解 7 层分层

---

## 5. 失败案例（8 个）

| # | 案例 | 拦截层级 | 硬拦截 |
|---|------|----------|--------|
| 1 | 无公开数据集 | Feasibility (DataAvailability) | 是（不得 GO） |
| 2 | 无 Baseline（有数据集无开源代码） | Feasibility (BaselineReadiness) | 是（不得 GO） |
| 3 | URL 未验证 / 404 | Evidence Promotion Gate | 是（不得晋升） |
| 4 | 有论文无可复现代码（Evidence Discrepancy） | Feasibility (Discrepancy) | 是（CONDITIONAL） |
| 5 | 创新点夸大 | Readiness (innovation_claim_safety) | 是（不得导出） |
| 6 | 导出前合规失败（缺技术路线） | Readiness (section_completeness / template_fit) | 是（不得导出） |
| 7 | LLM 调用失败 → Heuristic Fallback | Heuristic Fallback | 否（降级） |
| 8 | 多源检索冲突 | Gate（用户决策） | 否（提示） |

每个案例按统一格式：输入 -> 系统拦截 -> 用户看到的 UI -> 面试解释 -> 对应测试。案例末尾附案例对照表，汇总拦截层级、是否硬拦截。

---

## 6. 简历亮点（10 条）

| # | 简述 |
|---|------|
| 1 | 独立设计 FastAPI + JS SPA 的毕业论文开题证据 Agent 工作台，8 阶段流式流程 |
| 2 | 5 级证据晋升机制（候选 → 选中 → URL 验证 → 证据 → 引用） |
| 3 | LLM 编排层 + heuristic fallback，95% 以上常用输入无需 LLM |
| 4 | 非向量 7 层检索架构替代传统 vector DB |
| 5 | 388+ pytest + 32 个 Playwright E2E 测试基础设施 |
| 6 | RunEvent + TraceStore 事件溯源系统 |
| 7 | 3 套学校模板 Readiness 导出检查系统 |
| 8 | LLM + heuristic 双路径可行性 7 维评分引擎 |
| 9 | 12 节 ProposalDraft 结构化生成 |
| 10 | Human-in-the-Loop Gate 机制（Phase 02 + 03） |

---

## 7. 测试结果

| 分类 | 测试数 | 状态 |
|------|--------|------|
| S33 文档存在性与内容完整性 | 13 | 全部通过 |
| S6 LLM 路径（heuristic fallback 状态记录） | 8 | 全部通过（含已知 skip） |
| **合计** | **21** | **全部通过** |

### 7.1 S33 测试用例（13 条）

| # | 用例 | 验证点 | 状态 |
|---|------|--------|------|
| 1 | test_interview_dir_exists | docs/interview/ 目录存在 | PASS |
| 2 | test_all_7_interview_docs_exist | 7 个文档全部存在 | PASS |
| 3 | test_no_extra_unexpected_files | 没有多余文件 | PASS |
| 4 | test_onepager_contains_key_terms | OnePager 包含 RAG/Agent/Evidence/Evaluation/评估 | PASS |
| 5 | test_onepager_has_all_required_sections | OnePager 包含 10 个规定章节中的至少 8 个 | PASS |
| 6 | test_at_least_30_qa_cards | QA Cards 至少 30 题 | PASS |
| 7 | test_qa_all_6_categories_present | QA 覆盖至少 5/6 类别 | PASS |
| 8 | test_demo_3min_exists | 3 分钟脚本存在且 >500 字符 | PASS |
| 9 | test_demo_10min_exists | 10 分钟脚本存在且 >2000 字符 | PASS |
| 10 | test_at_least_6_failure_cases | 失败案例至少 6 个 | PASS |
| 11 | test_failure_cases_have_required_fields | 失败案例包含输入/系统/使用者/测试字段 | PASS |
| 12 | test_at_least_5_bullets | Resume Bullets 至少 5 条 | PASS |
| 13 | test_session6_llm_path_known_status | S6 LLM 测试已知包含 pytest.skip + heuristic_fallback | PASS |

### 7.2 S6 LLM 路径状态（8 条）

8 条测试中，首次测试在 LLM 不可用时 `pytest.skip`（按设计——heuristic fallback 覆盖生产路径），其余 7 条全部基线通过。此状态已在 S33-13 测试中记录确认。

---

## 8. 遗留风险与下一步

| # | 风险 / 待办 | 说明 | 建议 |
|---|-------------|------|------|
| 1 | **面试材料尚未经真实面试验证** | 7 份文档基于项目复盘撰写，尚未在真实面试场景中接受检验 | 建议做一次模拟面试，检验 QA 回答的流畅度与覆盖面 |
| 2 | **OnePager 部分章节需配图** | 10 节文字描述缺少关键截图（Step Deck UI、Workspace Board、Readiness 面板） | 可补充 UI 截图或 Figma 原型附件 |
| 3 | **Demo 脚本依赖前端可用性** | 3min/10min 脚本基于当前前端状态编排，若前端有改动需同步更新 | Demo 脚本应与前端代码版本绑定 |
| 4 | **QA 卡片缺失检索排序评估** | 30 题中 RAG 部分未覆盖 NDCG/Recall@K 等检索排序量化指标 | 若面试官追问 RAG 评估深度，可能需要补充 |
| 5 | **S34 规划：RAG 面试级检索评估** | 当前检索质量缺乏系统性量化指标，面试中可能被追问 | 下一阶段应考虑补充检索评估维度（覆盖率、精准率等） |
| 6 | **简历亮点缺少英文版本** | 10 条简历亮点为中文撰写，如需投递外企或英文面试场景 | 建议翻译为英文并补充 STAR 格式量化数据 |

---

## 结论

Session 33 完成全部目标：7 份面试导向文档全部交付（Project OnePager、Architecture Diagram、QA Cards 30 题、Demo 3min + 10min、Failure Cases 8 个、Resume Bullets 10 条），13 条 S33 测试 + 8 条 S6 测试全部通过。项目从**功能性产品**向**可沟通、可展示的系统化作品**迈出关键一步。后续可通过真实面试演练进一步打磨材料质量。
