# PaperAgent Re3.6 state_keys 收口 + F821/F822 修复 + 20 篇批量回归 SOP

> 承接：Re3.5 时间线调试器 UI 已完成，但审核发现 state_keys 空壳（15 个 node 未传参）、16 个 F821/F822 潜在 bug、dataset_extractor 仍误提取 COCO、前端无截图验证。
> **本 SOP 聚焦：state_keys 全节点覆盖 → F821/F822 逐个修复 → dataset prompt 强化 → 截图验证 → 20 篇批量回归**
> 预计总时长：5-7 小时，分 5 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 审计发现总结

### P0 — 功能空壳

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| A1 | **state_keys 全部为空列表** | R35-046 trace: `state_keys: []`；15 个 `_emit()` 调用均无 `state_keys=` 参数 | 时间线调试器"状态变更"面板永远为空 |
| A2 | **前端无截图验证** | Re3.5 完工报告标注"待手动验证"，0 张截图 | 验收条件 #1-5/10/15 共 7 项未关闭 |

### P1 — 潜在 Bug

| # | 问题 | 位置 | 数量 |
|---|---|---|---|
| B1 | F821 undefined-name | `eval/__init__.py`(5), `llm.py`(1), `citation_expand.py`(1), `re10_fix2_to_csv.py`(1), `test_re1_1_no_secret_leak.py`(1) | 10 |
| B2 | F822 undefined-export | `_research_agent_compat.py` `__all__` 导出 6 个不存在的符号 | 6 |
| B3 | dataset_extractor 仍提取 COCO | R35-033: `dataset_candidates: ['COCO']`，应为 LIDC-IDRI | 1 |

### P2 — 验证缺口

| # | 问题 | 说明 |
|---|---|---|
| C1 | 100 篇测试集仅 Batch20 跑过 16 篇 | 84 篇未验证，Re3.4 仅跑了 6 个出问题的 |
| C2 | ruff 95 个 errors（E402:53, E701:16, F821:10, F822:6, 其他:10） | Re3.5 目标 <50 未达成 |

## 1. 本轮目标

1. **state_keys 全节点覆盖**——15+ 个 `_emit()` 调用全部传入 `state_keys=`，时间线"状态变更"面板有内容
2. **F821/F822 逐个修复**——16 个潜在 bug 消零
3. **dataset_extractor prompt 强化**——医学领域数据集不再误提取 COCO
4. **截图验证**——8 张时间线截图，关闭 Re3.5 遗留的 7 个 ⚠️ 项
5. **20 篇批量回归**——从 100 篇测试集中选 20 篇（含已通过的 + 新领域），验证系统鲁棒性

不做：
- React+Vite 前端
- LangSmith 集成
- 新增搜索源
- 100 篇全量（Re3.7）

## 2. Phase 设计

### Phase 1：state_keys 全节点覆盖 (1h)

#### 完整 _emit() 调用清单

审计确认共 **25 个 `_emit()` 调用**分布在 13 个文件中（search_planner.py 有自定义 `_emit` 且 3 处调用）。另外 verify.py、search_agent.py、quality_filter.py **不用 `_emit()`**，而是手工构造 trace dict——需要单独处理。

#### Fix 1.1: 使用 _emit() 的 11 个文件（22 处调用）

| 文件 | 调用数 | node 名称 | 返回的 state keys |
|---|---|---|---|
| `intake.py` | 1 | intake | `topic`, `target_tier`, `trace_events` |
| `topic_parser.py` | 2 | topic_parser | `topic_atoms`, `method_words`, `object_words`, `domain`, `trace_events` |
| `search_planner.py` | 3 | search_planner | `search_plan`, `trace_events` |
| `content.py` | 6 | dataset_repo / evidence_auditor / work_package / low_bar_review / human_gate / final_recommendation | 各自返回 key 不同 |
| `dataset_repo_extractor.py` | 1 | dataset_repo | `dataset_candidates`, `repo_candidates`, `trace_events` |
| `baseline_classifier.py` | 2 | evidence_auditor | `baseline_candidates`, `parallel_candidates`, `trace_events` |
| `devils_advocate_node.py` | 1 | devils_advocate | `review_report`, `devils_advocate_block_count`, `trace_events` |
| `feasibility_assessor.py` | 1 | feasibility_assessor | `feasibility_report`, `trace_events` |
| `innovation_extractor.py` | 1 | innovation_extractor | `innovation_points`, `stitching_plan`, `trace_events` |
| `optimization_advisor.py` | 1 | optimization_advisor | `optimization_directions`, `trace_events` |
| `narrative_builder.py` | 1 | narrative_builder | `research_narrative`, `narrative_revision_count`, `trace_events` |
| `sota_matcher.py` | 1 | sota_matcher | `sota_comparison`, `trace_events` |
| `json_graph_builder.py` | 1 | json_graph_builder | `evidence_graph`, `trace_events` |
| `targeted_repair.py` | 2 | targeted_repair | `search_plan`, `repair_rounds`, `trace_events` |

**修改方式**：每个 `_emit()` 调用添加 `state_keys=[...]` 参数。

**示例**（`feasibility_assessor.py`）：
```python
# 修改前
trace = _emit("feasibility_assessor", t0,
              {"n_baseline": len(baselines), "n_dataset": n_dataset, "n_repo": n_repo},
              {"verdict": result.get("verdict", "unknown"), "score": result.get("score", 0)},
              [{"tool": "feasibility_assessor.llm" if prov != "heuristic" else "heuristic"}],
              prov, [])

# 修改后
trace = _emit("feasibility_assessor", t0,
              {"n_baseline": len(baselines), "n_dataset": n_dataset, "n_repo": n_repo},
              {"verdict": result.get("verdict", "unknown"), "score": result.get("score", 0)},
              [{"tool": "feasibility_assessor.llm" if prov != "heuristic" else "heuristic"}],
              prov, [],
              state_keys=["feasibility_report", "trace_events"])
```

**批量修改策略**：
1. 每个文件先读 `return` 语句，确认返回的 dict keys
2. 在 `_emit()` 调用末尾添加 `state_keys=[...]`
3. 对于有多个 return 路径的 node（如 verify.py 有 2 个 return），统一传相同的 `state_keys` 列表

#### Fix 1.2: 不使用 _emit() 的 3 个文件

**verify.py**、**search_agent.py**、**quality_filter.py** 手工构造 trace dict，不走 `_emit()`。需要在 trace dict 构造后手动添加 `state_keys` 字段。

**verify.py**（2 处 return）：
```python
# 在 return 前，找到 trace dict 构造处添加：
trace["state_keys"] = ["verified_papers", "weak_papers", "paper_candidates", "trace_events"]
# 如果有 errors 路径：
trace["state_keys"] = ["verified_papers", "weak_papers", "paper_candidates", "trace_events", "errors", "provider_profile"]
```

**search_agent.py**（1 处 return）：
```python
# 在 trace["elapsed_s"] = ... 后添加：
trace["state_keys"] = ["raw_results", "paper_candidates", "repo_candidates", "search_steps", "trace_events"]
```

**quality_filter.py**（2 处 return）：
```python
# 早退路径：
trace["state_keys"] = ["paper_candidates", "filter_results", "trace_events"]
# 正常路径：
trace["state_keys"] = ["paper_candidates", "filter_results", "trace_events"]
```

#### Fix 1.3: search_planner.py 自定义 _emit

`search_planner.py` 在 L31 自定义了一个 `_emit` 函数（覆盖了 import 的），需要在其返回的 dict 中也添加 `state_keys` 字段。

```python
# search_planner.py L31 的 _emit 函数
def _emit(node, t0, ins, out, tools, prov, errs):
    return {
        ...,
        "elapsed_s": round(time.time() - t0, 3),
        "state_keys": ["search_plan", "trace_events"],  # Re3.6: 添加
    }
```

#### 验证

```bash
# 单元测试
.venv/Scripts/python.exe -m pytest apps/api/tests/test_re1_2_graph_nodes.py -v

# 确认 state_keys 非空（需要先跑一个 case）
.venv/Scripts/python.exe -c "
import json
d = json.load(open('tmp_re36_eval/test_state_keys/trace.json', encoding='utf-8'))
for ev in d:
    sk = ev.get('state_keys', [])
    if not sk:
        print(f'EMPTY: {ev[\"node\"]}')
    else:
        print(f'OK: {ev[\"node\"]} -> {sk}')
"
```

### Phase 2：F821/F822 逐个修复 (1h)

#### F821 清单（10 个）

| # | 文件 | 行 | 未定义名 | 分析 | 修复方案 |
|---|---|---|---|---|---|
| 1 | `eval/__init__.py` | 103 | `v` | 列表推导式中变量泄露 | 检查上下文，可能是 `[v for v in ...]` 的笔误 |
| 2-6 | `eval/__init__.py` | 109-111 | `x` (×5) | 同上，`x` 在推导式外被引用 | 修正变量名或添加 `# noqa: F821` |
| 7 | `llm.py` | 208 | `_collect_stream` | 函数在条件分支中定义，另一分支引用 | 将定义提到外层或改为函数参数 |
| 8 | `citation_expand.py` | 247 | `_extract_arxiv_id_from_url` | 函数名拼写错误或被删除 | 搜索项目中同名函数，修正引用 |
| 9 | `re10_fix2_to_csv.py` | 246 | `est` | 变量名笔误（应为 `est_` 或 `estimate`） | 修正变量名 |
| 10 | `test_re1_1_no_secret_leak.py` | 41 | `value` | 测试中变量未定义 | 修正或标记 `# noqa: F821` |

**处理策略**：
- #1-6 (`eval/__init__.py`): 检查是否是推导式 bug。如果 eval 模块已废弃，整体归档。
- #7 (`llm.py`): **可能是真 bug**——`_collect_stream` 在某分支被调用但未定义。需检查流式响应逻辑。
- #8 (`citation_expand.py`): 搜索 `def _extract_arxiv_id` 确认正确函数名。
- #9-10: 低优先级，脚本/测试文件，可直接 `# noqa` 或修正。

#### F822 清单（6 个）

| # | 文件 | 行 | 未定义导出名 |
|---|---|---|---|
| 1-6 | `_research_agent_compat.py` | 24-25 | `parse_topic`, `plan_tools_v2`, `synthesize_v2`, `chat_json_strict`, `FAMILY_TO_ADAPTER`, `audit_candidates` |

**分析**：`_research_agent_compat.py` 是 Re3.0 的兼容层，`__all__` 导出了 6 个已删除的函数名。

**修复方案**：
- 如果 compat 层仍在使用：从其他模块 import 这些函数
- 如果 compat 层已无引用：整体归档到 `_archived_legacy_sessions/` 或删除

```bash
# 检查是否有其他文件 import _research_agent_compat
grep -r "_research_agent_compat" apps/api/ --include="*.py"
```

#### 验证

```bash
.venv/Scripts/python.exe -m ruff check . --select F821,F822
# 期望：0 errors
```

### Phase 3：dataset_extractor prompt 强化 (30min)

#### Fix 3.1: 强化医学领域约束

**文件**：`apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py`

Re3.5 的 anti-false-positive 规则不够强。强化为：

```python
# 在 system prompt 中添加更强的约束：
"""
## 医学领域数据集约束

当论文涉及医学影像（肺结节、CT、MRI、X-ray 等）时：
- 优先识别领域专用数据集：LIDC-IDRI, MIMIC-CXR, ChestX-ray14, NIH ChestX-ray, TCIA, BRATS
- COCO 和 ImageNet 是通用数据集，在医学论文中几乎一定是错误识别
- 如果论文同时提到 COCO 和领域数据集，只报告领域数据集
- 如果不确定，报告 status="not_found_in_paper" 而不是猜测
"""
```

#### Fix 3.2: known_dataset_names 继续扩充

**文件**：`apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`（content.py 中的 heuristic 列表）

Re3.5 已添加了部分医学数据集名。确认列表完整：

```python
# 确保包含（Re3.5 已添加的 + 补充）
known_dataset_names = [
    # 通用
    "COCO", "Pascal VOC", "ImageNet", "CIFAR", "MNIST",
    # 缺陷检测
    "NEU-DET", "GC10-DET", "MVTec AD",
    # SLAM/点云
    "KITTI", "TUM RGB-D", "EuRoC", "Bonn", "ScanNet", "Middlebury",
    # 自动驾驶
    "Cityscapes", "nuScenes", "DOTA", "VisDrone", "UAVDT",
    # 遥感
    "DOTA", "xView",
    # 医学（Re3.5 添加）
    "LIDC-IDRI", "MIMIC-CXR", "ChestX-ray14", "NIH ChestX-ray",
    "BRATS", "ISIC", "TCIA", "PACS",
    # 补充（Re3.6）
    "DeepCrack", "CrackTree", "GAPs384",
    "ShapeNet", "ModelNet",
    "PlantVillage",
]
```

**注意**：这仅影响 heuristic 匹配，不影响 LLM prompt 示例（不违反 hardcoding ban）。

### Phase 4：截图验证 (30min)

#### 4.1 前置条件

- Phase 1-3 完成
- `.env` 有真实 DeepSeek API key
- Phase 1 验证时跑了一个测试 case

#### 4.2 截图清单

启动 server → 浏览器打开 `http://127.0.0.1:18181/web/` → 选择一个已完成的 case（R35-046 或新跑的 case）→ 截取 8 张截图：

| # | 截图名称 | 内容 | 通过标准 |
|---|---|---|---|
| 1 | 01_timeline_overview | 时间线全貌，27 个彩色节点段 | 段可见且宽度不同 |
| 2 | 02_timeline_search_agent | 点击 search_agent 节点 | 工具调用标签 ≥3 个 |
| 3 | 03_timeline_verify | 点击 verify 节点 | 输入/输出摘要可见 |
| 4 | 04_timeline_state_keys | 点击任意节点 | "状态变更"区域有 ≥1 个绿色 key 标签 |
| 5 | 05_timeline_dragging | 拖动 slider 过程中 | 累计计数（papers/repos）数字变化 |
| 6 | 06_timeline_final | 点击 final_recommendation 节点 | 输出含计数信息 |
| 7 | 07_console_clean | F12 Console 截图 | 无红色错误 |
| 8 | 08_timeline_error_node | 如果有错误节点（否则用 devils_advocate） | 红色段 或 详情面板有错误信息 |

**保存路径**：`tmp_re36_eval/screenshots/`

#### 4.3 验收标准

- 截图 #4 (state_keys) 是 **P0**——如果绿色标签为空，说明 Phase 1 失败
- 截图 #7 (Console 无红色) 是 **P0**
- 其余为 P1

### Phase 5：20 篇批量回归 (2.5-3h)

#### 5.1 章节选择

从 100 篇测试集中选 20 篇，覆盖：
- **已验证通过的 8 篇**（V-*-33 3 篇 + Re3.4 6 篇中 5 篇通过 + Re3.5 2 篇）→ 快速冒烟
- **未测过的 12 篇**，按领域矩阵选：

| Case ID | ENG-THESIS | 题目 | 领域 | 选择理由 |
|---|---|---|---|---|
| R36-003 | 003 | 基于点云多平面检测的三维重建关键技术研究 | 三维视觉/点云 | 未测，中-高难度 |
| R36-007 | 007 | 基于视觉的无人机识别与跟踪技术研究 | 遥感/无人机 | 未测，中难度 |
| R36-015 | 015 | 基于患者虚拟定位的三维人体重建关键技术研究 | 医学/人体 | 未测，高难度+合规 |
| R36-021 | 021 | 基于深度学习的自动驾驶感知算法研究 | 自动驾驶 | 未测，中难度 |
| R36-052 | 052 | 基于深度强化学习的无人驾驶感知与决策研究 | 自动驾驶 | 未测，高难度 |
| R36-060 | 060 | 基于深度学习的车道线检测方法研究 | 自动驾驶 | 未测，中难度 |
| R36-074 | 074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木/裂缝 | Batch20 ACCEPT，验证回归 |
| R36-079 | 079 | 基于结构光的隧道裂缝检测技术研究与实现 | 土木/裂缝 | 未测，中-高难度 |
| R36-084 | 084 | 基于U-Net卷积网络的地质岩层裂缝检测方法 | 土木/裂缝 | 未测，U-Net 领域 |
| R36-091 | 091 | 基于云计算的输电线路缺陷检测平台 | 电力巡检 | 未测，中难度 |
| R36-094 | 094 | 基于SCADA数据的风机叶片结冰诊断研究 | 能源装备 | 未测，非 CV 为主 |
| R36-100 | 100 | 基于深度学习的配电设备视觉识别技术研究 | 电力巡检 | 未测，中难度 |

**领域分布**：三维视觉(1) + 遥感(1) + 医学(1) + 自动驾驶(3) + 土木(3) + 电力(2) + 能源(1) = 12 篇新

#### 5.2 执行方式

**分批串行提交**，每批 4 篇，批间等待 API 冷却 30s：

```bash
# 启动 server
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 批量提交脚本
# 每篇提交后等待完成，检查 state.json，再提交下一篇
```

**自动化验证脚本**：

```python
# scripts/re36_batch_verify.py
import json, os, sys

CASES = [
    ("R36-003", "基于点云多平面检测的三维重建关键技术研究"),
    ("R36-007", "基于视觉的无人机识别与跟踪技术研究"),
    # ... 12 篇
]

results = []
for case_id, topic in CASES:
    state_path = f"tmp_re36_eval/{case_id}/state.json"
    if not os.path.exists(state_path):
        results.append((case_id, "SKIP", "no state.json"))
        continue
    
    d = json.load(open(state_path, encoding="utf-8"))
    vp = len(d.get("verified_papers", []))
    fr = d.get("final_recommendation", {})
    feas = d.get("feasibility_report", {})
    review = d.get("review_report", {})
    trace_path = f"tmp_re36_eval/{case_id}/trace.json"
    trace = json.load(open(trace_path, encoding="utf-8")) if os.path.exists(trace_path) else []
    
    has_recursion = any("RecursionError" in str(e) for ev in trace for e in ev.get("errors", []))
    fr_match = fr.get("n_papers", 0) == vp
    state_keys_nonempty = sum(1 for ev in trace if ev.get("state_keys"))
    
    issues = []
    if vp < 3: issues.append(f"vp={vp}<3")
    if not fr_match: issues.append(f"fr.n_papers={fr.get('n_papers')}!={vp}")
    if fr.get("n_papers", 0) == 0: issues.append("fr_n_papers=0")
    if has_recursion: issues.append("RecursionError")
    if state_keys_nonempty < 5: issues.append(f"state_keys_nonempty={state_keys_nonempty}")
    
    status = "FAIL" if issues else "PASS"
    results.append((case_id, status, f"vp={vp} feas={feas.get('verdict','?')} review={review.get('overall_verdict','?')} sk={state_keys_nonempty} | {';'.join(issues)}"))

print("\n=== Re3.6 Batch Results ===")
for case_id, status, detail in results:
    print(f"{case_id}: {status} | {detail}")
n_pass = sum(1 for _, s, _ in results if s == "PASS")
print(f"\nTotal: {n_pass}/{len(results)} PASS")
```

#### 5.3 验证检查清单

**P0 — 必须通过**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 12 篇全部完成 | 12 个 state.json 存在 |
| 2 | 12 篇无 RecursionError | trace.json 检查 |
| 3 | 12 篇 verified_papers ≥ 3 | state.json |
| 4 | 12 篇 final_rec 计数 > 0 且匹配 | state.json |
| 5 | 12 篇 state_keys 非空率 ≥ 80% | trace 中有 state_keys 的节点比例 |

**P1 — 应该通过**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 6 | feasibility 有区分度 | 12 篇不全是同一 verdict |
| 7 | review verdict 有区分度 | 12 篇不全是同一 verdict |
| 8 | 无 "deep learning" 硬编码 | 检查 search_steps（非 "深度学习" 题目） |
| 9 | R36-015 识别合规风险 | feasibility reason 含 "合规" 或 "隐私" |
| 10 | R36-094 识别非 CV 领域 | feasibility 不是全 not_recommended |

**P2 — 加分项**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 11 | dataset_candidates 非空 | ≥3 篇有数据集 |
| 12 | repo_candidates 非空 | ≥3 篇有仓库 |
| 13 | R36-074 与 Batch20 结果一致 | 仍为 feasible |

#### 5.4 失败处理

- **≥10 篇 PASS**：视为通过，失败的 ≤2 篇记录为已知限制
- **<10 篇 PASS**：分析失败模式（是 API 限流还是系统 bug），修复后重跑失败 case
- **某领域全部失败**：可能是搜索适配器对该领域覆盖不足，记录领域 gap

### Phase 6：完工报告 + CHANGELOG (30min)

#### 6.1 完工报告

撰写 `Plan/PaperAgent_Re3.6_完工报告.md`，包含：
- state_keys 覆盖率统计（X/25 节点非空）
- F821/F822 修复清单（逐项 before→after）
- 8 张截图对照表
- 20 篇批量回归结果表（含与 Batch20 对比）
- SOP 验收条件逐项对照

#### 6.2 CHANGELOG

```markdown
## [Unreleased]

### Added (Re3.6)
- state_keys coverage: all graph nodes now report returned state keys in trace
- 20-paper batch regression with domain matrix coverage

### Fixed (Re3.6)
- F821 undefined-name: 10 errors fixed (eval/__init__.py, llm.py, citation_expand.py, etc.)
- F822 undefined-export: 6 errors fixed (_research_agent_compat.py __all__)
- dataset_extractor medical domain constraint strengthened (COCO→LIDC-IDRI)

### Changed (Re3.6)
- ruff errors: 95 → target <50 (F821/F822 = 0)
- Timeline debugger "state changes" panel now shows non-empty key tags
```

## 3. 执行者规则

1. **Phase 1 必须在 Phase 4 之前完成**——截图需要验证 state_keys 有内容
2. **Phase 2-3 可以与 Phase 1 并行**——不同文件
3. **Phase 5 串行提交**——避免 API 限流
4. **Phase 5 每篇完成后立即检查**——不要等全部跑完才发现问题
5. **P0 项失败必须修复后重跑**
6. **遵循 CODELY.md 中的所有开发约定**
7. **VOAPI/MiniMax = 0**
8. **所有 LLM 凭证从 .env 读取**

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `apps/api/app/services/agents/graph/nodes/*.py` (~13 个) | 🔧 state_keys 传入 | 1 |
| `apps/api/app/services/agents/graph/nodes/verify.py` | 🔧 手工 trace 添加 state_keys | 1 |
| `apps/api/app/services/agents/graph/nodes/search_agent.py` | 🔧 手工 trace 添加 state_keys | 1 |
| `apps/api/app/services/agents/graph/nodes/quality_filter.py` | 🔧 手工 trace 添加 state_keys | 1 |
| `apps/api/app/services/agents/eval/__init__.py` | 🔧 F821 修复或归档 | 2 |
| `apps/api/app/services/llm.py` | 🔧 F821 _collect_stream | 2 |
| `apps/api/app/services/agents/citation_expand.py` | 🔧 F821 函数名 | 2 |
| `apps/api/app/services/agents/_research_agent_compat.py` | 🔧 F822 或归档 | 2 |
| `apps/api/scripts/re10_fix2_to_csv.py` | 🔧 F821 | 2 |
| `apps/api/tests/test_re1_1_no_secret_leak.py` | 🔧 F821 | 2 |
| `apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py` | 🔧 医学约束 | 3 |
| `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py` | 🔧 known_dataset_names | 3 |
| `scripts/re36_batch_verify.py` | 🆕 批量验证脚本 | 5 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re36_eval/screenshots/*.png` | 8 张截图 |
| `tmp_re36_eval/R36-*/state.json` | 12 篇 state |
| `tmp_re36_eval/R36-*/trace.json` | 12 篇 trace |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.6_完工报告.md` | 完工报告 |
| `CHANGELOG.md` | 更新 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | state_keys 全节点非空 | trace.json 检查 | P0 |
| 2 | 截图 #4 (state_keys) 有绿色标签 | 截图 | P0 |
| 3 | 截图 #7 (Console) 无红色 | 截图 | P0 |
| 4 | F821 = 0 | ruff check | P0 |
| 5 | F822 = 0 | ruff check | P0 |
| 6 | 12 篇全部完成 | state.json 存在 | P0 |
| 7 | 12 篇无 RecursionError | trace.json | P0 |
| 8 | 12 篇 verified_papers ≥ 3 | state.json | P0 |
| 9 | 12 篇 final_rec 匹配 | state.json | P0 |
| 10 | state_keys 非空率 ≥ 80% | trace.json | P0 |
| 11 | ruff errors < 50 | ruff check | P1 |
| 12 | feasibility 有区分度 | state.json | P1 |
| 13 | review 有区分度 | state.json | P1 |
| 14 | R36-015 识别合规风险 | state.json | P1 |
| 15 | 无 "deep learning" 硬编码 | search_steps | P1 |
| 16 | 8 张截图全部截取 | 文件检查 | P1 |
| 17 | 完工报告 + CHANGELOG | 文件检查 | P2 |
| 18 | VOAPI/MiniMax = 0 | 全程 | P0 |

## 6. 执行顺序

```
Phase 1 (1h):    state_keys 全节点覆盖 (15+ 处修改)
       ↓                              ↑ 可并行
Phase 2 (1h):    F821/F822 修复        Phase 3 (30min): dataset prompt 强化
       ↓
Phase 4 (30min): 8 张截图验证
       ↓
Phase 5 (2.5-3h): 20 篇批量回归 ← 核心
       ↓
Phase 6 (30min): 完工报告 + CHANGELOG
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DeepSeek API 429 | 高 | 批量回归无法完成 | 分批提交，批间冷却 30s |
| search_agent.py 手工 trace 添加出错 | 中 | trace 格式不一致 | 改完后跑 test_re1_2_graph_nodes |
| F821 修复引入回归 | 低 | 代码行为变化 | 逐个修复后跑测试 |
| 12 篇中某领域全部失败 | 中 | 系统鲁棒性不足 | 记录领域 gap，分析搜索适配器覆盖 |
| 截图时 case 未完成 | 低 | 截图为空 | 用已完成的 R35-046 case |
| state_keys 漏改某 node | 低 | 覆盖率不达标 | 改完后跑验证脚本检查所有 trace |

## 8. TODO 推进（Re3.7+）

| TODO | 评估 |
|---|---|
| 100 篇全量回归 | Re3.7（20 篇通过后扩展） |
| PubMed E-utilities | Re3.7 |
| Unpaywall | Re3.7 |
| LangSmith 集成 | Re3.7 |
| React+Vite 前端 | Re4.0 |
| StageContract 机制 | Re4.0 |
| search_agent think→call→observe 明细 | Re3.7 |
| 时间线键盘导航 | Re3.7 |
| E402 测试文件 ruff 修复 | 接受现状或 Re3.7 |
