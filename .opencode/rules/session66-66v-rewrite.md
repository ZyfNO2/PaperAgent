# Session66 / S66v 智能体重写强约束 (对话固化)

> 本规则由用户在 S66 + S66v 系列会话中**逐条口述**，与 `CLAUDE.md` 同级强制加载。
> 起草日：2026-07-01。 适用范围：所有 S66* session。

---

## 0. 方向校准 (最重要)

1. **你编写的是 agent，不是搜索引擎**。  
   工具调用、智能体范式、提示词 必须先到位，分数系统 / 启发式打分器是**冗余脏逻辑**，要全部删掉。
2. **agent 的产物要"像科研 skill 跑出来的"** —— 用户目标产物是 11 项里命中 ≥80%。不准走"标题里出现某关键词就 keep"这种泄题后处理。
3. **学术诚信红线** —— 严禁:
   - 把标的论文标题 / repo 名 / 数据集名写进 `query_atoms_en` / prompts / 任何文件
   - 后处理 `if "ShipsEar" in title: keep`
   - 把内存里的"已搜到结果 ID"塞进 inputs 给 LLM
4. **主力测试模型**: MiniMax M3（写在 `.env`，全局 `MINIMAX_MODEL=MiniMax-M3`）。

---

## 1. 已经废除 (Legcy)

旧的 7-step 串行流水线 (`research_planner_agent.topic_understand → problem_decompose → search_strategy_build → collect → screen → assemble → direction_advice`) 与其所有子模块（`candidate_cleaner`、`literature_role_classifier`、`research_skill_bridge`、`research_query_builder`、`research_query_expander`、`research_baselines.py`、`research_datasets.py`、`agent_router.py`）被标 **Legcy**：

- 不再在 `tool_orchestrator` 中作为执行路径
- 文件保留以便回看，但**不许新增功能**
- 新实现写到 `apps/api/app/services/agents/` 目录下，与旧模块物理隔离
- 标 Legcy 的入口（`topic_research_flow.py`、`one_topic.py`）保留对外接口，仅路由到新 agent

### Legcy 文件路径

```
apps/api/app/services/research_planner_agent.py
apps/api/app/services/research_skill_bridge.py
apps/api/app/services/research_topic_parser.py
apps/api/app/services/research_prompts.py
apps/api/app/services/research_prompts_v2.py
apps/api/app/services/research_query_builder.py
apps/api/app/services/research_query_expander.py
apps/api/app/services/research_baselines.py
apps/api/app/services/research_datasets.py
apps/api/app/services/agent_router.py
apps/api/app/services/retrieval/candidate_cleaner.py
apps/api/app/services/retrieval/literature_role_classifier.py
apps/api/app/services/retrieval/tool_orchestrator.py
apps/api/app/services/topic_research_flow.py
```

---

## 2. 复刻目标:学术 skill + ARC 的"强度"

### 2.1 学术 skill 骨架 (academic-research-skills v3.9.2)

- **academic-paper 8 phase**: CONFIG → RESEARCH → ARCHITECTURE → ARGUMENTATION → DRAFTING → CITATIONS+ABSTRACT → PEER REVIEW → FORMAT
- **deep-research 6 phase**: SCOPING (RQ + Methodology + Devil's Advocate) → INVESTIGATION (Biblio + verification) → ANALYSIS (Synthesis + Gap + DA) → COMPOSITION → REVIEW (Editor + Ethics + DA) → REVISION
- **关键不变量**:
  - IRON RULE: every claim needs citation (灰区 = FAIL)
  - Devil's Advocate 3 次强制 checkpoint
  - Source-verification 等级 (Tier 1 peer-reviewed > preprint > gray lit)
  - Socratic integrity (问真问题，不替答)

### 2.2 AutoResearchClaw 范式 (23-stage pipeline)

- 8 个 phase 下的 23 stage
- 3 个 gate stage (Stage 5/9/20) 需要人复核
- LLM 失败自动 retry 3 次 + 切 simulated
- **配置驱动而非代码驱动** (config.arc.yaml)

### 2.3 落到 PaperAgent 的精简目标

新 agent 必须至少做到：

1. **ReAct loop** (Thought → Tool call → Observation → 下一轮 Thought)
2. **6 个工具** (legcy 7 个中保留真正有效的):
   - `arxiv_search(query)` — 用 query 模式 `/abs/{id}` + `?search_query=ti:...`, sortBy=relevance
   - `crossref_search(query)` — 短自然语言 + `rows<=20`
   - `openalex_search(query, per_page, filter)` — `search+filter=type:article`
   - `github_search(query, language, min_stars)` — 不带 `github pytorch implementation` 这类噪音词
   - `paperswithcode_search(query)` — 真实走 code 任务页或诚实返回空，**禁止假白名单**
   - `dataset_web_search(topic_en, domain)` — 同上
3. **3 个 LLM 调用** (legcy 当前 5-6 个太碎):
   - `parse_topic` 一次: 产出 domain_route + method/task/object terms + query_atoms_en (≤6 个具体词) + query_atoms_zh (≤6 个)
   - `synthesize` 一次: 输入 = `[(tool_name, candidates[], context)]`, 输出 = 7-bucket 分栏 JSON, follow academic-paper `report_compiler_agent` 的 contract
   - `devils_advocate` 一次 (checkpoint): 对 synthesize 的输出做反方质疑并修订
4. **零评分器** — 不存在 `retrieval_score`、`quality_score`、`relevance_score` 字段。
5. **零 hardcoded 候选目录** — 静态 baseline/dataset 目录全部删掉；agent 必须现场从工具拿证据
6. **Deterministic query building** — `_pick_atoms(topic_parse)` 给出 6 个具体搜索词（来自 LLM parse 的输出），不准再用 `research_query_expander.expand_topic`

---

## 3. 流程铁律 (S66 智能体 path)

### 3.1 Step 1: parse_topic
LLM 一次出 domain_route / method_terms / task_terms / object_terms / query_atoms_en (≤6 个) / query_atoms_zh (≤6 个)。

失败 → heuristic_rules 兜底 (基于关键字的硬分类，不是打分)，但**不允许**用 `if-else` 拼接 query。

### 3.2 Step 2: plan_tools
输入 = Step 1 的 query_atoms_en。  
LLM 一次产出 ≤6 个 ToolCall，每个 ToolCall 写明 tool / target (=paper / repo / dataset) / query (从 atoms 选 1-3 个拼接) / max_results / rationale。

输出形如 ReAct 的 "Action plan"。

### 3.3 Step 3: execute_tools (ReAct loop)
- 同时发 ≤6 个 ToolCall，async 抓回 raw candidates
- 每个 tool 返回 `[{title, url, year, venue, authors, abstract, source_id}]` 统一 schema
- OpenAlex 限流 (429) → 立刻切到 Crossref（circuit breaker）
- arXiv XML 解析失败 → 记录并继续，不让全体挂掉

### 3.4 Step 4: synthesize (LLM)
**输入**: `(raw_topic, plan, tool_results[])`

**输出** 严格照搬 academic-paper `report_compiler_agent` 的 contract: 7-bucket dict：
```
{
  "reference_papers": [{"title", "url", "why_relevant", "citation_key"}],  # ≤8
  "baseline_candidates": [{"title", "url", "repo", "why_baseline"}],       # ≤5
  "parallel_reference_papers": [{"title", "url", "parallel_axis"}],        # ≤5
  "module_reference_papers": [{"title", "url", "module_focus"}],           # ≤5
  "dataset_candidates": [{"name", "url", "license", "scale"}],             # ≤5
  "repo_candidates": [{"name", "url", "language", "stars"}],              # ≤5
  "evidence_gaps": [str]                                                   # ≤5
}
```

强制:
- 每条 paper 必须有 title **真的来自 tool_results** (硬约束)
- 不知道就 `evidence_gaps.append(...)` 不准猜
- `"auto_generated" in citation_key` 不准出现

### 3.5 Step 5: devils_advocate (LLM)
输入 synthesize 的输出 + tool_results 全文  
输出 revised_7_bucket + 风险标签

### 3.6 Step 6: STOP

---

## 4. 输出不变式 (follow academic-research-skills)

1. **Every claim has a citation** —— 7 个 bucket 里每条都得能链回 raw tool candidate
2. **No fabrication** —— 找不到就说 gap，不准凭空写
3. **Bilingual topic retrieval** —— 中文题目时 query_atoms_en 必须真有英文
4. **Listing transparency** —— 7 个 bucket + gaps 必出
5. **Atomic commit per task** —— 每个 Step 一个 commit，不混多个 Step

---

## 5. 验收 (反向对齐 ground truth)

### 5.1 Ground truth 来源 (S66)

用户给的 Topic 59 (水声) ground truth：

- baseline (2): "A Spatio-temporal Deep Learning…", "An Investigation of Preprocessing Filters…"
- parallel (3): "Cross-Domain Knowledge Transfer…", "Underwater Acoustic Target Recognition based on Smoothness-inducing…", "Underwater Acoustic Target Recognition on ShipsEar Dataset"
- datasets (3): DeepShip, ShipsEar, SonAIr
- repos (3): zakaria76al/USC, lucascesarfd/underwater_snd, PANN_Models_DeepShip

### 5.2 验收门槛

3 题 (53 / 55 / 59) 各跑一次，每个题的 11 项目标 ≥80% 命中，且:
- 不准用 keyword substring 在后处理里"作弊"
- 没真命中的项必须落到 `evidence_gaps`

### 5.3 步骤约束

- 一步一步来：先看每一步的**输出 + 工具调用是否合理**，再继续下一步
- 撞墙 → 翻 `C:/Users/ZYF/Desktop/Paper/academic-research-skills/` 找范式，**绝不**回去加阈值
- MiniMax 配额不够 → 切 DeepSeek 作为次选，但 S66 默认走 MiniMax

---

## 6. 文件落地

- 新 agent: `apps/api/app/services/agents/` 目录
- 与旧的 legcy 路径**物理隔离**
- 新 agent 不引旧模块（最多引 `services/llm.py` 和 `services/retrieval/adapters/*.py` 的纯函数）
- 新 prompts: `apps/api/app/services/agents/prompts/`

---

## 7. 一次性心智转换

| 旧 legcy | 新 agent |
|---|---|
| 5-6 次 LLM 调用 | 3 次 LLM |
| 数字评分器 (`retrieval_score`, `quality_score`) | 全部删除 |
| 静态 baseline / dataset 目录 | 全部删除 |
| 硬规则 `if X in title: keep` | 全部删除 |
| 7 步顺序函数 | ReAct loop + 7-bucket synthesize + Devil's Advocate |
| 假白名单 `search_dataset_web / paperswithcode` | 删除假实现，写真调用（或者诚实返回空） |
| 加阈值 `if score < 0.2 reject` | LLM synthesize 自己看 |

---

## 8. 跟 CLAUDE.md 已有约束的关系

- 测试 + 子 agent + 截图规范: **沿用**
- `MINIMAX_*` 凭据 + `.env`: **沿用**
- 阶段开发流程: 继续按 Phase 编号，但本会话从 `Phase 66v` 开始
- 前端交互契约: 与本会话**无关**，继续按上一节
- S62 方向生成 LLM-first 强约束: 在 53/55 的方向生成步骤上**继续沿用**

---

## 9. 跟用户对话风格的微调

- 用户偏好逐步、可视化，先看每一步的真实输出再优化
- 用户嫌"评分系统"，请**不再新增任何 `*_score` 字段**
- 用户要"我自己也能复刻这个 skill"——你的代码必须**可读 + 可追源**，prompt 必须能让用户在不读代码的前提下复述意图
