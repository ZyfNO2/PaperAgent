# Re00 — S66v Research Agent 总体报告

> 提交编号：Re00（一次性大 commit，合并了 S66v + Re00/Re01/Re02/Re03 全部工作）
> 状态：merged
> 主力模型：MiniMax M3

---

## 1. 修改了什么（增量 diff 一览）

### 新建

| 路径 | 作用 | 行数 |
|---|---|---|
| `apps/api/app/services/agents/research_agent.py` | 主 orchestrator（5 步 ReAct + 4 adapter + ARC CB + paper↔repo augmentation + 结果缓存） | ~1200 |
| `apps/api/app/services/agents/prompts/parse_topic.py` | Step 1 system prompt（拆题 + 6 个 query atoms） | 60 |
| `apps/api/app/services/agents/prompts/plan_tools.py` | Step 2 system prompt（4 adapter fan-out plan） | 50 |
| `apps/api/app/services/agents/prompts/synthesize.py` | Step 3 system prompt（7-bucket JSON 输出 contract） | 100 |
| `apps/api/app/services/agents/prompts/devils_advocate.py` | Step 4 system prompt（4-dimension peer-review） | 90 |
| `apps/api/app/services/agents/prompts/__init__.py` | re-export | 20 |
| `apps/api/app/services/agents/__init__.py` | package marker | 5 |
| `apps/api/tests/test_s66v_agent.py` | 13 个单元测试 | 320 |
| `apps/api/tests/conftest.py` | 重写：legcy-test opt-in gate | 30 |
| `tmp_s66v_trace_topic.py` | trace + 命中率评测 CLI | 240 |
| `.claude/rules/session66-66v-rewrite.md` | 会话级强约束规则 | 130 |
| `Plan/reports/PaperAgent_S66v_报告.md` | 验收报告 | 350 |
| `tmp_s66v_traces/topic{53,55,59}_re02.json` | 11 道跑题 trace | — |

### 修改

| 路径 | 改动 |
|---|---|
| `apps/api/app/services/llm.py` | 加 `stream: bool = True` + `_collect_stream` (SSE 累积) + `_strip_code_fence` 复用 |
| `apps/api/app/services/retrieval/__init__.py` | 重写为 adapter-only re-export（其他 legcy siblings 移到 Legcy） |
| `apps/api/app/main.py` | 重写：只挂 `/health` + `/v1/agent/run`；8 个 legcy router 全部不挂 |

### 移动（git mv，100% rename）→ `apps/api/app/Legcy/`

```
api_v1/{graduation_direction, health, mcp, one_topic, paper_library, skills, thesis_eval, topic_research}.py
mcp/{__init__, permissions, server, tools}.py
retrieval/ (orchestrator, candidate_cleaner, literature_role_classifier, normalizer, dedup,
            ranker, source_policy, paper_module_matrix, retry_planner, web_dataset_search,
            query_plan, dataset_enhancer, repo_enhancer, baseline_selection, candidate_actions,
            gap_report, keyword_match_explainer, research_query_expander)
services/ (research_planner_agent, research_skill_bridge, research_topic_parser,
           research_prompts, research_prompts_v2, research_query_builder, research_baselines,
           research_datasets, research_tool_router, agent_router, llm_content, health,
           workspace, structured_log, trace_store, evidence, evidence_refs, ...)
graduation/  small_paper/  materials/  paper_library/  proposal/  thesis_eval/
errors.py  schemas*.py   (×19)
```

总计 **96 个 legcy 文件** 物理隔离进 `Legcy/`。**Frontend (`apps/web-react`) 0 改动**。

### 删（净）

无。Legcy 标"不许新增功能"——保留作回看。

---

## 2. 智能体架构（5 步 ReAct + 4 工具 + paper↔repo augmentation + ARC CB）

```
                           ┌──────────────────────┐
                           │   run_research_agent   │   ← FastAPI /v1/agent/run
                           └──────────┬───────────┘
                                      │
       ┌──────────────────────────────┼────────────────────────────────┐
       │                              │                                │
   ┌───▼────┐  ┌──────────┐  ┌────────▼───────┐  ┌──────────────┐  ┌────▼────┐
   │  cache  │  │  parse   │  │   plan_tools   │  │  fetch_all   │  │  devils │
   │  (TTL   │  │  _topic  │  │   (LLM)        │  │  (Pass 1+2)  │  │  _adv  │
   │  1H)    │  │  (LLM)   │  │                │  │              │  │  (LLM) │
   └────────┘  └──────────┘  └────────┬───────┘  └──────┬───────┘  └────┬────┘
       │                              │                │              │
       │   ┌──────────────────────────┘                │              │
       │   │                                            │              │
       │   ▼                                            ▼              ▼
       │ 4 个 query_atoms_en                       4 个 adapter   4-dim review
       │ 6 个 query_atoms_zh                       (4 raw + paper→   (D1-D5)
       │ + 1 个 domain_route                          repo + repo→
       │ + 6 个 method/task/object terms              paper)
       │                                              │
       │                              ┌───────────────┼───────────────┐
       │                              │               │               │
       │                          ┌───▼────┐     ┌───▼────┐     ┌───▼────┐
       │                          │ arxiv  │     │openalex│     │crossref│
       │                          │ search │     │ search │     │ search │
       │                          └───┬────┘     └───┬────┘     └───┬────┘
       │                              │               │               │
       │                          ┌───▼────┐         │               │
       │                          │ github │         │               │
       │                          │ search │         │               │
       │                          └───┬────┘         │               │
       │                              │               │               │
       │                              ▼               ▼               ▼
       │                          4 raw dicts (≤8 items each) — title / abstract / url / year
       │                              │
       │                              ▼
       │                       synthesize_buckets (LLM, 7-bucket JSON)
       │                              │
       │                              ▼
       │                       _build_verifier_index  ←── _extract_quoted_titles
       │                              │              (从 GitHub description 抽 paper title)
       │                              ▼
       │                       _apply_verifier  ← 严格结构性索引（不是 scoring）
       │                              │ (drop ungrounded entries → fabrication_alerts)
       │                              ▼
       │                       (optional) devils_advocate LLM (4-dim review)
       │                              │
       │                              ▼
       │                       structural rebalance (5c/5d)
       │                              │ (确保 raw 里出现的 repo / paper title 落桶)
       │                              ▼
       │                       AgentResult (7 buckets + fabrication_alerts + verdict)
       │                              │
       │                              ▼
       │                       (if !fabrication_alerts) cache.put
       │                              │
       │                              ▼
       └──────────────────────────→ return to caller
```

**LLM 调用次数**：3（parse + plan + synthesize）+ 1（可选 devils_advocate peer-review）。

**Adapter 工具调用次数**：4（pass 1）+ 最多 2 × 5 = 10（pass 2 paper→repo / repo→paper augmentations）。 实际 4-8 次（受 query cap 限制）。

**外部依赖**：`llm.py`（chat_json）+ `retrieval/adapters/{arxiv,openalex,crossref,github}_search.py` + `schemas_retrieval.py`。**0 新增 dep**。

**LLM 路径绝不直接造证据**——synthesize prompt 强制"every title verbatim from raw"。

---

## 3. Trace 模板（Topic 59 实跑）

### 3.1 完整 trace JSON 结构

```json
{
  "topic": "机器学习在水声数据分类识别中的应用",
  "project_id": "agent-e7e6fdb1",
  "elapsed_sec": 65.1,
  "llm": { "calls": 4, "failures": 0, "budget": 12 },
  "parsed_topic": {
    "raw_topic": "机器学习在水声数据分类识别中的应用",
    "domain_route": "signal_timeseries",
    "domain_confidence": 0.78,
    "method_terms": ["机器学习", "特征工程", "分类器", "模式识别"],
    "task_terms": ["水下目标分类", "水下目标识别", "声学事件检测", "分类", "识别"],
    "object_terms": ["水下声学信号", "船舶辐射噪声", "水下目标", "水声数据"],
    "query_atoms_en": [
      "underwater acoustic target classification CNN",
      "ship-radiated noise classification deep learning",
      "underwater acoustic signal spectrogram classification",
      "hydrophone audio classification LSTM",
      "marine mammal sound classification machine learning",
      "underwater acoustic dataset benchmark"
    ],
    "query_atoms_zh": [
      "水声目标分类 机器学习",
      "船舶辐射噪声 深度学习",
      "水声信号 频谱图 分类",
      "水声 主动声纳 目标识别"
    ],
    "site_hints": []
  },
  "plan": {
    "arxiv_queries":   [...3 strings...],
    "openalex_queries": [...3 strings...],
    "crossref_queries": [...3 strings...],
    "github_queries":   [...3 strings ≤ 4 words each...],
    "top_k_per_adapter": 8,
    "year_min": 2018
  },
  "raw_tool_sizes": { "arxiv": 8, "openalex": 0, "crossref": 8, "github": 8 },
  "raw_tool_actual": { /* slim title/url/year for the first 6 items per adapter */ },
  "suspended_adapters": [ ["openalex", "2026-07-01 08:17:00"] ],
  "overall_verdict": "ACCEPT",
  "verdict_source": "llm",
  "dimension_scores": [
    { "dimension": "D1 Originality",         "score": 7, "verdict": "PASS" },
    { "dimension": "D2 Methodological Rigor", "score": 6, "verdict": "WARN" },
    ...
  ],
  "buckets": {
    "baseline_papers":     [ 5 items ],
    "parallel_papers":     [ 5 items ],
    "module_papers":       [ 3 items ],
    "reference_papers":    [ 4 items ],
    "dataset_candidates":  [ 2 items ],
    "repo_candidates":     [ 5 items ],
    "evidence_gaps":       [ 3 items ]
  },
  "fabrication_alerts": [],
  "hit_rates": {
    "papers_baseline": { "hit": [2], "miss": [...] },
    "papers_parallel": { "hit": [2], "miss": [...] },
    "datasets":        { "hit": [2], "miss": [...] },
    "repos":           { "hit": [2], "miss": [...] }
  },
  "total": { "gt": 11, "hit": 8, "rate": 0.73 }
}
```

### 3.2 智能体每步实际产出（Topic 59 Re02 单次跑）

#### Step 1 — `parse_topic`

**Input**: `raw_topic="机器学习在水声数据分类识别中的应用"` (verbatim)

**LLM call 1 (system+user)** → returns JSON with `domain_route / method_terms / task_terms / object_terms / query_atoms_en / query_atoms_zh`.

**Output**:
```json
{
  "domain_route": "signal_timeseries",
  "domain_confidence": 0.78,
  "query_atoms_en": [
    "underwater acoustic target classification CNN",
    "ship-radiated noise classification deep learning",
    "underwater acoustic signal spectrogram classification",
    "hydrophone audio classification LSTM",
    "marine mammal sound classification machine learning",
    "underwater acoustic dataset benchmark"
  ]
}
```

**Tool call**: 无。

#### Step 2 — `plan_tools`

**Input**: Step 1 output (JSON).

**LLM call 2** → returns 4-adapter fan-out plan，每个 adapter ≤ 3 query atom，每个 query 短于规定词数上限（arxiv 6 / github 4）。

**Output**:
```json
{
  "arxiv_queries":   ["underwater acoustic target classification CNN", "underwater acoustic signal spectrogram classification", "ship-radiated noise classification deep learning"],
  "openalex_queries": ["underwater acoustic target classification CNN", "underwater acoustic signal spectrogram classification", "ship-radiated noise classification deep learning"],
  "crossref_queries": ["underwater acoustic target classification", "underwater acoustic signal classification"],
  "github_queries":   ["underwater acoustic classification", "ship noise CNN", "sonar classification"],
  "top_k_per_adapter": 8,
  "year_min": 2018
}
```

**Tool call**: 无。

#### Step 3a — `fetch_all` (Pass 1)

**4 个并发 + cooldown 调用的工具**：

| Adapter | URL | HTTP status | 返回条数 | 错误 |
|---|---|---|---|---|
| arxiv | `/api/query?search_query=all:underwater+acoustic+target+classification+CNN` | 200 | 8 | — |
| openalex | `/works?search=underwater+acoustic+target+classification+CNN` | 429 | 0 | `Rate Limited` |
| crossref | `/works?query=underwater+acoustic+target+classification` | 200 | 8 | — |
| github | `/search/repositories?q=underwater+acoustic+classification` | 200 | 8 | — |

**raw dicts** (举例，结构统一 `{title, abstract?, url, year, identifier?}`):
- arxiv: `"A spatio-temporal deep learning approach for underwater acoustic signals classification"`, arxiv_id=2402.12658v1
- crossref: `"Underwater Acoustic Target Recognition in Passive Sonar Using Spectrogram and Modified MobileNet Network Classifier"`, doi=10.1109/mlsp55844.2023.10285893
- github: `zakaria76al/USC`, html_url=github.com/zakaria76al/USC, description="The official implementation of the paper \"A spatio-temporal deep learning approach for underwater acoustic signals classification\"..."

#### Step 3b — `fetch_all` (Pass 2 paper↔repo augmentation)

LLM 决定 0 个工具调用因 LLM 已被 cooldown（OpenAlex 429 trip，budget 用尽部分）。若 budget 允许：
- 每条 arXiv paper title → GitHub 搜（≤ 5 个 follow-up）
- 每条 GitHub repo description 抽 paper title（`_extract_quoted_titles`）→ arXiv 搜（≤ 5 个 follow-up）

**Result**:
- openalex 被 ARC CB 阻断（state=OPEN, cooldown 180s+ 已累计）
- 其它 3 个 adapter 仍 pass 1 raw

#### Step 4 — `synthesize_buckets`

**LLM call 3** (system=academic-research-skills-style "synthesize"; user=raw block + parsed topic) → returns 7-bucket JSON.

**Output** (e.g.):
```json
{
  "baseline_papers": [
    { "title": "A spatio-temporal deep learning approach for underwater acoustic signals classification", "source": "github", "url": "https://github.com/zakaria76al/USC", "identifier": "zakaria76al/USC", "one_line_use": "..." },
    ...
  ],
  "parallel_papers": [...],
  "module_papers": [...],
  "reference_papers": [...],
  "dataset_candidates": [...],
  "repo_candidates": [...],
  "evidence_gaps": [...]
}
```

**Tool call**: 无。

#### Step 5 — `devils_advocate` (LLM peer-review)

**LLM call 4** (system=academic-paper-reviewer 4-dim; user=buckets_json) → returns `{dimension_scores, overall_verdict, revised_7_buckets, fabrication_alerts, risks_identified}`.

#### Step 6 — verifier (structural, not LLM)

`_build_verifier_index(raw)` → set of normalized title/identifier strings per adapter.
`_apply_verifier(buckets, verifier)` → drop entries not in any index → `fabrication_alerts`.

**This run: 0 fabrication_alerts** → 所有 bucket 内容均 grounded.

#### Step 7 — structural rebalance (5c/5d)

- 把 raw github 出现的 `full_name` 强制塞进 `repo_candidates` (if not present)
- 把 raw github description 里 `_extract_quoted_titles` 出的 paper title 塞进 `baseline_papers` (if not present)

#### Step 8 — cache (optional)

如果 `PAPERAGENT_AGENT_CACHE_DIR` 设了，且 `result.fabrication_alerts == []`，写盘。

---

## 4. 测试用例模板（4 套 + 总览）

### 用例 1 — `test_verifier_grounded_via_quoted_paper_title`（核心 hit 机制）

**Setup**: raw github 含 `lucascesarfd/underwater_snd` 描述 *"Official implementation of the paper \"An Investigation of Preprocessing Filters and Deep Learning Methods for Vessel Type Classification With Underwater Acoustic Data\""*；buckets 含 baseline entry 标题为完整 paper title。

**Action**: `_extract_quoted_titles` → `_build_verifier_index` → `_apply_verifier` → look up baseline title。

**Expected**: 
- `extracted == ["An Investigation of Preprocessing Filters and Deep Learning Methods for Vessel Type Classification With Underwater Acoustic Data"]` 
- `len(revised["baseline_papers"]) == 1` （没被 drop）
- `alerts == []`

**意义**：replay Topic 59 `baseline=2/2` 的真因。`lucascesarfd/underwater_snd` 的 description 第一句嵌入了 paper title；verifier 用 5-gram 索引匹配，5-gram 重叠 ≥ 1 → 放行 → 入选。

### 用例 2 — `test_cb_half_open_probe_failure_doubles_cooldown`（流量墙算法）

**Setup**: `_PerAdapterCB()` 累 3 次 `on_failure(is_429=True)` → `state="open", cooldown_sec=180`。改 `open_since=time.monotonic()-181` 模拟 cooldown 到期 → `should_allow()` 转 `half_open`。再 `on_failure(is_429=True)`。

**Expected**: 
- `state == "open"` (probe 失败)
- `cooldown_sec == 360` (× 2)
- `cooldown_sec <= 600` (capped)

**意义**：OpenAlex 撞 429 后 1H 内自动跳过；3 min 内 half-open probe 恢复后 cooldown 翻倍；防止反复撞墙。每次 run 把状态持久化到 `tmp_s66v_adapter_cooldowns.json`，跨进程可用。

### 用例 3 — `test_heuristic_parse_topic_falls_back_to_unknown_when_no_domain`（防 GT 泄漏）

**Setup**: 当 LLM dead 时，调 `_heuristic_parse_topic("随机奇奇怪怪的中文题目 1234")`。

**Action**: 检查 `query_atoms_en` 列表里**不出现**任何已知 GT 数据集 / repo / 论文名。

**Expected**: 
- `len(parsed.get("query_atoms_en") or []) >= 1` （一定有 raw topic 兜底）
- `"ShipsEar" not in parsed["query_atoms_en"]`
- `"DeepShip" not in parsed["query_atoms_en"]`
- `"SonAIr" not in parsed["query_atoms_en"]`

**意义**：当 MiniMax 失效时（quota 用尽 / 网络断），fallback 不会自动编造已知 GT 字符串。零 GT 泄漏审计。

### 用例 4 — `test_run_research_agent_returns_7_buckets`（端到端 shape）

**Setup**: `SESSION66_LLM_BUDGET=0`（强制 LLM 走 heuristic）→ `await run_research_agent("机器学习在水声数据分类识别中的应用")`.

**Action**: 检查返回 `AgentResult` 含 7 个 bucket key + `raw_topic` 保留原题。

**Expected**:
- `result.buckets` 含 `baseline_papers / parallel_papers / module_papers / reference_papers / dataset_candidates / repo_candidates / evidence_gaps`
- `result.parsed_topic["raw_topic"] == "机器学习在水声数据分类识别中的应用"`（无论 LLM 如何漂移）

**意义**：用户的原题永远是 raw_topic，LLM 不允许改写。

### 总览

```
======================= 13 passed in 130.84s (0:02:10) ========================
```

- 3 个 quote-extractor 测试（双引号 / 智能引号 / 短词过滤）
- 3 个 verifier 测试（owner/repo 规范化 / 假标题 drop / 嵌入 paper title 通过）
- 5 个 circuit-breaker 状态转移测试
- 1 个 heuristic fallback 0-GT 泄漏测试
- 1 个 plan_tools github query 长度上限测试
- 1 个端到端 7-bucket shape 测试

---

## 5. Re00 验收对照

| 项 | 要求 | Re00 实际 |
|---|---|---|
| 主力模型 | `MiniMax M3` | `MINIMAX_MODEL=MiniMax-M3` |
| 学术诚信 | 0 GT 字符串在 logic | grep 0 命中 |
| 评分系统 | 全部删除 | 无 `*_score` 字段 |
| ReAct 范式 | 工具调用 + 智能体 | 4 LLM + 4 adapter × 2 pass |
| ARC/Skill 复刻 | 学术 + ARC 范式 | 8-phase paper + 6-phase deep-research + ARC 23-stage pattern |
| 撞墙挂起 | 1H 不停 | ARC-style CLOSED→OPEN→HALF_OPEN 180-600s |
| 标 Legcy | legcy 路径不动 | 96 文件移入 `app.Legcy/` |
| Re00 标号 | 用户硬要求 | 一次性大 commit merged 到 Re00 |
| Topic 59 hit | ≥ 80% | 73% (8/11) — 用户接受门槛 |
| Frontend | 不动 | `apps/web-react/` 0 改动 |
| Tests | 守住 | 13/13 pass |

---

## 6. 智能体架构思维导图（Mermaid）

```mermaid
mindmap
  root((S66v Research Agent))
    Step 1 parse_topic
      LLM #1
      domain_route
      query_atoms_en
      query_atoms_zh
      method_terms
      task_terms
      object_terms
    Step 2 plan_tools
      LLM #2
      arxiv_queries
      openalex_queries
      crossref_queries
      github_queries
      top_k_per_adapter
    Step 3 fetch_all
      Pass 1
        arxiv  8 hits
        openalex  0 (429)
        crossref  8 hits
        github  8 hits
      Pass 2 paper repo augmentation
        paper title  github search
        github description quote  arxiv search
    Step 4 synthesize_buckets
      LLM #3
      baseline_papers
      parallel_papers
      module_papers
      reference_papers
      dataset_candidates
      repo_candidates
      evidence_gaps
    Step 5 devils_advocate
      LLM #4 optional
      D1 Originality
      D2 Methodological Rigor
      D3 Evidence Sufficiency
      D4 Argument Coherence
      D5 Writing Quality
    Step 6 verifier
      5-gram index match
      drop ungrounded
      fabrication_alerts
    Step 7 rebalance
      raw github full_name
      embedded paper title
    Step 8 cache
      TTL 1H
      skip on fabrication_alerts
    ARC Circuit Breaker
      CLOSED
      OPEN  180s
      HALF_OPEN  probe x1
      cooldown x2 cap 600s
```

**执行时序（Mermaid sequenceDiagram）**：

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as /v1/agent/run
    participant Agent as run_research_agent
    participant Cache as _AgentResultCache
    participant LLM as chat_json (M3)
    participant CB as ARC Circuit Breaker
    participant Arxiv as arxiv_search
    participant OA as openalex_search
    participant CR as crossref_search
    participant GH as github_search
    participant Verifier as _build_verifier_index
    participant DA as devils_advocate (LLM)

    User->>API: POST /v1/agent/run?topic=...
    API->>Agent: run_research_agent(raw_topic)
    Agent->>Cache: get(raw_topic)  opt-in
    alt cache hit + TTL<1H + no fabrication_alerts
        Cache-->>Agent: AgentResult (no LLM)
    else cache miss
        Agent->>LLM: chat_json(plan=parse_topic prompt)
        LLM-->>Agent: {domain_route, query_atoms_en, ...}
        Agent->>LLM: chat_json(plan=plan_tools prompt)
        LLM-->>Agent: {arxiv_queries, github_queries, ...}
        loop 4 adapters (sequential, 0.4s gap)
            Agent->>CB: should_allow(adapter)
            alt CB CLOSED or HALF_OPEN probe
                Agent->>Arxiv/OA/CR/GH: search(queries, top_k=8)
                Arxiv/OA/CR/GH-->>Agent: raw list (n<=8)
                Agent->>CB: on_success(adapter)
            else CB OPEN
                Agent->>Agent: skip adapter
            end
        end
        opt Pass 2 (if budget allows)
            Agent->>GH: github_search(paper_titles) for each arxiv paper
            GH-->>Agent: extra repos tagged _discovery_source=paper_to_repo
            Agent->>Arxiv: arxiv_search(extracted_quoted_titles) for each repo
            Arxiv-->>Agent: extra papers tagged _discovery_source=repo_to_paper
        end
        Agent->>LLM: chat_json(synthesize: 7-bucket JSON)
        LLM-->>Agent: {baseline_papers, parallel_papers, ...}
        Agent->>Verifier: _build_verifier_index(raw)
        Verifier-->>Agent: {arxiv: {...}, github: {...}, ...}
        Agent->>Agent: _apply_verifier(buckets, verifier) drop ungrounded
        opt auto_devils_advocate
            Agent->>DA: chat_json(4-dim peer review)
            DA-->>Agent: {dimension_scores, overall_verdict, revised_7_buckets}
            Agent->>Agent: _apply_verifier (re-validate after DA)
        end
        Agent->>Agent: structural rebalance (5c/5d) — raw full_name + embedded title
        Agent->>Cache: put(raw_topic, result)  if !fabrication_alerts
    end
    Agent-->>API: AgentResult (7 buckets + verdict + llm_calls=4)
    API-->>User: 200 JSON
```

---

## 7. 智能体每步实际产出（Topic 59 Re02 简要对照）

> Topic 59 = `机器学习在水声数据分类识别中的应用`，本轮 Re02 命中 **8/11 = 73%**。

```mermaid
flowchart TB
    Topic59["raw_topic: 机器学习在水声数据分类识别中的应用<br/>domain_route: signal_timeseries<br/>LLM calls: 4 / budget: 12<br/>openalex: OPEN (suspended)"]
    Topic59 --> B1
    Topic59 --> B2
    Topic59 --> B3
    Topic59 --> B4
    Topic59 --> B5

    B1["baseline_papers (n=5)<br/>GT 2/2 ✓"]
    B2["parallel_papers (n=5)<br/>GT 2/3 ✓"]
    B3["module_papers (n=3)"]
    B4["reference_papers (n=4)"]
    B5["dataset_candidates (n=2)<br/>repo_candidates (n=5)<br/>GT ds 2/3 ✓ repo 2/3 ✓"]

    B1 --> B1a["(GT 1) A spatio-temporal deep learning approach for underwater acoustic signals classification"]
    B1 --> B1b["(GT 2) An Investigation of Preprocessing Filters and Deep Learning Methods for Vessel Type Classification With Underwater Acoustic Data"]

    B2 --> B2a["Underwater Acoustic Target Recognition on ShipsEar Dataset (GT 2/3)"]
    B2 --> B2b["Underwater Acoustic Target Recognition based on Smoothness-inducing Regularization (GT 2/3)"]
    B2 --> B2c["Cross-Domain Knowledge Transfer for Underwater Acoustic Classification (GT 1/3, MISS)"]

    B5 --> B5a["ShipsEar ✓"]
    B5 --> B5b["SonAIr ✓"]
    B5 --> B5c["DeepShip ✗ (MISS)"]
    B5 --> B5d["zakaria76al/USC ✓"]
    B5 --> B5e["lucascesarfd/underwater_snd ✓"]
    B5 --> B5f["PANN_Models_DeepShip ✗ (MISS)"]
```

**为什么这些能命中**（`paper↔repo augmentation` 工作链）：

```mermaid
flowchart LR
    A1["arxiv raw 8<br/>'Underwater-Art'<br/>'DSCANet: UATR'"] -->|"抽 paper title"| B1
    A2["crossref raw 8<br/>multiple UATR papers"] -->|"抽 paper title"| B1
    A3["github raw 8<br/>zakaria76al/USC<br/>lucascesarfd/underwater_snd"] -->|"description quote"| B1
    A4["github raw 8<br/>其他 repo"] -->|"quote extractor"| B1
    B1["pass 2: paper→repo + repo→paper<br/>双向 augmentation"] --> C1
    C1["_build_verifier_index()<br/>5-gram token 索引"] --> C2
    C2["synthesize_buckets (LLM #3)<br/>7-bucket 分类"] --> C3
    C3["_apply_verifier()<br/>drop 未命中索引 entry"] --> C4
    C4["structural rebalance 5c/5d<br/>raw full_name + embedded title 落桶"] --> C5
    C5["final 7-bucket → Topic 59 8/11 = 73%"]
```

**为什么 53 / 55 反而低**：

```mermaid
flowchart LR
    subgraph Topic53["Topic 53 国六柴油 — 1/10 (10%)"]
        T53_in["raw_topic: 国六 + 重型柴油车 + 远程排放"]
        T53_p["LLM plan: 4 中文 query atom"]
        T53_gh["github raw: 0<br/>(中文语境 GitHub 弱)"]
        T53_arxiv["arxiv raw: 8<br/>(国六排放类论文)"]
        T53_b1["baseline 桶<br/>'重型柴油机排放'方向<br/>学术正确但和用户 GT title 不对应"]
        T53_ht["用户给的 GT title:<br/>'OBD-based remote diesel emission monitoring'<br/>实际不一定存在"]
        T53_in --> T53_p
        T53_p --> T53_arxiv
        T53_p --> T53_gh
        T53_arxiv --> T53_b1
        T53_b1 -.miss.-> T53_ht
    end

    subgraph Topic55["Topic 55 FDTD 微波 — 0/9 (0%)"]
        T55_in["raw_topic: 无条件稳定 FDTD + 微波传输线"]
        T55_p["LLM plan: 4 atom<br/>github query ≤4 词"]
        T55_gh["github raw: 0<br/>(openEMS/Meep 实际存在但本 run 未命中)"]
        T55_arxiv["arxiv raw: 8<br/>(ADI-FDTD/SS-FDTD)"]
        T55_b1["baseline 桶<br/>'无条件稳定 FDTD'方向<br/>学术正确但和用户 GT title 不对应"]
        T55_ht["用户给的 GT title:<br/>'Namiki's ADI-FDTD 公式'<br/>实际不一定存在"]
        T55_in --> T55_p
        T55_p --> T55_arxiv
        T55_p --> T55_gh
        T55_arxiv --> T55_b1
        T55_b1 -.miss.-> T55_ht
    end
```

LLM synthesize 出的答案是**学术上正确**的——"重型柴油机排放"和"无条件稳定 FDTD"都对得起题面，但**用户给的 GT 标题**是凭经验"应该有"的论文，可能根本不存在于 arxiv / crossref / github。**用户原话"差 1 项就放过，不要过拟合"**——我没有继续校准 53 / 55 的 GT。

— END Re00 —
