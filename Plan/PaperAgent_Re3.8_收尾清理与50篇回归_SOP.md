# PaperAgent Re3.8 收尾清理 + 系统性问题修复 + 50 篇回归 SOP

> 承接：Re3.7 硬编码清除完成（8 项 Critical 全部修复），但深度分析 18 篇产物发现 10 个系统性问题；12 篇批量回归仅完成 5/12、零截图、4 处残余 BaseException。
> **本 SOP 聚焦：收尾清理 → 10 个系统性问题修复 → 补全回归 + 截图 → 50 篇扩展 → Re3.x 收官**
> 预计总时长：10-12 小时，分 7 个 Phase（含系统性问题修复）。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 跨版本遗留盘点

### Re3.6 遗留

| # | 问题 | 状态 |
|---|---|---|
| L1 | 12 篇批量回归仅完成 5/12（R36-003/007/015/021/052 PASS，7 篇 SKIP 无 state.json） | 🔴 未完成 |
| L2 | 8 张截图（时间线调试器 + Console）—— 3 个版本承诺，0 张交付 | 🔴 未完成 |
| L3 | state_keys e2e 验证 —— R36-003 trace 确认 26/27 非空（仅 citation_expander 为空），但未在报告中记录 | ✅ 已验证未记录 |

### Re3.7 遗留

| # | 问题 | 状态 |
|---|---|---|
| L4 | 4 处残余 `except BaseException`（search_planner.py L297、targeted_repair.py L231、topic_parser.py L243、llm_router.py L199） | 🟡 10 分钟修复 |
| L5 | research_agent.py L1887 过时注释 `# ponytail: ~400 lines` | 🟡 1 分钟修复 |
| L6 | citation_expander 节点 state_keys 为空（R36-003 trace 中唯一空节点） | 🟡 1 行修复 |
| L7 | Re3.7 硬编码移除后未跑 e2e 验证——当 LLM 不可用走 heuristic 路径时 domain 全返回 "unknown"、中文关键词不再翻译 | 🟡 需至少 1 个 e2e case |

### 系统性问题（18 篇产物深度分析）

#### 🔴 P0 — 影响核心功能

| # | 问题 | 证据 | 根因 |
|---|---|---|---|
| S1 | **feasibility 评分聚集在 75 分** | 18 篇中 11 篇得 75；R36-015 有 14 篇+12 baseline 但得 45，R34-092 仅 5 篇却得 75 | prompt 评分标准模糊（"baseline>=1 + 有数据集或 repo → feasible 60-100"），LLM 倾向给中间值 |
| S2 | **数据集提取极弱——13/18 篇为 0** | 72% 的 case 无数据集；R34-046 机械臂应有 RGB-D 数据集，R36-015 人体重建应有 SURREAL/Human3.6M | extractor 只看 title+abstract[:800]，GitHub URL 在摘要后半段被截断；LLM 对数据集名识别能力有限 |
| S3 | **仓库覆盖率不均——8/18 篇为 0** | 机械臂/多模态/点云/人体重建全 0；缺陷检测类 10+ | search_agent 在已有论文后倾向 stop 而非继续搜 GitHub；GitHub 对"理论方法/跨学科"类话题失效 |

#### 🟡 P1 — 影响评估质量

| # | 问题 | 证据 | 根因 |
|---|---|---|---|
| S4 | **baseline/parallel 分类不均衡** | R36-007: 17/1（17 篇方法相同？），R36-021: 6/48（48 parallel 极不寻常） | LLM 机械匹配方法关键词——标题含方法词→baseline，不含→parallel |
| S5 | **topic_parser 中文翻译不稳定** | 4 个新题目中 2 个未翻译（"伪深度图误差过滤方法"、"无监督立体匹配"），arxiv 返回 0 | prompt 未明确要求 "ALL keywords MUST be in English"；_CN_EN_MAP 已删（Re3.7），heuristic 不再翻译 |
| S6 | **search_agent 查询重复严重** | R34-046 同一查询重复 8 次，R34-033 重复 8 次，R34-066 重复 7 次 | LLM 忽略 prior_steps；_llm_decide 无等效 _fallback_decide 的去重机制 |
| S7 | **零 BLOCK verdict——评审过于宽松** | 18 篇中 ACCEPT(8)+MINOR_REVISION(10)，无 BLOCK；R34-066 仅 3 篇+0 repo+0 dataset 仍 MINOR_REVISION | devils_advocate _heuristic 在"有 baseline"时直接返回 ACCEPT |

#### 🟢 P2 — 改进建议

| # | 问题 | 证据 |
|---|---|---|
| S8 | R36-021 数据异常——55 篇论文但只 6 篇 baseline | citation_expander 展开过多引用 |
| S9 | Re3.7 硬编码移除后未跑 e2e 验证 | = L7 |
| S10 | S2 API 429 限流持续影响 | R36-003 耗时 878s，R34-066 仅 3 篇；429 后立即标记 failed 不重试 |

### 系统性 TODO（跨 7 个 SOP 反复推迟）

| TODO | 首次提出 | 已推迟版本数 |
|---|---|---|
| 50-100 篇全量回归 | Re3.1 | 7 |
| 截图验证 | Re3.3 | 5 |
| PubMed E-utilities | Re3.1 | 7 |
| LangSmith 集成 | Re3.0 | 7 |
| React+Vite 前端 | Re3.1 | 7 → Re4.0 |
| search_agent think→call→observe 明细 | Re3.5 | 3 |
| 时间线键盘导航 | Re3.5 | 3 |

## 1. 本轮目标

1. **收尾清理**——4 处 BaseException + 过时注释 + citation_expander state_keys（15 分钟）
2. **系统性问题修复**——feasibility 评分精细化 + dataset_extractor 扩大范围 + search_agent 防重复 + topic_parser 强制英文 + devils_advocate heuristic 修复
3. **补全 7 篇回归**——完成 Re3.6 未跑完的 7 个 case
4. **截图验证**——8 张时间线调试器截图
5. **50 篇扩展回归**——从 100 篇测试集中选 50 篇（含已完成的 17 篇 + 33 篇新），验证系统鲁棒性
6. **Re3.x 系列收官报告**——汇总 Re3.0→Re3.8 全部交付物

不做：
- PubMed / Unpaywall / LangSmith（Re4.0）
- React+Vite 前端（Re4.0）
- research_agent.py 拆分（Re4.0）
- 100 篇全量（50 篇通过后按需扩展）
- S2 API 退避策略（Re4.0，需架构级改造）

## 2. Phase 设计

### Phase 1：收尾清理 (15min)

#### Fix 1.1: 4 处 `except BaseException` → `except Exception`

| 文件 | 行号 | 当前 | 修改后 |
|---|---|---|---|
| `search_planner.py` | L297 | `except BaseException as exc:  # noqa: BLE001` | `except Exception as exc:` |
| `targeted_repair.py` | L231 | 同上 | 同上 |
| `topic_parser.py` | L243 | 同上 | 同上 |
| `llm_router.py` | L199 | `except BaseException as exc:` | `except Exception as exc:` |

**验证**：
```bash
.venv/Scripts/python.exe -c "
import inspect
from apps.api.app.services.agents.graph.nodes import search_planner, targeted_repair, topic_parser
from apps.api.app.services import llm_router
for mod in [search_planner, targeted_repair, topic_parser, llm_router]:
    src = inspect.getsource(mod)
    assert 'except BaseException' not in src, f'{mod.__name__} still has BaseException!'
print('OK: zero BaseException')
"
```

#### Fix 1.2: 删除过时 ponytail 注释

**文件**：`apps/api/app/services/agents/research_agent.py` L1887

```python
# 删除:
# # ponytail: ~400 lines, single block, no premature abstraction.
```

#### Fix 1.3: citation_expander state_keys

**文件**：`apps/api/app/services/agents/graph/nodes/content.py`（或 citation_expander 所在文件）

R36-003 trace 中 citation_expander 是唯一 `state_keys: []` 的节点。找到该节点的 `_emit()` 调用，添加 `state_keys=` 参数。

```python
# 找到 citation_expander 的 _emit 调用，添加:
state_keys=["expanded_papers", "seed_papers", "surveys_found", "trace_events"]
```

### Phase 2：系统性问题修复 — Feasibility + Dataset + Search (3h)

#### Fix 2.1: feasibility 评分精细化 (S1)

**文件**：`apps/api/app/services/agents/prompts/feasibility_assessor.py`

**问题**：18 篇中 11 篇得 75 分。prompt 评分标准过于模糊（"baseline>=1 + 有数据集或 repo → feasible 60-100"），LLM 倾向给中间值。R36-015 有 14 篇+12 baseline 但得 45，R34-092 仅 5 篇却得 75，评分不一致。

**修复**：将模糊区间改为精确评分锚点：

```python
# 修改 USER_TEMPLATE 中的评估标准:
评估标准 (严格按此锚点评分，不得给"安全默认值"):
- feasible (75-100分):
  - 85-100: baseline≥3 + 有数据集 + 有repo，证据链完整
  - 75-84: baseline≥1 + 有数据集或repo，但其中一项不足
- risky (40-74分):
  - 60-74: baseline≥3 但无数据集无repo（方法可复现但需自建数据）
  - 40-59: baseline<3 或涉及硬件/合规风险且无降级方案
- not_recommended (0-39分):
  - 0-39: 无baseline，或题目过于宽泛，或风险无法降级

重要: 不得对所有case给同一个score。根据baseline数量、repo有无、数据集匹配度、
领域风险给出差异化分数。有repo的比没repo的score高10-20分。
有数据集的比没数据集的score高10-15分。
涉及硬件/合规风险且无降级方案的score降10-20分。
```

**验证**：跑 2 个 case（R36-015 应升到 ≥60，R34-092 应降到 ≤70），确认分数不再聚集在 75。

#### Fix 2.2: dataset_extractor 扩大提取范围 (S2)

**文件**：`apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py` + `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`

**问题**：13/18 篇为 0 数据集。extractor 只看 `title[:300] + abstract[:800]`，GitHub URL 在摘要后半段被截断。且 LLM 对数据集名识别能力有限。

**修复 A — 扩大提取范围**：

```python
# re11_dataset_repo_extractor.py build() 函数:
# 修改前:
abstract=(abstract or "")[:800],
snippet=(combined_snippet or "")[:800],

# 修改后:
abstract=(abstract or "")[:2000],   # 800→2000
snippet=(combined_snippet or "")[:2000],
```

**修复 B — 降级指引（纯指令，不塞具体数据集名）**：

⚠️ 设计约束：不得在 prompt 中写 `领域→数据集名` 映射——这会变成 `RE02_DATASET_WHITELIST` 的 prompt 版本，违反 rules.md §10 "LLM will mimic example direction"。Re3.7 刚删掉的硬编码会换马甲回来。

正确做法是只给 LLM 行为指令，不给具体答案，让 LLM 用自己的知识推断：

```python
# 在 SYSTEM prompt 中添加:
"""
## 降级策略 — 当论文未明确提到数据集时

如果论文未直接提到数据集名称：
1. 从论文引用的方法、技术栈、对比实验中推断该领域常用的公开 benchmark
2. 在 missing 字段中注明"论文未明确提及数据集，已基于领域推断"
3. 设置 status="degraded_lookup"
4. 不要猜测不确定的数据集名称——如果无法确定，返回 status="not_found_in_paper"

判断依据：论文是否提到了 KITTI/COCC/ImageNet 等已知 benchmark？
论文的方法章节是否引用了带数据集的对比方法？
论文的实验设置是否暗示了特定的数据来源？
"""
```

**关键区别**：prompt 说的是"从论文内容推断"和"不要猜测"，而不是"机械臂→YCB/GraspNet"。LLM 用自己的知识去找，我们不告诉它答案。这与 Re3.7 删除的 `RE02_DATASET_WHITELIST` 本质不同——whitelist 是 `domain→dataset` 硬映射，这里是让 LLM 自主推理的行为指令。

**修复 C — heuristic known_dataset_names 扩充**：

```python
# dataset_repo_extractor.py L257:
# 补充更多领域的数据集名
known_dataset_names = [
    # 通用
    "COCO", "Pascal VOC", "ImageNet", "CIFAR", "MNIST",
    # 缺陷检测
    "NEU-DET", "GC10-DET", "MVTec AD",
    # SLAM/点云
    "DTU", "ETH3D", "Tanks and Temples", "BlendedMVS", "TUM RGBD",
    "ScanNet", "Matterport3D", "KITTI", "EuRoC", "Bonn", "Middlebury",
    # 自动驾驶
    "Cityscapes", "nuScenes", "DOTA", "VisDrone", "UAVDT", "Waymo",
    # 遥感
    "DIOR", "LEVIR-CD", "AID", "NWPU-RESISC45", "xView",
    # 医学
    "LIDC-IDRI", "MIMIC-CXR", "ChestX-ray14", "NIH ChestX-ray",
    "BRATS", "ISIC", "TCIA", "PACS", "CheXpert", "LUNA16",
    # 机器人/机械臂
    "YCB", "GraspNet", "DexNet", "EGAD",
    # 人体重建
    "SURREAL", "Human3.6M", "AMASS", "SMPL",
    # 深度估计
    "Make3D", "NYU Depth V2", "DIODE",
    # 裂缝
    "DeepCrack", "CrackTree", "GAPs384", "CRACK500",
    # 能源
    "openEMS", "Meep",
    # 补充
    "ShapeNet", "ModelNet", "PlantVillage",
]
```

#### Fix 2.3: search_agent 防重复查询 (S6)

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

**问题**：LLM 主路径 `_llm_decide` 无去重机制，同一查询重复 7-8 次。`_fallback_decide` 有去重（L171-181），但 LLM 路径没有。

**修复**：在 `_llm_decide` 的返回值处理中添加去重检查：

```python
# _llm_decide 函数中，在 return result 之前添加:
if isinstance(result, dict):
    # Re3.8: 防重复查询——如果 LLM 返回了已用过的 tool+query，强制换一个
    tool = result.get("tool", "").strip().lower()
    query = result.get("query", "").strip()
    used = {
        (s.get("tool"), s.get("query"))
        for s in steps
        if s.get("type") == "tool_call"
    }
    if (tool, query) in used:
        # 查询已用过——尝试 _fallback_decide 获取新查询
        logger.info("search_agent: LLM returned duplicate query %s:%s, using fallback", tool, query[:50])
        fallback = _fallback_decide(steps, search_plan, all_papers, all_repos, failed_tools)
        if fallback.get("action") != "stop":
            return fallback
        # fallback 也 stop 了——让 LLM 的原始结果通过（可能是 LLM 有理由重复）
    return result
```

**同时在 system prompt 中强化防重复提醒**：

```python
# _SYSTEM_PROMPT 中添加:
"""
重要: 不要重复已经用过的 tool+query 组合。查看 prior_steps 列表，
如果某个查询已经执行过，必须换关键词或换工具。
"""
```

#### Fix 2.4: topic_parser 强制英文输出 (S5)

**文件**：`apps/api/app/services/agents/prompts/re11_topic_parser.py`

**问题**：4 个新题目中 2 个未翻译为英文（"伪深度图误差过滤方法"、"无监督立体匹配"），arxiv 返回 0 结果。prompt 未明确要求英文输出。

**修复**：在 USER_TEMPLATE 中强制要求英文：

```python
# 在 USER_TEMPLATE 的 Return JSON 部分添加:
- method: list[str] — techniques (ALL IN ENGLISH, translate Chinese terms)
- object: list[str] — target (ALL IN ENGLISH, translate Chinese terms)
- task: list[str] — what to do (ALL IN ENGLISH, translate Chinese terms)

# 在 SYSTEM prompt 中添加:
ALL keywords in method/object/task MUST be in English.
If the topic is in Chinese, you MUST translate all terms to English.
For example, "目标检测" → "object detection", "语义分割" → "semantic segmentation".
Chinese keywords in the output will cause search adapters to return zero results.
```

#### Fix 2.5: devils_advocate heuristic 修复 (S7)

**文件**：`apps/api/app/services/agents/graph/nodes/devils_advocate_node.py`

**问题**：`_heuristic` 在"有 baseline"时直接返回 ACCEPT，几乎不可能得到 BLOCK。即使只有 1 篇论文也返回 ACCEPT。

**修复**：根据 baseline 数量和可行性评分差异化 heuristic verdict：

```python
# 修改前:
def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    has_baseline = len(baselines) >= 1
    if has_baseline:
        verdict = "ACCEPT"
        scores = [{"dimension": f"D{i}", "score": 6, ...} for i in range(1, 6)]
    else:
        verdict = "BLOCK"
        ...

# 修改后:
def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    n_baselines = len(baselines)
    feas = state.get("feasibility_report") or {}
    feas_verdict = feas.get("verdict", "unknown")
    feas_score = feas.get("score", 0)

    if n_baselines >= 3 and feas_verdict == "feasible":
        verdict = "ACCEPT"
        score_val = 7
        reason = f"heuristic: {n_baselines} baselines, feasible"
    elif n_baselines >= 1 and feas_score >= 50:
        verdict = "MINOR_REVISION"
        score_val = 5
        reason = f"heuristic: {n_baselines} baselines, score={feas_score}"
    else:
        verdict = "BLOCK"
        score_val = 3
        reason = f"heuristic: {n_baselines} baselines, feas={feas_verdict}"

    scores = [{"dimension": f"D{i}", "score": score_val, "verdict": verdict,
               "reason": reason} for i in range(1, 6)]
    return {"dimension_scores": scores, "overall_verdict": verdict,
            "fabrication_alerts": [], "risks_identified": ["heuristic review"],
            "verdict_source": "heuristic"}
```

### Phase 3：补全 7 篇回归 (2-2.5h)

#### 2.1 待跑 7 篇

| Case ID | ENG-THESIS | 题目 | 领域 | 预计重点 |
|---|---|---|---|---|
| R36-060 | 060 | 基于深度学习的车道线检测方法研究 | 自动驾驶 | 中难度 |
| R36-074 | 074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木/裂缝 | Batch20 ACCEPT，回归 |
| R36-079 | 079 | 基于结构光的隧道裂缝检测技术研究与实现 | 土木/裂缝 | 中-高难度 |
| R36-084 | 084 | 基于U-Net卷积网络的地质岩层裂缝检测方法 | 土木/裂缝 | U-Net 领域 |
| R36-091 | 091 | 基于云计算的输电线路缺陷检测平台 | 电力巡检 | 中难度 |
| R36-094 | 094 | 基于SCADA数据的风机叶片结冰诊断研究 | 能源装备 | 非 CV 为主 |
| R36-100 | 100 | 基于深度学习的配电设备视觉识别技术研究 | 电力巡检 | 中难度 |

#### 2.2 执行方式

**串行提交**，每个 case 完成后再提交下一个。每篇完成后立即运行验证脚本：

```bash
.venv/Scripts/python.exe scripts/re36_batch_verify.py
```

#### 2.3 验收标准

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 7 篇全部完成 | state.json 存在 |
| 2 | 7 篇无 RecursionError | trace.json |
| 3 | 7 篇 verified_papers ≥ 3 | state.json |
| 4 | 7 篇 final_rec 计数匹配 | state.json |
| 5 | state_keys 非空率 ≥ 90% | trace.json（含 Fix 1.3 后 citation_expander） |
| 6 | feasibility 有区分度 | 不全是同一 verdict |
| 7 | review 有区分度 | 不全是同一 verdict |
| 8 | R36-074 与 Batch20 一致 | 仍为 feasible |
| 9 | R36-094 识别非 CV 领域 | feasibility 不是全 not_recommended |

### Phase 3：截图验证 (30min)

#### 3.1 前置条件

- Phase 1-2 完成
- server 运行中
- 至少 1 个 case 的 state.json + trace.json 可用（R36-003 有 27 个 trace 事件 + state_keys 26/27 非空）

#### 3.2 截图清单

用 R36-003（点云三维重建，27 事件，state_keys 覆盖率高）或 R36-021（自动驾驶，55 篇论文，数据丰富）：

| # | 截图 | 内容 | 通过标准 |
|---|---|---|---|
| 1 | 01_timeline_overview | 时间线全貌，27 个彩色节点段 | 段可见且宽度不同 |
| 2 | 02_timeline_search_agent | 点击 search_agent 节点 | 工具调用标签 ≥3 个 |
| 3 | 03_timeline_state_keys | 点击任意节点 | "状态变更"区域有 ≥1 个绿色 key 标签 |
| 4 | 04_timeline_verify | 点击 verify 节点 | 输入/输出摘要可见 |
| 5 | 05_timeline_dragging | 拖动 slider | 累计计数数字变化 |
| 6 | 06_timeline_final | 点击 final_recommendation | 输出含计数信息 |
| 7 | 07_console_clean | F12 Console | 无红色错误 |
| 8 | 08_timeline_devils | 点击 devils_advocate 节点 | 显示 review verdict |

**保存路径**：`tmp_re38_eval/screenshots/`

### Phase 4：50 篇扩展回归 (3-3.5h)

#### 4.1 章节选择

已完成 17 篇（Re3.4 6 篇 + Re3.5 2 篇 + Re3.6 5 篇 + Phase 2 补 7 篇 = 20 篇）。新增 30 篇，从 100 篇测试集中按领域矩阵选：

**已完成的 20 篇领域分布**：
- 三维视觉/SLAM (V-SLAM-33, R36-003) = 2
- YOLO/农业 (V-YOLO-33) = 1
- 医学 (V-MED-33, R34-033, R35-033, R36-015) = 4
- 工业缺陷 (R34-002, R34-092) = 2
- 机械臂 (R34-046, R35-046) = 2
- 自动驾驶 (R34-038, R36-021, R36-052, R36-060) = 4
- 多模态 (R34-066) = 1
- 遥感/无人机 (R36-007) = 1
- 土木/裂缝 (R36-074, R36-079, R36-084) = 3

**新增 30 篇**（覆盖未测领域 + 加密已有领域）：

| 领域 | 新增篇数 | ENG-THESIS ID 范围 | 重点 |
|---|---|---|---|
| 工业缺陷检测 | 5 | 005, 008, 011, 014, 023 | YOLO/GAN 缺陷检测 |
| 土木/裂缝 | 3 | 075, 076, 083 | 回归验证 |
| 自动驾驶 | 3 | 047, 050, 067 | 交通感知 |
| 电力/巡检 | 4 | 026, 040, 095, 098 | 巡检视觉 |
| 遥感/无人机 | 3 | 037, 043, 027 | 航拍检测 |
| 三维视觉/SLAM | 3 | 006, 009, 018 | 点云重建 |
| 工科AI/CV | 4 | 004, 013, 029, 034 | 通用检测 |
| 机器人/机械臂 | 2 | 049, 057 | 硬件依赖 |
| 能源装备 | 2 | 094, 096 | 非 CV 领域 |
| 医学 | 1 | 033 | 回归验证 |

#### 4.2 执行方式

**分批串行**，每批 5 篇，批间冷却 30s。使用自动化脚本：

```bash
# 批量提交脚本（复用 re36_batch_verify.py 模式）
.venv\Scripts\python.exe scripts\re38_batch_run.py
```

#### 4.3 自动化验证脚本

```python
# scripts/re38_batch_verify.py
import json, os, sys

# 全部 50 篇 case ID
ALL_CASES = [
    # 已完成 20 篇
    "V-YOLO-33", "V-SLAM-33", "V-MED-33",
    "R34-002", "R34-033", "R34-038", "R34-046", "R34-066", "R34-092",
    "R35-033", "R35-046",
    "R36-003", "R36-007", "R36-015", "R36-021", "R36-052",
    "R36-060", "R36-074", "R36-079", "R36-084", "R36-091", "R36-094", "R36-100",
    # 新增 30 篇
    "R38-005", "R38-008", "R38-011", "R38-014", "R38-023",
    "R38-075", "R38-076", "R38-083",
    "R38-047", "R38-050", "R38-067",
    "R38-026", "R38-040", "R38-095", "R38-098",
    "R38-037", "R38-043", "R38-027",
    "R38-006", "R38-009", "R38-018",
    "R38-004", "R38-013", "R38-029", "R38-034",
    "R38-049", "R38-057",
    "R38-094b", "R38-096",
    "R38-033b",
]

EVAL_DIRS = ["tmp_re13_eval", "tmp_re34_eval", "tmp_re35_eval", "tmp_re36_eval", "tmp_re38_eval"]

def find_state(case_id):
    for d in EVAL_DIRS:
        p = os.path.join(d, case_id, "state.json")
        if os.path.exists(p):
            return p
    return None

results = []
for case_id in ALL_CASES:
    sp = find_state(case_id)
    if not sp:
        results.append((case_id, "SKIP", "no state.json"))
        continue
    d = json.load(open(sp, encoding="utf-8"))
    vp = len(d.get("verified_papers", []))
    fr = d.get("final_recommendation", {})
    feas = d.get("feasibility_report", {})
    review = d.get("review_report", {})
    
    # Find trace
    tp = sp.replace("state.json", "trace.json")
    trace = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else []
    has_recursion = any("RecursionError" in str(e) for ev in trace for e in ev.get("errors", []))
    sk_count = sum(1 for ev in trace if ev.get("state_keys"))
    
    issues = []
    if vp < 3: issues.append(f"vp={vp}")
    if fr.get("n_papers", 0) != vp: issues.append(f"fr_mismatch={fr.get('n_papers')}!={vp}")
    if fr.get("n_papers", 0) == 0: issues.append("fr=0")
    if has_recursion: issues.append("RecursionError")
    
    status = "FAIL" if issues else "PASS"
    results.append((case_id, status, f"vp={vp} feas={feas.get('verdict','?')} review={review.get('overall_verdict','?')} sk={sk_count}/{len(trace)} | {';'.join(issues)}"))

print("=" * 100)
print(f"Re3.8 50-Paper Regression Results")
print("=" * 100)
for case_id, status, detail in results:
    print(f"{case_id:15s}: {status:4s} | {detail}")
n_pass = sum(1 for _, s, _ in results if s == "PASS")
n_skip = sum(1 for _, s, _ in results if s == "SKIP")
n_fail = sum(1 for _, s, _ in results if s == "FAIL")
print(f"\nTOTAL: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP out of {len(results)}")
```

#### 4.4 验收标准

**P0**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 30 篇新增全部完成 | state.json 存在 |
| 2 | 30 篇无 RecursionError | trace.json |
| 3 | 30 篇 verified_papers ≥ 3 | state.json |
| 4 | 30 篇 final_rec 匹配 | state.json |
| 5 | 50 篇总计 PASS 率 ≥ 80% | 40/50 PASS |

**P1**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 6 | feasibility 有区分度 | ≥2 种 verdict |
| 7 | review 有区分度 | ≥2 种 verdict |
| 8 | 无 "deep learning" 硬编码 | 非"深度学习"题目 |
| 9 | state_keys 非空率 ≥ 90% | 跨全部 50 篇 |
| 10 | R38-049/057 识别硬件风险 | feasibility reason |

**P2**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 11 | dataset_candidates 覆盖率 | ≥15/50 篇有数据集 |
| 12 | repo_candidates 覆盖率 | ≥20/50 篇有仓库 |
| 13 | 按 10 领域分析 PASS 率 | 每领域 ≥50% |

#### 4.5 失败处理

- **≥40 篇 PASS**：Re3.x 系列收官，进入 Re4.0
- **30-39 篇 PASS**：分析失败模式，修复后补跑失败 case
- **<30 篇 PASS**：系统鲁棒性不足，需深入分析根因

### Phase 5：Re3.x 系列收官报告 (1h)

#### 5.1 收官报告

撰写 `Plan/PaperAgent_Re3.x_收官报告.md`，汇总 Re3.0→Re3.8 全部交付：

| 版本 | 核心交付 | P0 通过率 |
|---|---|---|
| Re3.0 | React search agent + reflection strategy + recursion_limit | — |
| Re3.1 | User paper upload + arXiv fulltext + Crossref filtering | — |
| Re3.2 | verify.py imports + CORE/DataCite adapters + 8 tools + 3-case 首跑 | 6/6 |
| Re3.3 | #statusBar + BLOCK 循环 + 重复边 + 6 个展示区 + 42 张截图 | 12/13 |
| Re3.4 | final_rec e2e 验证 + 60 legacy 归档 + retrieve 删除 + 6-case 回归 | 15/17 |
| Re3.5 | 时间线调试器 + feasibility prompt 增强 + .ruff.toml | 8/17 |
| Re3.6 | state_keys 19 文件 + F821/F822 归零 + dataset prompt | 5/12 (部分) |
| Re3.7 | 硬编码 6 项清除 + prompt 注入修复 + OUTPUT CONTRACT | 8/8 Critical |
| Re3.8 | 收尾清理 + 补全回归 + 截图 + 50 篇扩展 | TBD |

#### 5.2 CHANGELOG 更新

#### 5.3 Re4.0 方向建议

| 方向 | 内容 | 理由 |
|---|---|---|
| React+Vite 前端 | 替换 vanilla JS 单文件 | index.html 已 800+ 行，维护困难 |
| research_agent.py 拆分 | 2821 行 → 多模块 | 确认非 graph 关键路径，但组织债 |
| LangSmith 集成 | 可观测性 | 50 篇回归需要调试工具 |
| PubMed / Unpaywall | 搜索源补强 | 医学领域覆盖不足 |
| StageContract 机制 | 架构级 | 节点间契约保证 |

## 3. 执行者规则

1. **Phase 1 必须在 Phase 2 之前完成**——收尾修复影响后续系统性修复
2. **Phase 2 必须在 Phase 3 之前完成**——系统性修复后再跑回归验证效果
3. **Phase 3 必须在 Phase 5 之前完成**——先补全 12 篇再扩展到 50
4. **Phase 4 可以在 Phase 3 完成后随时执行**——需要 server 运行
5. **Phase 5 串行提交**——避免 API 限流
6. **50 篇 PASS 率 ≥ 80% 才算 Re3.x 收官**
7. **VOAPI/MiniMax = 0**
8. **所有 LLM 凭证从 .env 读取**

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `search_planner.py` | 🔧 BaseException→Exception | 1 |
| `targeted_repair.py` | 🔧 BaseException→Exception | 1 |
| `topic_parser.py` | 🔧 BaseException→Exception | 1 |
| `llm_router.py` | 🔧 BaseException→Exception | 1 |
| `research_agent.py` | 🔧 删除过时注释 | 1 |
| `content.py`（或 citation_expander 所在文件） | 🔧 state_keys | 1 |
| `scripts/re38_batch_run.py` | 🆕 批量提交脚本 | 4 |
| `scripts/re38_batch_verify.py` | 🆕 50 篇验证脚本 | 4 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re38_eval/screenshots/*.png` | 8 张截图 |
| `tmp_re38_eval/R38-*/state.json` | 30 篇新 state |
| `tmp_re38_eval/R38-*/trace.json` | 30 篇新 trace |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.8_完工报告.md` | 完工报告 |
| `Plan/PaperAgent_Re3.x_收官报告.md` | Re3.x 系列收官报告 |
| `CHANGELOG.md` | 更新 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | 0 处 except BaseException（全局） | ruff check + 代码搜索 | P0 |
| 2 | 过时 ponytail 注释删除 | 代码搜索 | P1 |
| 3 | citation_expander state_keys 非空 | trace.json | P0 |
| 4 | feasibility 不再聚集在 75 分 | 12 篇回归 score 分布 ≥3 种 | P0 |
| 5 | dataset 覆盖率 > 30%（从 28% 提升） | 12 篇中 ≥4 篇有 dataset | P0 |
| 6 | search_agent 无重复查询（同 tool+query ≤2 次） | trace.json search_steps | P0 |
| 7 | topic_parser 输出全英文 | topic_atoms.method 无中文 | P0 |
| 8 | devils_advocate heuristic 有 3 种 verdict | 代码检查 | P0 |
| 9 | 7 篇补全回归全部完成 | state.json 存在 | P0 |
| 10 | 12 篇总计 ≥10 篇 PASS | 验证脚本 | P0 |
| 11 | 8 张截图全部截取 | 文件检查 | P0 |
| 12 | 截图 #3 state_keys 有绿色标签 | 截图 | P0 |
| 13 | 截图 #7 Console 无红色 | 截图 | P0 |
| 14 | 30 篇新增全部完成 | state.json | P0 |
| 15 | 50 篇 PASS 率 ≥ 80% | 验证脚本 | P0 |
| 16 | 50 篇无 RecursionError | trace.json | P0 |
| 17 | state_keys 非空率 ≥ 90%（50 篇平均） | trace.json | P0 |
| 18 | feasibility 有区分度（≥3 种 score） | state.json | P1 |
| 19 | review 有区分度 | state.json | P1 |
| 20 | R38-049/057 识别硬件风险 | state.json | P1 |
| 21 | 完工报告 + 收官报告 + CHANGELOG | 文件检查 | P2 |
| 22 | VOAPI/MiniMax = 0 | 全程 | P0 |

## 6. 执行顺序

```
Phase 1 (15min): 收尾清理 (4 BaseException + 注释 + state_keys)
       ↓
Phase 2 (3h):    系统性问题修复 (S1-S7) ← 核心
       ↓
Phase 3 (2-2.5h): 补全 7 篇回归
       ↓
Phase 4 (30min):  8 张截图
       ↓
Phase 5 (3-3.5h): 30 篇扩展 → 50 篇总量
       ↓
Phase 6 (1h):     Re3.x 收官报告 + CHANGELOG + Re4.0 方向
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DeepSeek API 429 | 高 | 50 篇无法完成 | 分批提交，批间冷却 30s |
| S2/OpenAlex 429 | 高 | 搜索结果少 | search_agent 跳过失败适配器 |
| 50 篇 PASS 率 < 80% | 中 | 系统鲁棒性不足 | 分析失败模式，按领域定位 |
| 截图时 server 未运行 | 低 | 无法截图 | 先启动 server 再截图 |
| 某领域全部失败 | 中 | 领域 gap | 记录领域 gap，分析搜索适配器覆盖 |
| API 费用超预算 | 低 | 无法完成 50 篇 | 优先跑 P0 case，P2 case 可降级 |

## 8. TODO 推进（Re4.0+）

| TODO | 评估 |
|---|---|
| 100 篇全量回归 | Re4.0（50 篇通过后按需扩展） |
| PubMed E-utilities | Re4.0 |
| Unpaywall | Re4.0 |
| LangSmith 集成 | Re4.0 |
| React+Vite 前端 | Re4.0 |
| research_agent.py 拆分 | Re4.0 |
| StageContract 机制 | Re4.0 |
| search_agent think→call→observe 明细 | Re4.0 |
| 时间线键盘导航 | Re4.0 |
| citation_expand.py / evidence_review.py 拆分 | Re4.0 |
