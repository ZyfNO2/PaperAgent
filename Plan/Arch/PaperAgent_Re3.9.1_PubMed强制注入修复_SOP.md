# PaperAgent Re3.9.1 PubMed 强制注入修复 SOP

> 承接：Re3.9 审核发现 PubMed 领域门控代码正确但运行时从未被 LLM 选中。R39-MED（medical_ai 领域）8 步搜索全部使用 base tools，PubMed 虽在 `available_extra_tools` 中但 LLM 忽略了它。
> **本 SOP 聚焦：让 PubMed 在医学领域被实际调用**
> 预计总时长：1-1.5 小时，分 2 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 问题根因分析

### 当前状态

```
_get_domain_tools("medical_ai") → {"pubmed"}         ✅ 正确
_build_decision_prompt → available_extra_tools: ["pubmed"]  ✅ 传给 LLM
_SYSTEM_PROMPT L86 → "pubmed: 搜医学/生物论文"        ✅ LLM 能看到
_fallback_decide L226-236 → 医学→pubmed fallback       ✅ 代码正确

LLM 决策结果 → 8 步全部选 base tools，从未选 pubmed    ❌ LLM 不选
_fallback_decide 仅在 LLM 不可用时触发                 ❌ LLM 可用
```

### 根因

1. **LLM prompt 不够强制**：`available_extra_tools` 是 JSON 中的一个字段，LLM 把它当信息性而非指令性
2. **fallback_decide 的 pubmed 注入仅在 LLM 不可用时触发**：L226-236 在 `_fallback_decide` 函数内，但 LLM 一直可用所以从未走到
3. **`available_tools` 早退检查**（L450-451）：硬编码 8 个 base tools，不含 pubmed——如果 8 个全失败，会 break 但 pubmed 从未被尝试

### R39-MED 实际执行

```
step 0: openalex (429, 0 results)
step 1: arxiv (24 results) ← 够了，LLM 倾向 stop
step 2: github (1 repo)
step 3: semantic_scholar (429, 0 results)
step 4: crossref (12 results)
step 5: huggingface (0 results)
step 6: core (0 results)
step 7: arxiv (重复查询，被防重复逻辑拦截后 fallback)
```

LLM 在 step 1 拿到 24 篇后认为"够了"，不再尝试 pubmed。

## 1. 本轮目标

1. **LLM 路径强制注入**——在 `_llm_decide` 返回后，如果 domain 是医学且 pubmed 未被调用且未失败，强制插入一个 pubmed 调用
2. **验证 PubMed 实际被调用**——跑 1 个医学 case，确认 trace 中 pubmed 出现在 search_steps

不做：
- 修改 _SYSTEM_PROMPT（已有 pubmed 描述）
- 修改 _get_domain_tools（已正确）
- 修改 _fallback_decide（已有 pubmed fallback，但需要同步到 LLM 路径）

## 2. Phase 设计

### Phase 1：LLM 路径强制注入 PubMed (30min)

#### Fix 1.1: _llm_decide 返回后注入 PubMed

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

**策略**：不依赖 LLM 主动选择 pubmed——在 `_llm_decide` 返回后、执行前，检查是否应该强制注入 pubmed。

在 `search_agent_node` 的主循环中，LLM 决策之后、tool 执行之前添加注入逻辑：

```python
# search_agent_node 主循环中，在 thought = _llm_decide(...) 之后：

# Re3.9.1: 强制注入领域专用工具（如 pubmed）
# 如果 domain 有专用工具且该工具未被调用且未失败，在第 2 步强制注入
domain_str_for_inject = str(atoms.get("domain", "unknown"))
if isinstance(atoms.get("domain"), list) and atoms.get("domain"):
    domain_str_for_inject = str(atoms["domain"][0])

domain_tools = _get_domain_tools(domain_str_for_inject)
if domain_tools:
    # 检查 domain tools 是否已被调用
    used_tools = {s.get("tool") for s in steps if s.get("type") == "tool_call"}
    unused_domain_tools = domain_tools - used_tools - failed_this_round - skip_adapters
    # 在第 2 步（已有一些结果后）注入，不是第 1 步（避免占用第一步）
    if unused_domain_tools and len(steps) >= 2 and thought.get("action") != "stop":
        # 取第一个未用的 domain tool
        inject_tool = sorted(unused_domain_tools)[0]
        method_kws = atoms.get("method") or []
        obj_kws = atoms.get("object") or []
        inject_query = " ".join((method_kws + obj_kws)[:3])
        if inject_query:
            logger.info("search_agent: injecting domain tool %s for %s domain",
                        inject_tool, domain_str_for_inject)
            # 覆盖 LLM 的决策——这一次用 domain tool
            thought = {
                "action": "search",
                "tool": inject_tool,
                "query": inject_query,
                "reason": f"domain injection: {domain_str_for_inject} topic, forced {inject_tool}",
            }
```

**关键设计**：
- 在第 2 步注入（不是第 1 步）——让 LLM 先用基础工具获取一些结果，避免第一步被 pubmed 占用
- 仅当 domain tool 未被调用且未失败时注入——不会重复调用
- 仅当 LLM 没有决定 stop 时注入——如果 LLM 要 stop 且 pubmed 还没试过，也注入（见 Fix 1.2）
- 覆盖 LLM 的决策——这一次搜索步强制用 domain tool

#### Fix 1.2: LLM 决定 stop 时也注入未试过的 domain tool

如果 LLM 在 step 1 拿到 24 篇后决定 stop，但 pubmed 还没试过——应该先试 pubmed 再 stop：

```python
# 在 thought.get("action") == "stop" 的检查之前添加：

# Re3.9.1: 如果 LLM 要 stop 但 domain tool 还没试过，先试一次
if thought.get("action") == "stop" and domain_tools:
    used_tools = {s.get("tool") for s in steps if s.get("type") == "tool_call"}
    unused_domain_tools = domain_tools - used_tools - failed_this_round - skip_adapters
    if unused_domain_tools and len(steps) < _MAX_STEPS - 1:
        inject_tool = sorted(unused_domain_tools)[0]
        method_kws = atoms.get("method") or []
        obj_kws = atoms.get("object") or []
        inject_query = " ".join((method_kws + obj_kws)[:3])
        if inject_query:
            logger.info("search_agent: injecting domain tool %s before stop (domain=%s)",
                        inject_tool, domain_str_for_inject)
            thought = {
                "action": "search",
                "tool": inject_tool,
                "query": inject_query,
                "reason": f"domain injection before stop: {domain_str_for_inject} topic",
            }
```

#### Fix 1.3: available_tools 早退检查包含 domain tools

**当前 L450-451 硬编码 8 个 base tools，不含 pubmed**：

```python
# 修改前:
available_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                   "huggingface", "core", "datacite"}

# 修改后:
available_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                   "huggingface", "core", "datacite"} | domain_tools
```

这样如果所有 base tools 失败 + domain tools 也失败，才会触发早退 stop。

#### Fix 1.4: all_tool_order 包含 pubmed

**当前 L507 all_tool_order 硬编码 8 个 tools，不含 pubmed**——导致 trace 的 `raw_tools` 和 `per_adapter` 不含 pubmed：

```python
# 修改前:
all_tool_order = [tool for tool in (
    "arxiv", "openalex", "crossref", "github", "semantic_scholar",
    "huggingface", "core", "datacite"
) if tool in raw]

# 修改后:
all_tool_order = [tool for tool in (
    "arxiv", "openalex", "crossref", "github", "semantic_scholar",
    "huggingface", "core", "datacite", "pubmed"
) if tool in raw]
```

### Phase 2：验证 (30min)

#### 2.1 冒烟验证

跑 1 个医学 case（肺结节检测或医学 LLM 可信度），确认：
- trace 中 search_steps 包含 pubmed 调用
- trace 中 raw_tools 包含 "pubmed"
- trace 中 per_adapter 包含 "pubmed" 条目

```bash
# 提交医学 case
curl -X POST http://127.0.0.1:18181/api/v1/research/ \
  -H "Content-Type: application/json" \
  -d '{"topic": "基于YOLOV5的肺结节检测算法研究", "target_tier": "SCI-Q2"}'

# 完成后检查
.venv\Scripts\python.exe -c "
import json
d = json.load(open('tmp_re39_eval/R39-LUNG/state.json', encoding='utf-8'))
ss = d.get('search_steps', [])
for s in ss:
    print(f'step {s.get(\"step\")}: type={s.get(\"type\")} tool={s.get(\"tool\")} n={s.get(\"n_results\",\"-\")}')
pubmed_steps = [s for s in ss if s.get('tool') == 'pubmed']
assert len(pubmed_steps) >= 1, 'PubMed was never called!'
print(f'OK: PubMed called {len(pubmed_steps)} time(s)')
"
```

#### 2.2 非医学验证

跑 1 个非医学 case（机械臂或裂缝），确认 pubmed **不被调用**：

```bash
curl -X POST http://127.0.0.1:18181/api/v1/research/ \
  -H "Content-Type: application/json" \
  -d '{"topic": "基于深度学习的混凝土桥梁裂缝检测研究", "target_tier": "SCI-Q2"}'

# 检查 pubmed 未出现
.venv\Scripts\python.exe -c "
import json
d = json.load(open('tmp_re39_eval/R39-CRACK/state.json', encoding='utf-8'))
ss = d.get('search_steps', [])
pubmed_steps = [s for s in ss if s.get('tool') == 'pubmed']
assert len(pubmed_steps) == 0, f'PubMed should NOT be called for non-medical topic! ({len(pubmed_steps)} calls)'
print('OK: PubMed not called for non-medical topic')
"
```

#### 2.3 验收标准

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | 医学 case search_steps 含 pubmed | trace.json | P0 |
| 2 | 医学 case raw_tools 含 pubmed | trace.json | P0 |
| 3 | 非医学 case search_steps 不含 pubmed | trace.json | P0 |
| 4 | 医学 case 无 RecursionError | trace.json | P0 |
| 5 | 医学 case verified_papers ≥ 3 | state.json | P0 |
| 6 | available_tools 含 domain_tools | 代码检查 | P0 |
| 7 | all_tool_order 含 pubmed | 代码检查 | P0 |
| 8 | commit | git log | P1 |

## 3. 执行顺序

```
Phase 1 (30min): 代码修复 (注入逻辑 + available_tools + all_tool_order)
       ↓
Phase 2 (30min): 验证 (1 医学 + 1 非医学)
       ↓
Commit: git add -A && git commit -m "fix(re3.9.1): PubMed强制注入 — LLM路径domain tool注入+stop前注入+available_tools修正"
```

## 4. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 注入覆盖 LLM 有意义的决策 | 低 | 搜索策略被打断 | 仅在第 2 步后注入，且仅一次 |
| PubMed 返回 0 结果（非医学查询） | 低 | 浪费一个搜索步 | 领域门控已保证只对医学注入 |
| PubMed API 429 | 低 | PubMed 3 req/s 免费额度足够 | 返回 [] 不影响 pipeline |
| 注入后 LLM 混乱 | 低 | LLM 看到 prior_steps 中有 pubmed 结果 | LLM 会正常处理 |
