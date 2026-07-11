# PaperAgent Re3.9.4 关键词翻译强制 + 相关性拦截 + 连通性自动触发 + Trace 保存 SOP

> 承接：Re3.9.3 实时论文展示 + Graph 可视化。前端测试发现"建筑工程施工安全预警"题目搜不到论文。
> 
> **根因链**：
> 1. topic_parser 输出中文关键词 → arXiv/Crossref 返回 0
> 2. search_agent React 循环只检查数量不检查相关性 → 12 篇不相关论文就 stop
> 3. quality_gate 只检查数量 ≥1 就放行 → 不相关论文进入后续分析
> 4. 连通性面板页面加载时未触发 → 用户不知道哪些 API 可用
> 5. 无 Trace 保存按钮 → 前端测试结果无法持久化
>
> **本 SOP 聚焦：强制翻译后处理 + 搜索后相关性检查 + 连通性自动触发 + Trace 保存按钮**
> 预计总时长：4-5 小时，分 5 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 根因分析

### 关键词翻译失败

```
topic_parser prompt: "ALL keywords MUST be in English"
LLM 实际输出: method=["建筑工程施工安全预警"]  ← 仍输出中文
→ arXiv 搜索 "建筑工程施工安全预警" → 0 results
→ Crossref 搜索 → 0 results
→ 只有 OpenAlex 能模糊匹配
```

**根因**：DeepSeek 对 prompt 指令的遵循率约 50%，不足以保证 100% 英文输出。需要代码层面后处理强制翻译。

### 搜索后无相关性拦截

```
search_agent 搜到 12 篇论文（来自 OpenAlex，但内容是"模式识别综述""交通预测"等）
→ LLM 看 n_papers=12，认为"够了" → stop
→ quality_filter 只过滤垃圾标题（Figure/Table），不检查语义相关性
→ quality_gate 看 n_papers ≥ 1 → 放行
→ verify 才检查相关性，但 verify 通过的论文如果 ≥1 就不再 repair
→ 不相关论文一路走到 final_recommendation
```

**根因**：search_agent 和 quality_gate 之间缺少"相关性快速检查"——应该看论文标题是否和 topic_atoms 关键词有交集。

### 连通性面板

```
页面加载时: loadConnectivity() 已在 init 中调用
但: 用户可能没有注意到，且无法手动重新触发
```

### Trace 保存

```
当前: trace 在 graph 跑完后写入 trace.json，用户无法手动保存当前时间线状态
需要: 一个"保存 Trace"按钮，将当前时间线 + state 下载为 JSON
```

## 1. 本轮目标

1. **topic_parser 后处理强制翻译**——LLM 返回后检查非 ASCII，自动调用 LLM 翻译单个词
2. **quality_filter 增加相关性检查**——过滤掉标题与 topic_atoms 完全无关的论文
3. **search_agent 相关性感知 stop**——如果搜索结果和题目完全不相关，触发 reflection 而非 stop
4. **连通性自动触发 + 手动刷新按钮**
5. **Trace 保存按钮**——下载当前 case 的 trace + state 为 JSON 文件

不做：
- 重写 search_agent 的 React 循环
- 修改 graph 拓扑
- 完整回归测试（1 个 case 验证即可）

## 2. Phase 设计

### Phase 1：topic_parser 后处理强制翻译 (1h)

#### Fix 1.1: 检测非 ASCII 并强制翻译

**文件**：`apps/api/app/services/agents/graph/nodes/topic_parser.py`

在 LLM 返回结果后、返回 state patch 前，检查每个关键词是否包含非 ASCII 字符。如果有，调用 LLM 翻译：

```python
def _force_translate_keywords(atoms: dict) -> dict:
    """Post-process: force-translate any non-ASCII keywords to English."""
    import re
    from apps.api.app.services import llm_router
    
    def _has_chinese(s: str) -> bool:
        return any(ord(c) > 127 for c in s)
    
    translated = dict(atoms)
    
    for key in ("method", "object", "task", "scenario", "domain"):
        vals = translated.get(key) or []
        new_vals = []
        for v in vals:
            if _has_chinese(v):
                try:
                    prompt = f'Translate the following Chinese academic term to English. Output ONLY the English translation, no explanation.\n\nChinese: {v}\nEnglish:'
                    result = llm_router.call_json(
                        prompt,
                        system="You are a translator. Output only the English term.",
                        profile="fast_json",
                        max_tokens=50,
                        timeout=10,
                        expected="dict",
                    )
                    if isinstance(result, dict):
                        en = result.get("translation", "") or result.get("english", "") or str(result)
                    else:
                        en = str(result)
                    en = en.strip().strip('"').strip("'")
                    if en and not _has_chinese(en):
                        new_vals.append(en)
                        logger.info("topic_parser: force-translated '%s' -> '%s'", v, en)
                    else:
                        new_vals.append(v)  # 保留原文
                except Exception as exc:
                    logger.warning("topic_parser: translate failed for '%s': %s", v, exc)
                    new_vals.append(v)
            else:
                new_vals.append(v)
        translated[key] = new_vals
    
    return translated
```

在 `topic_parser_node` 的 LLM 返回后调用：

```python
# topic_parser_node 中:
if isinstance(out, dict):
    out = _force_translate_keywords(out)  # Re3.9.4: 强制翻译后处理
```

**验证**：
```bash
.venv\Scripts\python.exe -c "
from apps.api.app.services.agents.graph.nodes.topic_parser import _force_translate_keywords
result = _force_translate_keywords({
    'method': ['卷积神经网络', 'CNN'],
    'object': ['建筑工程施工安全'],
    'task': ['预警'],
    'domain': ['civil_engineering'],
})
for k, v in result.items():
    for val in v:
        assert all(ord(c) < 128 for c in val), f'{k}: {val} still has Chinese!'
print('OK:', result)
"
```

### Phase 2：quality_filter 相关性检查 (1h)

#### Fix 2.1: 标题关键词匹配过滤

**文件**：`apps/api/app/services/agents/graph/nodes/quality_filter.py`

在现有 LLM/ heuristic 过滤之后，增加一层相关性检查——如果论文标题与 topic_atoms 的 method/object/task 关键词完全没有交集，标记为 `low_relevance` 并移到 weak_papers：

```python
def _relevance_filter(
    candidates: list[dict[str, Any]],
    atoms: dict[str, Any],
) -> tuple[list[dict], list[dict]]:
    """Filter out papers whose titles have zero keyword overlap with topic.
    
    Returns (relevant, irrelevant).
    """
    # 收集 topic_atoms 中的所有关键词（小写）
    topic_keywords = set()
    for key in ("method", "object", "task", "scenario"):
        for v in (atoms.get(key) or []):
            for word in str(v).lower().split():
                if len(word) >= 3:
                    topic_keywords.add(word)
    
    if not topic_keywords:
        return candidates, []  # 没有 atoms 关键词，跳过
    
    relevant = []
    irrelevant = []
    for c in candidates:
        title = (c.get("title") or "").lower()
        # 检查标题中是否有至少一个 topic 关键词
        has_overlap = any(kw in title for kw in topic_keywords)
        if has_overlap:
            relevant.append(c)
        else:
            irrelevant.append(c)
    
    return relevant, irrelevant
```

在 `quality_filter_node` 中调用：

```python
# quality_filter_node 中，在 kept 列表确定后:
atoms = state.get("topic_atoms") or {}
if atoms and kept:
    relevant, irrelevant = _relevance_filter(kept, atoms)
    if irrelevant:
        logger.info("quality_filter: %d papers moved to low_relevance (no keyword overlap)",
                    len(irrelevant))
        # 不删除——移到 weak_papers（让 verify 仍能看到）
        # 但标记为 low_relevance
        for p in irrelevant:
            p["relevance_flag"] = "low_relevance"
        kept = relevant
        # 将不相关的加入 weak_papers（而非直接丢弃）
        # verify 可以决定是否接受
```

**关键设计**：
- 不直接丢弃——移到 weak_papers + 标记 `relevance_flag`
- 如果所有论文都不相关（relevant 为空），保留全部（安全网）
- 只做关键词匹配，不做语义判断（LLM 相关性判断留给 verify）

### Phase 3：search_agent 相关性感知 stop (1h)

#### Fix 3.1: stop 前检查相关性

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

当 LLM 决定 stop 时，检查已搜到的论文是否和题目相关。如果完全不相关且还有剩余步骤，触发 reflection 而非直接 stop：

```python
# search_agent_node 主循环中，当 thought.get("action") == "stop" 时:

if thought.get("action") == "stop":
    # Re3.9.4: 相关性感知 stop——检查论文是否和题目相关
    atoms = state.get("topic_atoms") or {}
    if atoms and unique_papers and len(steps) < _MAX_STEPS - 1:
        relevant_count = _count_relevant_papers(unique_papers, atoms)
        total_count = len(unique_papers)
        relevance_ratio = relevant_count / total_count if total_count > 0 else 0
        
        if relevance_ratio < 0.3 and total_count < 10:
            # 论文大部分不相关且数量不多——触发 reflection
            logger.info("search_agent: stop blocked, relevance=%d/%d=%.0f%%, triggering reflection",
                        relevant_count, total_count, relevance_ratio * 100)
            # 生成新的查询策略
            reflection = _generate_reflection_query(atoms, steps, all_papers)
            if reflection:
                thought = {
                    "action": "search",
                    "tool": reflection.get("tool", "arxiv"),
                    "query": reflection.get("query", ""),
                    "reason": f"reflection: low relevance ({relevance_ratio:.0%}), trying new strategy",
                }
                # 不 stop，继续搜索
                steps.append({
                    "step": step_idx,
                    "type": "reflection",
                    "reason": f"relevance {relevance_ratio:.0%}, {reflection.get('strategy','')}",
                })
                # 继续循环
            else:
                # reflection 失败——真正 stop
                steps.append({"step": step_idx, "type": "stop", "reason": thought.get("reason", "")})
                break
        else:
            steps.append({"step": step_idx, "type": "stop", "reason": thought.get("reason", "")})
            break
    else:
        steps.append({"step": step_idx, "type": "stop", "reason": thought.get("reason", "")})
        break
```

#### Fix 3.2: _count_relevant_papers 和 _generate_reflection_query

```python
def _count_relevant_papers(papers: list[dict], atoms: dict) -> int:
    """Count papers whose titles have keyword overlap with topic_atoms."""
    topic_keywords = set()
    for key in ("method", "object", "task", "scenario"):
        for v in (atoms.get(key) or []):
            for word in str(v).lower().split():
                if len(word) >= 3:
                    topic_keywords.add(word)
    
    if not topic_keywords:
        return len(papers)  # 无法判断——默认全部相关
    
    count = 0
    for p in papers:
        title = (p.get("title") or "").lower()
        if any(kw in title for kw in topic_keywords):
            count += 1
    return count


def _generate_reflection_query(atoms: dict, steps: list, papers: list) -> dict | None:
    """Generate a new search query using reflection strategies.
    
    Strategies: broaden, synonym, switch_tool, simplify.
    """
    from apps.api.app.services.agents.search_reflection_helpers import (
        generate_broaden_query,
        generate_synonym_query,
        generate_simplify_query,
    )
    
    used_queries = {
        (s.get("tool"), s.get("query"))
        for s in steps
        if s.get("type") == "tool_call"
    }
    
    method = atoms.get("method") or []
    obj = atoms.get("object") or []
    
    # Strategy 1: simplify——只用 object 词
    if obj:
        q = " ".join(obj[:2])
        if ("arxiv", q) not in used_queries:
            return {"tool": "arxiv", "query": q, "strategy": "simplify:object_only"}
    
    # Strategy 2: broaden——用更宽泛的领域词
    domain = atoms.get("domain") or []
    if domain and method:
        q = f"{method[0]} {domain[0]}"
        if ("crossref", q) not in used_queries:
            return {"tool": "crossref", "query": q, "strategy": "broaden:method+domain"}
    
    # Strategy 3: synonym——替换关键词
    if method:
        q = f"{method[0]} application"
        if ("openalex", q) not in used_queries:
            return {"tool": "openalex", "query": q, "strategy": "synonym:method+application"}
    
    # Strategy 4: 用 topic 原文搜索
    # (从 atoms 的 raw_topic 获取)
    return None
```

### Phase 4：连通性自动触发 + 手动刷新 (30min)

#### Fix 4.1: 页面加载时自动触发连通性检查

**文件**：`apps/web/index.html`

当前 `loadConnectivity()` 已在 init 中调用（L1074-1191），但需要确认它在 DOM 完全加载后执行：

```javascript
// 确保 init 在 DOM 加载后执行
// 当前 L1074: initStateMachine();
// 当前 L1190: loadHistory();
// 当前 L1191: renderUploadList();
// 修改为:
initStateMachine();
loadGraphTopology();  // Re3.9.3
loadConnectivity();   // Re3.9.4: 确保页面加载即触发
loadHistory();
renderUploadList();
```

#### Fix 4.2: 连通性面板添加刷新按钮

```html
<!-- 修改连通性面板标题 -->
<div class="panel-title">
  连通性
  <button onclick="loadConnectivity()" 
          style="float:right;font-size:10px;padding:2px 8px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;cursor:pointer;color:#64748b;">
    ↻ 刷新
  </button>
</div>
```

#### Fix 4.3: 连通性检查添加加载状态

```javascript
function loadConnectivity() {
  // Re3.9.4: 显示加载状态
  document.getElementById('connPanel').innerHTML = 
    '<div style="color:#94a3b8;font-size:11px;padding:4px;">检查中...</div>';
  
  fetch('/api/v1/research/health/providers').then(function(r) { 
    return r.json(); 
  }).then(function(d) {
    // ... 现有渲染逻辑 ...
  }).catch(function() {
    document.getElementById('connPanel').innerHTML = 
      '<div style="color:#ef4444;font-size:11px;padding:4px;">检查失败</div>';
  });
}
```

### Phase 5：Trace 保存按钮 (30min)

#### Fix 5.1: 前端添加保存按钮

**文件**：`apps/web/index.html`

在时间线调试器标题栏添加保存按钮：

```html
<!-- 时间线调试器标题 -->
<div class="tl-header">
  <span class="tl-title">⏱ 时间线调试器</span>
  <span class="tl-meta" id="tlMeta">— / —</span>
  <button onclick="saveTrace()" 
          style="font-size:10px;padding:2px 8px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;cursor:pointer;color:#64748b;margin-left:8px;">
    💾 保存 Trace
  </button>
</div>
```

#### Fix 5.2: saveTrace 函数

```javascript
function saveTrace() {
  if (!currentCaseId) {
    alert('请先选择一个 Case');
    return;
  }
  
  // 同时获取 trace + state + timeline
  Promise.all([
    fetch('/api/v1/research/' + currentCaseId + '/trace').then(function(r) { return r.json(); }),
    fetch('/api/v1/research/' + currentCaseId + '/state').then(function(r) { return r.json(); }),
    fetch('/api/v1/research/' + currentCaseId + '/timeline').then(function(r) { return r.json(); }),
  ]).then(function(results) {
    var trace = results[0];
    var state = results[1];
    var timeline = results[2];
    
    var exportData = {
      case_id: currentCaseId,
      saved_at: new Date().toISOString(),
      topic: state.topic,
      trace: trace,
      timeline: timeline,
      summary: {
        n_verified_papers: (state.verified_papers || []).length,
        n_repo_candidates: (state.repo_candidates || []).length,
        n_dataset_candidates: (state.dataset_candidates || []).length,
        feasibility: state.feasibility_report || {},
        review: state.review_report || {},
        final_recommendation: state.final_recommendation || {},
        search_steps: state.search_steps || [],
      },
    };
    
    // 下载为 JSON 文件
    var blob = new Blob([JSON.stringify(exportData, null, 2)], {type: 'application/json'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = currentCaseId + '_trace_' + new Date().toISOString().slice(0,19).replace(/[:-]/g,'') + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }).catch(function(e) {
    alert('保存失败: ' + e);
  });
}
```

#### Fix 5.3: Graph 运行完成后自动保存 trace

在 `fetchAndRenderAll` 完成后，如果 case 刚跑完（不是从历史加载），自动下载 trace：

```javascript
// fetchAndRenderAll 完成后:
// Re3.9.4: 如果是新跑的 case，自动提示保存
if (isNewCase) {
    showSavePrompt();
}

function showSavePrompt() {
    var html = '<div style="background:#dcfce7;border-radius:8px;padding:8px;margin:6px 0;font-size:12px;color:#16a34a;cursor:pointer;" onclick="saveTrace()">';
    html += '✓ Graph 完成！点击这里保存 Trace 和结果';
    html += '</div>';
    document.getElementById('statusBar').innerHTML += html;
}
```

## 3. 验证 (30min)

### 验证 case

| Case | 题目 | 验证重点 |
|---|---|---|
| R39-CONS | 基于卷积神经网络的建筑工程施工安全预警研究 | 关键词翻译 + 相关性过滤 + reflection |

### 验收标准

| # | 条件 | 通过标准 | 优先级 |
|---|---|---|---|
| 1 | topic_parser 输出全英文 | method/object/task 无中文 | P0 |
| 2 | quality_filter 过滤不相关论文 | kept 数量 < candidates | P0 |
| 3 | search_agent 低相关性触发 reflection | trace 有 reflection step | P0 |
| 4 | 建筑安全题目搜到相关论文 | vp ≥ 1（与建筑/安全/CNN 相关） | P0 |
| 5 | 连通性页面加载即触发 | 截图显示绿色/红色状态 | P0 |
| 6 | 连通性刷新按钮可用 | 点击后重新检查 | P0 |
| 7 | Trace 保存按钮下载 JSON | 文件存在且可解析 | P0 |
| 8 | graph 完成无报错 | state.json | P0 |
| 9 | F12 Console 无红色 | 截图 | P0 |

### 截图清单

| # | 截图 | 内容 |
|---|---|---|
| 1 | 01_connectivity_auto | 页面加载后连通性自动显示 |
| 2 | 02_relevant_papers | 搜到的论文与建筑安全相关 |
| 3 | 03_reflection_step | trace 中有 reflection step |
| 4 | 04_save_trace | 点击保存后下载的 JSON 文件 |
| 5 | 05_console_clean | F12 Console 无红色 |

## 4. 执行者规则

1. **Phase 1 最先**——关键词翻译影响后续所有搜索
2. **Phase 2-3 顺序执行**——quality_filter 在 search_agent 之后
3. **Phase 4-5 可并行**——纯前端改动
4. **只需 1 个 case 验证**
5. **commit per phase**

### Commit 规范

| Phase | Commit message |
|---|---|
| 1 | `fix(re3.9.4-phase1): topic_parser后处理强制翻译 — 非ASCII关键词自动LLM翻译` |
| 2 | `feat(re3.9.4-phase2): quality_filter相关性检查 — 标题关键词交集过滤` |
| 3 | `feat(re3.9.4-phase3): search_agent相关性感知stop — 低相关性触发reflection` |
| 4 | `feat(re3.9.4-phase4): 连通性自动触发+手动刷新按钮` |
| 5 | `feat(re3.9.4-phase5): Trace保存按钮 — 下载JSON` |

## 5. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `topic_parser.py` | 🔧 _force_translate_keywords 后处理 | 1 |
| `quality_filter.py` | 🔧 _relevance_filter 关键词交集 | 2 |
| `search_agent.py` | 🔧 相关性感知 stop + _count_relevant_papers + _generate_reflection_query | 3 |
| `index.html` | 🔧 连通性自动触发 + 刷新按钮 + Trace 保存按钮 | 4+5 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re39_eval/R39-CONS/` | 建筑安全验证 case |
| `tmp_re39_eval/screenshots/01-05_*.png` | 5 张截图 |
| `R39-CONS_trace_*.json` | 保存的 Trace 文件 |

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| _force_translate_keywords LLM 调用增加延迟 | 中 | topic_parser 耗时 +2-5s | 每个词独立翻译，可并行 |
| 相关性过滤误杀相关论文 | 中 | 论文数量不足 | 只移到 weak_papers，不丢弃；relevant 为空时保留全部 |
| reflection 查询仍搜不到 | 中 | 搜索步数耗尽 | 最多触发 1-2 次 reflection，之后正常 stop |
| 连通性检查阻塞页面 | 低 | 首屏渲染慢 | 异步 fetch，不阻塞 UI |
| Trace 文件过大 | 低 | 下载慢 | 只导出 trace + summary，不导出完整 state |
