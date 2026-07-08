# PaperAgent Re3.0 全链路重新设计 SOP

> 承接：Re2.4 审核完成
> **本 SOP 是全链路重新设计，不是补丁。**
> 预计总时长：8-10 小时，分 7 个 Phase，每个 Phase 有验证门控。
> 模型：DeepSeek (主)。

## 0. 全系统审计发现的致命问题

### 0.0 参考项目（执行者必读）

本 SOP 的 React/Reflection 设计参考以下两个项目。执行者必须在 Phase 3/4 之前阅读对应文件：

**AutoResearchClaw (ARC)** — `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`
- 23 阶段状态机，有 PIVOT/REFINE 策略切换、StageContract、gate rollback
- 撞墙时先读 `researchclaw/pipeline/_helpers.py` 的 `_safe_json_loads` 和 `_chat_with_prompt`

**academic-research-skills (ARS)** — `C:\Users\ZYF\Desktop\Paper\academic-research-skills`
- 13 agent + 6 phase，有 3 checkpoint Devil's Advocate、evidence sufficiency gate、failure paths 策略切换
- prompt 工程参考 `shared/ground_truth_isolation_pattern.md`

**B站毕业论文合集** — 设计文档 `docs/design/PaperAgent_Re2_FullChain_Design.md` §1.3
- 100+1+1+1 可行性公式、学术裁缝 A+B+C、Research Gap 5 类型

### 0.1 链路断裂（导致返回垃圾）

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 1 | **retrieve 第一次不用 search_plan** | retrieve.py L243: `search_plan = state.get("search_plan") if repair_rounds > 0 else None` | search_planner 生成的正确查询词被完全忽略，retrieve 自己从 atoms 重建查询 |
| 2 | **`len(q) > 5` 过滤短关键词** | retrieve.py L68 | "YOLO"(4)、"crop"(4)、"SLAM"(4)、"GAN"(3) 被丢弃 |
| 3 | **硬编码 `"deep learning"` fallback** | retrieve.py L62, L79; search_planner.py L202 | 过滤后 queries 为空 → fallback 到 "deep learning" → 全是垃圾 |
| 4 | **domain_map 只有 5 个 domain，缺 vision_2d 等** | retrieve.py L72-78 | 11 个 allowed domain 中 6 个会 fallback 到 "deep learning" |

### 0.2 数据丢失（导致分析节点输入为空）

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 5 | **`research_narratives` vs `research_narrative` 字段名不匹配** | narrative_builder 返回 `research_narratives`(复数)，state 定义 `research_narrative`(单数) | **叙事数据永远丢失**，devils_advocate 永远收到空叙事 |
| 6 | **revision_count 双重递增** | narrative_builder 和 optimization_advisor 都递增 `narrative_revision_count` | MAX=2 实际只允许 1 次修订循环 |
| 7 | **weak_papers 被 quality_gate 清空** | quality_gate promote 后返回 `weak_papers: []` | 审计轨迹丢失 |

### 0.3 没有 React/Reflection（参考项目有，没照抄）

| # | 问题 | 参考项目怎么做的 | 当前系统 |
|---|---|---|---|
| 8 | **搜索策略不会切换** | ARS: 英文搜空 → 切中文数据库；ARC: PIVOT(换策略) vs REFINE(重试) | 只重试同样的查询词，不换策略 |
| 9 | **没有 evidence sufficiency gate** | ARS: `<5 sources → re-search with alternative keywords` | quality_gate 只看数量，不看质量 |
| 10 | **LLM 不参与搜索决策** | ARC: Stage 3 SEARCH_STRATEGY 用 LLM 决定搜什么 | `PAPERAGENT_SKIP_SEARCH_PLANNER=true` → LLM planner 永远不调用 |
| 11 | **没有思考→调用→观察循环** | ARC: diagnose → fix → re-run → re-assess 循环 | retrieve 是单次调用，不观察结果决定是否继续 |

## 1. 本轮目标

**全链路重新设计，让 agent 有 React + Reflection 能力。**

必须完成：

1. **搜索链路修复**：retrieve 用 search_plan 的查询词；删除硬编码 fallback；删除 len 过滤。
2. **数据流修复**：修复 research_narrative 字段名；修复 revision_count 双重递增。
3. **React 范式**：retrieve 节点改为"思考→调用→观察"循环——LLM 决定搜什么、观察结果、决定是否继续。
4. **Reflection 范式**：搜索结果不足时自动切换策略（换关键词/换工具/扩大范围），不是简单重试。
5. **100 篇抽样验证**：从 100 篇中选 10 个不同领域的题目，每个步骤验证。
6. **自查门控**：每个 Phase 结束后跑 validator，不通过不进入下一 Phase。

不做：

- 前端改动（Re2.4 前端够用）。
- Docker / 部署。
- 新增分析节点。

## 2. 设计原则

### 2.1 禁止硬编码

- **禁止任何 fallback 到 "deep learning" 或其他固定字符串。**
- 如果 queries 为空 → 用 topic 原文作为查询词（不是 "deep learning"）。
- 如果 topic 也是空 → 报错，不 fallback。

### 2.2 React 范式（照抄 ARC）

```
LLM 思考: "题目是 YOLO 农作物识别。我需要搜 arxiv 找 YOLO + crop 的论文。"
  ↓
工具调用: arxiv_search("YOLO crop recognition")
  ↓
观察: "返回 8 篇，其中 3 篇关于农作物检测。还不够，我需要更多 baseline。"
  ↓
LLM 思考: "我需要搜 GitHub 找 YOLO 农作物相关的 repo。"
  ↓
工具调用: github_search("YOLO crop detection")
  ↓
观察: "返回 5 个 repo，其中 2 个可直接使用。够了，停止搜索。"
  ↓
输出: 13 篇论文 + 2 个 repo
```

### 2.3 Reflection 范式（照抄 ARS + ARC）

```
搜索结果不足 (< 3 verified)?
  ↓
Reflection: "当前查询词 'YOLO crop' 返回太少。"
  ↓
策略切换 (不是简单重试):
  - 换关键词: "YOLO agriculture" → "YOLO plant detection" → "object detection crop"
  - 换工具: OpenAlex 429 → 增加 Crossref top_k
  - 扩大范围: "YOLO crop" → "YOLO" (更宽)
  ↓
最多 2 轮策略切换，之后仍不足 → 标记 "evidence insufficient" → blocked
```

### 2.4 验证门控

每个 Phase 结束后必须跑 3-case 验证。验证 case 从 100 篇中选不同领域：

| Case | 题目 | 领域 | 选原因 |
|---|---|---|---|
| V-YOLO | 基于yolo的农作物识别 | 工科AI | 之前返回全垃圾，验证修复 |
| V-SLAM | 基于深度学习的视觉SLAM语义地图的研究 | SLAM | 之前能跑通，验证不退化 |
| V-MED | 基于大语言模型的医学问答可信度评估方法研究 | NLP/医学 | 之前有 feasible + innovation，验证不退化 |

## 3. Phase 设计

### Phase 1：搜索链路修复 (1h)

#### Fix 1.1: retrieve.py — 始终使用 search_plan

```python
# 旧 (L243):
search_plan = state.get("search_plan") if repair_rounds > 0 else None

# 新:
search_plan = state.get("search_plan")  # 始终使用 search_planner 生成的查询词
```

#### Fix 1.2: retrieve.py — 删除 len(q) > 5 过滤

```python
# 旧 (L68):
queries = [q for q in dict.fromkeys(queries).keys() if len(q) > 5][:6]

# 新:
queries = [q for q in dict.fromkeys(queries).keys() if len(q) >= 2][:6]
```

#### Fix 1.3: retrieve.py — 删除硬编码 "deep learning" fallback

```python
# 旧 (L62):
head = (method[:2] + obj[:2]) or [topic.split()[0] if topic else "deep learning"]

# 新:
if not (method or obj):
    # atoms 为空时，用 topic 原文作为查询词
    head = [topic[:100]] if topic else []
else:
    # 组合查询: method + object
    head = []
    if method and obj:
        head.append(" ".join(method[:1] + obj[:1]))
    if len(method) > 1:
        head.append(method[1])
    if len(obj) > 1:
        head.append(obj[1])
```

#### Fix 1.4: retrieve.py — 删除 domain_map 硬编码

```python
# 旧 (L72-86):
domain_map = {
    "medical_ai": "deep learning medical AI",
    ...
}
fallback_q = domain_map.get(atoms["domain"], "deep learning")

# 新: 如果 queries 为空，用 topic 原文
if not queries:
    queries = [topic[:100]] if topic else []
    # 不再 fallback 到 "deep learning"
```

#### Fix 1.5: search_planner.py — 删除硬编码 "deep learning"

```python
# 旧 (L202):
head = (topic or "deep learning").split()[0]

# 新:
head = topic.split()[0] if topic else ""
```

#### 验证

3-case 验证：
- V-YOLO: retrieve queries 不含 "deep learning"，verified 中有标题含 "YOLO" 或 "crop" 的论文
- V-SLAM: 不退化
- V-MED: 不退化

### Phase 2：数据流修复 (30min)

#### Fix 2.1: research_narrative 字段名统一

**文件**：`apps/api/app/services/agents/graph/nodes/narrative_builder.py`

```python
# 旧: return {"research_narratives": result}
# 新: return {"research_narrative": result}
```

**文件**：`apps/api/app/services/agents/graph/nodes/devils_advocate_node.py`

```python
# 旧: state.get("research_narratives")
# 新: state.get("research_narrative")
```

**文件**：`apps/api/app/services/agents/graph/nodes/__init__.py`

```python
# 旧: "research_narratives"
# 新: "research_narrative"
```

**文件**：`apps/api/app/services/agents/graph/state.py`

确认字段名是 `research_narrative`（单数）。

#### Fix 2.2: revision_count 单一递增

**文件**：`apps/api/app/services/agents/graph/nodes/optimization_advisor.py`

```python
# 旧: "narrative_revision_count": current + 1
# 新: 不递增（只有 narrative_builder 递增）
```

#### 验证

3-case 验证：
- V-MED: devils_advocate 收到非空 narrative（修复 Fix 2.1）
- V-MED: narrative_revision_count 每次循环只 +1（修复 Fix 2.2）

### Phase 3：React 范式 — 搜索决策 Agent (2h)

#### 参考项目文件（执行者必须先读）

**ARC (AutoResearchClaw)**：
- 路径：`C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`
- 必读文件：
  - `researchclaw/pipeline/stages.py` — Stage 枚举 + GATE_ROLLBACK + DECISION_ROLLBACK (PIVOT vs REFINE)
  - `researchclaw/pipeline/_literature.py` — `_execute_search_strategy()` LLM 生成搜索计划 + `_expand_search_queries()` 自动扩展查询词
  - `researchclaw/pipeline/runner.py` — `execute_pipeline(from_stage=rollback_target)` 回滚执行 + 版本管理
  - `researchclaw/pipeline/contracts.py` — StageContract (input_files/output_files/dod/max_retries)
- 抄什么：
  - LLM 决定搜什么工具、什么查询词（不是固定调全部适配器）
  - 搜索后观察结果，不够就继续搜（思考→调用→观察循环）
  - PIVOT vs REFINE：换策略 vs 重试

**ARS (academic-research-skills)**：
- 路径：`C:\Users\ZYF\Desktop\Paper\academic-research-skills`
- 必读文件：
  - `shared/agents/deep-research/agents/research_question_agent.md` — 确定研究方向 + domain
  - `shared/agents/deep-research/agents/bibliography_agent.md` — 文献检索 + `<5 sources → expand search strategy`
  - `shared/agents/deep-research/agents/source_verification_agent.md` — 证据验证 (L1-L7 层级)
  - `shared/skills/deep-research/SKILL.md` — failure_paths 表（F2: 搜空 → 换关键词/换数据库）
  - `shared/agents/academic-paper-reviewer/agents/devils_advocate_reviewer_agent.md` — 3 checkpoint + CRITICAL/Major/Minor 分级
- 抄什么：
  - evidence sufficiency gate（`<5 sources → re-search with alternative keywords`）
  - 搜索策略切换（英文搜空 → 换中文数据库；关键词太窄 → 换同义词）
  - failure paths 表（每种失败有对应的策略切换方案）

#### 设计

将 retrieve 从"固定调用所有适配器"改为"LLM 决定搜什么"。

**新文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

```python
"""React-based search agent.

LLM decides which tools to call, observes results, decides whether to continue.
Inspired by ARC's SEARCH_STRATEGY stage.
"""

SYSTEM = """你是学术搜索策略师。根据题目和已有结果，决定下一步搜索什么。

可用工具:
- arxiv: 搜预印本论文
- openalex: 搜学术期刊论文
- crossref: 搜DOI注册论文
- github: 搜代码仓库
- semantic_solar: 搜高被引论文

判断标准:
- 如果还没有论文 → 搜 method+object 组合
- 如果论文太少 (<5) → 扩大范围或换关键词
- 如果论文够多 (≥5) 但没 repo → 搜 github
- 如果论文够多 + 有 repo → 停止

输出 JSON:
{"action": "search" | "stop", "tool": "arxiv|openalex|crossref|github|semantic_scholar", "query": "...", "reason": "..."}

如果搜索结果已经足够，输出:
{"action": "stop", "reason": "已有 N 篇论文 + M 个 repo，足够开始分析"}
"""

async def search_agent_node(state):
    """React 循环: 思考→调用→观察→决定。"""
    topic = state.get("topic", "")
    atoms = state.get("topic_atoms", {})
    
    # 从 search_plan 获取初始查询词
    search_plan = state.get("search_plan", {})
    plan_queries = {q["tool"]: q["query"] for q in search_plan.get("queries", [])}
    
    all_papers = []
    all_repos = []
    all_raw = {}
    steps = []
    max_steps = 8  # 最多 8 步工具调用
    
    for step_idx in range(max_steps):
        # 1. 思考: LLM 决定下一步
        thought = llm_decide(topic, atoms, all_papers, all_repos, steps)
        
        if thought["action"] == "stop":
            steps.append({"step": step_idx, "type": "stop", "reason": thought["reason"]})
            break
        
        tool = thought["tool"]
        query = thought["query"]
        
        # 2. 调用工具
        if tool in REGISTRY:
            results = await REGISTRY[tool]([query], 12)
        else:
            results = []
        
        # 3. 观察
        n_results = len(results)
        all_papers.extend([r for r in results if r.get("title")])
        all_raw.setdefault(tool, []).extend(results)
        
        steps.append({
            "step": step_idx,
            "type": "tool_call",
            "tool": tool,
            "query": query,
            "n_results": n_results,
            "reason": thought.get("reason", ""),
        })
    
    # 去重
    seen = set()
    unique_papers = []
    for p in all_papers:
        key = p.get("title", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique_papers.append(p)
    
    return {
        "paper_candidates": unique_papers,
        "raw_results": all_raw,
        "search_steps": steps,  # 新字段: 记录 React 循环
    }
```

**State 新增**：`search_steps: list[dict]` — 记录每步工具调用。

**Graph 改动**：`paper_retriever` 节点替换为 `search_agent`。

#### 验证

3-case 验证：
- V-YOLO: search_steps 中有 ≥2 步工具调用，不是一次调用所有适配器
- V-YOLO: paper_candidates 中有标题含 "YOLO" 或 "crop" 的论文
- V-SLAM: 不退化
- V-MED: 不退化

### Phase 4：Reflection 范式 — 策略切换 (1h)

#### 参考项目文件（执行者必须先读）

**ARC**：
- `researchclaw/pipeline/stages.py` — `DECISION_ROLLBACK = {"pivot": HYPOTHESIS_GEN, "refine": ITERATIVE_REFINE}`，`MAX_DECISION_PIVOTS = 2`
- `researchclaw/pipeline/runner.py` — `_consecutive_empty_metrics()` 连续空结果检测 → force PROCEED
- `researchclaw/pipeline/experiment_repair.py` — diagnose → fix → re-run → re-assess 循环

**ARS**：
- `shared/skills/deep-research/SKILL.md` — failure_paths 表：
  - F2: bibliography <5 sources → "Expand search strategy, alternative keywords, grey literature, relax time range, adjacent disciplines"
  - F8: English search empty → "Switch to Chinese academic databases"
  - F3: Methodology mismatch → "Return to Phase 1, suggest 3 alternative methods"

#### 设计

当 verify 返回 0 accept 且有候选论文时，targeted_repair 不只生成新查询词，而是**切换搜索策略**。

**修改文件**：`apps/api/app/services/agents/graph/nodes/targeted_repair.py`

参考 ARS 的 failure paths：
- 策略 1: 换关键词（"YOLO crop" → "YOLO agriculture" → "object detection crop"）
- 策略 2: 扩大范围（"YOLO crop" → "YOLO"）
- 策略 3: 换工具（OpenAlex 429 → 增加 Crossref top_k）

```python
SYSTEM = """你是搜索策略修复师。当前搜索结果不理想，需要切换策略。

策略选项:
1. 换关键词: 用同义词或更宽泛的词替换当前查询词
2. 扩大范围: 去掉限定词，只搜核心方法词
3. 换工具: 如果某适配器返回 0，尝试用其他适配器搜同样查询

当前状态:
- 题目: {topic}
- 已用查询词: {prior_queries}
- 各适配器返回数: {per_adapter}
- 失败适配器: {failed_adapters}
- verified 论文数: {n_verified}
- 候选论文数: {n_candidates}

输出 JSON:
{"strategy": "synonym|broaden|switch_tool", "queries": [{"tool": "...", "query": "..."}], "reason": "..."}
"""
```

**修改文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

在 repair 轮次中：
- 策略 "synonym": 用新关键词搜
- 策略 "broaden": 去掉限定词搜
- 策略 "switch_tool": 跳过失败适配器，给其他适配器增加 top_k

#### 验证

3-case 验证：
- V-YOLO: 如果第一轮 0 accept，repair 轮次使用不同查询词（不是重复 "YOLO crop"）
- V-SLAM: 不退化
- V-MED: 不退化

### Phase 4.5：标答 ground truth（已完成，直接使用）

标答文件已生成并通过 arxiv.org + GitHub API 验证：

**文件**：`tmp_re30_eval/ground_truth/verified_ground_truth.json`

包含 10 个领域的预期 keywords、baselines（真实论文）、datasets、repos、feasibility。执行者直接读取此文件做对比，不需要自己生成。

标答不是绝对真值，每次搜索结果不同。但标答提供了一个"这个题目应该搜到什么方向"的锚点。如果 PaperAgent 的搜索方向与标答完全不同（如标答说应该搜 YOLO+crop，但 PaperAgent 搜了 deep learning），就是搜索退化。

标答对比方法见 §4.3 自查标准的"标答对比"部分。

### Phase 5：渐进式验证 (4h)

**不要一开始就跑 20 篇。先跑 3 篇稳定基础，再逐篇排查链路问题，全部通了再全量。**

#### 5.1 冒烟测试：3 篇快速验证 (30min)

选 3 个已知能跑通的题目，验证 Phase 1-4 的修复没有引入退化：

| # | 题目 | 领域 | 选原因 |
|---|---|---|---|
| 1 | 基于深度学习的视觉SLAM语义地图的研究 | SLAM | Re2.3 有 6 accept，验证不退化 |
| 2 | 基于大语言模型的医学问答可信度评估方法研究 | NLP/医学 | Re2.3 有 feasible(75)，验证不退化 |
| 3 | 基于yolo的农作物识别 | 工科AI | 之前返回全垃圾，验证修复 |

跑完后按 §4.3 规则自查。**3 篇全部通过才继续 5.2。如果有问题，先修再继续。**

#### 5.2 逐篇链路排查 (2h)

从 100 篇中选不同领域的题目，**1 篇 1 篇跑**，每篇跑完后检查链路每个环节：

| # | 题目 | 领域 | 重点排查 |
|---|---|---|---|
| 4 | 基于深度学习的钢铁表面缺陷检测研究 | 工业缺陷 | arxiv 上论文少，验证搜索是否退化 |
| 5 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木 | 验证 Crossref 返回质量 |
| 6 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | 电力巡检 | 验证 GitHub repo 提取 |
| 7 | 基于深度学习的交通标志检测与识别研究 | 自动驾驶 | 验证 dataset 提取 |
| 8 | 基于YOLOV5的肺结节检测算法研究 | 医学 | 验证高难度题目的 feasibility |

每篇跑完后的排查流程：

```
跑完 1 篇
  ↓
按 §4.3 规则自查
  ↓
发现问题?
  ├── 搜索不好（查询词退化/结果不相关）
  │   ↓
  │   保持输入不变，检查:
  │   1. topic_parser 提取的 method/object/task 对不对？
  │   2. search_planner 生成的查询词对不对？
  │   3. retrieve 实际用了什么查询词？（trace 的 tool_calls）
  │   4. 如果查询词不对 → 修 search_planner/retrieve，重跑这一篇
  │   5. 如果查询词对但结果不好 → 检查适配器返回（OpenAlex 429? Crossref 质量?）
  │
  ├── 提取问题（有论文但 0 repo / 0 dataset）
  │   ↓
  │   把论文标题直接喂给 dataset_repo_extractor，看它能不能提取:
  │   1. 论文摘要中提到的 GitHub URL
  │   2. 论文摘要中提到的 dataset 名（如 NEU-DET、KITTI）
  │   3. 如果提取不到 → 修 dataset_repo_extractor prompt，重跑这一篇
  │
  ├── verify 问题（有候选但 0 accept）
  │   ↓
  │   检查 verify 的 reason 字段:
  │   1. verify 是不是太严格？（全 weak_reject）
  │   2. verify prompt 的判断标准对不对？
  │   3. 如果 verify 过于严格 → 修 verify prompt，重跑这一篇
  │
  └── 没问题 → 继续下一篇
```

**每修一个问题，重跑当前这一篇验证。直到这一篇全部链路通过，才继续下一篇。**

#### 5.3 单篇全流程验证 (30min)

从 5.2 中选 1 篇最复杂的题目（如 ENG-THESIS-033 肺结节检测），手动跟踪完整 20 节点链路：

```
intake → topic_parser → search_planner → search_agent → quality_filter →
verify → quality_gate → citation_expander → verify → quality_gate →
dataset_repo → evidence_graph → baseline_classifier → feasibility →
work_package → innovation → sota → narrative → review → optimize →
devils → human → final
```

检查每个节点的输入输出是否正确：
- topic_parser → method/object/task 是否正确？
- search_agent → 查询词是否包含题目关键词？
- quality_filter → 是否过滤了非论文？
- verify → accept/weak/reject 判断是否合理？
- dataset_repo → repo/dataset 是否被提取？
- feasibility → 判断是否与标答方向一致？
- innovation → 创新点是否引用真实论文？
- devils_advocate → verdict 是否合理（不是永远 BLOCK）？

#### 5.4 全量验证 (1h, 无人值守)

全部链路通了之后，跑 20 篇全量验证，检查是否有退化：

| # | ID | 题名 | 领域 |
|---|---|---|---|
| 1 | ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | 工业缺陷检测 |
| 2 | ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | 工业缺陷检测 |
| 3 | ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | 自动驾驶 |
| 4 | ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | 自动驾驶 |
| 5 | ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | 三维视觉/SLAM |
| 6 | ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | 三维视觉/SLAM |
| 7 | ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | 遥感/无人机 |
| 8 | ENG-THESIS-038 | 基于深度学习的无人机图像目标检测算法研究 | 遥感/无人机 |
| 9 | ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | 机器人/机械臂 |
| 10 | ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | 机器人/机械臂 |
| 11 | ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木/基础设施 |
| 12 | ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | 土木/基础设施 |
| 13 | ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | 电力/轨交巡检 |
| 14 | ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | 电力/轨交巡检 |
| 15 | ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | 能源装备 |
| 16 | ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | 能源装备 |
| 17 | ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | 工科AI/计算机视觉 |
| 18 | ENG-THESIS-034 | 基于深度学习的目标检测算法研究 | 工科AI/计算机视觉 |
| 19 | ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | 医学/人体 |
| 20 | (自定义) | 基于yolo的农作物识别 | 工科AI |

跑完后按 §4.3 规则逐篇自查 + 标答对比。

#### 通过标准

- ≥17/20 graph 完成
- ≥15/20 无垃圾（按 §4.3 规则判断）
- ≥13/20 论文与题目相关
- ≥16/20 无重复
- ≥16/20 无 Table/Figure
- ≥10/20 React 搜索有 ≥2 步
- 连续 crash < 3

**标答对比通过标准**（执行者按 §4.3 规则判断，不需要跑脚本）：

- 查询词方向与标答 keywords 一致（至少覆盖一半）
- 搜到的论文方向与标答 baselines 相关（不要求精确匹配，方向一致即可）
- 如果标答有 repo（如 ultralytics/yolov5），PaperAgent 应该也能搜到
- feasibility 判断方向与标答一致（标答 feasible → agent 不应 not_recommended）

**注意**：baseline_recall 和 dataset_recall 不要求高——每次搜索结果不同，标答也是 LLM 生成的不是绝对真值。但 keyword_recall 应该高（如果查询词都不对，结果一定垃圾）。

### Phase 6：汇总报告 (30min)

输出 `Plan/PaperAgent_Re3.0_完工报告.md`：
1. 全链路审计发现的问题清单
2. 每个修复的代码改动 + 验证结果
3. 10 篇跨领域验证结果表
4. React/Reflection 范式实现说明
5. 与参考项目对照
6. 已知限制

## 4. 执行者规则

### 4.1 改动隔离

每次改代码前 `git stash create`。验证通过记录 changelog。验证失败 `git checkout` 回滚。

### 4.2 失败处理

- Phase 1 失败 → 回滚 → 用旧代码继续 Phase 2（数据流修复不依赖搜索修复）
- Phase 3 失败 → 回滚 → 用旧 retrieve 继续 Phase 4
- Phase 4 失败 → 回滚 → 用旧 targeted_repair 继续 Phase 5
- Phase 5 连续 3 次 crash → 停止，输出部分结果

### 4.3 自查标准（执行者必须掌握，不依赖硬编码脚本）

**执行者改完代码后，不能只看 "graph 完成" 就算通过。必须按以下规则判断结果质量。**

**禁止用硬编码的 regex 列表或模式匹配做自查。你是 LLM，用你的理解力判断。**

#### 怎么读结果

跑完一个 case 后，读取 `state.json`，关注以下字段：
- `topic_atoms`：题目的 method/object/task 关键词
- `trace_events` 中 node=retrieve/search_agent 的 `tool_calls`：实际用了什么查询词
- `verified_papers` + `weak_papers`：搜到的论文列表
- `repo_candidates`：提取到的代码仓库
- `dataset_candidates`：提取到的数据集
- `feasibility_report`：可行性判断
- `review_report`：审查判断

#### 判断规则

**规则 1：查询词是否与题目匹配（最重要）**

从 `topic_atoms` 中提取 method/object/task 关键词。从 retrieve trace 中提取实际查询词。

判断：查询词是否包含题目的核心关键词？如果题目是"基于yolo的农作物识别"，method=["YOLO"]，object=["crop"]，但查询词变成了 "deep learning"——查询词比题目更宽泛，从具体退化到了通用领域，结果一定是垃圾。

不是查 "deep learning" 这个字符串出没出现，而是判断：**查询词的方向对不对**。如果题目的关键词是 YOLO + crop，查询词里至少要有 YOLO 或 crop 或 agriculture。如果查询词完全不包含题目的任何关键词，就是搜索退化。

**规则 2：论文是否与题目相关**

从 verified_papers + weak_papers 的标题看，有多少与题目相关？不是用 regex 匹配，而是用你的理解力判断：这些论文标题是否涉及题目所述的领域/方法/对象？

如果题目是"基于yolo的农作物识别"，但论文列表里全是"Deep Learning 500 Questions"、"keras-team/keras"、"annotated_deep_learning_paper_implementations"——这些是教程仓库或泛领域教材，不是学术论文，也不是关于 YOLO 或农作物的。这就是垃圾。

如果论文标题里有 "YOLO"、"crop detection"、"plant disease"、"agriculture" 等——至少方向是对的。

**规则 3：GitHub 仓库是否混入论文列表**

检查 verified_papers/weak_papers 中是否有 `source=github` 的条目。GitHub 搜索结果应该是代码仓库，应该在 `repo_candidates` 里，不应该当论文处理。如果 GitHub 结果混入了论文列表，说明 retrieve 或 quality_filter 没有正确区分 repo 和 paper。

**规则 4：repo 和 dataset 是否被提取**

检查 `repo_candidates` 和 `dataset_candidates`。如果 verified_papers 有 3+ 篇论文，但 repo_candidates 为空——可能是提取链路断了（dataset_repo_extractor 没有从论文中提取 GitHub 链接或数据集名）。

同时检查 repo URL 格式：应该是 `github.com/owner/repo`，不是 `api.github.com/repos/owner/repo`。

dataset 名称应该是具体的（如 "NEU-DET"、"KITTI"、"PlantVillage"），不是空的或通用的（如 "dataset"、"data"、"benchmark"）。

**规则 5：是否有重复论文**

检查 verified_papers + weak_papers 中是否有相同标题出现 2 次以上。第二轮 verify（引文扩展后）应该和第一轮去重。

**规则 6：是否有非论文条目混入**

检查论文标题是否以 "Table \d" 或 "Figure \d" 开头——这些是 Crossref 返回的表格/图片标题，不是论文。同样检查是否有教程、讲义、百科条目等非学术论文混入。

**规则 7：feasibility 判断是否合理**

检查 `feasibility_report.verdict`。如果题目是"基于yolo的农作物识别"（这是一个成熟方向，有大量论文和 repo），但 feasibility=not_recommended——说明搜索结果太少导致判断错误，不是题目本身不可行。

反过来，如果题目是"基于石墨烯薄膜电热效应的风机叶片防冰除冰系统"（这不是纯 CV 方向，arxiv 上论文极少），feasibility=not_recommended 是正确的。

#### 标答对比

标答文件已生成：`tmp_re30_eval/ground_truth/verified_ground_truth.json`

包含 10 个领域的预期关键词、baseline 论文、dataset、repo、feasibility。执行者跑完 20 篇后，读取标答文件，对每个 case 做平行对比：

- PaperAgent 的查询词是否覆盖标答的 keywords？
- PaperAgent 搜到的论文是否与标答 baselines 相关（标题方向一致即可，不要求精确匹配）？
- PaperAgent 提取的 dataset 是否包含标答中的已知数据集？
- PaperAgent 提取的 repo 是否包含标答中的已知 repo？
- PaperAgent 的 feasibility 判断是否与标答方向一致？

标答不是绝对真值，每次搜索结果不同。但标答提供了一个"这个题目应该搜到什么方向"的锚点。如果 PaperAgent 的搜索方向与标答完全不同（如标答说应该搜 YOLO+crop，但 PaperAgent 搜了 deep learning），就是搜索退化。

#### 每次验证必须自查

每个 Phase 的 3-case 验证和 Phase 5 的 20 篇验证，**必须**在跑完 graph 后按以上规则逐项检查。自查不通过的 case 即使 graph 完成了也算失败。

### 4.3 禁止事项

- **禁止任何 fallback 到 "deep learning" 或其他固定字符串。**
- **禁止硬编码 domain_map。**
- **禁止用 `len(q) > 5` 过滤短关键词。**
- **禁止第一次 retrieve 不用 search_plan。**
- 禁止同时改多个文件。
- 禁止改完代码不跑 3-case 验证。
- 禁止用 VOAPI / MiniMax。
- 禁止用 mock 数据。

## 5. 交付物

代码：

- `apps/api/app/services/agents/graph/nodes/retrieve.py` 🔧 (Phase 1: 删除硬编码 + 用 search_plan)
- `apps/api/app/services/agents/graph/nodes/search_planner.py` 🔧 (Phase 1: 删除硬编码)
- `apps/api/app/services/agents/graph/nodes/narrative_builder.py` 🔧 (Phase 2: 字段名修复)
- `apps/api/app/services/agents/graph/nodes/devils_advocate_node.py` 🔧 (Phase 2: 字段名修复)
- `apps/api/app/services/agents/graph/nodes/optimization_advisor.py` 🔧 (Phase 2: revision_count 修复)
- `apps/api/app/services/agents/graph/nodes/__init__.py` 🔧 (Phase 2: 字段名修复)
- `apps/api/app/services/agents/graph/nodes/search_agent.py` 🆕 (Phase 3: React 搜索 Agent)
- `apps/api/app/services/agents/graph/nodes/targeted_repair.py` 🔧 (Phase 4: 策略切换)
- `apps/api/app/services/agents/graph/state.py` 🔧 (新增 search_steps)
- `apps/api/app/services/agents/graph/research_graph.py` 🔧 (paper_retriever → search_agent)
- `apps/api/scripts/re30_batch_run.py` 🆕
- `apps/api/scripts/re30_verify.py` 🆕

数据：

- `tmp_re30_eval/verify/` (3-case 验证结果)
- `tmp_re30_eval/ground_truth/verified_ground_truth.json` (标答，已生成)
- `tmp_re30_eval/batch_20/` (20 篇结果)
- `tmp_re30_eval/changelog.md`

数据：

- `tmp_re30_eval/verify/` (3-case 验证结果)
- `tmp_re30_eval/batch_10/` (10 篇结果)
- `tmp_re30_eval/changelog.md`

报告：

- `Plan/PaperAgent_Re3.0_完工报告.md`

## 6. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | 无 "deep learning" 硬编码 fallback | `rg '"deep learning"' retrieve.py search_planner.py` 返回 0 |
| 2 | retrieve 始终用 search_plan | 代码检查 |
| 3 | 无 `len(q) > 5` 过滤 | 代码检查 |
| 4 | research_narrative 字段名统一 | 3-case 验证 devils_advocate 收到非空 narrative |
| 5 | revision_count 单一递增 | 3-case 验证每次循环 +1 |
| 6 | React 搜索循环 | search_steps 有 ≥2 步 |
| 7 | Reflection 策略切换 | repair 轮次使用不同查询词 |
| 8 | 20 篇 ≥17 完成 | Phase 5 |
| 9 | 20 篇 ≥15 无垃圾 | Phase 5 |
| 10 | 20 篇 ≥13 相关 | Phase 5 |
| 11 | 查询词方向与标答一致 | 标答对比 |
| 12 | 论文方向与标答 baselines 相关 | 标答对比 |
| 13 | repo/dataset 提取与标答方向一致 | 标答对比 |
| 14 | feasibility 判断与标答方向一致 | 标答对比 |
| 15 | changelog 完整 | 文件检查 |
| 16 | VOAPI/MiniMax = 0 | 全程 |
