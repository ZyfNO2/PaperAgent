# PaperAgent Re2 — 功能增强 SOP

> 承接：Re1.5 质量验证与批量测试
> 设计参考：`docs/design/PaperAgent_Re2_FullChain_Design.md`
> **本 SOP 设计为无人值守执行。** 用户不在场，执行者按 Phase 顺序自主执行。
> 预计总时长：4-6 小时。
> 模型：DeepSeek (主)。

## 0. 执行者必读

### 0.1 核心原则

1. **每改一处代码，必须立即重跑 1 个 case 验证。验证不通过则 `git checkout` 回滚该文件，继续下一任务。**
2. **Phase 间的失败不传染。** Phase 0 挂了不影响 Phase 2 独立运行。
3. **连续 3 次失败（crash 或 路由错误）必须停止当前 Phase，跳到下一个 Phase。**
4. **禁止同时改多个文件。** 每次只改一个文件，验证通过后再改下一个。
5. **所有产出写入 `tmp_re2_eval/`，不覆盖 `tmp_re15_eval/` 或 `tmp_re14_eval/`。**

### 0.2 可跳过 vs 必须完成

| 任务 | 可跳过? | 跳过条件 |
|---|---|---|
| Phase 0: 条件边路由 | ❌ 不可跳过 | Re2 核心功能 |
| Phase 1: Prompt 增强 | ❌ 不可跳过 | Re2 核心功能 |
| Phase 2: 性能优化 | ⚠ 可部分跳过 | 并行化失败则保持串行，记录原因 |
| Phase 3: E2E 验证 | ❌ 不可跳过 | 硬性交付物 |
| Phase 4: 汇总报告 | ❌ 不可跳过 | 硬性交付物 |

### 0.3 改动隔离机制

每次修改代码前：

```bash
git stash create > /tmp/re2_stash_baseline
```

修改后验证不通过时：

```bash
git checkout -- <file>
```

验证通过后：

```bash
echo "<file>: <改动原因> → 验证通过" >> tmp_re2_eval/changelog.md
```

### 0.4 现状摘要（执行者必读）

Re1.4 已完成 6 个分析节点的线性接入。当前状态：

| 组件 | 状态 | 说明 |
|---|---|---|
| 6 个分析节点 | ✅ 已实现 | feasibility/innovation/sota/narrative/optimization/devils_advocate |
| 节点注册 + graph 接线 | ✅ 线性直连 | **无条件边**，devils_advocate → human_gateway 直连 |
| 6 个 prompt 文件 | ✅ MVP 版本 | **上下文极薄**：feasibility 只传计数，innovation 只传 title，devils_advocate 截断 50-200 字 |
| trace_events Annotated | ✅ 已修复 | state.py 已有 `Annotated[list, operator.add]`，节点已返回 `[trace]` |
| 4 个 validator | ✅ 已存在 | e2e_completeness / paper_authenticity / topic_relevance / feasibility_diversity |
| 前端 | ✅ 已重写 | 4 tab / 卡片 / 证据图谱 / 工作包 / 历史 |
| 条件边路由 | ❌ 未实现 | feasibility blocked 不跳 optimization_advisor；devils_advocate 不回环 narrative_builder |
| 并行执行 | ❌ 未实现 | innovation → sota 串行，sota 不依赖 innovation 但未并行 |
| 节点超时配置 | ❌ 未实现 | 所有节点硬编码 timeout=30，无 NODE_TIMEOUTS |
| 平行论文优化分析 | ❌ 未实现 | optimization_advisor 只传计数，不传 parallel 论文摘要 |

### 0.5 Re1.5 依赖

Re1.5 的以下结论影响 Re2 执行：

| Re1.5 结论 | 对 Re2 的影响 |
|---|---|
| feasibility prompt 无区分度（全 risky） | Re2 Phase 1 必须增强 feasibility prompt，传入论文摘要 |
| devils_advocate 全 BLOCK | Re2 Phase 1 必须增强 devils_advocate prompt，传入完整上下文 |
| trace_events 无 crash | Re2 Phase 0 可以安全添加条件边 |
| 20 篇 smoke test 数据 | Re2 Phase 3 可复用相同选题做验证 |

**如果 Re1.5 尚未执行**：Re2 仍可独立执行。Phase 1 的 prompt 增强不依赖 Re1.5 结果，但验证标准会放宽（无批量基线对比）。

---

## 1. 模型策略

| Provider | 用途 | env | 单 case 预计 |
|---|---|---|---|
| DeepSeek | 全部 Phase | `FAST_JSON_PRIMARY=deepseek` | 70-200s |

---

## 2. 测试选题

从 Re1.5 SOP §2 复用，选 3 个代表性 case：

| # | ID | 题名 | 领域 | 难度 | 用途 |
|---|---|---|---|---|---|
| 1 | ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木 | 低-中 | 保毕业 baseline，验证正常路径 |
| 2 | ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | 三维视觉 | 中-高 | 验证 prompt 增强效果 |
| 3 | ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | 机器人 | 高 | 验证 devils_advocate 条件边（可能触发 MINOR_REVISION 回环）|

---

## 3. Phase 设计

### Phase 0：条件边路由 (60-90min)

#### 0.1 目标

实现 Re2 设计文档 §7 定义的两条条件边：

1. **feasibility_assessor → 路由**：feasibility verdict = "not_recommended" 时跳过 work_package/innovation/sota/narrative，直接到 optimization_advisor
2. **devils_advocate → 路由**：MINOR_REVISION → 回到 narrative_builder 修正；BLOCK → 回到 optimization_advisor 重新规划

#### 0.2 实现步骤

**步骤 1：添加 revision counter 到 ResearchState**

文件：`apps/api/app/services/agents/graph/state.py`

在 Re1.4 字段块末尾添加：

```python
    # === Re2 new fields ===
    narrative_revision_count: int  # devils_advocate 回环计数器
```

验证：`python -c "from apps.api.app.services.agents.graph.state import ResearchState; print('ok')"`

**步骤 2：实现 `_route_after_feasibility`**

文件：`apps/api/app/services/agents/graph/research_graph.py`

```python
def _route_after_feasibility(state: ResearchState) -> str:
    """Route after feasibility assessment.

    - not_recommended → optimization_advisor (skip work_package chain)
    - feasible / risky → work_package (normal flow)
    """
    verdict = state.get("feasibility_report", {}).get("verdict", "risky")
    if verdict == "not_recommended":
        return "optimization_advisor"
    return "work_package"
```

修改 graph 接线：

```python
# 旧：
graph.add_edge("feasibility_assessor", "work_package")

# 新：
graph.add_conditional_edges(
    "feasibility_assessor",
    _route_after_feasibility,
    {
        "work_package": "work_package",
        "optimization_advisor": "optimization_advisor",
    },
)
```

验证：运行 case 1 (ENG-THESIS-074)。
- [ ] graph 完成无 crash。
- [ ] 如果 feasibility verdict = "feasible" 或 "risky" → trace 中有 work_package 节点。
- [ ] 如果 feasibility verdict = "not_recommended" → trace 中无 work_package 节点，有 optimization_advisor 节点。
- [ ] 如果验证失败 → `git checkout -- research_graph.py` → 记录失败 → 跳过此步骤，保持线性边。

**步骤 3：实现 `_route_after_devils`**

文件：`apps/api/app/services/agents/graph/research_graph.py`

```python
MAX_NARRATIVE_REVISIONS = 2

def _route_after_devils(state: ResearchState) -> str:
    """Route after devil's advocate review.

    - ACCEPT → human_gate
    - MINOR_REVISION → narrative_builder (if revisions < MAX)
    - MINOR_REVISION → human_gate (if revisions >= MAX, stop looping)
    - BLOCK → optimization_advisor (if revisions < MAX)
    - BLOCK → human_gate (if revisions >= MAX, stop looping)
    """
    verdict = state.get("review_report", {}).get("overall_verdict", "ACCEPT")
    revisions = state.get("narrative_revision_count", 0)

    if verdict == "ACCEPT":
        return "human_gate"

    if revisions >= MAX_NARRATIVE_REVISIONS:
        # Stop looping regardless of verdict
        return "human_gate"

    if verdict == "MINOR_REVISION":
        return "narrative_builder"
    if verdict == "BLOCK":
        return "optimization_advisor"

    return "human_gate"  # default
```

修改 graph 接线：

```python
# 旧：
graph.add_edge("devils_advocate", "human_gate")

# 新：
graph.add_conditional_edges(
    "devils_advocate",
    _route_after_devils,
    {
        "human_gate": "human_gate",
        "narrative_builder": "narrative_builder",
        "optimization_advisor": "optimization_advisor",
    },
)
```

**步骤 4：narrative_builder 递增 revision counter**

文件：`apps/api/app/services/agents/graph/nodes/narrative_builder.py`

在 `narrative_builder_node` 的 return 中添加 `narrative_revision_count`：

```python
    current_count = state.get("narrative_revision_count", 0)
    return {"research_narratives": result,
            "narrative_revision_count": current_count + 1,
            "trace_events": [trace]}
```

同样，`optimization_advisor` 被回环时也需要递增（防止 BLOCK → optimization → devils → BLOCK 无限循环）：

文件：`apps/api/app/services/agents/graph/nodes/optimization_advisor.py`

在 `optimization_advisor_node` 的 return 中添加：

```python
    current_count = state.get("narrative_revision_count", 0)
    return {"optimization_directions": result,
            "narrative_revision_count": current_count + 1,
            "trace_events": [trace]}
```

验证：运行 case 1 (ENG-THESIS-074)。
- [ ] graph 完成无 crash。
- [ ] trace 中 devils_advocate → human_gate（正常路径，ACCEPT）。
- [ ] 如果 devils_advocate 返回 MINOR_REVISION → trace 中有 narrative_builder 二次出现。
- [ ] 如果 devils_advocate 返回 BLOCK → trace 中有 optimization_advisor 二次出现。
- [ ] revision count 不超过 MAX_NARRATIVE_REVISIONS (2)。
- [ ] 如果验证失败 → `git checkout` → 记录失败 → 保持线性边。

**步骤 5：处理 graph 中重复边**

修改 `research_graph.py` 时注意：当前有两条重复的 `graph.add_edge("human_gate", "final_recommendation")` 和 `graph.add_edge("final_recommendation", END)`。删除重复的。

```python
# 删除这两行（重复）：
# graph.add_edge("human_gate", "final_recommendation")  # 第二次
# graph.add_edge("final_recommendation", END)            # 第二次
```

#### 0.3 验证

```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 18182
```

- [ ] `/health` 返回 200。
- [ ] 提交 case 1 (ENG-THESIS-074)，graph 完成无 crash。
- [ ] state.json 中 `trace_events` 有 ≥ 20 个事件。
- [ ] `narrative_revision_count` 存在于 state 中（即使值为 0 或 1）。
- [ ] 如果验证失败 → 回滚 → 记录 → 继续用线性边跑后续 Phase。

#### 0.4 检查清单

- [ ] `state.py` 有 `narrative_revision_count` 字段。
- [ ] `research_graph.py` 有 `_route_after_feasibility` 函数。
- [ ] `research_graph.py` 有 `_route_after_devils` 函数。
- [ ] `research_graph.py` 有 `MAX_NARRATIVE_REVISIONS = 2`。
- [ ] `feasibility_assessor` 使用条件边（不再线性到 work_package）。
- [ ] `devils_advocate` 使用条件边（不再线性到 human_gate）。
- [ ] `narrative_builder.py` 递增 `narrative_revision_count`。
- [ ] `optimization_advisor.py` 递增 `narrative_revision_count`。
- [ ] 重复的 `add_edge` 已删除。
- [ ] case 1 跑通无 crash。

---

### Phase 1：Prompt 增强 (90-120min)

#### 1.1 目标

当前 6 个 prompt 的核心问题：

| 节点 | 当前问题 | Re2 目标 |
|---|---|---|
| feasibility_assessor | 只传计数 (n_baseline=3)，LLM 无法区分领域和难度 | 传入 baseline/parallel 论文标题+摘要，LLM 可基于内容判断 |
| innovation_extractor | 只传 title+source，无摘要 | 传入 baseline/parallel 标题+摘要+方法标签 |
| sota_matcher | 只传 title+year，无摘要 | 传入 baseline 标题+摘要+年份+venue |
| narrative_builder | innovation 只截 50 字 | 传入完整 innovation 描述 + feasibility 详情 |
| optimization_advisor | 只传 verdict+计数，无 parallel 论文 | 传入 parallel 论文摘要表，实现 TODO-1 平行论文优化分析 |
| devils_advocate | feasibility 截 50 字，innovation 截 200 字 | 传入完整上下文（feasibility JSON + innovation JSON + narrative JSON） |

#### 1.2 实现规则

**每个 prompt 文件独立修改，改完立即验证，失败回滚。**

**通用规则**：
1. SYSTEM prompt 保持 ≤ 100 token（StepFun 约束，DeepSeek 不受此限但保持习惯）
2. USER_TEMPLATE 中论文数据用 JSON 传入，不用截断字符串
3. 每篇论文传入 `{"title": str, "abstract": str[:300], "year": str, "venue": str}`——摘要截 300 字防 token 爆炸
4. 论文数量上限 5 篇（baseline 5 + parallel 5 = 10 篇），超出截断
5. `[OUTPUT CONTRACT]` 保留

#### 1.3 逐文件修改

**修改 1：feasibility_assessor.py**

文件：`apps/api/app/services/agents/prompts/feasibility_assessor.py`

```python
SYSTEM = "你是开题可行性评估员。基于论文证据判断能不能保毕业。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

Baseline论文({n_baseline}篇):
{baselines_json}

Parallel论文({n_parallel}篇):
{parallels_json}

数据集: {n_dataset}个, 代码仓库: {n_repo}个

评估标准:
- feasible (70-100分): baseline≥2 + 有数据集 + 有repo
- risky (40-69分): baseline≥1 但数据集/repo不足
- not_recommended (0-39分): 无baseline或题目过于宽泛

输出JSON: {{"verdict":"feasible|risky|not_recommended","score":0-100,"reason":"<=100字，引用具体论文","100_plus_formula":{{"baseline_weight":0,"module_weights":[],"estimated_total":0,"assessment":"足够毕业|勉强|不足"}},"degradation_paths":["具体退化路线"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""

import json as _json

def build(topic: str, baselines: list, parallels: list, n_dataset: int, n_repo: int) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""), "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
                 "year": i.get("year", ""), "venue": i.get("venue", i.get("source", ""))}
                for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        n_baseline=len(baselines), baselines_json=_json.dumps(slim(baselines), ensure_ascii=False),
        n_parallel=len(parallels), parallels_json=_json.dumps(slim(parallels), ensure_ascii=False),
        n_dataset=n_dataset, n_repo=n_repo)}
```

同步修改 node 函数签名：

文件：`apps/api/app/services/agents/graph/nodes/feasibility_assessor.py`

```python
# 旧：
built = P.build(topic, n_baseline, n_parallel, n_dataset, n_repo)

# 新：
baselines = state.get("baseline_candidates") or []
parallels = state.get("parallel_candidates") or []
built = P.build(topic, baselines, parallels, n_dataset, n_repo)
```

验证：运行 case 1 (ENG-THESIS-074)。
- [ ] feasibility_report.verdict 不是固定的 "risky"。
- [ ] feasibility_report.reason 引用了具体论文标题或方法。
- [ ] feasibility_report.score 与 baseline 数量正相关。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

**修改 2：innovation_extractor.py**

文件：`apps/api/app/services/agents/prompts/innovation_extractor.py`

```python
SYSTEM = "你是学术裁缝专家。从baseline和parallel论文中提取可缝合模块。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

Baseline论文(复现目标):
{baselines_json}

Parallel论文(改进参考):
{parallels_json}

任务:
1. 分析每个baseline用了什么方法组件
2. 分析每个parallel做了什么改进
3. 找出可缝合的模块组合(A+B+C方案)
4. 评估缝合难度

输出JSON:
{{"innovation_points":[{{"description":"具体创新描述","baseline_used":"baseline论文标题","stitched_modules":["模块A","模块B"],"stitching_plan":"具体步骤","estimated_difficulty":"低|中|高","evidence_ref":"论文标题"}}],
"stitching_plan":{{"baseline_model":"模型名","module_b":"模块B来源","module_c":"模块C来源","stitching_steps":["1. 复现baseline","2. 提取模块B","3. 拼接测试"],"risk_notes":["具体风险"]}}}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""
```

验证：运行 case 1。
- [ ] innovation_points ≥ 1。
- [ ] innovation_points[0].description 不是泛泛的"借鉴XX模块"，而是引用了具体论文。
- [ ] stitching_plan.stitching_steps 有 ≥ 3 步具体操作。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

**修改 3：sota_matcher.py**

文件：`apps/api/app/services/agents/prompts/sota_matcher.py`

```python
SYSTEM = "你是实验设计顾问。选SOTA对比论文+给消融建议。保毕业档。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

Baseline论文(可选对比基线):
{baselines_json}

任务:
1. 选3篇作为对比基线
2. 推荐对比指标
3. 给3个消融实验建议
4. 给实验检查清单

输出JSON:
{{"comparison_papers":[{{"title":"论文标题","year":"年份","reason":"为什么选它对比"}}],
"metrics_to_compare":["指标名"],
"ablation_suggestions":[{{"name":"消融实验名","purpose":"验证什么","expected_drop":"预期降幅"}}],
"experiment_checklist":["实验项"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""
```

验证：运行 case 1。
- [ ] comparison_papers 有 3 篇，每篇有 reason。
- [ ] ablation_suggestions 有 ≥ 3 个。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

**修改 4：narrative_builder.py**

文件：`apps/api/app/services/agents/prompts/narrative_builder.py`

```python
SYSTEM = "你是论文叙事生成器。基于创新点和可行性生成3个问题+1个模型名。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

创新点:
{innovations_json}

可行性报告:
{feasibility_json}

任务:
1. 基于创新点提炼3个研究问题(每个问题必须引用具体论文)
2. 起一个模型昵称
3. 写200字叙事摘要
4. 给5章大纲

输出JSON:
{{"three_problems":[{{"problem":"问题描述","evidence":"证据","from_paper":"论文标题"}}],
"nick_model_name":"模型名",
"narrative_summary":"<=200字",
"chapter_outline":{{"chapter_1":{{"title":"绪论","sections":["研究背景","国内外现状","研究内容"]}}}},
"abstract_draft":"摘要草稿"}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""

import json as _json

def build(topic: str, innovations: list, feasibility: dict) -> dict[str, str]:
    inn_slim = [{"description": i.get("description", ""), "baseline_used": i.get("baseline_used", ""),
                 "stitched_modules": i.get("stitched_modules", [])} for i in innovations[:3]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        innovations_json=_json.dumps(inn_slim, ensure_ascii=False),
        feasibility_json=_json.dumps(feasibility, ensure_ascii=False)[:500])}
```

同步修改 node 函数：

文件：`apps/api/app/services/agents/graph/nodes/narrative_builder.py`

```python
# 旧：
built = P.build(topic, innovations, feasibility)

# 新（签名不变，但 P.build 内部已改）：
built = P.build(topic, innovations, feasibility)
```

验证：运行 case 1。
- [ ] three_problems 有 3 个问题。
- [ ] 每个问题的 from_paper 引用了具体论文标题。
- [ ] narrative_summary 长度 > 50 字。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

**修改 5：optimization_advisor.py**（含 TODO-1 平行论文优化分析）

文件：`apps/api/app/services/agents/prompts/optimization_advisor.py`

```python
SYSTEM = "你是研究方向优化顾问。基于平行论文对比给优化方向和退化路线。保毕业导向。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

可行性: {feasibility_json}

创新点数: {n_innovation}

Baseline论文:
{baselines_json}

Parallel论文(做了类似工作的论文):
{parallels_json}

任务:
1. 对比parallel论文的方法/数据集差异，找出当前题目可借鉴的方向
2. 基于 feasibility verdict 给优化路径或退化路线
3. 给风险缓解措施

输出JSON:
{{"optimization_paths":[{{"direction":"具体方向","expected_gain":"预期收益","difficulty":"低|中|高","action_items":["具体操作"],"ref_parallel":"参考的parallel论文标题"}}],
"degradation_paths":[{{"path":"退化路线","trade_off":"代价","survival_rate":"高|中|极高"}}],
"risk_mitigation":["具体措施"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""

import json as _json

def build(topic: str, feasibility: dict, innovations: list, baselines: list, parallels: list) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""), "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
                 "year": i.get("year", "")} for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        feasibility_json=_json.dumps({"verdict": feasibility.get("verdict", ""), "score": feasibility.get("score", 0)}, ensure_ascii=False),
        n_innovation=len(innovations),
        baselines_json=_json.dumps(slim(baselines), ensure_ascii=False),
        parallels_json=_json.dumps(slim(parallels), ensure_ascii=False))}
```

同步修改 node 函数签名：

文件：`apps/api/app/services/agents/graph/nodes/optimization_advisor.py`

```python
# 旧：
built = P.build(topic, feasibility, len(innovations), n_baseline)

# 新：
baselines = state.get("baseline_candidates") or []
parallels = state.get("parallel_candidates") or []
built = P.build(topic, feasibility, innovations, baselines, parallels)
```

验证：运行 case 1。
- [ ] optimization_paths ≥ 1，每条有 direction 和 action_items。
- [ ] optimization_paths[0].ref_parallel 引用了具体 parallel 论文标题（TODO-1 验证）。
- [ ] degradation_paths ≥ 1。
- [ ] risk_mitigation ≥ 2 条。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

**修改 6：devils_advocate_graph.py**

文件：`apps/api/app/services/agents/prompts/devils_advocate_graph.py`

```python
SYSTEM = "你是论文开题审查员。5维评分。根据证据充分性区分 verdict。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

可行性报告:
{feasibility_json}

创新点:
{innovations_json}

叙事:
{narrative_json}

工作包:
{work_packages_json}

5维评分(0-10):
- D1原创性: 是否真的发现了gap，还是硬凑
- D2方法学严谨性: baseline选择是否合理
- D3证据充分性: baseline≥2 + parallel≥2 + dataset≥1 → PASS; 否则 WARN/BLOCK
- D4论证连贯性: 3个问题是否真的被模块解决
- D5写作质量: 叙事是否自洽，有无过度宣传

verdict判定规则:
- 有baseline≥2 + work_package≥1 → ACCEPT 或 MINOR_REVISION
- 有baseline≥1 但work_package=0 → MINOR_REVISION
- 无baseline → BLOCK

输出JSON:
{{"dimension_scores":[{{"dimension":"D1","score":0,"verdict":"PASS|WARN|BLOCK","reason":"具体原因"}}],
"overall_verdict":"ACCEPT|MINOR_REVISION|BLOCK",
"fabrication_alerts":["如有编造"],
"risks_identified":["具体风险"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no prose, no fences."""

import json as _json

def build(topic: str, feasibility: dict, innovations: list, narrative: dict, work_packages: list) -> dict[str, str]:
    feas_slim = {"verdict": feasibility.get("verdict", ""), "score": feasibility.get("score", 0),
                 "reason": feasibility.get("reason", "")}
    inn_slim = [{"description": i.get("description", ""), "baseline_used": i.get("baseline_used", "")}
                for i in innovations[:3]]
    nar_slim = {"three_problems": narrative.get("three_problems", []),
                "nick_model_name": narrative.get("nick_model_name", ""),
                "narrative_summary": narrative.get("narrative_summary", "")}
    wp_slim = [{"title": w.get("title", ""), "description": w.get("description", "")}
               for w in work_packages[:3]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        feasibility_json=_json.dumps(feas_slim, ensure_ascii=False),
        innovations_json=_json.dumps(inn_slim, ensure_ascii=False),
        narrative_json=_json.dumps(nar_slim, ensure_ascii=False),
        work_packages_json=_json.dumps(wp_slim, ensure_ascii=False))}
```

验证：运行 case 1 和 case 3 (ENG-THESIS-046)。
- [ ] case 1 (低-中难度) 的 overall_verdict 不是 BLOCK（应为 ACCEPT 或 MINOR_REVISION）。
- [ ] case 3 (高难度) 的 overall_verdict 可能是 BLOCK 或 MINOR_REVISION。
- [ ] 两个 case 的 dimension_scores 有不同的 score。
- [ ] 如果 case 3 触发 MINOR_REVISION → Phase 0 的条件边应将路由回到 narrative_builder。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

#### 1.4 验证

- [ ] 6 个 prompt 文件已修改。
- [ ] 6 个 node 文件的签名同步修改（如有需要）。
- [ ] `changelog.md` 记录了每次改动和验证结果。
- [ ] case 1 跑通，feasibility/innovation/narrative/optimization/devils_advocate 的输出有实质内容。
- [ ] case 3 跑通，devils_advocate 不总是 BLOCK。

#### 1.5 检查清单

- [ ] feasibility_assessor prompt 传入 baseline/parallel 论文摘要。
- [ ] innovation_extractor prompt 传入 baseline/parallel 论文摘要。
- [ ] sota_matcher prompt 传入 baseline 论文摘要。
- [ ] narrative_builder prompt 传入完整 innovation JSON + feasibility JSON。
- [ ] optimization_advisor prompt 传入 parallel 论文摘要（TODO-1）。
- [ ] devils_advocate prompt 传入完整 feasibility/innovation/narrative/work_packages JSON。
- [ ] 所有 prompt 的 `[OUTPUT CONTRACT]` 保留。
- [ ] 所有 prompt 的 SYSTEM ≤ 100 token。
- [ ] case 1 和 case 3 的输出有区分度。

---

### Phase 2：性能优化 (45-60min)

#### 2.1 目标

1. **innovation_extractor + sota_matcher 并行执行**——sota 不依赖 innovation 输出，可并行
2. **节点超时配置**——从硬编码 timeout=30 改为可配置

#### 2.2 实现步骤

**步骤 1：innovation_extractor + sota_matcher 并行**

文件：`apps/api/app/services/agents/graph/research_graph.py`

LangGraph 的并行方式：两个节点都从 `work_package` 出发，汇聚到 `narrative_builder`。

```python
# 旧：
graph.add_edge("work_package", "innovation_extractor")
graph.add_edge("innovation_extractor", "sota_matcher")
graph.add_edge("sota_matcher", "narrative_builder")

# 新：
graph.add_edge("work_package", "innovation_extractor")
graph.add_edge("work_package", "sota_matcher")
graph.add_edge("innovation_extractor", "narrative_builder")
graph.add_edge("sota_matcher", "narrative_builder")
```

LangGraph 会自动并行执行 innovation_extractor 和 sota_matcher（两者都从 work_package 出发），narrative_builder 等两者都完成后才执行。

验证：运行 case 1。
- [ ] graph 完成无 crash。
- [ ] trace_events 中 innovation_extractor 和 sota_matcher 的 started_at 时间接近（并行启动）。
- [ ] narrative_builder 在两者都完成后才执行。
- [ ] 总耗时比串行减少（innovation ~20s + sota ~15s → 并行 ~20s）。
- [ ] 如果验证失败 → `git checkout` → 记录 → 保持串行。

**步骤 2：节点超时配置**

文件：`apps/api/app/services/agents/graph/research_graph.py`

在文件顶部添加：

```python
NODE_TIMEOUTS = {
    "topic_parser": 30,
    "verify": 45,
    "dataset_repo_extractor": 30,
    "feasibility_assessor": 20,
    "work_package": 30,
    "innovation_extractor": 30,
    "sota_matcher": 20,
    "narrative_builder": 45,
    "optimization_advisor": 20,
    "devils_advocate": 30,
}
```

注意：各节点当前硬编码 `timeout=30`。改为从 `NODE_TIMEOUTS` 读取需要修改每个 node 文件。

**简化方案**：不修改每个 node 文件，而是在 `llm_router.call_json` 的默认 timeout 中读取环境变量：

```python
# 各 node 文件中的 timeout=30 改为：
timeout=int(os.environ.get("NODE_TIMEOUT_DEFAULT", "30"))
```

或者更简单：**不修改 node 文件**，只在 `research_graph.py` 中定义 `NODE_TIMEOUTS` 供未来使用，当前保持 `timeout=30`。记录为"已定义但未接入"。

验证：
- [ ] `NODE_TIMEOUTS` 定义存在。
- [ ] case 1 跑通（并行化不影响正确性）。
- [ ] 如果并行化导致 crash → 回滚 → 保持串行 → 记录原因。

#### 2.3 验证

- [ ] innovation_extractor 和 sota_matcher 并行执行（或已回滚记录原因）。
- [ ] `NODE_TIMEOUTS` 已定义（或已记录"保持硬编码"）。
- [ ] case 1 总耗时 ≤ Phase 0 的耗时（并行化生效）或持平（回滚）。

#### 2.4 检查清单

- [ ] innovation_extractor 和 sota_matcher 从 work_package 并行出发。
- [ ] narrative_builder 等待两者完成。
- [ ] NODE_TIMEOUTS 已定义。
- [ ] case 1 跑通无 crash。
- [ ] 如果回滚 → changelog.md 记录了原因。

---

### Phase 3：E2E 验证 (60-90min)

#### 3.1 目标

用 3 个代表性 case 验证 Phase 0 + Phase 1 + Phase 2 的全部改动。

#### 3.2 运行

```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 18182
```

串行跑 3 个 case：

| # | Case | 题目 | 验证重点 |
|---|---|---|---|
| 1 | ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 正常路径：feasibility → work_package → innovation ∥ sota → narrative → devils → ACCEPT |
| 2 | ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | Prompt 增强：feasibility reason 引用论文，innovation 有具体缝合方案 |
| 3 | ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | 条件边：devils_advocate 可能 MINOR_REVISION → narrative_builder 回环 |

每个 case 完成后保存 state.json + trace.json 到 `tmp_re2_eval/<case_id>/`。

#### 3.3 自动验证

对每个 case 跑 validator：

```python
python -c "
import json, sys
sys.path.insert(0, '.')
from tests.self_test.e2e_completeness_validator import validate as e2e
from tests.self_test.paper_authenticity_validator import validate as auth
from tests.self_test.topic_relevance_validator import validate as rel

state = json.load(open('tmp_re2_eval/<case_id>/state.json'))
print('E2E:', e2e(state))
print('Auth:', auth(state))
print('Relevance:', rel(state))
"
```

#### 3.4 验证标准

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | 3 个 case 都完成（final_recommendation 非空） | state.json 检查 |
| 2 | case 1: e2e_completeness pass | validator |
| 3 | case 1: paper_authenticity pass | validator |
| 4 | case 1: feasibility reason 引用了具体论文 | 人工检查 state.json |
| 5 | case 1: innovation_points 有具体缝合方案（不是泛泛"借鉴XX"） | 人工检查 |
| 6 | case 1: devils_advocate overall_verdict 不是固定 BLOCK | 人工检查 |
| 7 | case 1: optimization_paths 引用了 parallel 论文 | 人工检查（TODO-1 验证）|
| 8 | case 2: feasibility score 与 case 1 不同 | 对比 |
| 9 | case 3: 如果 devils_advocate = MINOR_REVISION → trace 有 narrative_builder 二次出现 | trace.json 检查 |
| 10 | case 3: narrative_revision_count ≤ 2 | state.json 检查 |
| 11 | innovation_extractor 和 sota_matcher 并行（trace 时间戳接近） | trace.json 检查 |

#### 3.5 检查清单

- [ ] 3 个 case 的 state.json + trace.json 已保存。
- [ ] e2e_completeness ≥ 2/3 pass。
- [ ] paper_authenticity 3/3 pass。
- [ ] feasibility 有区分度（case 1 vs case 3 score 差 ≥ 20）。
- [ ] devils_advocate 不总是 BLOCK。
- [ ] optimization_paths 引用了 parallel 论文。
- [ ] 条件边路由生效（如有 MINOR_REVISION 则有回环 trace）。
- [ ] 并行化生效（innovation + sota 时间戳接近）或已回滚记录。

---

### Phase 4：汇总报告 (30min)

#### 4.1 报告内容

文件：`Plan/PaperAgent_Re2_完工报告.md`

```markdown
# PaperAgent Re2 完工报告

## 1. 条件边路由
- _route_after_feasibility: ✅/❌
- _route_after_devils: ✅/❌
- MAX_NARRATIVE_REVISIONS: ✅/❌
- 回环验证: ✅/❌ (case 3 是否触发回环)

## 2. Prompt 增强
| 节点 | 修改前 | 修改后 | 验证 |
|---|---|---|---|
| feasibility_assessor | 只传计数 | 传 baseline/parallel 摘要 | ✅/❌ |
| innovation_extractor | 只传 title | 传摘要+方法标签 | ✅/❌ |
| sota_matcher | 只传 title+year | 传摘要+venue | ✅/❌ |
| narrative_builder | innovation 截 50 字 | 传完整 JSON | ✅/❌ |
| optimization_advisor | 只传 verdict+计数 | 传 parallel 摘要 (TODO-1) | ✅/❌ |
| devils_advocate | 截断 50-200 字 | 传完整 JSON | ✅/❌ |

## 3. 性能优化
- innovation ∥ sota 并行: ✅/❌
- NODE_TIMEOUTS 定义: ✅/❌
- 耗时对比 (串行 vs 并行): Xs → Ys

## 4. E2E 验证结果
| Case | 领域 | 难度 | feasibility | innovation | devils | 完成 |
|---|---|---|---|---|---|---|
| ENG-THESIS-074 | 土木 | 低-中 | ... | ... | ... | ✅ |
| ENG-THESIS-016 | SLAM | 中-高 | ... | ... | ... | ✅ |
| ENG-THESIS-046 | 机器人 | 高 | ... | ... | ... | ✅ |

## 5. Validator 结果
- e2e_completeness: X/3 pass
- paper_authenticity: X/3 pass
- topic_relevance: X/3 pass

## 6. 已知限制
- 哪些 prompt 修改失败已回滚
- 并行化是否成功
- 条件边是否触发回环

## 7. changelog.md 引用
```

#### 4.2 检查清单

- [ ] 完工报告包含条件边路由状态。
- [ ] 完工报告包含 prompt 增强对比表。
- [ ] 完工报告包含性能优化结果。
- [ ] 完工报告包含 3 case 验证表。
- [ ] 完工报告包含 validator 结果。
- [ ] 完工报告包含已知限制。
- [ ] 完工报告包含 changelog.md 引用。

---

## 4. 交付物

代码：

- `apps/api/app/services/agents/graph/state.py` 🔧 (narrative_revision_count)
- `apps/api/app/services/agents/graph/research_graph.py` 🔧 (条件边 + 并行 + NODE_TIMEOUTS)
- `apps/api/app/services/agents/graph/nodes/feasibility_assessor.py` 🔧 (传论文数据)
- `apps/api/app/services/agents/graph/nodes/innovation_extractor.py` (prompt 签名不变)
- `apps/api/app/services/agents/graph/nodes/sota_matcher.py` (prompt 签名不变)
- `apps/api/app/services/agents/graph/nodes/narrative_builder.py` 🔧 (revision counter)
- `apps/api/app/services/agents/graph/nodes/optimization_advisor.py` 🔧 (传 parallel 数据 + revision counter)
- `apps/api/app/services/agents/graph/nodes/devils_advocate_node.py` (prompt 签名不变)
- `apps/api/app/services/agents/prompts/feasibility_assessor.py` 🔧
- `apps/api/app/services/agents/prompts/innovation_extractor.py` 🔧
- `apps/api/app/services/agents/prompts/sota_matcher.py` 🔧
- `apps/api/app/services/agents/prompts/narrative_builder.py` 🔧
- `apps/api/app/services/agents/prompts/optimization_advisor.py` 🔧
- `apps/api/app/services/agents/prompts/devils_advocate_graph.py` 🔧

数据：

- `tmp_re2_eval/ENG-THESIS-074/` (state.json + trace.json)
- `tmp_re2_eval/ENG-THESIS-016/` (state.json + trace.json)
- `tmp_re2_eval/ENG-THESIS-046/` (state.json + trace.json)
- `tmp_re2_eval/changelog.md`

报告：

- `Plan/PaperAgent_Re2_完工报告.md`

---

## 5. 执行者自测检查清单

> **执行 AI 在每个 Phase 结束后必须逐项确认。**

### Phase 0 检查

- [ ] `state.py` 有 `narrative_revision_count` 字段。
- [ ] `research_graph.py` 有 `_route_after_feasibility`。
- [ ] `research_graph.py` 有 `_route_after_devils`。
- [ ] `research_graph.py` 有 `MAX_NARRATIVE_REVISIONS = 2`。
- [ ] `feasibility_assessor` 使用条件边。
- [ ] `devils_advocate` 使用条件边。
- [ ] `narrative_builder.py` 递增 revision counter。
- [ ] `optimization_advisor.py` 递增 revision counter。
- [ ] 重复 `add_edge` 已删除。
- [ ] case 1 跑通无 crash。

### Phase 1 检查

- [ ] 6 个 prompt 文件已修改。
- [ ] feasibility prompt 传论文摘要。
- [ ] innovation prompt 传论文摘要。
- [ ] sota prompt 传论文摘要。
- [ ] narrative prompt 传完整 JSON。
- [ ] optimization prompt 传 parallel 摘要（TODO-1）。
- [ ] devils_advocate prompt 传完整 JSON。
- [ ] case 1 feasibility reason 引用论文。
- [ ] case 1 devils_advocate 不总是 BLOCK。
- [ ] case 1 optimization 引用 parallel 论文。

### Phase 2 检查

- [ ] innovation + sota 并行（或回滚记录）。
- [ ] NODE_TIMEOUTS 已定义。
- [ ] case 1 跑通无 crash。
- [ ] 耗时 ≤ Phase 0 耗时（或持平 + 记录原因）。

### Phase 3 检查

- [ ] 3 个 case 的 state.json + trace.json 已保存。
- [ ] e2e_completeness ≥ 2/3 pass。
- [ ] paper_authenticity 3/3 pass。
- [ ] feasibility 有区分度。
- [ ] devils_advocate 不总是 BLOCK。
- [ ] optimization 引用 parallel 论文。
- [ ] 条件边生效（如有回环）。
- [ ] 并行生效（或回滚记录）。

### Phase 4 检查

- [ ] 完工报告包含条件边状态。
- [ ] 完工报告包含 prompt 增强对比表。
- [ ] 完工报告包含性能优化结果。
- [ ] 完工报告包含 3 case 验证表。
- [ ] 完工报告包含 validator 结果。
- [ ] 完工报告包含已知限制。
- [ ] 完工报告包含 changelog 引用。

---

## 6. 禁止事项

- 禁止同时改多个文件（每次只改一个，验证后再改下一个）。
- 禁止改完代码不验证就继续（必须重跑 1 个 case）。
- 禁止验证失败不回滚（必须 `git checkout` 回滚）。
- 禁止连续 3 次 crash 后继续跑（停止当前 Phase，跳到下一个）。
- 禁止用 VOAPI / MiniMax。
- 禁止覆盖 `tmp_re14_eval/` / `tmp_re15_eval/`。
- 禁止用 mock 数据做验证。
- 禁止跳过 Phase 0 / Phase 1 / Phase 3 / Phase 4。

---

## 7. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | `_route_after_feasibility` 存在且生效 | Phase 0 case 1 |
| 2 | `_route_after_devils` 存在且生效 | Phase 0 case 1 |
| 3 | `narrative_revision_count` 存在 | state.json |
| 4 | revision 回环不超过 2 次 | state.json |
| 5 | feasibility prompt 传论文摘要 | prompt 文件检查 |
| 6 | optimization prompt 传 parallel 摘要 | prompt 文件检查 (TODO-1) |
| 7 | devils_advocate prompt 传完整 JSON | prompt 文件检查 |
| 8 | devils_advocate 不总是 BLOCK | case 1 + case 3 对比 |
| 9 | innovation + sota 并行（或回滚记录） | trace 时间戳 |
| 10 | 3 case 完成 | state.json |
| 11 | e2e_completeness ≥ 2/3 | validator |
| 12 | paper_authenticity 3/3 | validator |
| 13 | feasibility 有区分度 | case 1 vs case 3 score 差 ≥ 20 |
| 14 | optimization 引用 parallel 论文 | 人工检查 |
| 15 | 完工报告完整 | Phase 4 |
| 16 | changelog 记录所有改动 | Phase 1-2 |
