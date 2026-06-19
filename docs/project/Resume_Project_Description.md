# 简历项目描述 (Resume Project Description)

> 三种长度版本：**一句话 / 简历项目 / 面试展开**。
> 强调点：FastAPI + Pydantic v2 证据工作台 / 多源检索 / URL Verified / Trace / ReportQuality / Skill Registry / 资料卡片化 / 测试闭环。

---

## 一句话版本（≤ 60 字）

> TopicPilot-CN：中国研究生开题证据工作台，FastAPI + 多源检索 + URL 验证 + 资料卡片化 + Trace 持久化，覆盖主闭环 184 后端测试 + Playwright 主路径验收。

---

## 简历项目版本（3-5 行）

> **PaperAgent (TopicPilot-CN) — 交互式证据工作台** | FastAPI / Pydantic v2 / Playwright
>
> - 设计“输入题目 → 关键词拆解 → 多源检索 → 证据审核 → 开题报告”主闭环，支撑中国研究生开题选题场景；
> - 实现双栏证据工作台（user_preferred / system_found）、多源轻验证（OpenAlex / arXiv / GitHub / HuggingFace）、资料卡片化（PDF / 图片 / 网页 / 备注 → DraftEvidenceCard → Evidence Ledger）；
> - 内置 Trace JSONL 持久化与回放、报告质量 8 维审核、内部 Skill Registry、FinalPackage Markdown 报告生成；
> - 严格约束：`rejected 不引用 / pending 不直接 supports / failed verification 不 supports`；
> - 测试覆盖：后端 184 passed + 1 skipped，Playwright 主路径 59 passed，新增 Session 10 passed。

---

## 面试展开版本（项目介绍 + 难点 + 收获）

### 项目背景

中国研究生开题阶段，学生往往面对“题目能不能做、相关论文/数据集/Baseline 有没有、可行性如何”的多重不确定。TopicPilot-CN 把这个过程从“导师一句一句答疑”转成**显式证据链**：

- 用户只输入一个题目 + 目标档位（保毕业 / 稳中求新 / 冲高水平）；
- 系统自动拆关键词、做三线检索（论文 / 数据集 / GitHub）、给可行性五档（可做 / 收缩后可做 / 可转向 / 暂缓 / 不建议）；
- 用户在工作台里把候选证据**手动审核 / 移动 / 拒绝**，每条证据都带来源、解析置信度、URL 验证状态。

### 核心难点

1. **多源数据融合 + 严格 supports 规则**
   - 论文/数据集/GitHub/笔记四类证据统一为 `EvidenceItem`，但字段差异大；
   - 强约束：rejected / pending / failed verification 不得进入 `supports`，否则会污染报告；
   - 用 Pydantic v2 + `Literal` 类型枚举 + 工作台 lane 状态机解决。

2. **多源轻验证 + 离线兜底**
   - 论文走 arXiv + OpenAlex，仓库走 GitHub API，数据集走 HuggingFace；
   - 网络抖动时不能挂掉 → 所有外部调用都包 `try/except` + heuristic fallback；
   - 验证结果写入 `verification_status / verification_confidence / verification_source`，
     FinalPackage 引用表格直接展示给用户。

3. **资料卡片化的边界**
   - PDF / 图片 / 网页 / 备注 5 种入口，统一生成 `DraftEvidenceCard`；
   - PDF 用 pypdf 抽文本 + DOI/arxiv 正则；图片**不做 OCR**（明确边界）；
   - 卡片进入 Evidence Ledger 默认 `pending`，需用户确认。

4. **Trace 持久化与回放**
   - 每次 evidence 移动、verification 完成、material 上传、draft import 都写一条 trace；
   - `.runtime/traces/{project_id}.jsonl` 持久化，UI 提供 timeline；
   - FinalPackage 报告头部展示关键决策记录。

5. **ReportQuality 8 维审核**
   - 覆盖 coverage / verification / provenance / skill_sources / contradictions / unsupported_claims / trace_consistency / format；
   - 给出 verdict（PASS / WARN / FAIL）和 defense_questions，帮用户自查开题报告薄弱点。

### 关键能力

- **Pydantic v2 模型**：`OneTopicRequest / EvidenceItem / EvidenceRef / MaterialItem / DraftEvidenceCard / ReportCitation` 等
  20+ 模型贯穿 API + 前端。
- **FastAPI 路由**：单一 `one_topic.py` 串起 `/analyze /evidence /workspace /retrieval /materials /final-package /report/review /trace /skills`。
- **内部 Skill Registry**：`skills/registry.json` 注册 4 个内部 skill
  (`paper-card / dataset-validation / github-baseline / evidence-ledger`)，所有 AI 操作记录 `created_by_skill / scored_by_skill / validated_by_skill`，形成证据溯源链。
- **测试闭环**：pytest + Playwright 双层；后端单测覆盖 schemas + 服务层，Playwright 覆盖主路径 UI。

### 测试与质量

- 后端 184 passed, 1 skipped（含 Session 01-15）；
- Playwright 主路径 59 passed；
- 测试矩阵详见 [Test_Matrix.md](../testing/Test_Matrix.md)；
- `.runtime/` 留 trace / materials / retrieval 中间产物，便于复盘。

### 收获

- 学会**用类型 + 状态机约束领域规则**，而不是依赖运行期检查；
- 在“多源数据 + LLM + 用户输入”混合场景下，**优先设计降级路径**而不是只追求 happy path；
- 理解**作品化 ≠ 堆功能**：Session 16 主动停手做收束，把项目整理成可读、可跑、可复盘的作品。

### 可继续展开的方向（面试备问）

- Session 17 候选：Demo 数据固化与回归基线；
- 未来可能方向：全文 chunk 检索（待评估）、多 Agent 复核（仅当用户主动开启）。