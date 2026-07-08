# PaperAgent Re2.1 搜索增强与 Prompt 深度调优 SOP

> 承接：Re2 完工报告（条件边 + 创新链路验证通过）
> **本 SOP 设计为全程无人值守执行。** 用户不在场，执行者按 Phase 顺序自主执行。
> 预计总时长：4-6 小时。
> 模型：DeepSeek (主)。

## 0. 执行者必读

### 0.1 核心原则

1. **每改一处代码，必须立即重跑 3 个 case 验证（不是 1 个）。** 用 3 个覆盖不同领域/难度的 case 杜绝个案偏差。
2. **3 个验证 case 中 ≥2 个通过才算通过。** 如果 3 个全失败 → 回滚。
3. **每次只改一个文件，验证通过后再改下一个。**
4. **验证失败必须 `git checkout` 回滚，记录原因，继续下一任务。**
5. **Phase 间不传染。** Phase 1 失败不影响 Phase 2 独立运行。
6. **连续 3 次 graph crash → 停止当前 Phase，跳到下一个。**
7. **所有产出写入 `tmp_re21_eval/`，不覆盖旧 eval 目录。**

### 0.2 验证 case 集

每次代码改动后，重跑以下 3 个 case 验证：

| 验证 case | 题目 | 领域 | 难度 | 选原因 |
|---|---|---|---|---|
| V-MED | 基于大语言模型的医学问答可信度评估方法研究 | NLP/医学 | 中 | Re2 已验证创新链路跑通，有 9 accept + 4 innovation |
| V-SLAM | 基于深度学习的视觉SLAM语义地图的研究 | SLAM | 中-高 | Re1.3 v3 搜索修复后 6 accept，验证 S2 是否进一步提升 |
| V-CRACK | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木 | 低-中 | Re1.5 中 feasibility=risky(40)，验证 prompt 区分度 |

这 3 个 case 覆盖：NLP / SLAM / 工业检测 三个领域，低/中/高三个难度档。

### 0.3 验证通过标准

**对 3 个 case 的验证，以下每项需要 ≥2/3 通过：**

| 检查项 | 通过标准 |
|---|---|
| graph 完成 | ≥2/3 has_final=True |
| 无 crash | ≥2/3 无 InvalidUpdateError |
| 搜索结果非空 | ≥2/3 verified_papers + weak_papers ≥ 1 |
| 改动的目标指标改善 | ≥2/3 的目标指标有改善（见各 Phase 定义） |

**3 个全失败 → 回滚改动。**

### 0.4 改动隔离

```bash
# 改前备份
git stash create > /tmp/re21_stash_<phase>_<fix>

# 改后验证通过
echo "<file>: <改动> → 3 case 验证通过 (V-MED: pass, V-SLAM: pass, V-CRACK: fail)" >> tmp_re21_eval/changelog.md

# 改后验证失败
git checkout -- <file>
echo "<file>: <改动> → 3 case 验证全失败, 已回滚" >> tmp_re21_eval/changelog.md
```

## 1. 前置条件

- Re2 审核通过。
- `semantic_scholar_search.py` 已实现 `semantic_scholar_search()` 函数。
- S2_API_KEY 已配置。
- `tmp_re15_eval/smoke_20/` 有 20 篇 baseline 数据可对比。

## 2. 模型策略

```text
FAST_JSON_PRIMARY=deepseek
LLM_PROFILE=deepseek
S2_API_KEY=<已配置>
```

## 3. Phase 设计

### Phase 1：S2 主搜索源 (45min)

#### 问题

retrieve 节点只用 arxiv/openalex/crossref/github 4 个适配器。S2 已有适配器但只用于引文扩展。OpenAlex 429 限流导致搜索结果少。

#### 修改

**文件 1：`apps/api/app/services/retrieval/adapters/__init__.py`**

确认 `semantic_scholar` 已注册。如果没有：

```python
from .semantic_scholar_search import semantic_scholar_search
REGISTRY["semantic_scholar"] = semantic_scholar_search
```

**文件 2：`apps/api/app/services/agents/graph/nodes/retrieve.py`**

```python
# 旧：
tool_order = [tool for tool in ("arxiv", "openalex", "crossref", "github") if tool in REGISTRY]

# 新：
tool_order = [tool for tool in ("arxiv", "openalex", "crossref", "github", "semantic_scholar") if tool in REGISTRY]
```

**文件 3：`apps/api/app/services/agents/graph/nodes/search_planner.py`**

在 `_template_plan()` 中增加 S2 查询：

```python
if method and obj:
    _add("semantic_scholar", _compact(f"{method[0]} {obj[0]}"), "s2 method+object", "high-citation papers", "n>=5")
```

#### 3-case 验证

重跑 V-MED / V-SLAM / V-CRACK：

| 检查项 | 通过标准 |
|---|---|
| retrieve trace 有 semantic_scholar | ≥2/3 |
| paper_candidates ≥ Re1.5 同 case 的 1.3x | ≥2/3 |
| graph 完成 | ≥2/3 |

- [ ] 3 case 结果记录到 changelog。
- [ ] ≥2/3 通过 → 保留改动。
- [ ] 3 个全失败 → `git checkout` 回滚 → 记录 → 用旧 4 适配器继续 Phase 2。

### Phase 2：feasibility prompt 深度修复 (45min)

#### 问题

feasibility_assessor prompt 只传入论文计数，不传入论文内容。LLM 无法区分"2 baseline 有 repo"和"2 baseline 无 repo"。所有 case score 都是 15-45。

#### 修改

**文件：`apps/api/app/services/agents/prompts/feasibility_assessor.py`**

在 `build()` 函数中，把 baseline/parallel 论文的标题和 repo 有无传入 USER_TEMPLATE：

```python
# 新：传标题 + repo 状态
baseline_summary = "\n".join(
    f"- {p.get('title','')[:80]} (repo: {'有' if p.get('official_code_url') else '无'})"
    for p in baselines[:5]
) or "无 baseline 论文"

parallel_summary = "\n".join(
    f"- {p.get('title','')[:80]}"
    for p in parallels[:5]
) or "无 parallel 论文"
```

SYSTEM prompt 中的区分规则保持不变。

#### 3-case 验证

重跑 V-MED / V-SLAM / V-CRACK：

| 检查项 | 通过标准 |
|---|---|
| 3 个 case 的 feasibility score 不全相同 | ≥2/3 有差异 (max-min ≥ 15) |
| V-MED (9 accept) score ≥ V-CRACK (低 accept) | V-MED score > V-CRACK score |
| graph 完成 | ≥2/3 |

- [ ] 3 case 结果记录到 changelog。
- [ ] ≥2/3 通过 → 保留。
- [ ] 全失败 → 回滚 → 跳过。

### Phase 3：devils_advocate + innovation prompt 调优 (45min)

#### 问题

medical-LLM 创新链路跑通但 devils_advocate 仍 BLOCK（"创新点缺实现细节"）。BLOCK 只应留给编造证据。

#### 修改

**文件 1：`apps/api/app/services/agents/prompts/devils_advocate_graph.py`**

SYSTEM prompt 增加：

```
判断标准调整:
- 创新点缺少实现细节是正常的，不应仅因此判 BLOCK。
- BLOCK 仅用于: 创新点引用了不存在的论文/数据集/repo (编造证据)，或 baseline 完全缺失。
- 有 baseline + 有创新点 + 有工作包 → ACCEPT 或 MINOR_REVISION。
- 有 baseline + 创新点描述模糊 → MINOR_REVISION。
- 无 baseline → BLOCK。
```

**文件 2：`apps/api/app/services/agents/prompts/innovation_extractor.py`**

USER_TEMPLATE 增加 stitching_plan 结构要求：

```
每个创新点必须包含:
- stitching_plan: 缝合方案 (2-3 步具体操作, 不是抽象描述)
- baseline_used: 引用的 baseline 论文 ID
- stitched_modules: 引用的 parallel 论文 ID
```

#### 3-case 验证

重跑 V-MED / V-SLAM / V-CRACK：

| 检查项 | 通过标准 |
|---|---|
| review verdict 不全是 BLOCK | ≥2/3 verdict ∈ {ACCEPT, MINOR_REVISION} |
| innovation_points 的 stitching_plan 非空 | ≥2/3 有具体步骤 |
| fabrication_alerts 减少 | V-MED 的 alerts 数 < Re2 baseline |
| graph 完成 | ≥2/3 |

- [ ] 3 case 结果记录。
- [ ] ≥2/3 通过 → 保留。
- [ ] 全失败 → 回滚 → 跳过。

### Phase 4：20 篇回归 (DeepSeek, 60min, 无人值守)

#### 运行

```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python apps/api/scripts/re21_batch_run.py --provider deepseek --cases smoke_20
```

脚本自动：
- 串行跑 20 篇（每篇 ~100-150s，总 ~40min）。
- 输出到 `tmp_re21_eval/smoke_20/`。
- 自动调 validator。
- 连续 3 次失败停止。

#### 验证

- [ ] `summary_deepseek.json` 存在。
- [ ] ≥17/20 has_final=True。
- [ ] `comparison.json` 存在（Re1.5 vs Re2.1 对比）。

#### 对比分析

```bash
python apps/api/scripts/re21_compare.py --old tmp_re15_eval/smoke_20 --new tmp_re21_eval/smoke_20
```

对比指标：

| 指标 | 期望 |
|---|---|
| 平均 accept 数 | 增加 |
| not_recommended 比例 | 下降 |
| BLOCK 比例 | 下降 |
| cases_improved > cases_regressed | 改善 > 退化 |

### Phase 5：10 篇选跑 + 汇总 (30min, 无人值守)

#### 选跑

从 100 篇中选 10 篇覆盖之前 0 accept 或未测过的领域：

| # | ID | 题名 | 领域 |
|---|---|---|---|
| 1 | ENG-THESIS-046 | 机械臂目标检测避障 | 机器人 |
| 2 | ENG-THESIS-063 | 3D视觉机械臂抓取 | 机器人 |
| 3 | ENG-THESIS-066 | 多模态融合攻击防御 | 自动驾驶 |
| 4 | ENG-THESIS-092 | 海上风机叶片缺陷 | 能源装备 |
| 5 | ENG-THESIS-096 | 石墨烯薄膜风机防冰 | 能源装备 |
| 6 | ENG-THESIS-015 | 三维人体重建 | 医学 |
| 7 | ENG-THESIS-033 | YOLOV5肺结节检测 | 医学 |
| 8 | ENG-THESIS-004 | YOLOv4目标检测测距 | 工科AI |
| 9 | ENG-THESIS-010 | 交通标志检测识别 | 自动驾驶 |
| 10 | ENG-THESIS-079 | 结构光隧道裂缝 | 土木 |

```bash
set FAST_JSON_PRIMARY=deepseek
python apps/api/scripts/re21_batch_run.py --provider deepseek --cases 046,063,066,092,096,015,033,004,010,079
```

#### 汇总报告

输出 `Plan/PaperAgent_Re2.1_完工报告.md`：

1. Phase 1-3 改动清单 + 3-case 验证结果。
2. 20 篇回归对比表。
3. 10 篇选跑结果。
4. 改善指标。
5. 已知限制。

## 4. 执行者规则

### 4.1 改动隔离

每次改代码前 `git stash create`。
验证通过记录 changelog。
验证失败 `git checkout` 回滚 + 记录。

### 4.2 失败处理

- Phase 1 失败 → 用旧 4 适配器继续 Phase 2。
- Phase 2 失败 → 用旧 prompt 继续 Phase 3。
- Phase 3 失败 → 用旧 prompt 继续 Phase 4。
- Phase 4 连续 3 次 crash → 停止，跳到 Phase 5。
- **Phase 间不传染。**

### 4.3 验证脚本

```python
# apps/api/scripts/re21_verify.py
"""重跑 3 个验证 case，输出结果。"""

V_CASES = [
    ("V-MED", "基于大语言模型的医学问答可信度评估方法研究"),
    ("V-SLAM", "基于深度学习的视觉SLAM语义地图的研究"),
    ("V-CRACK", "基于深度学习的混凝土桥梁裂缝检测研究"),
]

def run_verification() -> dict:
    results = {}
    for vid, topic in V_CASES:
        out = run_graph(vid, topic)
        results[vid] = {
            "has_final": bool(out.get("final_recommendation")),
            "n_verified": len(out.get("verified_papers") or []),
            "n_weak": len(out.get("weak_papers") or []),
            "n_candidates": len(out.get("paper_candidates") or []),
            "feasibility_verdict": (out.get("feasibility_report") or {}).get("verdict", ""),
            "feasibility_score": (out.get("feasibility_report") or {}).get("score", 0),
            "review_verdict": (out.get("review_report") or {}).get("overall_verdict", ""),
            "n_innovation": len(out.get("innovation_points") or []),
            "n_work_packages": len(out.get("work_packages") or []),
            "retrieve_tools": [tc.get("tool") for tc in 
                [t for t in (out.get("trace_events") or []) if t.get("node") in ("retrieve","paper_retriever")][0].get("tool_calls",[])]
                if any(t.get("node") in ("retrieve","paper_retriever") for t in (out.get("trace_events") or [])) else [],
            "crash": False,
        }
    return results
```

每次改完代码后运行：

```bash
python apps/api/scripts/re21_verify.py
```

输出到 `tmp_re21_eval/verify/<timestamp>.json`，3 个 case 的结果一目了然。

## 5. 脚本设计

### re21_batch_run.py

与 `re15_batch_run.py` 相同结构，输出到 `tmp_re21_eval/`。

### re21_compare.py

```python
def compare(old_dir, new_dir):
    old = load_summary(old_dir)
    new = load_summary(new_dir)
    return {
        "old_avg_accept": avg(c["n_accept"] for c in old),
        "new_avg_accept": avg(c["n_accept"] for c in new),
        "old_not_recommended_rate": rate(c.get("feasibility_verdict")=="not_recommended" for c in old),
        "new_not_recommended_rate": rate(c.get("feasibility_verdict")=="not_recommended" for c in new),
        "old_block_rate": rate(c.get("review_verdict")=="BLOCK" for c in old),
        "new_block_rate": rate(c.get("review_verdict")=="BLOCK" for c in new),
        "cases_improved": count_improved(old, new),
        "cases_regressed": count_regressed(old, new),
    }
```

### re21_verify.py

3-case 验证脚本（见 §4.3）。

## 6. 禁止事项

- 禁止同时改多个文件。
- 禁止改完代码不跑 3-case 验证就继续。
- 禁止验证失败不回滚。
- 禁止用 VOAPI / MiniMax。
- 禁止覆盖旧 eval 目录。
- 禁止用 mock 数据做验证。
- 禁止只用 1 个 case 验证。
- 禁止跳过 Phase 4（回归测试是核心交付物）。

## 7. 交付物

代码：

- `apps/api/app/services/agents/graph/nodes/retrieve.py` 🔧
- `apps/api/app/services/agents/graph/nodes/search_planner.py` 🔧
- `apps/api/app/services/agents/prompts/feasibility_assessor.py` 🔧
- `apps/api/app/services/agents/prompts/devils_advocate_graph.py` 🔧
- `apps/api/app/services/agents/prompts/innovation_extractor.py` 🔧
- `apps/api/app/services/retrieval/adapters/__init__.py` 🔧 (如需)
- `apps/api/scripts/re21_batch_run.py` 🆕
- `apps/api/scripts/re21_compare.py` 🆕
- `apps/api/scripts/re21_verify.py` 🆕

数据：

- `tmp_re21_eval/verify/` (3-case 验证结果, 多次)
- `tmp_re21_eval/smoke_20/` (20 case + summary)
- `tmp_re21_eval/selected_10/` (10 case + summary)
- `tmp_re21_eval/comparison.json`
- `tmp_re21_eval/changelog.md`

报告：

- `Plan/PaperAgent_Re2.1_完工报告.md`

## 8. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | S2 加入主搜索 | ≥2/3 验证 case 的 retrieve trace 有 semantic_scholar |
| 2 | paper_candidates 增加 | ≥2/3 验证 case 候选数 ≥ Re1.5 的 1.3x |
| 3 | feasibility 有区分度 | 3 验证 case 的 score max-min ≥ 15 |
| 4 | devils_advocate 不全是 BLOCK | ≥2/3 验证 case verdict ∈ {ACCEPT, MINOR_REVISION} |
| 5 | 20 篇回归 ≥17 完成 | Phase 4 summary |
| 6 | 平均 accept 数增加 | comparison.json: new > old |
| 7 | not_recommended 比例下降 | comparison.json |
| 8 | BLOCK 比例下降 | comparison.json |
| 9 | 10 篇选跑 ≥7 完成 | Phase 5 |
| 10 | changelog 记录所有改动 | 文件检查 |
| 11 | 每次改动有 3-case 验证记录 | verify/ 目录 |
| 12 | 完工报告完整 | Phase 5 |
| 13 | VOAPI/MiniMax = 0 | 全程 |
