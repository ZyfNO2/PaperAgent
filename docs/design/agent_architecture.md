# PaperAgent Agent 范式与 LangGraph 架构图

> 基于 `apps/api/app/services/agents/graph/research_graph.py` 源码绘制，反映 Re3.8 当前状态。

## 1. 全链路 LangGraph 架构

```mermaid
graph TD
    START(["START"]) --> intake

    subgraph Phase1["Phase 1 — 主题解析与检索"]
        intake["intake<br/>接收题目 + 用户约束 + 档位<br/>写入: case_id, topic, user_papers"]
        topic_parser["topic_parser<br/>LLM 关键词分解 method / object / task / scenario<br/>Profile: fast_json → DeepSeek<br/>写入: topic_atoms"]
        search_planner["search_planner<br/>生成多轮查询矩阵 (broad → focused → repair)<br/>写入: search_plan"]
        paper_retriever["paper_retriever<br/>(search_agent — React Agent)<br/>think → call → observe 循环<br/>写入: raw_results, paper_candidates,<br/>repo_candidates, search_steps"]
        quality_filter["quality_filter<br/>LLM 判断是否真实学术论文<br/>Fallback: heuristic regex<br/>写入: filter_results"]
        verify["verify<br/>逐篇验证 accept / weak_reject / reject<br/>写入: verified_papers, weak_papers"]
        quality_gate{{"quality_gate<br/>条件路由网关"}}
    end

    intake --> topic_parser
    topic_parser --> search_planner
    search_planner --> paper_retriever
    paper_retriever --> quality_filter
    quality_filter --> verify
    verify --> quality_gate

    subgraph Adapters["8 源检索适配器 (asyncio.gather 并发)"]
        direction LR
        A1["arxiv"]
        A2["openalex"]
        A3["crossref"]
        A4["github"]
        A5["semantic_scholar"]
        A6["huggingface"]
        A7["core"]
        A8["datacite"]
    end

    paper_retriever -.->|fan-out 并发| Adapters
    Adapters -.->|fan-in 去重| paper_retriever

    quality_gate -->|n_papers=0 + total≥3 + rounds<2| targeted_repair
    quality_gate -->|n_papers≥1 + 首轮| citation_expander
    quality_gate -->|n_papers≥1 + 已展开| dataset_repo_extractor
    quality_gate -->|n_papers<1 + rounds≥2| final_recommendation
    quality_gate -->|n_papers=0 + total<3 + rounds≥2| final_recommendation

    targeted_repair["targeted_repair<br/>生成补缺查询 (synonym / broaden / switch_tool)<br/>写入: search_plan patch, repair_rounds++"] -->|loop back| paper_retriever

    citation_expander["citation_expander<br/>种子论文选择 → S2 引用展开<br/>写入: seed_papers, expanded_papers,<br/>citation_expansion_done=True"] -->|second round verify| verify

    subgraph Phase2["Phase 2 — 证据分析"]
        dataset_repo_extractor["dataset_repo_extractor<br/>从论文全文/摘要提取数据集与仓库<br/>写入: dataset_candidates, repo_candidates"]
        evidence_graph_builder["evidence_graph_builder<br/>构建证据关系图 (nodes + edges)<br/>写入: evidence_graph"]
        baseline_classifier["baseline_classifier<br/>LLM 分类 baseline / parallel / survey<br/>写入: baseline_candidates, parallel_candidates"]
        feasibility_assessor{{"feasibility_assessor<br/>LLM 5 档可行性判断<br/>写入: feasibility_report"}}
    end

    dataset_repo_extractor --> evidence_graph_builder
    evidence_graph_builder --> baseline_classifier
    baseline_classifier --> feasibility_assessor

    feasibility_assessor -->|feasible / risky| work_package
    feasibility_assessor -->|not_recommended| optimization_advisor

    subgraph Phase3["Phase 3 — 创新分析与叙事"]
        work_package["work_package<br/>LLM 生成工作包 (复现步骤)<br/>写入: work_packages"]
        innovation_extractor["innovation_extractor<br/>LLM 提取创新点 (A+B+C 缝合方案)<br/>写入: innovation_points, stitching_plan"]
        sota_matcher["sota_matcher<br/>LLM 对比 SOTA<br/>写入: sota_comparison"]
        narrative_builder["narrative_builder<br/>LLM 生成 3 问题 + 摘要 + 5 章大纲<br/>写入: research_narratives"]
        low_bar_review{{"low_bar_review<br/>低栏审查条件路由<br/>写入: low_bar_review"}}
    end

    work_package -->|fan-out 并行| innovation_extractor
    work_package -->|fan-out 并行| sota_matcher
    innovation_extractor -->|fan-in| narrative_builder
    sota_matcher -->|fan-in| narrative_builder
    narrative_builder --> low_bar_review

    low_bar_review -->|status=pass| optimization_advisor
    low_bar_review -->|total<4 + rounds<2| targeted_repair
    low_bar_review -->|rounds≥2 / blocked| final_recommendation

    subgraph Phase4["Phase 4 — 多视角审查与终审"]
        optimization_advisor["optimization_advisor<br/>LLM 优化方向 + 退化路线建议<br/>写入: optimization_directions"]
        devils_advocate{{"devils_advocate<br/>LLM 5 维评分<br/>ACCEPT / MINOR_REVISION / BLOCK<br/>写入: review_report"}}
        human_gate["human_gate<br/>人工审核 (默认 pass-through)<br/>写入: human_gate"]
        final_recommendation["final_recommendation<br/>汇总计数 + 生成报告<br/>写入: final_recommendation"]
    end

    optimization_advisor --> devils_advocate

    devils_advocate -->|ACCEPT| human_gate
    devils_advocate -->|MINOR_REVISION + revisions<2| narrative_builder
    devils_advocate -->|MINOR_REVISION + revisions≥2| human_gate
    devils_advocate -->|BLOCK + block_count≤1 + feasible| optimization_advisor
    devils_advocate -->|BLOCK + not_recommended| human_gate
    devils_advocate -->|BLOCK + block_count>1| human_gate

    human_gate --> final_recommendation
    final_recommendation --> END_NODE(["END"])
```

## 2. LangGraph 构建方式

### 2.1 代码骨架 (`research_graph.py`)

```python
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

def build_graph(*, checkpointer=None):
    # 1. 创建状态图，绑定 ResearchState TypedDict
    graph = StateGraph(ResearchState)

    # 2. 批量注册节点 (REGISTRY 字典: name → function)
    for name, fn in REGISTRY.items():
        graph.add_node(name, fn)

    # 3. 线性主干边
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "topic_parser")
    graph.add_edge("topic_parser", "search_planner")
    graph.add_edge("search_planner", "paper_retriever")
    graph.add_edge("paper_retriever", "quality_filter")
    graph.add_edge("quality_filter", "verify")
    graph.add_edge("verify", "quality_gate")

    # 4. 条件路由边 (4 个网关)
    graph.add_conditional_edges("quality_gate",     _route_after_quality_gate,    {...})
    graph.add_conditional_edges("feasibility_assessor", _route_after_feasibility, {...})
    graph.add_conditional_edges("low_bar_review",   _route_after_review,          {...})
    graph.add_conditional_edges("devils_advocate",  _route_after_devils,          {...})

    # 5. 并行扇出/扇入
    graph.add_edge("work_package", "innovation_extractor")  # fan-out
    graph.add_edge("work_package", "sota_matcher")          # fan-out
    graph.add_edge("innovation_extractor", "narrative_builder")  # fan-in
    graph.add_edge("sota_matcher", "narrative_builder")          # fan-in

    # 6. 编译 (checkpointer 支持断点续跑)
    return graph.compile(checkpointer=checkpointer or MemorySaver())
```

### 2.2 ResearchState TypedDict

```python
class ResearchState(TypedDict, total=False):
    # Intake
    case_id: str
    topic: str
    user_constraints: dict[str, Any]
    user_papers: list[dict[str, Any]]

    # Topic parsing
    topic_atoms: dict[str, Any]  # {method, object, task, scenario, domain, ...}

    # Search
    search_plan: dict[str, Any]
    raw_results: dict[str, list[dict[str, Any]]]
    search_steps: list[dict[str, Any]]  # React agent step log

    # Evidence
    paper_candidates: list[dict[str, Any]]
    verified_papers: list[dict[str, Any]]
    weak_papers: list[dict[str, Any]]
    evidence_graph: dict[str, Any]
    evidence_audit: dict[str, Any]

    # Classification
    baseline_candidates: list[dict[str, Any]]
    parallel_candidates: list[dict[str, Any]]
    dataset_papers: list[dict[str, Any]]
    surveys: list[dict[str, Any]]

    # Datasets / repos
    dataset_candidates: list[dict[str, Any]]
    repo_candidates: list[dict[str, Any]]

    # Re1.3 citation expansion
    seed_papers: list[dict[str, Any]]
    expanded_papers: list[dict[str, Any]]
    surveys_found: list[dict[str, Any]]
    citation_expansion_done: bool

    # Re1.4 analysis
    feasibility_report: dict[str, Any]
    innovation_points: list[dict[str, Any]]
    stitching_plan: dict[str, Any]
    sota_comparison: dict[str, Any]
    research_narrative: dict[str, Any]
    optimization_directions: dict[str, Any]
    review_report: dict[str, Any]

    # Loop counters
    narrative_revision_count: int
    devils_advocate_block_count: int

    # Output
    work_packages: list[dict[str, Any]]
    low_bar_review: dict[str, Any]
    human_gate: dict[str, Any]
    final_recommendation: dict[str, Any]

    # Telemetry (Annotated: 自动 merge)
    trace_events: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
    provider_profile: str
```

节点返回 **partial patch** (dict)，LangGraph 自动 merge。`trace_events` 和 `errors` 使用 `Annotated[..., operator.add]` 自动追加而非覆盖。

## 3. 4 个条件路由网关

```mermaid
graph LR
    subgraph G1["quality_gate"]
        direction LR
        Q1["n=0, total≥3, rounds<2 → repair"]
        Q2["n≥1, 首轮 → citation_expander"]
        Q3["n≥1, 已展开 → continue"]
        Q4["n<1, rounds≥2 → blocked"]
    end
    subgraph G2["feasibility_assessor"]
        direction LR
        F1["feasible / risky → work_package"]
        F2["not_recommended → optimization_advisor"]
    end
    subgraph G3["low_bar_review"]
        direction LR
        L1["status=pass → ready (→optimization)"]
        L2["total<4, rounds<2 → repair"]
        L3["else → blocked"]
    end
    subgraph G4["devils_advocate"]
        direction LR
        D1["ACCEPT → human_gate"]
        D2["MINOR + rev<2 → narrative_builder"]
        D3["MINOR + rev≥2 → human_gate"]
        D4["BLOCK + cnt≤1 + feasible → optimization"]
        D5["BLOCK + not_recommended → human_gate"]
        D6["BLOCK + cnt>1 → human_gate"]
    end
```

## 4. 3 个循环模式

```mermaid
graph LR
    subgraph Loop1["修复循环 (max 2 轮)"]
        R1["targeted_repair"] -->|loop back| R2["paper_retriever"]
        R2 --> R3["quality_filter → verify → quality_gate"]
        R3 -->|still insufficient| R1
    end

    subgraph Loop2["引用展开循环 (1 次)"]
        C1["citation_expander"] -->|second round| C2["verify"]
        C2 --> C3["quality_gate"]
    end

    subgraph Loop3["叙事修订循环 (max 2 次)"]
        N1["devils_advocate"] -->|MINOR_REVISION| N2["narrative_builder"]
        N2 --> N3["low_bar_review → optimization_advisor"]
        N3 --> N1
    end
```

| 循环 | 路径 | 计数器 | 上限 | 环境变量 |
|---|---|---|---|---|
| 修复 | `targeted_repair → paper_retriever → ... → quality_gate` | `evidence_audit.repair_rounds` | 2 | `PAPERAGENT_MAX_REPAIR_ROUNDS` |
| 引用展开 | `citation_expander → verify → quality_gate` | `citation_expansion_done` (bool) | 1 次 | — |
| 叙事修订 | `devils_advocate → narrative_builder → ... → devils_advocate` | `narrative_revision_count` | 2 | `MAX_NARRATIVE_REVISIONS` |
| BLOCK 重试 | `devils_advocate → optimization_advisor → devils_advocate` | `devils_advocate_block_count` | 1 | `MAX_BLOCK_RETRIES` |

## 5. LLM Provider 路由

```mermaid
graph TD
    subgraph Router["llm_router.py"]
        direction TB
        P1["fast_json<br/>DeepSeek (主, env FAST_JSON_PRIMARY=deepseek)<br/>StepFun (fallback)<br/>用途: JSON 生成节点"]
        P2["execution<br/>StepFun<br/>用途: 简单执行, 无最终判断"]
        P3["premium_review<br/>VOAPI<br/>用途: 终审采样"]
    end

    subgraph JSON_Pipeline["3-phase JSON 解析 (json_repair.py)"]
        direction TB
        J1["Phase A: 直接 json.loads"]
        J2["Phase B: reasoning 字段扫描<br/>(reasoner 模型把 JSON 藏在 reasoning 里)"]
        J3["Phase C: fallback formatter<br/>(带 schema_hint 重新请求 LLM)"]
        J1 -->|失败| J2
        J2 -->|失败| J3
    end

    topic_parser -.->|call_json expected=dict| P1
    search_planner -.->|call_json expected=dict| P1
    verify -.->|call_json expected=list| P1
    quality_filter -.->|call_json expected=list| P1
    baseline_classifier -.->|call_json expected=dict| P1
    feasibility_assessor -.->|call_json expected=dict| P1
    innovation_extractor -.->|call_json expected=dict| P1
    sota_matcher -.->|call_json expected=dict| P1
    narrative_builder -.->|call_json expected=dict| P1
    optimization_advisor -.->|call_json expected=dict| P1
    devils_advocate -.->|call_json expected=dict| P1

    P1 -.->|call_json| JSON_Pipeline
```

## 6. Ponytail 节点范式

每个 LangGraph 节点遵循统一模式：

```python
def some_node(state: ResearchState) -> dict[str, Any]:
    """节点 docstring: 读取 X, 写入 Y."""
    t0 = time.time()

    # 1. 幂等检查 — 已有结果则跳过
    if state.get("some_result"):
        return {"trace_events": [_emit(..., skipped=True)]}

    # 2. 尝试 LLM 调用 (1 次, profile=fast_json)
    try:
        built = P.build(topic, ...)
        out = call_json(built["user"], system=built["system"],
                       profile="fast_json", expected="dict", timeout=30)
        result = out if isinstance(out, dict) else _heuristic(state)
        prov = "fast_json"
    except Exception as exc:
        # 3. 确定性 fallback — LLM 不可用时不崩溃
        logger.warning("xxx LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    # 4. 返回 partial state patch (不原地修改)
    return {
        "some_result": result,
        "trace_events": [_emit("xxx", t0, input_summary, output_summary,
                                tool_calls, prov, state_keys)],
    }
```

核心原则：
- **1 次 LLM 调用** — 每个节点最多 1 次
- **确定性 fallback** — LLM 失败降级到规则逻辑
- **partial patch 返回** — 不原地修改 state
- **trace_event 记录** — 耗时 / 工具 / provider / state_keys

## 7. 节点注册表 (22 个节点)

| 节点名 | 模块 | 读取 | 写入 | 别名 |
|---|---|---|---|---|
| `intake` | `intake.py` | topic, user_papers | case_id | — |
| `topic_parser` | `topic_parser.py` | topic | topic_atoms | — |
| `search_planner` | `search_planner.py` | topic_atoms | search_plan | — |
| `paper_retriever` | `search_agent.py` | search_plan, topic_atoms | raw_results, paper_candidates, repo_candidates, search_steps | `search_agent` |
| `quality_filter` | `quality_filter.py` | paper_candidates | filter_results | — |
| `verify` | `verify.py` | paper_candidates, topic_atoms | verified_papers, weak_papers | `paper_verifier` |
| `quality_gate` | `quality_gate.py` | verified_papers, evidence_audit | evidence_audit | — |
| `targeted_repair` | `targeted_repair.py` | evidence_audit, topic_atoms | search_plan (patch) | — |
| `citation_expander` | `citation_expander.py` | verified_papers | seed_papers, expanded_papers, citation_expansion_done | — |
| `dataset_repo_extractor` | `dataset_repo_extractor.py` | verified_papers | dataset_candidates, repo_candidates | `dataset_repo` |
| `evidence_graph_builder` | `json_graph_builder.py` | verified_papers, baseline_candidates | evidence_graph | — |
| `baseline_classifier` | `baseline_classifier.py` | verified_papers, topic_atoms | baseline_candidates, parallel_candidates | `evidence_auditor` |
| `feasibility_assessor` | `feasibility_assessor.py` | baseline_candidates, dataset_candidates | feasibility_report | — |
| `work_package` | `content.py` | baselines, datasets, repos | work_packages | `work_package_brainstorm` |
| `innovation_extractor` | `innovation_extractor.py` | baselines, parallels | innovation_points, stitching_plan | — |
| `sota_matcher` | `sota_matcher.py` | baselines, parallels | sota_comparison | — |
| `narrative_builder` | `narrative_builder.py` | innovations, feasibility | research_narratives | — |
| `low_bar_review` | `content.py` | work_packages, evidence_audit | low_bar_review | — |
| `optimization_advisor` | `optimization_advisor.py` | parallels, feasibility | optimization_directions | — |
| `devils_advocate` | `devils_advocate_node.py` | narrative, feasibility, innovations | review_report | — |
| `human_gate` | `content.py` | review_report, final_recommendation | human_gate | — |
| `final_recommendation` | `content.py` | all state | final_recommendation | — |

## 8. 检索适配器层

```mermaid
graph TD
    SA["search_agent (React Agent)<br/>think → call → observe"]

    subgraph Registry["adapters/REGISTRY"]
        A1["arxiv_search<br/>arXiv API"]
        A2["openalex_search<br/>OpenAlex API"]
        A3["crossref_search<br/>Crossref API"]
        A4["github_search<br/>GitHub API"]
        A5["semantic_scholar<br/>S2 API (metadata only)"]
        A6["huggingface<br/>HF Hub API"]
        A7["core<br/>CORE API"]
        A8["datacite<br/>DataCite API"]
    end

    SA -->|asyncio.gather 并发| Registry
    Registry -->|circuit breaker| CB["AdapterSuspendState<br/>per-adapter 429 退避<br/>persist 到 JSON"]

    CB -->|CB OPEN| SKIP["跳过该适配器<br/>不阻塞其他"]
    CB -->|CB CLOSED| PASS["正常调用"]
```

规则：
- 8 源共享 `search_planner` 生成的同一查询列表
- 一个适配器 429/timeout 不阻塞 pipeline (circuit breaker + `failed_tools` 跳过)
- GitHub 结果 → `repo_candidates`，不进入 `verified_papers`
- 跨源去重: normalized title + DOI priority
