# PaperAgent Re3.4 收口验证 + 技术债清理 + 选择性回归 SOP

> 承接：Re3.2 + Re3.3 代码修复完成，3-case 真实 LLM 跑通，但 final_recommendation 计数未在 e2e 中验证；58 个 legacy session 测试报 collection error；retrieve.py 死代码；466 个 ruff errors；re14/re15/re24 产物未文档化。
> **本 SOP 聚焦：收口 P0 gap → 清理技术债 → 选择性回归出问题的章节**
> 预计总时长：4-5 小时，分 4 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 前置审计发现总结

### 未关闭的 P0 Gap

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| G1 | **final_recommendation 计数在产物中全为 0** | V-YOLO-33: n_papers=0 (实际 4), n_repo=0 (实际 12); V-SLAM-33: n_papers=0 (实际 43) | 代码已修复 (content.py L339)，但 3 个 case 用旧代码跑，未验证 |

### 技术债清单

| # | 问题 | 范围 | 数量 |
|---|---|---|---|
| D1 | **Legacy session 测试 collection error** | `apps/api/tests/test_session*.py` | 58 个文件，导入已删除模块 (evidence, paper_library, graduation, proposal, thesis_eval, small_paper, research_planner_agent 等) |
| D2 | **retrieve.py 死代码** | `nodes/retrieve.py` (296 行) | `retrieve_node` 在 graph 中无任何 edge 引用，被 `search_agent` 替代；仅 `test_re1_2_retrieve_parallel.py` 仍引用 |
| D3 | **Ruff errors** | `apps/api/` 全量 | 466 个 (324 个可自动修复)：F401(262), E402(56), F841(44), F541(40), E401(18), F821(14), E701(13) 等 |
| D4 | **re14/re15/re24 产物未文档化** | `tmp_re13_eval/re14-*` (10), `re15-*` (2), `re24-*` (24) | 多个 case 主题乱码或 0 检索结果，无对应 SOP/完工报告 |
| D5 | **SOP 文档字段名不一致** | Re3.3 SOP 写 `feasibility_report.tier`，实际代码用 `feasibility_report.verdict` | 文档误导 |

### Batch20 中出问题的章节

| ENG-THESIS | 题目 | Batch20 结果 | 问题 |
|---|---|---|---|
| 002 | 基于深度学习的磁瓦在线检测技术研究 | 0 论文/0 仓库/0 数据集 | **完全失败** |
| 038 | 基于深度学习的无人机图像目标检测算法研究 | BLOCK, not_recommended, score=25, 0 baseline | **可行性误判** |
| 046 | 基于视觉的机械臂目标检测和避障路径规划 | MINOR_REVISION, risky | **高风险选题评估不准** |
| 066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | MINOR_REVISION, risky | **多模态/对抗攻击领域陌生** |
| 092 | 海上风机叶片缺陷检测及分类 | MINOR_REVISION, risky | **能源装备领域覆盖不足** |
| 093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测 | MINOR_REVISION, risky | **电力巡检领域覆盖不足** |

**已验证无需重跑**（V-*-33 已覆盖）：
- SLAM 类 (016/048/051/053/056/058/059/062/065/068/072) → V-SLAM-33 ACCEPT
- YOLO 农业类 (027/037) → V-YOLO-33 ACCEPT
- 医学 LLM → V-MED-33 MINOR_REVISION

## 1. 本轮目标

1. **收口 P0**：补跑 1 个 case，确认 final_recommendation 计数 > 0
2. **清理技术债**：legacy tests 归档 + retrieve.py 移除 + ruff 自动修复 + re14/re15/re24 产物清理
3. **选择性回归**：重跑 Batch20 中 6 个出问题的章节，确认修复有效
4. **文档收尾**：更新 CHANGELOG + 完工报告

不做：
- 100 篇全量回归
- 新增搜索源 (PubMed/Unpaywall)
- React+Vite 前端
- LangSmith 集成
- StageContract 机制

## 2. Phase 设计

### Phase 1：收口 P0 — final_recommendation 验证 (30min)

#### 1.1 补跑 1 个 case

用 V-YOLO-33 的题目（`基于yolo的农作物识别`，短关键词 + 有 repo），确认 final_recommendation 计数 > 0。

**提交**：
```bash
curl -X POST http://127.0.0.1:18181/api/v1/research/ \
  -H "Content-Type: application/json" \
  -d '{"topic": "基于yolo的农作物识别", "target_tier": "SCI-Q2"}'
```

**验证**：
```bash
# 完成后检查 state.json
.venv/Scripts/python.exe -c "
import json
d = json.load(open('tmp_re34_eval/V-YOLO-34/state.json', encoding='utf-8'))
fr = d.get('final_recommendation', {})
vp = d.get('verified_papers', [])
rc = d.get('repo_candidates', [])
assert fr.get('n_papers', 0) == len(vp), f'n_papers={fr.get(\"n_papers\")} != {len(vp)}'
assert fr.get('n_repo', 0) == len(rc), f'n_repo={fr.get(\"n_repo\")} != {len(rc)}'
assert fr.get('n_papers', 0) > 0, 'n_papers still 0!'
print(f'OK: n_papers={fr[\"n_papers\"]}, n_repo={fr[\"n_repo\"]}, n_baseline={fr.get(\"n_baseline\",0)}')
"
```

**通过标准**：
- `final_recommendation.n_papers` == `len(verified_papers)` 且 > 0
- `final_recommendation.n_repo` == `len(repo_candidates)` 且 > 0
- 无 RecursionError

**失败处理**：如果仍为 0，检查 content.py `final_recommendation_node` 是否被正确调用，以及 state merge 是否覆盖了计数字段。

### Phase 2：技术债清理 (1.5h)

#### Fix 2.1: Legacy session 测试归档 (30min)

**文件**：`apps/api/tests/test_session*.py` (58 个文件)

**问题**：这些测试导入 Re3.0 之前删除的模块（`app.services.evidence`, `app.services.paper_library`, `app.services.graduation`, `app.services.proposal`, `app.services.thesis_eval`, `app.services.small_paper`, `app.services.research_planner_agent`, `app.services.research_topic_parser` 等），导致 pytest collection error。

**方案**：移到归档目录，不参与 pytest 收集：

```bash
# 创建归档目录
mkdir apps/api/tests/_archived_legacy_sessions

# 移动所有 test_session*.py
mv apps/api/tests/test_session*.py apps/api/tests/_archived_legacy_sessions/

# 添加 .gitignore 或 conftest 防止收集
echo "# Legacy session tests from Re1.x-Re2.x, archived in Re3.4" > apps/api/tests/_archived_legacy_sessions/README.md
```

**验证**：
```bash
.venv/Scripts/python.exe -m pytest apps/api/tests --collect-only -q 2>&1 | findstr /i "error"
# 期望：无 collection error
```

#### Fix 2.2: retrieve.py 死代码移除 (15min)

**文件**：
- `apps/api/app/services/agents/graph/nodes/retrieve.py` (296 行)
- `apps/api/app/services/agents/graph/nodes/__init__.py` (L39: `"retrieve": _retrieve.retrieve_node`)
- `apps/api/tests/test_re1_2_retrieve_parallel.py`

**问题**：`retrieve_node` 在 graph 中无任何 edge 引用（被 `search_agent` 替代），但仍在 `nodes/__init__.py` 注册，导致 graph 编译时添加了一个不可达节点。

**修复**：

1. `nodes/__init__.py`：删除 `retrieve` 注册行和相关 import
2. `retrieve.py`：删除文件
3. `test_re1_2_retrieve_parallel.py`：移到 `_archived_legacy_sessions/`
4. 保留 `api/v1/research.py` 中的 `if node == "retrieve" or node == "paper_retriever"` 字符串比较（向后兼容 trace 审计）

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.research_graph import build_graph
g = build_graph()
print('OK: graph compiles without retrieve node')
"
.venv/Scripts/python.exe -m pytest apps/api/tests/test_re1_2_graph_nodes.py -v
# 期望：4/4 passed
```

#### Fix 2.3: Ruff 自动修复 (30min)

**范围**：`apps/api/` 全量

**策略**：分两步——先自动修复，再手动处理剩余

```bash
# Step 1: 自动修复 (324 个)
.venv/Scripts/python.exe -m ruff check apps/api/ --fix

# Step 2: 检查剩余
.venv/Scripts/python.exe -m ruff check apps/api/ --statistics
```

**Step 3: 手动处理不可自动修复的**：

重点处理：
- **F821 undefined-name (14 个)**：可能是真正的 bug，逐个检查
- **F822 undefined-export (6 个)**：`__init__.py` 中导出不存在的符号
- **F811 redefined-while-unused (5 个)**：删除重复定义
- **E741 ambiguous-variable-name (3 个)**：重命名 `l`/`I`/`O`

**不处理**（pre-existing 且无害）：
- E703 多余分号（JS 风格遗留，不影响运行）

**验证**：
```bash
.venv/Scripts/python.exe -m ruff check apps/api/ --statistics
# 期望：F821/F822/F811 = 0，其余显著减少
```

#### Fix 2.4: re14/re15/re24 产物清理 (15min)

**问题**：`tmp_re13_eval/` 下有 36 个 re14/re15/re24 目录，多个为失败运行（主题乱码、0 检索结果），无文档。

**方案**：

1. 保留有价值的成功运行（`re14-medical-llm` 等有完整数据的）
2. 删除明显的失败/调试运行（乱码主题、0 结果、screenshot-test 等）
3. 列出保留的 case 及其主题

```bash
# 检查每个 case 的 topic 和 verified_papers 数量
.venv/Scripts/python.exe -c "
import json, os
for d in sorted(os.listdir('tmp_re13_eval')):
    if not (d.startswith('re14') or d.startswith('re15') or d.startswith('re24')):
        continue
    path = f'tmp_re13_eval/{d}/state.json'
    if not os.path.exists(path):
        print(f'{d}: NO state.json')
        continue
    s = json.load(open(path, encoding='utf-8'))
    topic = s.get('topic', '?')[:30]
    vp = len(s.get('verified_papers', []))
    errs = len(s.get('errors', []))
    print(f'{d}: topic={topic!r} vp={vp} errs={errs}')
"
```

**删除标准**：`topic` 为乱码/空 或 `verified_papers` 为 0 且 `errors` 为空（静默失败）

#### Fix 2.5: SOP 文档字段名修正 (5min)

**文件**：`Plan/PaperAgent_Re3.3_前端修复与全量截图验证_SOP.md`

**修复**：所有 `feasibility_report.tier` → `feasibility_report.verdict`

```bash
# 搜索确认
findstr /n "tier" Plan/PaperAgent_Re3.3_前端修复与全量截图验证_SOP.md
```

### Phase 3：选择性回归 — 6 个出问题章节 (2-2.5h)

#### 3.1 章节选择与理由

从 Batch20 结果中选取 6 个有问题的章节，覆盖之前未通过的边界场景：

| Case ID | ENG-THESIS | 题目 | Batch20 问题 | 回归重点 |
|---|---|---|---|---|
| R34-002 | 002 | 基于深度学习的磁瓦在线检测技术研究 | 完全失败 (0 论文) | search_agent 是否能检索到结果 |
| R34-038 | 038 | 基于深度学习的无人机图像目标检测算法研究 | BLOCK / not_recommended / score=25 | feasibility 是否有区分度 |
| R34-046 | 046 | 基于视觉的机械臂目标检测和避障路径规划研究与应用 | MINOR_REVISION / risky | 高风险选题（硬件依赖）评估 |
| R34-066 | 066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | MINOR_REVISION / risky | 多模态/对抗攻击领域 |
| R34-092 | 092 | 海上风机叶片缺陷检测及分类 | MINOR_REVISION / risky | 能源装备领域（非 CV 为主） |
| R34-033 | 033 | 基于YOLOV5的肺结节检测算法研究 | 未在 Batch20 中 | 医学+高难度+数据合规风险 |

**选择逻辑**：
- 002 / 038：之前完全失败或误判，必须重跑验证修复
- 046 / 066 / 092：Batch20 中 risky 且 MINOR_REVISION，检查可行性评估是否改善
- 033：新增——高难度 + 医学数据合规，测试系统对 "数据权限" 风险的识别能力

#### 3.2 执行方式

**串行提交**（避免 API 限流），每个 case 完成后再提交下一个：

```bash
# 启动 server
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 逐个提交（示例）
curl -X POST http://127.0.0.1:18181/api/v1/research/ \
  -H "Content-Type: application/json" \
  -d '{"topic": "基于深度学习的磁瓦在线检测技术研究", "target_tier": "SCI-Q2"}'
```

**每个 case 完成后**，提取 state.json 和 trace.json 到 `tmp_re34_eval/`：

```bash
mkdir tmp_re34_eval
# 完成后
curl http://127.0.0.1:18181/api/v1/research/{case_id}/state > tmp_re34_eval/R34-002_state.json
curl http://127.0.0.1:18181/api/v1/research/{case_id}/trace > tmp_re34_eval/R34-002_trace.json
```

#### 3.3 验证检查清单

**P0 — 必须通过**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | graph 完成无 RecursionError | trace.json 无 RecursionError |
| 2 | R34-002 verified_papers ≥ 3 | 之前为 0，必须修复 |
| 3 | R34-038 feasibility 不是 not_recommended | 之前误判为 not_recommended (score=25) |
| 4 | final_recommendation 计数 > 0 | 所有 6 个 case |
| 5 | 无 asyncio 崩溃 | trace.json 无 event loop error |
| 6 | 无 NameError | trace.json 无 name 're' is not defined |

**P1 — 应该通过**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 7 | R34-046 识别出硬件依赖风险 | feasibility_report.reason 包含 "硬件" 或 "机械臂" |
| 8 | R34-066 识别出多模态/对抗攻击领域 | research_narrative 非空 |
| 9 | R34-092 识别出能源装备领域（非纯 CV） | feasibility_report 不是全 not_recommended |
| 10 | R34-033 识别出数据合规风险 | feasibility_report.reason 包含 "合规" 或 "数据" 或 "医疗" |
| 11 | 无 "deep learning" 硬编码 fallback | search_steps 中的 query 不含 "deep learning"（除非题目本身是） |
| 12 | review verdict 有区分度 | 6 个 case 的 verdict 不全是同一个值 |

**P2 — 加分项**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 13 | dataset_candidates 非空 | ≥1 个 case 有数据集 |
| 14 | repo_candidates 非空 | ≥1 个 case 有仓库 |
| 15 | 短关键词不被过滤 | R34-033 的 query 包含 "YOLO" |

#### 3.4 自动化验证脚本

```bash
.venv/Scripts/python.exe -c "
import json, os

cases = {
    'R34-002': {'min_papers': 3, 'prev_fail': True},
    'R34-038': {'feasibility_not': 'not_recommended'},
    'R34-046': {'check_risk': '硬件'},
    'R34-066': {'check_narrative': True},
    'R34-092': {'feasibility_not': 'not_recommended'},
    'R34-033': {'check_risk': '数据'},
}

for case_id, checks in cases.items():
    path = f'tmp_re34_eval/{case_id}_state.json'
    if not os.path.exists(path):
        print(f'{case_id}: SKIP (no state.json)')
        continue
    d = json.load(open(path, encoding='utf-8'))
    vp = len(d.get('verified_papers', []))
    fr = d.get('final_recommendation', {})
    feas = d.get('feasibility_report', {})
    narrative = d.get('research_narrative', {})
    review = d.get('review_report', {})
    
    issues = []
    if 'min_papers' in checks and vp < checks['min_papers']:
        issues.append(f'vp={vp} < {checks[\"min_papers\"]}')
    if fr.get('n_papers', 0) == 0:
        issues.append('final_rec n_papers=0')
    if 'feasibility_not' in checks and feas.get('verdict') == checks['feasibility_not']:
        issues.append(f'feasibility={feas.get(\"verdict\")}')
    if 'check_risk' in checks:
        reason = feas.get('reason', '')
        if checks['check_risk'] not in reason:
            issues.append(f'reason missing {checks[\"check_risk\"]!r}')
    if checks.get('check_narrative') and not narrative:
        issues.append('narrative empty')
    
    status = 'FAIL' if issues else 'PASS'
    print(f'{case_id}: {status} | vp={vp} feas={feas.get(\"verdict\",\"?\")} review={review.get(\"overall_verdict\",\"?\")} fr.n_papers={fr.get(\"n_papers\",0)}')
    for iss in issues:
        print(f'  ! {iss}')
"
```

### Phase 4：完工报告 + CHANGELOG (30min)

#### 4.1 完工报告

撰写 `Plan/PaperAgent_Re3.4_完工报告.md`，包含：
- P0 收口验证结果（final_recommendation 计数对照表）
- 技术债清理统计（归档文件数、删除文件数、ruff 修复前后对比）
- 6-case 回归结果对照表（与 Batch20 结果对比）
- SOP 验收条件逐项对照
- 已知限制

#### 4.2 CHANGELOG 更新

```markdown
## [Unreleased]

### Added (Re3.4)
- Selective regression: 6 problematic chapters re-tested

### Fixed (Re3.4)
- final_recommendation counts verified in e2e (were 0 in Re3.3 artifacts)
- 58 legacy session tests archived (collection errors eliminated)
- retrieve.py dead code removed (296 lines, superseded by search_agent)
- ruff auto-fix: 324+ errors resolved
- re14/re15/re24 failed test artifacts cleaned up
- Re3.3 SOP field name corrected (tier → verdict)

### Changed (Re3.4)
- pytest collection: no more legacy session import errors
- graph compilation: retrieve node no longer registered
```

## 3. 执行者规则

1. **Phase 1 必须在 Phase 3 之前完成**——先确认 final_rec 修复再跑回归
2. **Phase 2 可以与 Phase 1 并行**——技术债清理不影响 e2e 验证
3. **Phase 3 串行提交**——避免 API 限流
4. **P0 项失败必须修复后重跑**
5. **遵循 CODELY.md 中的所有开发约定**
6. **VOAPI/MiniMax = 0**
7. **所有 LLM 凭证从 .env 读取**
8. **legacy 测试归档不删除**——移到 `_archived_legacy_sessions/` 保留历史

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `apps/api/tests/_archived_legacy_sessions/` | 🆕 归档目录 + 58 个移动文件 | 2 |
| `apps/api/app/services/agents/graph/nodes/retrieve.py` | 🗑️ 删除 | 2 |
| `apps/api/app/services/agents/graph/nodes/__init__.py` | 🔧 移除 retrieve 注册 | 2 |
| `apps/api/tests/test_re1_2_retrieve_parallel.py` | 📦 移到归档 | 2 |
| `apps/api/` 全量 Python 文件 | 🔧 ruff --fix | 2 |
| `Plan/PaperAgent_Re3.3_前端修复与全量截图验证_SOP.md` | 🔧 tier→verdict | 2 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re34_eval/R34-002_state.json` | 磁瓦检测 state |
| `tmp_re34_eval/R34-002_trace.json` | 磁瓦检测 trace |
| `tmp_re34_eval/R34-038_state.json` | 无人机目标检测 state |
| `tmp_re34_eval/R34-038_trace.json` | 无人机目标检测 trace |
| `tmp_re34_eval/R34-046_state.json` | 机械臂避障 state |
| `tmp_re34_eval/R34-046_trace.json` | 机械臂避障 trace |
| `tmp_re34_eval/R34-066_state.json` | 多模态攻击防御 state |
| `tmp_re34_eval/R34-066_trace.json` | 多模态攻击防御 trace |
| `tmp_re34_eval/R34-092_state.json` | 风机叶片检测 state |
| `tmp_re34_eval/R34-092_trace.json` | 风机叶片检测 trace |
| `tmp_re34_eval/R34-033_state.json` | 肺结节检测 state |
| `tmp_re34_eval/R34-033_trace.json` | 肺结节检测 trace |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.4_完工报告.md` | 完工报告 + 回归对照表 |
| `CHANGELOG.md` | 更新 Unreleased 段落 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | **final_recommendation 计数 > 0** | e2e state.json 检查 | **P0** |
| 2 | **final_recommendation 计数 == len(list)** | e2e state.json 一致性检查 | **P0** |
| 3 | pytest collection 无 error | `pytest --collect-only -q` | P0 |
| 4 | retrieve.py 已删除 | 文件不存在 | P1 |
| 5 | graph 编译通过 | build_graph() 成功 | P1 |
| 6 | ruff errors < 50 (从 466 降) | `ruff check --statistics` | P1 |
| 7 | R34-002 verified_papers ≥ 3 | state.json | P0 |
| 8 | R34-038 feasibility ≠ not_recommended | state.json | P0 |
| 9 | 6-case 无 RecursionError | trace.json | P0 |
| 10 | 6-case final_rec 计数 > 0 | state.json | P0 |
| 11 | R34-046 识别硬件风险 | feasibility reason | P1 |
| 12 | R34-033 识别数据合规风险 | feasibility reason | P1 |
| 13 | 无 "deep learning" 硬编码 | search_steps 检查 | P1 |
| 14 | review verdict 有区分度 | 6-case 不全相同 | P1 |
| 15 | CHANGELOG 更新 | 文件检查 | P2 |
| 16 | 完工报告存在 | 文件检查 | P2 |
| 17 | VOAPI/MiniMax = 0 | 全程 | P0 |

## 6. 执行顺序

```
Phase 1 (30min):  补跑 1 case → 确认 final_rec 计数
       ↓                              ↑ 可并行
Phase 2 (1.5h):   legacy 归档 + retrieve 删除 + ruff fix + 产物清理
       ↓
Phase 3 (2-2.5h): 6-case 选择性回归 ← 核心
       ↓
Phase 4 (30min):  完工报告 + CHANGELOG
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DeepSeek API 429 | 中 | case 无法完成 | 等待重试 / 切 StepFun |
| ruff --fix 引入回归 | 低 | 代码行为变化 | fix 后立即跑 test_re1_2_graph_nodes |
| retrieve.py 删除后 graph 报错 | 低 | graph 编译失败 | 先删 __init__.py 注册，保留文件直到验证通过 |
| R34-002 仍然 0 论文 | 中 | 搜索适配器问题 | 检查 search_steps 中的 query 和 tool 选择 |
| R34-038 仍然 not_recommended | 中 | feasibility 评估逻辑问题 | 检查 feasibility_assessor 的 LLM prompt |
| 6-case 耗时超预期 | 中 | 总时长 >5h | P0 项优先，P1 项可降级为 smoke test |

## 8. TODO 推进（Re3.5+）

| TODO | 评估 |
|---|---|
| 100 篇全量回归 | Re3.5（6-case 选择性回归通过后） |
| PubMed E-utilities | Re3.5（医学领域补充） |
| Unpaywall | Re3.5（开放获取 PDF） |
| LangSmith 集成 | Re3.5（可观测性） |
| React+Vite 前端 | Re4.0（架构级重写） |
| StageContract 机制 | Re4.0 |
| ruff 剩余手动修复 (F821/F822 等) | Re3.5 |
