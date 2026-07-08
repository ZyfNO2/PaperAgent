# PaperAgent Re1.4 — 全链路 MVP SOP

> 承接：`PaperAgent_Re1.3_前端接入与引文扩展搜索_SOP.md`  
> 设计参考：`docs/design/PaperAgent_Re2_FullChain_Design.md`  
> 本轮原则：**先通后优**。6 个分析节点全部接入 graph，跑通不 crash 即可。prompt 质量、条件边路由、前端美化留到 Re2。

---

## 0. 前提条件

Re1.3 必须已完成并验收通过：

- [ ] 14+2 节点 graph 可运行（含 quality_filter + citation_expander）
- [ ] SSE 端点 `/api/v1/research/stream` 可用
- [ ] 前端 `apps/web/index.html` 可显示搜索结果 + verify 标记
- [ ] DeepSeek provider 默认可用
- [ ] 单 case 搜索阶段 ≤3 min (DeepSeek)

---

## 1. 本轮目标

**一句话**：在 baseline_classifier 之后接入 6 个分析节点，让 graph 从"只搜论文"变成"搜完就给建议"，一周内跑通。

### 必须完成

1. ResearchState 扩展 6 个新字段
2. 6 个新节点实现（每节点 = prompt + node 函数 + heuristic fallback）
3. 节点注册到 `__init__.py`
4. `research_graph.py` 线性接入（先不加条件边，全走 passthrough）
5. 6 个新 API 端点
6. 前端加"分析结果"面板
7. 端到端跑通 3 个题目

### 不做

- 条件边路由（先线性直连，devils_advocate 不回环）
- prompt 调优（写了就行，不反复调）
- 自测验证器（MVP 不跑 validator，只跑 E2E）
- 性能优化（只要 <10 min 就行，不追求 <5 min）
- 档位分层（固定保毕业）

---

## 2. 7 天排期

| 天 | 产出 | 验收 |
|---|---|---|
| Day 1 | ResearchState 扩展 + 6 个 prompt 文件 | `python -c "from app.services.agents.graph.state import ResearchState"` 不报错 |
| Day 2 | 6 个 node 文件 + 注册 + graph 接线 | `build_graph()` 不报错 |
| Day 3 | 6 个 API 端点 | `curl /api/v1/research/{case_id}/feasibility` 返回 JSON |
| Day 4 | 前端分析面板 | 浏览器能看到分析结果流入 |
| Day 5 | 端到端跑 1 个题目 | 题目"基于YOLOv5的钢材表面缺陷检测研究"跑完不 crash |
| Day 6 | 跑 3 个题目 + 修明显问题 | 3/3 跑完，`final_recommendation` 非空 |
| Day 7 | 完工报告 | `Plan/PaperAgent_Re1.4_完工报告.md` |

---

## 3. ResearchState 扩展

```python
# graph/state.py — 在现有 ResearchState 末尾追加

    # === Re1.4 新增 ===
    feasibility_report: dict[str, Any]
    innovation_points: list[dict[str, Any]]
    stitching_plan: dict[str, Any]
    sota_comparison: dict[str, Any]
    research_narrative: dict[str, Any]
    optimization_directions: dict[str, Any]
    review_report: dict[str, Any]
```

---

## 4. 6 个节点实现

### 4.1 通用 node 模板

每个节点遵循同一个模式：

```python
"""<node_name> — Re1.4 MVP."""
import time, logging
from typing import Any
from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def _emit(node, t0, ins, out, tools, prov, errs):
    return {"node": node, "started_at": _now_iso(), "input_summary": ins,
            "output_summary": out, "tool_calls": tools, "errors": errs,
            "provider": prov, "ended_at": _now_iso(), "elapsed_s": round(time.time()-t0, 3)}

def <node_name>_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    try:
        from apps.api.app.services import llm_router
        from apps.api.app.services.agents.prompts import <prompt_module> as P
        built = P.build(...)
        out = llm_router.call_json(built["user"], system=built["system"],
                                   profile="fast_json", max_tokens=2000,
                                   expected="dict", timeout=30)
        result = _normalize(out, state)
        prov = "fast_json"
    except Exception as exc:
        logger.warning("<node_name> LLM failed: %s — heuristic fallback", exc)
        result = _heuristic(state)
        prov = "heuristic"

    trace = _emit("<node_name>", t0, {...}, {...}, [...], prov, [])
    return {"<output_field>": result, "trace_events": list(state.get("trace_events") or []) + [trace]}
```

### 4.2 feasibility_assessor

**文件**: `nodes/feasibility_assessor.py` + `prompts/feasibility_assessor.py`

**Prompt (最简版)**:

```python
SYSTEM = "你是开题可行性评估员。基于证据数量判断能不能保毕业。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
Baseline数: {n_baseline}, Parallel数: {n_parallel}, Dataset数: {n_dataset}, Repo数: {n_repo}

输出JSON: {{"verdict":"feasible|risky|not_recommended","score":0-100,"reason":"<=50字"}}"""

def build(topic, n_baseline, n_parallel, n_dataset, n_repo):
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], n_baseline=n_baseline, n_parallel=n_parallel,
        n_dataset=n_dataset, n_repo=n_repo)}
```

**Heuristic fallback**:

```python
def _heuristic(state):
    nb = len(state.get("baseline_candidates") or [])
    nd = len(state.get("dataset_candidates") or [])
    nr = len(state.get("repo_candidates") or [])
    if nb >= 2 and nd >= 1:
        v, s = "feasible", 75
    elif nb >= 1:
        v, s = "risky", 50
    else:
        v, s = "not_recommended", 20
    return {"verdict": v, "score": s, "reason": f"heuristic: {nb}B/{nd}D/{nr}R",
            "100_plus_formula": {"baseline_weight": 100 if nb else 0,
                                  "module_weights": [1]*min(nr, 3),
                                  "estimated_total": (100 if nb else 0) + min(nr, 3)},
            "degradation_paths": []}
```

**输出字段**: `feasibility_report`

### 4.3 innovation_extractor

**文件**: `nodes/innovation_extractor.py` + `prompts/innovation_extractor.py`

**Prompt (最简版)**:

```python
SYSTEM = "你是学术裁缝专家。从baseline和parallel中提取可缝合模块。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
Baseline论文: {baselines}
Parallel论文: {parallels}

分析每个baseline用了什么方法组件，每个parallel做了什么改进。
输出JSON:
{{"innovation_points":[{{"description":"...","baseline_used":"...","stitched_modules":["..."],"stitching_plan":"...","estimated_difficulty":"低|中|高"}}],
"stitching_plan":{{"baseline_model":"...","module_b":"...","module_c":"...","stitching_steps":["1. ..."],"risk_notes":[]}}}}"""

def build(topic, baselines, parallels):
    def slim(items):
        return [{"title": i.get("title",""), "source": i.get("source","")} for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], baselines=slim(baselines), parallels=slim(parallels))}
```

**Heuristic fallback**:

```python
def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []
    b_title = (baselines[0].get("title","") if baselines else "未知baseline")
    p_title = (parallels[0].get("title","") if parallels else "未知parallel")
    return {
        "innovation_points": [{"description": f"在{b_title}基础上借鉴{p_title}的模块",
                                "baseline_used": b_title, "stitched_modules": [p_title],
                                "stitching_plan": "待LLM生成", "estimated_difficulty": "中"}],
        "stitching_plan": {"baseline_model": b_title, "module_b": p_title, "module_c": "",
                           "stitching_steps": ["1. 复现baseline", "2. 提取parallel模块", "3. 拼接测试"],
                           "risk_notes": ["heuristic fallback，需人工确认"]}
    }
```

**输出字段**: `innovation_points`, `stitching_plan`

### 4.4 sota_matcher

**文件**: `nodes/sota_matcher.py` + `prompts/sota_matcher.py`

**Prompt (最简版)**:

```python
SYSTEM = "你是实验设计顾问。选SOTA对比论文+给消融建议。保毕业档。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
Baseline论文: {baselines}

选3篇作为对比基线，给3个消融实验建议。
输出JSON:
{{"comparison_papers":[{{"title":"...","year":"..."}}],
"metrics_to_compare":["Accuracy","F1"],
"ablation_suggestions":[{{"name":"去掉模块B","purpose":"...","expected_drop":"1-3%"}}],
"experiment_checklist":["对比实验","消融实验","定性分析"]}}"""

def build(topic, baselines):
    def slim(items):
        return [{"title": i.get("title",""), "year": i.get("year","")} for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], baselines=slim(baselines))}
```

**Heuristic fallback**:

```python
def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    return {
        "comparison_papers": [{"title": b.get("title",""), "year": b.get("year","")}
                              for b in baselines[:3]],
        "metrics_to_compare": ["Accuracy", "F1", "mAP"],
        "ablation_suggestions": [
            {"name": "去掉模块B", "purpose": "验证模块B贡献", "expected_drop": "1-3%"},
            {"name": "去掉模块C", "purpose": "验证模块C贡献", "expected_drop": "1-3%"},
            {"name": "去掉B+C", "purpose": "验证整体创新", "expected_drop": "3-5%"}],
        "experiment_checklist": ["对比实验(≥3个baseline)", "消融实验(≥3组)",
                                  "参数敏感性实验(≥4组)", "定性分析(case study)"]
    }
```

**输出字段**: `sota_comparison`

### 4.5 narrative_builder

**文件**: `nodes/narrative_builder.py` + `prompts/narrative_builder.py`

**Prompt (最简版)**:

```python
SYSTEM = "你是论文叙事生成器。生成3个问题+1个模型名。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
创新点: {innovations}
可行性: {feasibility}

生成叙事。
输出JSON:
{{"three_problems":[{{"problem":"...","from_paper":"..."}},{{"problem":"...","from_paper":"..."}},{{"problem":"...","from_paper":"..."}}],
"nick_model_name":"...",
"narrative_summary":"<=200字"}}"""

def build(topic, innovations, feasibility):
    inn_text = "; ".join(i.get("description","")[:50] for i in innovations[:3])
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], innovations=inn_text,
        feasibility=feasibility.get("verdict","unknown"))}
```

**Heuristic fallback**:

```python
def _heuristic(state):
    topic = state.get("topic", "")
    baselines = state.get("baseline_candidates") or []
    b0 = (baselines[0].get("title","") if baselines else "现有方法")
    # 从 topic 提取一个简称作为 nick name
    import re
    words = re.findall(r'[A-Za-z]+', topic)
    nick = (words[0] + "-Net") if words else "Proposed-Net"
    return {
        "three_problems": [
            {"problem": f"{b0}在复杂场景下精度不足", "from_paper": b0},
            {"problem": "现有方法对小目标检测能力有限", "from_paper": b0},
            {"problem": "推理速度难以满足实时需求", "from_paper": b0}],
        "nick_model_name": nick,
        "narrative_summary": f"在{topic}中，现有方法存在三个问题。本文提出{nick}，"
                              f"通过改进模块解决上述问题。",
        "chapter_outline": {},
        "abstract_draft": ""
    }
```

**输出字段**: `research_narrative`

### 4.6 optimization_advisor

**文件**: `nodes/optimization_advisor.py` + `prompts/optimization_advisor.py`

**Prompt (最简版)**:

```python
SYSTEM = "你是研究方向优化顾问。给优化方向和退化路线。保毕业导向。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
可行性: {feasibility}
创新点数: {n_innovation}
Baseline数: {n_baseline}

输出JSON:
{{"optimization_paths":[{{"direction":"...","expected_gain":"...","difficulty":"低|中|高","action_items":["..."]}}],
"degradation_paths":[{{"path":"...","trade_off":"...","survival_rate":"高|中|极高"}}],
"risk_mitigation":["..."]}}"""

def build(topic, feasibility, n_innovation, n_baseline):
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], feasibility=feasibility.get("verdict","unknown"),
        n_innovation=n_innovation, n_baseline=n_baseline)}
```

**Heuristic fallback**:

```python
def _heuristic(state):
    feas = state.get("feasibility_report", {})
    verdict = feas.get("verdict", "risky")
    if verdict == "feasible":
        paths = [{"direction": "增加数据增强策略", "expected_gain": "提升2-5%",
                  "difficulty": "低", "action_items": ["调研CutMix/Mosaic效果"]}]
        degradation = [{"path": "去掉一个创新模块，仅保留核心改进",
                         "trade_off": "创新点减少但可毕业", "survival_rate": "高"}]
    else:
        paths = [{"direction": "简化题目范围", "expected_gain": "降低复现难度",
                  "difficulty": "低", "action_items": ["收缩到单一数据集/单一场景"]}]
        degradation = [{"path": "换用更简单的baseline", "trade_off": "创新性降低",
                         "survival_rate": "高"},
                       {"path": "改投更低级别期刊", "trade_off": "Q4→无级别",
                         "survival_rate": "极高"}]
    return {"optimization_paths": paths, "degradation_paths": degradation,
            "risk_mitigation": ["优先复现baseline确认代码可运行", "准备备选数据集"]}
```

**输出字段**: `optimization_directions`

### 4.7 devils_advocate

**文件**: `nodes/devils_advocate_node.py` + `prompts/devils_advocate_graph.py`

**Prompt (最简版)**:

```python
SYSTEM = "你是论文开题审查员。5维评分。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
可行性: {feasibility}
创新点: {innovations}
叙事: {narrative}
工作包: {work_packages}

5维评分(0-10): D1原创性 D2方法学 D3证据充分性 D4论证连贯 D5写作质量
输出JSON:
{{"dimension_scores":[{{"dimension":"D1","score":0,"verdict":"PASS|WARN|BLOCK","reason":"..."}}],
"overall_verdict":"ACCEPT|MINOR_REVISION|BLOCK","fabrication_alerts":[],"risks_identified":[]}}"""

def build(topic, feasibility, innovations, narrative, work_packages):
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:100],
        feasibility=str(feasibility.get("verdict",""))[:50],
        innovations=str(innovations[:2])[:200],
        narrative=str(narrative.get("narrative_summary",""))[:200],
        work_packages=str(work_packages[:2])[:200])}
```

**Heuristic fallback**:

```python
def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    has_baseline = len(baselines) >= 1
    if has_baseline:
        verdict = "ACCEPT"
        scores = [{"dimension": f"D{i}", "score": 6, "verdict": "PASS",
                   "reason": "heuristic: has baseline"} for i in range(1,6)]
    else:
        verdict = "BLOCK"
        scores = [{"dimension": f"D{i}", "score": 3, "verdict": "BLOCK",
                   "reason": "heuristic: no baseline"} for i in range(1,6)]
    return {"dimension_scores": scores, "overall_verdict": verdict,
            "fabrication_alerts": [], "risks_identified": ["heuristic review"],
            "verdict_source": "heuristic"}
```

**输出字段**: `review_report`

---

## 5. Graph 接线 (线性，无条件边)

```python
# research_graph.py — 在现有 graph 末尾追加

# 现有: ... → baseline_classifier
# 追加:
graph.add_edge("baseline_classifier", "feasibility_assessor")
graph.add_edge("feasibility_assessor", "work_package")
graph.add_edge("work_package", "innovation_extractor")
graph.add_edge("innovation_extractor", "sota_matcher")
graph.add_edge("sota_matcher", "narrative_builder")
graph.add_edge("narrative_builder", "low_bar_review")
graph.add_edge("low_bar_review", "optimization_advisor")
graph.add_edge("optimization_advisor", "devils_advocate")
graph.add_edge("devils_advocate", "human_gate")
graph.add_edge("human_gate", "final_recommendation")
graph.add_edge("final_recommendation", END)
```

**注意**：Re1.2 的 `low_bar_review → targeted_repair` 条件边保留，但 `optimization_advisor` 和 `devils_advocate` 之间不加回环。MVP 不做 MINOR_REVISION → narrative_builder 回退。

---

## 6. 节点注册

```python
# nodes/__init__.py — 追加

from . import feasibility_assessor as _feasibility
from . import innovation_extractor as _innovation
from . import sota_matcher as _sota
from . import narrative_builder as _narrative
from . import optimization_advisor as _optimization
from . import devils_advocate_node as _devils

REGISTRY["feasibility_assessor"] = _feasibility.feasibility_assessor_node
REGISTRY["innovation_extractor"] = _innovation.innovation_extractor_node
REGISTRY["sota_matcher"] = _sota.sota_matcher_node
REGISTRY["narrative_builder"] = _narrative.narrative_builder_node
REGISTRY["optimization_advisor"] = _optimization.optimization_advisor_node
REGISTRY["devils_advocate"] = _devils.devils_advocate_node
```

---

## 7. API 端点

```python
# api/v1/research.py — 追加 6 个端点

@router.get("/{case_id}/feasibility")
def case_feasibility(case_id: str):
    state = _load_state(case_id)
    return state.get("feasibility_report", {})

@router.get("/{case_id}/innovation")
def case_innovation(case_id: str):
    state = _load_state(case_id)
    return {"innovation_points": state.get("innovation_points", []),
            "stitching_plan": state.get("stitching_plan", {})}

@router.get("/{case_id}/sota")
def case_sota(case_id: str):
    state = _load_state(case_id)
    return state.get("sota_comparison", {})

@router.get("/{case_id}/narrative")
def case_narrative(case_id: str):
    state = _load_state(case_id)
    return state.get("research_narrative", {})

@router.get("/{case_id}/optimization")
def case_optimization(case_id: str):
    state = _load_state(case_id)
    return state.get("optimization_directions", {})

@router.get("/{case_id}/review")
def case_review(case_id: str):
    state = _load_state(case_id)
    return state.get("review_report", {})
```

---

## 8. 前端改动

在 `apps/web/index.html` 的 SSE 事件处理中，新增对分析节点的渲染：

```javascript
// 在现有 node_complete 事件处理中追加
es.addEventListener("node_complete", (e) => {
    const data = JSON.parse(e.data);
    const node = data.node;
    const output = data.output;

    if (node === "feasibility_assessor") {
        renderFeasibility(output.feasibility_report);
    } else if (node === "innovation_extractor") {
        renderInnovation(output);
    } else if (node === "sota_matcher") {
        renderSota(output.sota_comparison);
    } else if (node === "narrative_builder") {
        renderNarrative(output.research_narratives);
    } else if (node === "optimization_advisor") {
        renderOptimization(output.optimization_directions);
    } else if (node === "devils_advocate") {
        renderReview(output.review_report);
    }
});

function renderFeasibility(report) {
    const color = {feasible: "green", risky: "orange", not_recommended: "red"}[report.verdict] || "gray";
    document.getElementById("analysis-section").innerHTML =
        `<div style="border-left:3px solid ${color};padding:8px">
         <b>可行性: ${report.verdict} (${report.score}分)</b><br>${report.reason}
         </div>`;
}
```

在 HTML body 中加一个分析结果容器：

```html
<div id="analysis-section" style="margin-top:20px;"></div>
```

---

## 9. SSE 端点改动

现有的 `POST /api/v1/research/stream` 端点已经通过 `graph.stream(stream_mode="updates")` 推送每个节点的输出。新增的 6 个节点会自动产生 `node_complete` 事件，**SSE 端点不需要改代码**。

前提是 `_slim_output()` 函数能处理新字段名。如果没有这个函数或它过滤了未知字段，直接透传即可。

---

## 10. 测试

### Loop 1: Graph 可构建

```python
def test_graph_builds():
    from app.services.agents.graph.research_graph import build_graph
    g = build_graph()
    assert g is not None
```

### Loop 2: 单节点 fallback

对每个节点，构造空 state，验证 heuristic fallback 不 crash：

```python
def test_all_nodes_heuristic():
    from app.services.agents.graph.nodes import REGISTRY
    empty_state = {"topic": "test", "trace_events": [], "errors": []}
    for name in ["feasibility_assessor", "innovation_extractor", "sota_matcher",
                  "narrative_builder", "optimization_advisor", "devils_advocate"]:
        result = REGISTRY[name](empty_state)
        assert result is not None
        assert "trace_events" in result
```

### Loop 3: 端到端 3 题目

| # | 题目 | 验证 |
|---|---|---|
| 1 | 基于YOLOv5的钢材表面缺陷检测研究 | `final_recommendation` 非空 + `feasibility_report.verdict` 存在 |
| 2 | 基于深度学习的视觉SLAM语义地图的研究 | 同上 |
| 3 | 基于大语言模型的医学问答可信度评估方法研究 | 同上 |

通过条件：
- 3/3 不 crash
- 3/3 `state.json` 中有 `feasibility_report` + `review_report`
- 3/3 `trace.json` 中有 20+ 个 node 事件（含 6 个新节点）
- 3/3 `final_recommendation` 非空

**并行策略**：3 个题目相互独立，分发 3 个 subagent 并行跑。主线程趁等待时 review 已完成的节点代码 + 检查前端渲染。

---

## 11. 验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | 20 节点 graph 可构建 | `build_graph()` 不报错 |
| 2 | 6 个新节点注册 | `REGISTRY` 含 6 个新 key |
| 3 | 6 个 API 端点可调 | `curl` 返回 JSON |
| 4 | 前端显示分析结果 | 手动测试 |
| 5 | 端到端跑通 3 题目 | E2E 测试 |
| 6 | 每个节点有 trace 事件 | trace.json 检查 |
| 7 | LLM 失败时 fallback 不 crash | Loop 2 验证 |
| 8 | 单 case <10 min (DeepSeek) | node_timings |

---

## 12. 禁止事项

- 禁止调 prompt 超过 2 轮（MVP 不追求质量）
- 禁止加条件边回环（devils_advocate 不回退）
- 禁止加自测验证器（Re2 再做）
- 禁止追求 <5 min 性能（<10 min 就行）
- 禁止改现有 14+2 节点的代码（只追加）
- 禁止引入新依赖

---

## 13. 交付物

代码：
- `nodes/feasibility_assessor.py` 🆕
- `nodes/innovation_extractor.py` 🆕
- `nodes/sota_matcher.py` 🆕
- `nodes/narrative_builder.py` 🆕
- `nodes/optimization_advisor.py` 🆕
- `nodes/devils_advocate_node.py` 🆕
- `prompts/feasibility_assessor.py` 🆕
- `prompts/innovation_extractor.py` 🆕
- `prompts/sota_matcher.py` 🆕
- `prompts/narrative_builder.py` 🆕
- `prompts/optimization_advisor.py` 🆕
- `prompts/devils_advocate_graph.py` 🆕
- `graph/state.py` 🔧 (追加字段)
- `graph/research_graph.py` 🔧 (追加边)
- `graph/nodes/__init__.py` 🔧 (追加注册)
- `api/v1/research.py` 🔧 (追加端点)
- `apps/web/index.html` 🔧 (追加分析面板)

报告：
- `Plan/PaperAgent_Re1.4_完工报告.md`

---

## 14. Re1.4 完成后进入 Re2

Re1.4 是 Re2 的前置步骤。Re1.4 跑通后，Re2 做的事：

1. **条件边路由**：devils_advocate MINOR_REVISION → narrative_builder 回退
2. **prompt 调优**：基于 Re1.4 的真实输出优化 6 个 prompt
3. **自测框架**：4 个 validator（paper/repo/dataset/conclusion）
4. **性能优化**：verify 批量化、innovation+sota 并行
5. **前端美化**：分析结果详细渲染
