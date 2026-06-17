# TopicPilot-CN Agent 化路线 (待补功能 Plan)

> 日期：2026-06-17
> 状态：**简陋版 (placeholder) — 后续用真实 LLM Agent 实现**

---

## 1. 现状

当前 TopicPilot-CN 是"模板化流水线":
- **Phase 01** 用户手工填表 (case_id / 专业 / 学位 / 目标档位 / 题目)
- **Phase 02** heuristic 拆题 (正则扫 8 个高风险词 + 拼 TopicSpec)
- **Phase 03** 规则化 7 层 × ~17 个 query (硬编码)
- **Phase 04** 调 arXiv 拉论文 (基于 Phase 03 query 列表), baseline/dataset 是 placeholder
- **Phase 05-08** 规则 + LLM(M3) 混合

**问题**:
- 用户必须"懂自己的题目"才能填表 (实际痛点: 题目怎么拆开, 关键词怎么选)
- 检索词是模板化的, 不会"针对题目灵活调整"
- baseline / dataset 全是 placeholder "Placeholder-Baseline-1", YOLO 工业缺陷题明明 NEU-DET / GC10-DET / YOLOv5/8 都有, 但 search 没真的用题目关键词去查

---

## 2. 待补功能 1: 选题拆解 Agent (Phase 01 增强)

**目标**: 用户**只输入 1 个原始题目**, Agent 自动:
1. 拆研究对象 / 任务 / 模态 / 方法 / 数据 / 评价
2. 识别 8 个高风险词 (智能 / 高精度 / 端到端 / 大模型 / 通用 / 实时 / 数字孪生 / 多模态)
3. 推 5-8 个**针对该题目的具体关键词** (中英双语)
4. 给 1 段"题目原意理解" (中文)
5. 推**可能缺的研究对象** (自动补 intake_rating 评估)

**简陋版 placeholder** (本工作**不实现**, 仅列计划):
```python
def topic_decompose_agent(raw_topic: str, goal_level: str) -> dict:
    """简陋 LLM 调用 — 后续用 LangGraph 多轮 + 引用 chain"""
    prompt = f"""
    你是一个研究生开题助手. 学生输入: {raw_topic}
    目标档位: {goal_level}
    
    请输出 JSON:
    - research_object: 字符串
    - task: list[str]
    - modality: list[str]
    - method: list[str]
    - data_requirement: list[str]
    - evaluation_metrics: list[str]
    - risk_terms: list[str] (8 个高风险词中匹配到的)
    - suggested_keywords_zh: list[str] (5-8 个针对该题目的中文检索词)
    - suggested_keywords_en: list[str] (5-8 个英文检索词)
    - intent_zh: 字符串 (题目原意 1 段话)
    - missing_objects: list[str] (可能缺的对象)
    """
    return chat_json(...)
```

**触发点**: Phase 01 提交时, 后端先调 `topic_decompose_agent` 拿到 keyword + spec, 存到 `topics.intake_payload` 里, Phase 02-04 直接读。

**待补**:
- LangGraph 多 Agent (Topic Parser + Query Planner + 同义词联想)
- M3 调 3 轮 (生成 / 评审 / 修改)
- 引用强制 (每条关键词必须来自真实论文/课程)
- 不确定性提示 (Agent 不确定时给"建议查 X 数据库" 而非硬编)

---

## 3. 待补功能 2: LLM 检索 Agent (Phase 03/04 增强)

**目标**: 拿到 Phase 02 的 `TopicSpec + keywords` 后, LLM Agent:
1. **文献 Agent**: 根据 method / task / data 抽 5-10 个检索词, 分别打 arXiv / Semantic Scholar / OpenAlex, 取前 N 篇
2. **数据集 Agent**: 根据 data_requirement 抽 3-5 个 dataset name, 优先从 Papers with Code / Hugging Face / kaggle 拉
3. **Baseline Agent**: 根据 method 推 3-5 个候选 baseline 名字, 优先 GitHub 搜 (要求 README + license)
4. **工程模板 Agent**: 找 1 个 thesis_template + 1 个 experiment_template

**简陋版 placeholder** (本工作**不实现**, 仅列计划):
```python
def literature_agent(topic: TopicSpec, max_papers: int = 10) -> list[PaperEvidence]:
    """基于 TopicSpec 智能检索文献 — 简陋版: 直接调 arxiv + LLM 评 relevance"""
    keywords = topic.suggested_keywords_en + topic.method_family
    arxiv_papers = search_arxiv(keywords, max_total=max_papers)
    # LLM 评每篇论文 relevance + 抽 1 句中文简介
    for p in arxiv_papers:
        meta = llm_summarize_paper(p)  # 返回 {relevance, zh_summary, zh_keywords, field}
    return [arxiv_to_paper_evidence(p, meta) for p in arxiv_papers]


def dataset_agent(topic: TopicSpec) -> list[DatasetCandidate]:
    """找 3-5 个真实公开数据集 — 简陋版: LLM 从训练数据里给候选名 + arxiv 搜"""
    candidates = llm_suggest_datasets(topic)  # 调 LLM 给 ["NEU-DET", "GC10-DET", ...]
    return [verify_dataset(name) for name in candidates]


def baseline_agent(topic: TopicSpec) -> list[BaselineCandidate]:
    """找 3-5 个真实 baseline — 简陋版: LLM 给候选 + 查 GitHub API"""
    candidates = llm_suggest_baselines(topic)  # ["YOLOv8", "YOLOv5", "Faster R-CNN", ...]
    return [verify_github(c) for c in candidates]
```

**触发点**: Phase 03/04 heuristic fallback 时调, LLM 失败仍用 placeholder (向后兼容)

**待补**:
- 真接 OpenAlex API (250M+ 论文, 比 arxiv 覆盖广)
- 真接 Papers with Code API (历史快照, 不全但 baseline 准)
- 真接 Hugging Face Datasets API
- LLM 评 relevance + 5 维评分 (citation / year / venue / code / dataset)
- 强制 verify (HEAD 一下 GitHub repo, 404 标红)
- 数据集 vs 题目匹配度 (license / scale / 任务类型)

---

## 4. 集成路线 (后续)

**Phase 09: LLM Agent 化**
- 引入 LangGraph 状态机
- 选题拆解 Agent (TopicParser → KeywordExpander → RiskDetector → IntentWriter)
- 每个 Agent 跑 3 轮 (生成 / 评审 / 修改)
- evidence_chain 引用强制 (每条建议必须来自真实论文 ID)

**Phase 10: 多源检索**
- OpenAlex (文献主源)
- Papers with Code (baseline 主源)
- Hugging Face Datasets (数据集主源)
- GitHub API (代码主源)
- LLM 只负责"合成 + 评审", 不"瞎编"

**Phase 11: Trace 增强**
- 每条建议的 evidence_chain (论文 → 数据集 → baseline → 引用) 可视化
- "我为什么推荐 YOLOv8" 的推理链 (用户能看)

**Phase 12: 端到端 LLM 循环**
- "题目不确定" → Agent 跑 5 轮, 用户选 1 个 Pivot → 重新检索
- 真实"导师 vs 学生"模拟 (不同 prompt 角色)

---

## 5. 与现有架构的兼容性

- `TopicSpec` / `EvidenceLedger` / `RiskScore` Pydantic 模型不动, 只新增字段:
  - `TopicSpec.intent_zh: str | None = None`
  - `TopicSpec.suggested_keywords_zh: list[str] = []`
  - `TopicSpec.suggested_keywords_en: list[str] = []`
  - `PaperEvidence.relevance_score: float = 0.0` (LLM 评)
  - `PaperEvidence.zh_summary: str | None = None` (LLM 翻译)
  - `PaperEvidence.zh_keywords: list[str] = []` (LLM 翻译)
- Heuristic fallback 保留 (LLM 挂掉仍能跑通)
- 现有 8 phase 端点不动, 只在内部用 LLM 替换 placeholder

---

## 6. 验收标准 (Phase 09 完工时)

- 用户输入 1 行题目, 30s 内拿到:
  - 结构化 TopicSpec
  - 5-10 个真 arXiv 论文 (≥80% 相关, 标 relevance_score)
  - 3-5 个真公开数据集 (NEU-DET / GC10-DET / COCO 等)
  - 3-5 个真 baseline (YOLOv8 / Faster R-CNN / DETR 等带 GitHub)
- LLM 失败时仍能用 heuristic (退路 100% 跑通)
- 每条建议有可追溯的 evidence chain (用户能点开看来源)
