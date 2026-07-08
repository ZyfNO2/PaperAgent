# PaperAgent Re3.5 前端时间线调试器 + 审计修复 SOP

> 承接：Re3.4 收口完成（P0 final_rec 验证通过，6-case 回归通过），但审核发现 3 个遗留问题：
> 1. feasibility prompt 缺硬件/合规维度
> 2. dataset_repo_extractor 精度不足（COCO→LIDC-IDRI 误识别）
> 3. ruff 100 errors（缺 .ruff.toml exclude）
>
> **本 SOP 核心：前端时间线调试器——可拖动的进度条，逐步查看每个 graph 节点的执行结果、工具调用、状态变化**
> 预计总时长：6-8 小时，分 6 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 现状分析

### 当前 trace 数据结构（已验证可用）

每个 trace 事件已包含：
```json
{
  "node": "search_agent",
  "started_at": "2026-07-08T11:02:14Z",
  "input_summary": {"topic_len": 17, "has_atoms": true, "has_plan": true},
  "output_summary": {"n_paper_candidates": 33, "n_repo_candidates": 13, "n_steps": 7, "per_adapter": {"arxiv": 12, "openalex": 12, ...}},
  "tool_calls": [{"tool": "openalex", "n": 12}, {"tool": "github", "n": 13}, ...],
  "errors": [],
  "provider": "react_search",
  "elapsed_s": 41.605
}
```

R34-002 共 27 个 trace 事件，覆盖从 intake 到 final_recommendation 的完整链路。

### 当前前端的局限

| 问题 | 现状 |
|---|---|
| 状态机 chips | 纯展示性，不可交互 |
| 进度条 | 只有 0→100%，无法定位到具体节点 |
| 执行轨迹 | 平铺列表，无时间维度，无工具调用详情 |
| 无法回溯 | 只能看最终 state，看不到中间状态 |

### 缺失的关键数据

| 数据 | 当前 | 需要 |
|---|---|---|
| 节点返回的 state keys | 未记录 | `state_patch` 字段——记录节点返回了哪些 key |
| 累计状态计数 | 需从最终 state 推算 | 每个节点执行后的 papers/repos/datasets 累计数 |
| search_steps 明细 | 在 state.json 中但不分节点 | trace 中 search_agent 的逐步 think→call→observe |

## 1. 本轮目标

1. **前端时间线调试器**——可拖动的进度条 + 节点详情面板 + 累计状态快照
2. **feasibility prompt 增强**——增加硬件/合规/数据权限维度
3. **dataset_repo_extractor 精度提升**——减少 COCO→LIDC-IDRI 类误识别
4. **.ruff.toml 配置 + ruff 收尾**——排除 archived 目录 + unsafe-fixes
5. **真实 LLM 验证**——2-case 验证调试器 + feasibility 增强
6. **完工报告**

不做：
- React+Vite 前端重写（Re4.0）
- 100 篇全量回归
- 新增搜索源
- LangSmith 集成

## 2. Phase 设计

### Phase 1：Backend — Trace 增强 (1h)

#### Fix 1.1: emit_trace 增加 state_patch 字段

**文件**：`apps/api/app/services/agents/graph/nodes/_util.py`

**问题**：当前 `emit_trace` 不记录节点返回了哪些 state key，前端无法知道每个节点修改了什么。

**修复**：增加 `state_keys` 参数，记录节点返回的 dict keys：

```python
def emit_trace(
    node: str,
    t0: float,
    ins: dict,
    out: dict,
    tools: list,
    prov: str,
    errs: list,
    state_keys: list[str] | None = None,  # Re3.5: keys returned by this node
) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": now_iso(),
        "input_summary": ins,
        "output_summary": out,
        "tool_calls": tools,
        "errors": errs,
        "provider": prov,
        "ended_at": now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
        "state_keys": state_keys or [],  # Re3.5
    }
```

#### Fix 1.2: 各 node 传入 state_keys

**涉及文件**：所有 graph nodes（约 15 个文件）

每个 node 的 return 语句已经返回一个 dict，只需在 `emit_trace` 调用时传入 `list(result.keys())`。

**示例**（content.py `final_recommendation_node`）：
```python
# 修改前
trace = _emit("final_recommendation", t0, {}, recommendation, [], "local", [])
return {"final_recommendation": recommendation, "trace_events": [trace]}

# 修改后
result = {"final_recommendation": recommendation, "trace_events": []}
trace = _emit("final_recommendation", t0, {}, recommendation, [], "local", [],
              state_keys=list(result.keys()))
result["trace_events"] = [trace]
return result
```

**批量修改策略**：用全局搜索找到所有 `_emit(` 调用，逐个添加 `state_keys` 参数。对于 return 前已构造 result dict 的 node，传 `list(result.keys())`；对于直接 return 的 node，传硬编码 key 列表。

#### Fix 1.3: 新增 timeline 端点

**文件**：`apps/api/app/api/v1/research.py`

新增 `GET /{case_id}/timeline` 端点，返回增强的 trace + 累计状态：

```python
@router.get("/{case_id}/timeline")
def case_timeline(case_id: str) -> dict[str, Any]:
    """Return trace events with progressive state counts for timeline debugger."""
    cd = _case_dir(case_id)
    trace_path = cd / "trace.json"
    state_path = cd / "state.json"
    if not trace_path.exists():
        raise HTTPException(404, f"trace not found for case {case_id!r}")

    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    # Build progressive counts from state + trace
    progressive = []
    n_papers = n_repos = n_datasets = n_baseline = 0

    # Known field mappings per node
    NODE_WRITES = {
        "search_agent": ("paper_candidates", "repo_candidates"),
        "verify": ("verified_papers", "weak_papers"),
        "citation_expander": ("expanded_papers", "seed_papers"),
        "dataset_repo": ("dataset_candidates", "repo_candidates"),
        "baseline_classifier": ("baseline_candidates", "parallel_candidates"),
    }

    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    for ev in trace:
        node = ev.get("node", "")
        out = ev.get("output_summary", {})
        # Accumulate counts from output_summary
        if "n_paper_candidates" in out:
            n_papers = out["n_paper_candidates"]
        if "n_repo_candidates" in out:
            n_repos = out["n_repo_candidates"]
        if "n_dataset_candidates" in out:
            n_datasets = out["n_dataset_candidates"]
        if "n_baseline" in out:
            n_baseline = out["n_baseline"]
        # For verify nodes, count from state
        if node == "verify":
            n_papers = len(state.get("verified_papers") or [])

        progressive.append({
            "node": node,
            "elapsed_s": ev.get("elapsed_s", 0),
            "cumulative": {
                "papers": n_papers,
                "repos": n_repos,
                "datasets": n_datasets,
                "baseline": n_baseline,
            },
        })

    return {
        "trace": trace,
        "progressive": progressive,
        "total_elapsed_s": sum(e.get("elapsed_s", 0) for e in trace),
        "n_events": len(trace),
    }
```

**验证**：
```bash
# 启动 server 后
curl http://127.0.0.1:18181/api/v1/research/R34-002/timeline | python -m json.tool | head -50
```

### Phase 2：Frontend — 时间线调试器 (2.5h)

#### 2.1: 时间线 UI 结构

**文件**：`apps/web/index.html`

在现有 `<div class="state-machine">` 下方，添加时间线调试器区域：

```html
<!-- Timeline Debugger (Re3.5) -->
<div class="timeline-debugger" id="timelineDebugger" style="display:none;">
  <div class="tl-header">
    <span class="tl-title">⏱ 时间线调试器</span>
    <span class="tl-meta" id="tlMeta">— / —</span>
  </div>

  <!-- Scrubber bar -->
  <div class="tl-scrubber" id="tlScrubber">
    <div class="tl-track" id="tlTrack">
      <!-- Node segments injected by JS, width ∝ elapsed_s -->
    </div>
    <div class="tl-cursor" id="tlCursor" style="left:0%"></div>
    <input type="range" id="tlSlider" min="0" max="100" value="0" class="tl-slider">
  </div>

  <!-- Node chips timeline -->
  <div class="tl-chips" id="tlChips">
    <!-- Clickable node chips -->
  </div>

  <!-- Detail panel -->
  <div class="tl-detail" id="tlDetail">
    <div class="tl-detail-node" id="tlDetailNode"></div>
    <div class="tl-detail-meta" id="tlDetailMeta"></div>
    <div class="tl-detail-io" id="tlDetailIO"></div>
    <div class="tl-detail-tools" id="tlDetailTools"></div>
    <div class="tl-detail-errors" id="tlDetailErrors"></div>
    <div class="tl-detail-state" id="tlDetailState"></div>
  </div>

  <!-- Progressive counts bar -->
  <div class="tl-progressive" id="tlProgressive">
    <span class="tl-prog-item">📄 <span id="tlProgPapers">0</span></span>
    <span class="tl-prog-item">📦 <span id="tlProgRepos">0</span></span>
    <span class="tl-prog-item">💾 <span id="tlProgDatasets">0</span></span>
    <span class="tl-prog-item">📐 <span id="tlProgBaseline">0</span></span>
  </div>
</div>
```

#### 2.2: 时间线 CSS

```css
/* Timeline Debugger */
.timeline-debugger{background:#fff;border-radius:8px;padding:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:10px;}
.tl-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
.tl-title{font-size:13px;font-weight:600;color:#475569;}
.tl-meta{font-size:11px;color:#94a3b8;}

/* Scrubber */
.tl-scrubber{position:relative;margin-bottom:8px;}
.tl-track{display:flex;height:24px;border-radius:4px;overflow:hidden;background:#f1f5f9;}
.tl-segment{height:100%;display:flex;align-items:center;justify-content:center;font-size:9px;color:#fff;cursor:pointer;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;transition:opacity .2s;position:relative;}
.tl-segment:hover{opacity:.8;}
.tl-segment.active{outline:2px solid #2563eb;outline-offset:-1px;z-index:2;}
.tl-segment.error{background:#ef4444 !important;}
.tl-cursor{position:absolute;top:0;height:24px;width:2px;background:#2563eb;z-index:3;pointer-events:none;transition:left .15s;}
.tl-slider{position:absolute;top:0;left:0;width:100%;height:24px;opacity:0;cursor:pointer;margin:0;}

/* Chips */
.tl-chips{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px;}
.tl-chip{padding:2px 8px;font-size:10px;border-radius:10px;background:#f1f5f9;color:#64748b;cursor:pointer;transition:all .2s;border:1px solid #e2e8f0;}
.tl-chip:hover{background:#e0e7ff;}
.tl-chip.active{background:#2563eb;color:#fff;border-color:#1d4ed8;}
.tl-chip.done{background:#dcfce7;color:#16a34a;border-color:#bbf7d0;}

/* Detail panel */
.tl-detail{background:#f8fafc;border-radius:6px;padding:10px;font-size:12px;min-height:60px;}
.tl-detail-node{font-size:14px;font-weight:600;color:#1e293b;margin-bottom:4px;}
.tl-detail-meta{font-size:11px;color:#94a3b8;margin-bottom:6px;}
.tl-detail-io{margin-bottom:6px;}
.tl-detail-io .io-label{font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;}
.tl-detail-io .io-content{font-size:11px;color:#475569;margin-left:8px;font-family:monospace;}
.tl-detail-tools{margin-bottom:6px;}
.tl-tool-tag{display:inline-block;padding:1px 6px;font-size:10px;border-radius:3px;background:#dbeafe;color:#1e40af;margin:1px 2px;}
.tl-detail-errors{color:#dc2626;font-size:11px;}
.tl-detail-state{margin-top:6px;padding-top:6px;border-top:1px solid #e2e8f0;}
.tl-state-key{display:inline-block;padding:1px 6px;font-size:10px;border-radius:3px;background:#f0fdf4;color:#15803d;margin:1px 2px;}

/* Progressive counts */
.tl-progressive{display:flex;gap:12px;padding:6px 0 0;border-top:1px solid #f1f5f9;}
.tl-prog-item{font-size:12px;color:#475569;}
.tl-prog-item span{font-weight:600;color:#2563eb;}
```

#### 2.3: 时间线 JS 逻辑

```javascript
// --- Timeline Debugger (Re3.5) ---
var tlTraceData = [];
var tlProgressiveData = [];
var tlCurrentIdx = 0;

// Node color palette
var TL_COLORS = {
  'intake': '#94a3b8', 'topic_parser': '#818cf8', 'search_planner': '#a78bfa',
  'search_agent': '#6366f1', 'quality_filter': '#7c3aed', 'verify': '#6d28d9',
  'quality_gate': '#5b21b6', 'citation_expander': '#4c1d95', 'dataset_repo': '#9333ea',
  'evidence_graph_builder': '#c026d3', 'evidence_auditor': '#a21caf',
  'baseline_classifier': '#86198f', 'feasibility_assessor': '#be185d',
  'work_package': '#9d174d', 'innovation_extractor': '#831843',
  'sota_matcher': '#e11d48', 'narrative_builder': '#be123c',
  'low_bar_review': '#881337', 'optimization_advisor': '#9f1239',
  'devils_advocate': '#9f1239', 'human_gate': '#475569',
  'final_recommendation': '#1e293b',
};

async function loadTimeline(caseId) {
  try {
    var resp = await fetch('/api/v1/research/' + caseId + '/timeline');
    if (!resp.ok) return;
    var data = await resp.json();
    tlTraceData = data.trace || [];
    tlProgressiveData = data.progressive || [];
    renderTimeline();
    document.getElementById('timelineDebugger').style.display = 'block';
  } catch(e) { console.error('timeline load:', e); }
}

function renderTimeline() {
  if (tlTraceData.length === 0) return;

  // Render segments (width ∝ elapsed_s)
  var totalElapsed = tlTraceData.reduce(function(s, e) { return s + (e.elapsed_s || 0.01); }, 0);
  var trackEl = document.getElementById('tlTrack');
  trackEl.innerHTML = '';

  tlTraceData.forEach(function(ev, i) {
    var pct = Math.max(1, ((ev.elapsed_s || 0.01) / totalElapsed) * 100);
    var color = TL_COLORS[ev.node] || '#64748b';
    var hasError = (ev.errors && ev.errors.length > 0);
    var seg = document.createElement('div');
    seg.className = 'tl-segment' + (hasError ? ' error' : '');
    seg.style.width = pct + '%';
    seg.style.background = color;
    seg.title = ev.node + ' (' + (ev.elapsed_s || 0) + 's)';
    seg.textContent = ev.node.substring(0, 6);
    seg.onclick = function() { selectTimelineNode(i); };
    trackEl.appendChild(seg);
  });

  // Render chips
  var chipsEl = document.getElementById('tlChips');
  chipsEl.innerHTML = '';
  tlTraceData.forEach(function(ev, i) {
    var chip = document.createElement('span');
    chip.className = 'tl-chip done';
    chip.textContent = (i + 1) + '.' + ev.node;
    chip.onclick = function() { selectTimelineNode(i); };
    chip.id = 'tlchip-' + i;
    chipsEl.appendChild(chip);
  });

  // Slider
  var slider = document.getElementById('tlSlider');
  slider.max = tlTraceData.length - 1;
  slider.value = 0;
  slider.oninput = function() {
    selectTimelineNode(parseInt(this.value));
  };

  document.getElementById('tlMeta').textContent = '1 / ' + tlTraceData.length +
    ' · ' + totalElapsed.toFixed(1) + 's';

  selectTimelineNode(0);
}

function selectTimelineNode(idx) {
  if (idx < 0 || idx >= tlTraceData.length) return;
  tlCurrentIdx = idx;
  var ev = tlTraceData[idx];
  var prog = tlProgressiveData[idx] || { cumulative: {} };

  // Update slider
  document.getElementById('tlSlider').value = idx;

  // Update cursor position
  var totalElapsed = tlTraceData.reduce(function(s, e) { return s + (e.elapsed_s || 0.01); }, 0);
  var elapsedUpTo = 0;
  for (var i = 0; i <= idx; i++) { elapsedUpTo += (tlTraceData[i].elapsed_s || 0.01); }
  var cursorPct = (elapsedUpTo / totalElapsed) * 100;
  document.getElementById('tlCursor').style.left = Math.min(cursorPct, 100) + '%';

  // Update active segment
  var segs = document.querySelectorAll('.tl-segment');
  segs.forEach(function(s, i) { s.classList.toggle('active', i === idx); });

  // Update chips
  var chips = document.querySelectorAll('.tl-chip');
  chips.forEach(function(c, i) { c.classList.toggle('active', i === idx); });

  // Render detail panel
  var node = ev.node || '?';
  var elapsed = ev.elapsed_s || 0;
  var provider = ev.provider || '—';
  var startedAt = ev.started_at || '—';

  document.getElementById('tlDetailNode').textContent =
    '步骤 ' + (idx + 1) + ': ' + node;
  document.getElementById('tlDetailMeta').innerHTML =
    '⏱ ' + elapsed + 's · 🤖 ' + provider + ' · 📅 ' + startedAt;

  // Input/output summary
  var ioHtml = '';
  if (ev.input_summary && Object.keys(ev.input_summary).length > 0) {
    ioHtml += '<div class="io-label">输入</div>';
    ioHtml += '<div class="io-content">' + JSON.stringify(ev.input_summary, null, 1) + '</div>';
  }
  if (ev.output_summary && Object.keys(ev.output_summary).length > 0) {
    ioHtml += '<div class="io-label">输出</div>';
    ioHtml += '<div class="io-content">' + JSON.stringify(ev.output_summary, null, 1) + '</div>';
  }
  document.getElementById('tlDetailIO').innerHTML = ioHtml;

  // Tool calls
  var toolsHtml = '';
  if (ev.tool_calls && ev.tool_calls.length > 0) {
    toolsHtml = '<div class="io-label">工具调用</div>';
    ev.tool_calls.forEach(function(tc) {
      var n = tc.n !== undefined ? ' (' + tc.n + ')' : '';
      toolsHtml += '<span class="tl-tool-tag">' + tc.tool + n + '</span>';
    });
  }
  document.getElementById('tlDetailTools').innerHTML = toolsHtml;

  // Errors
  var errHtml = '';
  if (ev.errors && ev.errors.length > 0) {
    errHtml = '<div class="io-label">错误</div>';
    ev.errors.forEach(function(err) {
      errHtml += '<div style="color:#dc2626;font-size:11px;">⚠ ' + err + '</div>';
    });
  }
  document.getElementById('tlDetailErrors').innerHTML = errHtml;

  // State keys
  var stateHtml = '';
  if (ev.state_keys && ev.state_keys.length > 0) {
    stateHtml = '<div class="io-label">状态变更</div>';
    ev.state_keys.forEach(function(k) {
      stateHtml += '<span class="tl-state-key">' + k + '</span>';
    });
  }
  document.getElementById('tlDetailState').innerHTML = stateHtml;

  // Progressive counts
  var cum = prog.cumulative || {};
  document.getElementById('tlProgPapers').textContent = cum.papers || 0;
  document.getElementById('tlProgRepos').textContent = cum.repos || 0;
  document.getElementById('tlProgDatasets').textContent = cum.datasets || 0;
  document.getElementById('tlProgBaseline').textContent = cum.baseline || 0;

  // Meta
  document.getElementById('tlMeta').textContent =
    (idx + 1) + ' / ' + tlTraceData.length + ' · ' + elapsed + 's';
}
```

#### 2.4: 集成到 fetchAndRenderAll

在 `viewCase()` 或 `fetchAndRenderAll()` 中调用 `loadTimeline(caseId)`：

```javascript
// 在 fetchAndRenderAll 末尾添加
await loadTimeline(caseId);
```

**验证**：
1. 启动 server，打开浏览器
2. 提交一个题目或查看历史 case
3. 时间线调试器应显示：
   - 彩色节点段（宽度按耗时比例）
   - 可拖动的 slider
   - 点击任意节点 → 右侧显示该节点的输入/输出/工具调用/错误/状态变更
   - 底部显示累计论文/仓库/数据集/基线计数
4. F12 Console 无红色错误

### Phase 3：Feasibility Prompt 增强 (1h)

#### Fix 3.1: 增加 domain-specific risk 维度

**文件**：`apps/api/app/services/agents/prompts/re10_feasibility_assessor.py`（或实际 prompt 文件）

**问题**：R34-046（机械臂）未识别硬件依赖风险；R34-033（肺结节）未识别数据合规风险。

**修复**：在 feasibility prompt 中增加 domain-specific risk 评估维度：

```python
# 在 system prompt 中添加：
"""
## Domain-Specific Risk Assessment

You MUST evaluate the following domain-specific risks when relevant:

1. **Hardware dependency**: If the topic involves robotics, robotic arms, SLAM, 
   autonomous driving, or IoT — assess whether physical hardware (cameras, 
   sensors, robotic platforms, GPU clusters) is required and whether the 
   student can access it.

2. **Data compliance**: If the topic involves medical imaging, patient data, 
   human subjects, or healthcare — assess data privacy, ethics committee 
   approval, and regulatory compliance (HIPAA/GDPR/中国人类遗传资源管理).

3. **Dataset availability**: If the topic requires specialized datasets — 
   assess whether public datasets exist and whether self-collection is feasible 
   within a thesis timeline.

Include relevant domain-specific risks in the "reason" field.
"""
```

**验证**：
```bash
# 重跑 R34-046，检查 feasibility_report.reason 是否包含 "硬件" 或 "机械臂"
# 重跑 R34-033，检查 feasibility_report.reason 是否包含 "合规" 或 "隐私"
```

#### Fix 3.2: feasibility_assessor.py 传递 domain hint

**文件**：`apps/api/app/services/agents/graph/nodes/feasibility_assessor.py`

在调用 LLM 前，从 state 中的 `topic_atoms` 提取 domain，作为 context 传入 prompt：

```python
# 在 build prompt 时添加 domain context
domain = state.get("topic_atoms", {}).get("domain", "")
# 如果 domain 涉及 robotics/medical，在 prompt 中强调对应风险维度
```

### Phase 4：dataset_repo_extractor 精度提升 (45min)

#### Fix 4.1: Prompt 增加反例指引

**文件**：`apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py`

**问题**：R34-033 提取到 COCO 作为肺结节检测数据集，实际应为 LIDC-IDRI。

**修复**：在 prompt 中增加反例指引，减少通用数据集误匹配：

```python
# 在 system prompt 中添加：
"""
## Anti-False-Positive Rules

- COCO is a general object detection dataset, NOT a medical dataset.
  If the paper is about medical imaging (lung nodule, tumor, etc.),
  COCO is almost certainly wrong — look for domain-specific datasets
  (e.g., LIDC-IDRI for lung nodules, MIMIC-CXR for chest X-rays).

- ImageNet is a general classification dataset, NOT a defect detection dataset.

- If the paper mentions a dataset name you don't recognize, report it
  faithfully — do NOT substitute a more familiar name.
"""
```

#### Fix 4.2: known_dataset_names 扩充医学领域

**文件**：`apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`（或 content.py 中的 known_dataset_names）

在 heuristic 匹配用的 `known_dataset_names` 列表中补充医学数据集：

```python
# 添加医学领域数据集
"LIDC-IDRI", "MIMIC-CXR", "ChestX-ray14", "NIH ChestX-ray",
"BRATS", "ISIC", "PACS", "TCIA",
```

**注意**：这仅影响 heuristic 匹配，不影响 LLM prompt 示例（不违反 hardcoding ban）。

### Phase 5：.ruff.toml + ruff 收尾 (30min)

#### Fix 5.1: 创建 .ruff.toml

**文件**：`G:\PaperAgent\.ruff.toml`（新建）

```toml
# Exclude archived legacy tests
exclude = [
    "apps/api/tests/_archived_legacy_sessions",
    ".venv",
    "tmp_re13_eval",
    "tmp_re34_eval",
    "tmp_re33_eval",
]

# Auto-fix settings
[lint]
fixable = ["ALL"]
```

#### Fix 5.2: 执行 unsafe-fixes

```bash
.venv/Scripts/python.exe -m ruff check apps/api/ --fix --unsafe-fixes
.venv/Scripts/python.exe -m ruff check apps/api/ --statistics
```

#### Fix 5.3: 手动处理 F821/F822

逐个检查 10 个 F821 (undefined-name) 和 6 个 F822 (undefined-export)：
- F821 可能是真正的 bug（引用不存在的变量）
- F822 是 `__init__.py` 导出不存在的符号
- 修复或添加 `# noqa: F821` 注释

**验证**：
```bash
.venv/Scripts/python.exe -m ruff check . --statistics
# 期望：total < 50
```

### Phase 6：真实 LLM 验证 + 完工报告 (1.5h)

#### 6.1 验证 case 选择

| Case | 题目 | 验证重点 |
|---|---|---|
| R35-046 | 基于视觉的机械臂目标检测和避障路径规划研究与应用 | feasibility 是否识别硬件风险 + 时间线调试器 |
| R35-033 | 基于YOLOV5的肺结节检测算法研究 | dataset 是否正确提取 LIDC-IDRI + feasibility 合规风险 |

#### 6.2 验证检查清单

**P0 — 必须通过**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 时间线调试器显示 | 27+ 个彩色节点段可见 |
| 2 | Slider 可拖动 | 拖动后详情面板更新 |
| 3 | 点击节点可选中 | 对应段高亮 + 详情显示 |
| 4 | 工具调用可见 | search_agent 节点显示 5+ 工具标签 |
| 5 | 累计计数更新 | 拖动 slider 时 papers/repos 数字变化 |
| 6 | R35-046 feasibility 识别硬件风险 | reason 包含 "硬件" 或 "机械臂" |
| 7 | R35-033 dataset 正确 | dataset_candidates 包含 LIDC-IDRI 或不含 COCO |
| 8 | 2-case 无 RecursionError | trace.json |
| 9 | 2-case final_rec 计数 > 0 | state.json |
| 10 | F12 Console 无红色错误 | 浏览器 |

**P1 — 应该通过**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 11 | R35-033 feasibility 识别合规风险 | reason 包含 "合规" 或 "隐私" 或 "医疗" |
| 12 | state_keys 在 trace 中可见 | 至少 5 个节点有非空 state_keys |
| 13 | /timeline 端点返回 progressive 数据 | progressive 数组长度 == trace 长度 |
| 14 | ruff errors < 50 | 全量检查 |
| 15 | 错误节点红色标记 | 有错误的节点段显示红色 |

**P2 — 加分项**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 16 | 时间线支持键盘左右键导航 | ← → 切换节点 |
| 17 | 节点段 hover 显示 tooltip | 显示节点名 + 耗时 |
| 18 | search_agent 节点展开搜索步骤 | 显示 think→call→observe 明细 |

#### 6.3 截图清单

| # | 截图 | 内容 |
|---|---|---|
| 1 | 01_timeline_overview | 时间线全貌 + 27 个节点段 |
| 2 | 02_timeline_search_agent | 选中 search_agent 节点，显示工具调用 |
| 3 | 03_timeline_verify | 选中 verify 节点，显示输入/输出 |
| 4 | 04_timeline_dragging | 拖动 slider 过程中，累计计数变化 |
| 5 | 05_timeline_error_node | 如果有错误节点，红色标记 |
| 6 | 06_feasibility_046 | R35-046 feasibility reason 包含硬件风险 |
| 7 | 07_dataset_033 | R35-033 dataset_candidates |
| 8 | 08_console_clean | F12 Console 无红色 |

#### 6.4 完工报告 + CHANGELOG

撰写 `Plan/PaperAgent_Re3.5_完工报告.md` + 更新 `CHANGELOG.md`。

## 3. 执行者规则

1. **Phase 1 必须在 Phase 2 之前完成**——前端需要增强后的 trace 数据
2. **Phase 3-4 可以与 Phase 1-2 并行**——prompt 修改不影响前端
3. **Phase 6 在所有修改完成后执行**——验证所有改动
4. **P0 项失败必须修复后重跑**
5. **遵循 CODELY.md 中的所有开发约定**
6. **禁止修改已有 API 接口签名**（backward-compatible only）
7. **VOAPI/MiniMax = 0**
8. **所有 LLM 凭证从 .env 读取**

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `apps/api/app/services/agents/graph/nodes/_util.py` | 🔧 增加 state_keys 参数 | 1 |
| `apps/api/app/services/agents/graph/nodes/*.py` (~15 个) | 🔧 传入 state_keys | 1 |
| `apps/api/app/api/v1/research.py` | 🆕 /timeline 端点 | 1 |
| `apps/web/index.html` | 🔧 时间线调试器 UI + CSS + JS | 2 |
| `apps/api/app/services/agents/prompts/re10_feasibility_*.py` | 🔧 domain-specific risk | 3 |
| `apps/api/app/services/agents/graph/nodes/feasibility_assessor.py` | 🔧 domain hint | 3 |
| `apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py` | 🔧 anti-false-positive | 4 |
| `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py` | 🔧 known_dataset_names 扩充 | 4 |
| `.ruff.toml` | 🆕 ruff 配置 | 5 |
| `apps/api/` 全量 | 🔧 ruff --fix --unsafe-fixes | 5 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re35_eval/R35-046_state.json` | 机械臂 state |
| `tmp_re35_eval/R35-046_trace.json` | 机械臂 trace |
| `tmp_re35_eval/R35-033_state.json` | 肺结节 state |
| `tmp_re35_eval/R35-033_trace.json` | 肺结节 trace |
| `tmp_re35_eval/screenshots/*.png` | 8 张截图 |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.5_完工报告.md` | 完工报告 |
| `CHANGELOG.md` | 更新 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | 时间线调试器可见 | 浏览器截图 | P0 |
| 2 | Slider 可拖动 | 浏览器操作 | P0 |
| 3 | 点击节点显示详情 | 浏览器操作 | P0 |
| 4 | 工具调用可见 | 截图 | P0 |
| 5 | 累计计数随拖动变化 | 截图 | P0 |
| 6 | R35-046 识别硬件风险 | state.json | P0 |
| 7 | R35-033 dataset 正确 | state.json | P0 |
| 8 | 2-case 无 RecursionError | trace.json | P0 |
| 9 | 2-case final_rec 计数 > 0 | state.json | P0 |
| 10 | F12 Console 无红色 | 截图 | P0 |
| 11 | R35-033 识别合规风险 | state.json | P1 |
| 12 | state_keys 在 trace 中非空 | trace.json | P1 |
| 13 | /timeline 端点可用 | curl | P1 |
| 14 | ruff errors < 50 | ruff check | P1 |
| 15 | 错误节点红色标记 | 截图 | P1 |
| 16 | 完工报告 + CHANGELOG | 文件检查 | P2 |
| 17 | VOAPI/MiniMax = 0 | 全程 | P0 |

## 6. 执行顺序

```
Phase 1 (1h):    Backend trace 增强 (state_keys + /timeline 端点)
       ↓                                    ↑ 可并行
Phase 3 (1h):    Feasibility prompt 增强    Phase 4 (45min): dataset_extractor 精度
       ↓                                    ↓
Phase 2 (2.5h):  前端时间线调试器 ← 核心
       ↓
Phase 5 (30min): .ruff.toml + ruff 收尾
       ↓
Phase 6 (1.5h):  2-case 验证 + 截图 + 完工报告
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 前端 JS 有其他隐藏 bug | 中 | 时间线不显示 | F12 Console 逐个排查 |
| state_keys 修改量大 | 低 | Phase 1 超时 | 先改 5 个核心 node，其余用空列表 |
| feasibility prompt 增强后 LLM 不遵循 | 中 | 硬件风险仍未识别 | 在 prompt 中用更强语气 + 示例 |
| .ruff.toml unsafe-fixes 引入回归 | 低 | 代码行为变化 | fix 后立即跑 test_re1_2_graph_nodes |
| DeepSeek API 429 | 中 | case 无法完成 | 等待重试 / 切 StepFun |

## 8. TODO 推进（Re3.6+）

| TODO | 评估 |
|---|---|
| 100 篇全量回归 | Re3.6 |
| PubMed E-utilities | Re3.6 |
| Unpaywall | Re3.6 |
| LangSmith 集成 | Re3.6 |
| React+Vite 前端 | Re4.0 |
| StageContract 机制 | Re4.0 |
| search_agent think→call→observe 明细展示 | Re3.6（需 trace 细粒度化） |
| 时间线键盘导航 | Re3.6（← → 切换节点） |
