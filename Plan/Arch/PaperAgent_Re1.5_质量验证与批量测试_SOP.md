# PaperAgent Re1.5 无人值守质量验证 SOP

> 承接：Re1.4 完工报告
> **本 SOP 设计为无人值守执行。** 用户不在场，执行者按 Phase 顺序自主执行。
> 预计总时长：6-8 小时。
> 模型：DeepSeek (主) / OpenCode big-pickle (备) / StepFun step-3.7 (对照)。

## 0. 执行者必读

### 0.1 核心原则

1. **每改一处代码，必须立即重跑 1 个 case 验证。验证不通过则 `git checkout` 回滚该文件，继续下一任务。**
2. **Phase 间的失败不传染。** Phase 1 挂了不影响 Phase 3 独立运行。
3. **连续 3 次失败（crash 或 0 verified）必须停止当前 Phase，跳到下一个 Phase。**
4. **禁止同时改多个文件。** 每次只改一个文件，验证通过后再改下一个。
5. **所有产出写入 `tmp_re15_eval/`，不覆盖 `tmp_re14_eval/` 或 `tmp_re13_eval/`。**

### 0.2 可跳过 vs 必须完成

| 任务 | 可跳过? | 跳过条件 |
|---|---|---|
| Phase 0: 修 crash | ❌ 不可跳过 | 后续全部依赖 |
| Phase 1: 20 篇批量跑 | ❌ 不可跳过 | 核心数据 |
| Phase 2: 自动修复 | ⚠ 可部分跳过 | 修复规则见 §4.2，每条独立，失败的跳过 |
| Phase 3: 三模型对照 | ⚠ StepFun 可跳过 | 402 配额错误时跳过该 case |
| Phase 4: 自测框架 | ❌ 不可跳过 | 核心交付物 |
| Phase 5: Playwright 截图 | ❌ 不可跳过 | 硬性交付物 |
| Phase 6: 汇总报告 | ❌ 不可跳过 | 硬性交付物 |

### 0.3 改动隔离机制

每次修改代码前：

```bash
# 记录当前文件状态
git stash create > /tmp/re15_stash_baseline
```

修改后验证不通过时：

```bash
# 回滚该文件
git checkout -- <file>
```

验证通过后：

```bash
# 保留改动，记录到变更日志
echo "<file>: <改动原因> → 验证通过" >> tmp_re15_eval/changelog.md
```

### 0.4 StepFun 配额处理

StepFun 运行时如果遇到 HTTP 402 (quota_exceeded)：
- 停止 StepFun 测试
- 在报告中记录 "StepFun 配额耗尽，已跑 X/3 case"
- 继续后续 Phase

## 1. 模型策略

| Provider | 用途 | env | 单 case 预计 |
|---|---|---|---|
| DeepSeek | 主路径 20 篇 | `FAST_JSON_PRIMARY=deepseek` | 87-106s |
| OpenCode big-pickle | 备选对照 3 篇 | `FAST_JSON_PRIMARY=opencode` | 需实测 |
| StepFun step-3.7 | 串行对照 3 篇 | `FAST_JSON_PRIMARY=stepfun` + `STEPFUN_RPM_LIMIT=10` + `VERIFIER_MAX_WORKERS=1` | 10-40min |

切换方式：修改 `.env` 中 `FAST_JSON_PRIMARY`，然后 `load_dotenv(override=True)` 或重启进程。

## 2. 20 篇 smoke test 选题

从 `docs/PaperAgent_工科学位论文爬取测试集_100篇.md` §7：

| # | ID | 题名 | 领域 | 难度 |
|---|---|---|---|---|
| 1 | ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | 医学/人体 | 高 |
| 2 | ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | 三维视觉/SLAM | 中-高 |
| 3 | ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | 三维视觉/SLAM | 中-高 |
| 4 | ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | 三维视觉/SLAM | 中-高 |
| 5 | ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | 遥感/无人机 | 中 |
| 6 | ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | 电力/轨交 | 中 |
| 7 | ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | 工业缺陷 | 中 |
| 8 | ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | 医学 | 高 |
| 9 | ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | 遥感/无人机 | 中 |
| 10 | ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | 机器人 | 高 |
| 11 | ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | 自动驾驶 | 中 |
| 12 | ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | 机器人 | 高 |
| 13 | ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | 自动驾驶 | 高 |
| 14 | ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木 | 低-中 |
| 15 | ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | 土木 | 低-中 |
| 16 | ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | 三维视觉 | 中-高 |
| 17 | ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | 电力/轨交 | 中 |
| 18 | ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | 能源装备 | 中-高 |
| 19 | ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | 电力/轨交 | 中 |
| 20 | ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | 能源装备 | 中-高 |

## 3. Phase 设计

### Phase 0：修基础设施 (30min)

#### 0.1 修 trace_events 并发 crash

**问题**：`research_graph.py` 中节点返回 `trace_events: list(state.get("trace_events")) + [trace]`，repair loop 中 LangGraph 并发写入时偶发 `InvalidUpdateError`。

**修复**：

文件：`apps/api/app/services/agents/graph/state.py`

```python
from typing import Annotated
import operator

class ResearchState(TypedDict, total=False):
    # ...
    trace_events: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
```

同时修改所有节点的 return：不再手动拼接 `list(state.get("trace_events")) + [trace]`，改为只返回 `[trace]`（LangGraph 自动拼接）。

涉及文件（每个文件只改 trace_events 和 errors 的 return）：
- `nodes/intake.py`
- `nodes/topic_parser.py`
- `nodes/search_planner.py`
- `nodes/retrieve.py`
- `nodes/quality_filter.py`
- `nodes/verify.py`
- `nodes/quality_gate.py`
- `nodes/targeted_repair.py`
- `nodes/citation_expander.py`
- `nodes/dataset_repo_extractor.py`
- `nodes/json_graph_builder.py`
- `nodes/baseline_classifier.py`
- `nodes/content.py` (work_package / low_bar_review / human_gate / final_recommendation)
- `nodes/feasibility_assessor.py`
- `nodes/innovation_extractor.py`
- `nodes/sota_matcher.py`
- `nodes/narrative_builder.py`
- `nodes/optimization_advisor.py`
- `nodes/devils_advocate_node.py`

**改动模式**（每个文件统一）：

```python
# 旧：
return {
    "trace_events": list(state.get("trace_events") or []) + [trace],
    "errors": list(state.get("errors") or []) + errors,
    # ...
}

# 新：
return {
    "trace_events": [trace],          # LangGraph 自动拼接
    "errors": errors,                 # LangGraph 自动拼接
    # ...
}
```

#### 0.2 修后端 import 路径

**问题**：Playwright 截图显示 `错误: No module named 'apps'`。

**修复**：

文件：`apps/api/app/main.py`

```python
import sys
from pathlib import Path

# 确保从任何目录启动都能 import apps
_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
```

#### 0.3 验证

```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 18181
```

- [ ] `/health` 返回 200。
- [ ] `POST /api/v1/research/` 提交一个题目（如 "基于深度学习的混凝土桥梁裂缝检测研究"），graph 完成无 `InvalidUpdateError`。
- [ ] state.json 中 `trace_events` 有 23 个事件。
- [ ] 如果验证失败：`git checkout -- apps/api/app/services/agents/graph/state.py` 回滚，记录失败原因，继续 Phase 1（用现有代码跑，接受偶发 crash）。

### Phase 1：20 篇 smoke test 批量跑 (DeepSeek, 60-90min)

#### 运行

```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python apps/api/scripts/re15_batch_run.py --provider deepseek --cases smoke_20
```

脚本自动：
- 串行跑 20 篇（每篇 ~100s）。
- 每篇完成后自动调 validator 做快速检查。
- 输出到 `tmp_re15_eval/smoke_20/<case_id>/`。
- 某篇 crash → 记录 error → 继续下一篇。
- 连续 3 篇 crash → 暂停，记录到报告，继续 Phase 3。

#### 验证

- [ ] `tmp_re15_eval/smoke_20/summary_deepseek.json` 存在。
- [ ] ≥17/20 `has_final=True`。
- [ ] 每篇有 `state.json` + `trace.json`。
- [ ] 收集每篇的 accept / weak_reject / feasibility_verdict / review_verdict。

### Phase 2：自动分析 + 规则驱动修复 (60-90min)

#### 2.1 自动分析

```bash
python apps/api/scripts/re15_analyze.py --dir tmp_re15_eval/smoke_20
```

输出 `tmp_re15_eval/analysis.json`，包含：

```json
{
  "n_cases": 20,
  "n_completed": 18,
  "domain_stats": {
    "三维视觉/SLAM": {"n": 5, "avg_accept": 3.2, "n_zero_accept": 1},
    "工业缺陷检测": {"n": 1, "avg_accept": 5.0, "n_zero_accept": 0},
    ...
  },
  "feasibility_stats": {
    "unique_verdicts": ["risky"],
    "all_same": true,
    "all_risky": true
  },
  "review_stats": {
    "unique_verdicts": ["BLOCK"],
    "all_same": true,
    "all_block": true
  },
  "zero_accept_cases": ["ENG-THESIS-046", "ENG-THESIS-063"],
  "repair_needed": {
    "feasibility_prompt": true,
    "review_prompt": true,
    "search_planner_crossref": false
  }
}
```

#### 2.2 规则驱动修复

每条修复**独立执行**，失败的跳过，不影响其他修复。

**修复 1：feasibility 无区分度**

触发条件：`analysis.json → repair_needed.feasibility_prompt == true`

修改文件：`apps/api/app/services/agents/prompts/feasibility_assessor.py`

修改规则（只改 SYSTEM prompt，不改 USER_TEMPLATE）：

```
旧: "你是研究生开题可行性评估专家。"
新: "你是研究生开题可行性评估专家。根据证据数量区分：
- 有 baseline ≥2 + 有 repo → verdict=feasible, score=70-85
- 有 baseline ≥1 但无 repo → verdict=risky, score=40-60
- 无 baseline → verdict=not_recommended, score=10-30
不得对所有 case 给同一个 score。"
```

验证：重跑 ENG-THESIS-074 (低-中) 和 ENG-THESIS-046 (高)。
- [ ] 两个 case 的 feasibility score 差 ≥ 20。
- [ ] 或 verdict 不同。
- [ ] 如果验证失败 → `git checkout -- feasibility_assessor.py` → 记录失败 → 跳过。

**修复 2：devils_advocate 无区分度**

触发条件：`analysis.json → repair_needed.review_prompt == true`

修改文件：`apps/api/app/services/agents/prompts/devils_advocate_graph.py`

修改规则：

```
新增到 SYSTEM:
"根据证据充分性区分 verdict:
- 有 baseline ≥2 + work_package ≥1 → ACCEPT 或 MINOR_REVISION
- 有 baseline ≥1 但 work_package=0 → MINOR_REVISION
- 无 baseline → BLOCK
不得对所有 case 给 BLOCK。"
```

验证：重跑 ENG-THESIS-074 和 ENG-THESIS-046。
- [ ] 两个 case 的 review verdict 不同。
- [ ] 或至少一个不是 BLOCK。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

**修复 3：0 accept 领域**

触发条件：`analysis.json → zero_accept_cases` 非空

修改文件：`apps/api/app/services/agents/graph/nodes/search_planner.py`

修改规则：在 `_template_plan` 中，为 Crossref 查询增加 `method + object` 组合（如果还没有）。

验证：重跑 1 个 zero_accept case。
- [ ] accept ≥ 1，或 feasibility=not_recommended（即系统正确判断"这个题目论文少"）。
- [ ] 如果验证失败 → `git checkout` → 记录 → 跳过。

#### 2.3 验证

- [ ] `tmp_re15_eval/analysis.json` 存在。
- [ ] `tmp_re15_eval/changelog.md` 记录了每次改动和验证结果。
- [ ] 如果 feasibility 修复成功 → 2 个 case 的 score 有差异。
- [ ] 如果 review 修复成功 → 2 个 case 的 verdict 有差异。
- [ ] 失败的修复已回滚，不影响后续。

### Phase 3：三模型对照 (60-90min)

#### 选 case

| 代表性 | Case ID | 难度 |
|---|---|---|
| 保毕业 | ENG-THESIS-074 | 低-中 |
| 中等 | ENG-THESIS-016 | 中-高 |
| 高风险 | ENG-THESIS-046 | 高 |

#### 运行

```bash
# OpenCode big-pickle (3 篇)
set FAST_JSON_PRIMARY=opencode
python apps/api/scripts/re15_batch_run.py --provider opencode --cases 074,016,046

# StepFun step-3.7 (3 篇, 串行)
set FAST_JSON_PRIMARY=stepfun
set STEPFUN_RPM_LIMIT=10
set VERIFIER_MAX_WORKERS=1
python apps/api/scripts/re15_batch_run.py --provider stepfun --cases 074,016,046
```

#### 402 处理

StepFun 遇到 HTTP 402 时：
- 停止 StepFun
- 记录已完成的 case 数
- 继续后续 Phase

#### 验证

- [ ] `tmp_re15_eval/model_comparison/` 下有 DeepSeek / OpenCode / StepFun 的结果。
- [ ] DeepSeek 3 case（复用 Phase 1 结果）。
- [ ] OpenCode ≥1 case 完成。
- [ ] StepFun ≥1 case 完成（或记录 402 配额耗尽）。
- [ ] 三模型对照表已生成。

### Phase 4：自测框架 (60min)

#### 4.1 Validator 文件

| 文件 | 检查内容 | 通过标准 |
|---|---|---|
| `tests/self_test/e2e_completeness_validator.py` | graph 是否完整执行 | 23 节点全有 + final 非空 |
| `tests/self_test/paper_authenticity_validator.py` | 污染模式检查 | 0 条 Term Entry / Core Concept / Figure \d |
| `tests/self_test/topic_relevance_validator.py` | verified_papers 与题目相关性 | ≥30% 论文标题含 topic_atoms 关键词 |
| `tests/self_test/feasibility_diversity_validator.py` | 批量 case 的 feasibility 区分度 | ≥2 种 verdict, score 差 ≥20 |

#### 4.2 自动化自测脚本

文件：`apps/api/scripts/re15_self_test.py`

```python
def run_self_test(state: dict) -> dict:
    """对一个 case 的 state 跑全部 validator。"""
    return {
        "e2e_completeness": e2e_completeness_validator.validate(state),
        "paper_authenticity": paper_authenticity_validator.validate(state),
        "topic_relevance": topic_relevance_validator.validate(state),
    }

def run_batch_self_test(eval_dir: str) -> dict:
    """对一批 case 跑 validator。"""
    states = [load_state(p) for p in Path(eval_dir).glob("*/state.json")]
    per_case = [{"case_id": s["case_id"], **run_self_test(s)} for s in states]
    return {
        "n_cases": len(states),
        "feasibility_diversity": feasibility_diversity_validator.validate_batch(states),
        "per_case": per_case,
        "overall": all(c.get("e2e_completeness",{}).get("pass") for c in per_case),
    }
```

#### 4.3 验证

- [ ] 4 个 validator 文件存在且有 `validate()` 函数。
- [ ] `tmp_re15_eval/self_test_report.json` 已生成。
- [ ] `paper_authenticity` 全部 pass。
- [ ] `e2e_completeness` ≥17/20 pass。
- [ ] `topic_relevance` ≥15/20 pass。

### Phase 5：Playwright 截图 (30-45min)

#### 策略

**用已完成 case 做历史加载测试**，不需要实时跑 graph。

#### 步骤

1. 启动后端：
```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 18181
```

2. 确认 `/health` 返回 200。如果启动失败：
   - 检查 import 路径（Phase 0.2 的修复是否生效）
   - 如果仍失败 → 跳过 Phase 5，在报告中记录"后端启动失败"
   - **但如果 Phase 0 成功了，这里不应该失败**

3. 运行 Playwright 测试：
```bash
python -m pytest apps/web/e2e/test_re1_5_playwright.py -s
```

测试内容：
- test_01_page_load：页面加载
- test_02_topic_input：输入题目
- test_03_submit：提交题目（触发 graph 运行）
- test_04_wait_complete：等待完成（5min timeout）
- test_05_paper_list：论文列表截图
- test_06_evidence_graph：证据图谱截图
- test_07_work_packages：工作包截图
- test_08_final_report：最终结果截图
- test_09_history_dropdown：历史下拉
- test_10_history_load：历史 case 加载截图

每个测试截图到 `tmp_re15_screenshots/`。

4. 如果 test_04 超时（graph 5min 没跑完）：
   - 改用历史 case 加载模式
   - 直接用 Phase 1 已完成的 case ID 做 `test_10_history_load`
   - 对历史 case 截图论文列表 / 证据图谱 / 工作包 / 最终结果

#### 验证

- [ ] `tmp_re15_screenshots/` 下有 ≥10 张截图。
- [ ] 每张截图 > 1KB。
- [ ] 截图中有论文卡片 + verdict 标记。
- [ ] 截图中有证据图谱分组。
- [ ] 截图中有工作包。
- [ ] 截图中有最终结果。
- [ ] Console errors 为空。

### Phase 6：汇总报告 (30min)

#### 报告内容

```markdown
# PaperAgent Re1.5 完工报告

## 1. 基础设施修复
- trace_events Annotated 修复: ✅/❌
- import 路径修复: ✅/❌

## 2. 20 篇 smoke test 结果
| Case | 领域 | 难度 | 耗时 | accept | weak | feasibility | review | 完成 |
|---|---|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

## 3. 质量分析
- 领域覆盖表
- feasibility verdict 分布
- review verdict 分布
- 修复记录 (changelog.md 引用)

## 4. 三模型对照
| Case | DeepSeek accept | OpenCode accept | StepFun accept |
|---|---|---|---|
| ... | ... | ... | ... |

## 5. 自测结果
- e2e_completeness: X/20 pass
- paper_authenticity: X/20 pass
- topic_relevance: X/20 pass
- feasibility_diversity: pass/fail

## 6. 截图索引
| 文件 | 内容 |
|---|---|
| 01_page_load.png | ... |
| ... | ... |

## 7. 已知限制
- 哪些领域仍有 0 accept
- 哪些修复失败已回滚
- StepFun 配额状态
```

## 4. 脚本设计

### 4.1 re15_batch_run.py

```python
"""Re1.5 批量运行脚本。

用法:
    python apps/api/scripts/re15_batch_run.py --provider deepseek --cases smoke_20
    python apps/api/scripts/re15_batch_run.py --provider opencode --cases 074,016,046
    python apps/api/scripts/re15_batch_run.py --provider stepfun --cases 074,016,046
"""

SMOKE_20 = [
    ("ENG-THESIS-015", "基于患者虚拟定位的三维人体重建关键技术研究"),
    ("ENG-THESIS-016", "基于深度学习的视觉SLAM语义地图的研究"),
    ("ENG-THESIS-018", "基于深度学习的三维点云补全方法研究"),
    ("ENG-THESIS-024", "基于深度学习的无监督三维点云配准算法研究"),
    ("ENG-THESIS-027", "基于YOLOv5模型的遥感影像飞机目标检测"),
    ("ENG-THESIS-028", "基于YOLOv5的绝缘子检测与缺陷识别方法研究"),
    ("ENG-THESIS-032", "基于深度学习的液晶屏表面缺陷检测方法研究"),
    ("ENG-THESIS-033", "基于YOLOV5的肺结节检测算法研究"),
    ("ENG-THESIS-043", "基于无人机平台的动态目标检测系统开发"),
    ("ENG-THESIS-046", "基于视觉的机械臂的目标检测和避障路径规划研究与应用"),
    ("ENG-THESIS-050", "基于深度学习的自动驾驶感知算法"),
    ("ENG-THESIS-063", "基于3D视觉的机械臂无序抓取系统研究"),
    ("ENG-THESIS-066", "面向自动驾驶中多模态融合感知算法的攻击和防御"),
    ("ENG-THESIS-074", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("ENG-THESIS-075", "基于深度学习的混凝土路面裂缝检测研究"),
    ("ENG-THESIS-080", "基于三维重建裂缝损伤检测算法研究"),
    ("ENG-THESIS-091", "基于云计算的输电线路缺陷检测平台"),
    ("ENG-THESIS-092", "海上风机叶片缺陷检测及分类"),
    ("ENG-THESIS-093", "基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究"),
    ("ENG-THESIS-096", "基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究"),
]
```

脚本自动：
- 切换 env（`os.environ["FAST_JSON_PRIMARY"] = args.provider`）
- 串行跑 case
- 每篇保存 state.json + trace.json
- 自动调 validator
- 连续 3 次失败停止
- 输出 summary JSON

### 4.2 re15_analyze.py

```python
"""Re1.5 自动分析脚本。

用法:
    python apps/api/scripts/re15_analyze.py --dir tmp_re15_eval/smoke_20
"""

# 读取所有 case 的 state.json
# 按领域/难度/verdict 统计
# 输出 analysis.json
# 输出 repair_needed 标志
```

### 4.3 re15_self_test.py

```python
"""Re1.5 自测脚本。

用法:
    python apps/api/scripts/re15_self_test.py --case ENG-THESIS-074
    python apps/api/scripts/re15_self_test.py --dir tmp_re15_eval/smoke_20
"""

# 单 case 或批量跑 validator
# 输出 JSON 报告
```

## 5. 执行者自测检查清单

> **执行 AI 在每个 Phase 结束后必须逐项确认。**

### Phase 0 检查

- [ ] `Annotated[list, operator.add]` 已加到 state.py。
- [ ] 所有节点的 trace_events return 改为 `[trace]`（不手动拼接）。
- [ ] `main.py` 加了 sys.path 修复。
- [ ] 跑 1 个 case 无 `InvalidUpdateError`。
- [ ] `python -m uvicorn apps.api.app.main:app --port 18181` 能启动。
- [ ] `/health` 返回 200。
- [ ] 如果失败 → 回滚 → 记录 → 继续用旧代码跑。

### Phase 1 检查

- [ ] `tmp_re15_eval/smoke_20/` 下有 ≥17 个 case 目录。
- [ ] `summary_deepseek.json` 存在。
- [ ] ≥17/20 `has_final=True`。
- [ ] 连续 crash < 3 次。

### Phase 2 检查

- [ ] `analysis.json` 存在。
- [ ] `changelog.md` 记录了每次改动和验证结果。
- [ ] feasibility 修复（如果触发）：2 case 的 score 有差异，或已回滚记录。
- [ ] review 修复（如果触发）：2 case 的 verdict 有差异，或已回滚记录。
- [ ] search_planner 修复（如果触发）：重跑后有 accept 或 not_recommended，或已回滚记录。

### Phase 3 检查

- [ ] OpenCode big-pickle 3 case 结果存在（或记录失败）。
- [ ] StepFun 3 case 结果存在（或记录 402 配额耗尽）。
- [ ] 三模型对照表已生成。

### Phase 4 检查

- [ ] 4 个 validator 文件存在。
- [ ] `re15_self_test.py` 存在。
- [ ] `self_test_report.json` 已生成。
- [ ] `paper_authenticity` 全部 pass。
- [ ] `e2e_completeness` ≥17/20 pass。

### Phase 5 检查

- [ ] `tmp_re15_screenshots/` 下有 ≥10 张截图。
- [ ] 每张 > 1KB。
- [ ] 截图有论文卡片 + 证据图谱 + 工作包 + 最终结果。
- [ ] Console errors 为空。
- [ ] 如果后端启动失败 → 记录原因 → 跳过 Phase 5。

### Phase 6 检查

- [ ] 完工报告包含 20 篇结果表。
- [ ] 完工报告包含三模型对照表。
- [ ] 完工报告包含自测结果。
- [ ] 完工报告包含截图索引。
- [ ] 完工报告包含已知限制。
- [ ] 完工报告包含 changelog.md 引用。

## 6. 禁止事项

- 禁止同时改多个文件（每次只改一个，验证后再改下一个）。
- 禁止改完代码不验证就继续（必须重跑 1 个 case）。
- 禁止验证失败不回滚（必须 `git checkout` 回滚）。
- 禁止连续 3 次 crash 后继续跑（停止当前 Phase，跳到下一个）。
- 禁止用 VOAPI / MiniMax。
- 禁止覆盖 `tmp_re13_eval/` 或 `tmp_re14_eval/`。
- 禁止用 mock 数据做自测。
- 禁止跳过 Phase 0 / Phase 1 / Phase 4 / Phase 6。

## 7. 交付物

代码：

- `apps/api/app/services/agents/graph/state.py` 🔧 (Annotated)
- `apps/api/app/main.py` 🔧 (import)
- `apps/api/scripts/re15_batch_run.py` 🆕
- `apps/api/scripts/re15_analyze.py` 🆕
- `apps/api/scripts/re15_self_test.py` 🆕
- `tests/self_test/e2e_completeness_validator.py` 🆕
- `tests/self_test/paper_authenticity_validator.py` 🔧
- `tests/self_test/topic_relevance_validator.py` 🆕
- `tests/self_test/feasibility_diversity_validator.py` 🆕
- `apps/web/e2e/test_re1_5_playwright.py` 🆕
- Phase 2 修复的文件 (视分析结果而定)

数据：

- `tmp_re15_eval/smoke_20/` (20 case 目录 + summary_deepseek.json)
- `tmp_re15_eval/model_comparison/` (三模型对照)
- `tmp_re15_eval/analysis.json`
- `tmp_re15_eval/changelog.md`
- `tmp_re15_eval/self_test_report.json`
- `tmp_re15_screenshots/` (≥10 张截图)

报告：

- `Plan/PaperAgent_Re1.5_Phase0_基础设施修复.md`
- `Plan/PaperAgent_Re1.5_Phase1_20篇SmokeTest.md`
- `Plan/PaperAgent_Re1.5_Phase2_质量分析与修复.md`
- `Plan/PaperAgent_Re1.5_Phase3_三模型对照.md`
- `Plan/PaperAgent_Re1.5_Phase4_自测框架.md`
- `Plan/PaperAgent_Re1.5_Phase5_Playwright截图.md`
- `Plan/PaperAgent_Re1.5_完工报告.md`

## 8. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | trace_events 不 crash | Phase 0 跑 1 case 无 InvalidUpdateError |
| 2 | 后端能启动 | /health 返回 200 |
| 3 | 20 篇 ≥17 完成 | Phase 1 summary |
| 4 | feasibility 有区分度或已回滚记录 | Phase 2 analysis |
| 5 | review 有区分度或已回滚记录 | Phase 2 analysis |
| 6 | OpenCode ≥1 case 完成 | Phase 3 |
| 7 | StepFun ≥1 case 或记录 402 | Phase 3 |
| 8 | 4 个 validator 存在 | Phase 4 |
| 9 | 自测报告已生成 | Phase 4 |
| 10 | paper_authenticity 全 pass | Phase 4 |
| 11 | e2e_completeness ≥17/20 | Phase 4 |
| 12 | ≥10 张截图 | Phase 5 |
| 13 | 截图非空白 | Phase 5 |
| 14 | Console 无 JS 报错 | Phase 5 |
| 15 | 完工报告完整 | Phase 6 |
| 16 | changelog 记录所有改动 | Phase 2 |
| 17 | VOAPI/MiniMax = 0 | 全程 |
