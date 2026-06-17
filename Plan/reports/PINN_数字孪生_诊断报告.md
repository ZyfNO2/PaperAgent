# 诊断报告: PINN 数字孪生题目暴露的 3 个症状

> 报告时间: 2026-06-18
> 触发: 用户切换题目到 "基于物理信息神经网络(PINN)的机构实时数字孪生"
> 调查方法: systematic-debugging Phase 1+2 (read code, trace data flow, cross-check Session 范围)
> 结论: **3 个症状全部是 Session 5+ 待做的功能, 不是真 bug**. 暂不改代码, 列入 Session 5 待办.

---

## 1. 用户报告的症状 (3 条)

| # | 截图位置 | 症状 |
|---|---|---|
| 1 | 图 1 "退化路线 (3 条)" | 3 张路线卡片全部说 "钢材表面缺陷", 但原题是 "PINN 数字孪生" |
| 2 | 图 1 "Baseline 通过" + 图 3 "Baseline 1: ResNet-50 (torchvision)" | Baseline 仍是 YOLO/ResNet-50, 与 PINN 主题不符 |
| 3 | 图 3 "证据检索" | 论文命中 2 篇完全无关的 arXiv (German survey / AGN survey), 数据集 1 个 "未匹配公开数据集" 标 "heurtisc" |

---

## 2. 根因调查

### 症状 1: 退化路线硬编码 "钢材"

**位置**: `apps/api/app/services/one_topic.py:622-649` (`generate_pivot_routes` 的 conservative 路线)

```python
cons = PivotRoute(
    level="conservative",
    new_topic=f"基于 {method} 的钢材表面缺陷检测方法研究",  # ← 硬编码
    preserved_keywords=preserved + ["钢材表面缺陷"],
    removed_keywords=removed + ["多模态", "高精度", "实时"],
    tradeoff="去掉多模态 / 实时, 限定到钢材+检测. ...",
    work_packages=[
        WorkPackageSuggestion(
            wp_id="WP1",
            title=f"基于公开数据集复现 {method} baseline",
            research_question=f"{method} 在钢材表面缺陷数据上的 baseline 性能如何?",
            method_approach=f"采用 {method} 官方实现, 在 NEU-DET/GC10-DET 上训练.",  # ← 硬编码
            data_source="NEU-DET / GC10-DET",  # ← 硬编码
            ...
        ),
        ...
    ],
)
```

**问题**: conservative 路线**完全忽略原题对象**, 无条件推荐"钢材 + 检测 + NEU-DET/GC10-DET"。这在 Session 4 (5 档 + 3 条退化路线) 验收时, 因为当时主要测的题目就是钢材/PCB/桥梁/皮肤这些**已稳定开源数据集的领域**, 所以硬编码保守路线"指向钢材"看起来很自然。

**Session 4 报告的限定** ([Session_04_Pivot_Routes_验收报告.md §6](file:///G:/PaperAgent/Plan/reports/Session_04_Pivot_Routes_验收报告.md)):
> Session 5: 去重 + 评分 (PaperRelevance / DatasetScore / RepoScore 公式 ...)

—— Session 4 没承诺路线**语义**对所有题目都对, 只承诺"架构 + API + 端到端跑通"。

### 症状 2: Baseline 是 YOLO/ResNet-50

**位置**: `apps/api/app/services/one_topic.py:441-474` (`_heuristic_baselines`)

```python
def _heuristic_baselines(keywords: KeywordBreakdown) -> list[BaselineHit]:
    method = (keywords.method_keywords[0] or "").lower() if keywords.method_keywords else ""
    if "yolo" in method:
        return [BaselineHit(... "YOLOv8 (Ultralytics 官方)" ...), ...]  # 钢材/缺陷类
    if "transformer" in method or "vit" in method:
        return [BaselineHit(... "Swin Transformer" ...)]
    if "bert" in method or "llm" in method or "gpt" in method:
        return [BaselineHit(... "BERT (HuggingFace)" ...)]
    # 兜底
    return [
        BaselineHit(baseline_id="BL99", name="ResNet-50 (torchvision)",
                     paper_title="Deep Residual Learning for Image Recognition",
                     ...),
    ]
```

**词典覆盖**: 5 个 method 关键词 (`yolo`, `transformer`/`vit`, `bert`/`llm`/`gpt`)

**未覆盖 method 词** (P0 待补):
- `PINN` / 物理信息神经网络
- `数字孪生` / `digital twin`
- `有限元` / `FEM` / `FEA`
- `图神经网络` / `GNN` / `GCN` / `GAT`
- `扩散模型` / `diffusion` (虽然 _METHOD_HINTS 有 "diffusion"→"Diffusion" 但 baseline 词典没接)
- `GAN` (同样 _METHOD_HINTS 里有但 baseline 词典没接)
- `Mamba` (同样)
- `强化学习` / `RL` (同样)
- `Transformer` 之外的 `DETR` / `DeiT` / `DINO`

**`PINN` 题目**: method_keywords=`["PINN"]` → method.lower()="pinn" → 5 个 if 全 false → 落到兜底 "ResNet-50"。

**Session 4 报告 §6 没承诺** baseline 词典全行业覆盖, baseline 评分 (RepoScore) 是 Session 5 才做。

### 症状 3: arXiv 论文/数据集明显不相关

**位置**: `apps/api/app/services/one_topic.py:299-367` (`build_search_plan`) + `_heuristic_breakdown` (line 156-228)

`build_search_plan` 生成的 paper 检索词:
```python
paper_zh = [
    f"{method_zh} {obj_zh} {task_zh}".strip(),  # "PINN 机构 目标检测"
    f"{obj_zh} {task_zh} 综述",                  # "机构 目标检测 综述"
]
paper_en = [
    f"{method_en} {obj_en} {task_zh}".strip(),   # "pinn   "
    f"{obj_en} {task_zh} survey",
    f"{method_en} {obj_en} benchmark".strip(),
]
```

**对 "基于物理信息神经网络(PINN)的机构实时数字孪生"**:
- `_heuristic_breakdown` 抽到 `method=["PINN"]` (因为 "pinn" in `_METHOD_HINTS`)
- `_has_specific_object`: 没有命中 `_OBJECT_HINTS` 任何 key (没有"钢/桥/叶/电/..."), 而且 `_has_specific_object` 兜底分支也走不到 ("机构" 里的字符不命中 `钢桥路叶电管轮轴果菜皮眼细行车PCB焊螺`) → `is_specific_object = False`
- `object_keywords=[]` (没有任何具象对象词), 退到 `obj.append(text)` = 整句话
- `task_keywords=[]` (没有"检测/分割/分类/...") → 兜底 `task_zh = "检测"`
- 实际发出的查询:
  - `paper_zh = ["PINN  基于物理信息神经网络(PINN)的机构实时数字孪生 检测", "基于物理信息神经网络(PINN)的机构实时数字孪生 检测 综述"]`
  - `paper_en = ["pinn  基于物理信息神经网络(pinn)的机构实时数字孪生  检测", "基于物理信息神经网络(pinn)的机构实时数字孪生  检测 survey", "pinn  基于物理信息神经网络(pinn)的机构实时数字孪生  benchmark"]`

— 这些查询 arXiv 完全匹配不到, arxiv 兜底返回按时间倒序的若干宽泛论文, 截图里看到 German Open-Ended Survey 和 AGN Boötes survey 就是 arXiv 最近 2 篇 (没真正相关, 只是兜底)。

**数据集**: `_heuristic_datasets` 也没命中 `钢/PCB/桥/皮肤` 任何分支, 落到 `DS99 "(未匹配公开数据集)"` 兜底 (line 431-437)。截图里 "heurtisc" 标签是 evidence store `_summary` 或渲染时把 `(未匹配)` 拼到了其他字符串里 (待确证, 优先级低)。

**Session 4 §6 明确说**:
> Session 5: 去重 + 评分 (PaperRelevance / DatasetScore / RepoScore 公式, **论文类型分类 survey/baseline/application/irrelevant**, DatasetScore 评分, RepoScore 评分)

— **irrelevant 分类**就是症状 3 的根治 (过滤掉 German survey / AGN 这种显然不相关的)。

---

## 3. Session 范围确认

| Session | 已做 (对照 report) | 没做 |
|---|---|---|
| 1 (Evidence 数据模型) | evidence ledger, 手动入池 | 自动评分/分类 |
| 2 (Evidence Workbench) | UI 渲染, 审核状态机 | PaperRelevance 公式 |
| 3 (Human Gates) | 关键词/检索词编辑 + regenerate | 论文类型分类 |
| 4 (Pivot Routes) | 5 档判定 + 3 条路线**架构** | 路线的**语义动态化**, baseline 词典补全, PaperRelevance 过滤 |
| **5 (待做)** | — | **去重 + 评分 (PaperRelevance / DatasetScore / RepoScore)**, 论文类型分类 (survey/baseline/application/**irrelevant**) |

**3 个症状全部落在 Session 5 范围**:
- 症状 1 → 路线生成需要**按原题语义生成**, 不是硬编码钢材; 这是路线评分 + 路线模板化的副产品
- 症状 2 → baseline 词典需要**扩 method 关键词覆盖** (PINN / 数字孪生 / GNN / ...), 同时 RepoScore 评分能标出 "低契合"
- 症状 3 → 论文类型分类 + PaperRelevance 评分能**自动过滤 irrelevant**

---

## 4. 测试覆盖检查

**当前测试** (`apps/api/tests/test_one_topic_api.py`) 覆盖了 4 个具象对象:
```python
("基于深度学习的PCB缺陷检测方法研究", "DeepPCB"),
("基于YOLO的桥梁裂缝检测", "CODEBRIM"),
("基于CNN的皮肤病变分类", "HAM10000"),
# + YOLO 钢材 (test_analyze_yolo_steel_happy_path)
```

**未覆盖场景** (P0 新增测试, Session 5):
- "基于 PINN 的机构数字孪生" → 应触发 `is_specific_object=False` 提示
- "基于 XXX 的极小众对象检测" → 已覆盖 (test_analyze_niche_topic_triggers_shrink_or_pause)
- "基于 GNN 的推荐系统" → 应触发 baseline 词典缺失
- "基于 Diffusion 的医学图像生成" → 应触发 baseline 词典缺失
- "基于 GAN 的数据增强" → 应触发 baseline 词典缺失
- "基于 LLM 的代码生成" → 已覆盖? (没单独测, 需确认)

---

## 5. 结论与建议

### 5.1 结论: **暂不改代码**

- 这 3 个症状不是引入式 bug, 是 Session 4 没承诺覆盖的**广义题目适配能力**
- SessionStart intel 也明确说: `retrieval_scoring: PaperRelevance / DatasetScore / RepoScore (SOP §7)` 是**当前实现缺少的 P0 功能**
- 改这 3 个症状的真实工作量 = Session 5 (评分 + 分类 + 词典扩展 + 路线模板化), **不在 "修复 bug" 范围内**

### 5.2 建议的 Session 5 待办 (P0)

1. **扩展 `_METHOD_HINTS` + `_heuristic_baselines` 词典**
   - 新增 method: `PINN`, `数字孪生`/`digital twin`, `有限元`, `GNN`/`GCN`/`GAT`, `扩散模型`/`diffusion`, `GAN`, `Mamba`, `强化学习`/`RL`, `DETR`/`DeiT`/`DINO`, `LoRA`/`PEFT`
   - 每个 method 配 1-2 个**真实可复现 baseline** (GitHub repo URL + 论文), 不要兜底到 ResNet-50

2. **新增 `_OBJECT_HINTS` 抽象对象词**
   - 数字孪生: `机构`, `机械系统`, `传动链`, `工业装备`
   - 推荐系统: `推荐`, `排序`
   - 时序: `时间序列`, `传感器`, `振动`
   - 没有具象对象时, 在 `topic_understanding.intent_zh` 明确提示 "原题对象偏抽象, 建议 Phase 02 补问"

3. **arXiv 论文类型分类 + PaperRelevance 评分**
   - 分类: `survey` / `baseline` / `application` / `irrelevant` (SOP §7 已有)
   - PaperRelevance 公式: 关键词覆盖率 + 引用数 + 年份新度 + 类型权重
   - 检索结果中 `irrelevant` 直接过滤, 不入 evidence pool

4. **路线模板化 (症状 1 根治)**
   - conservative 路线**不硬编码钢材**, 而是**按原题语义生成**:
     - 若原题有公开数据集 (has_public_dataset=True) → conservative 保留原题, 收缩范围 (去掉 risk_terms, 用原数据集)
     - 若原题无公开数据集 → conservative 推荐"相邻最稳对象" (从 `_PUBLIC_DATASET_OBJECTS` 选 nearest neighbor)
   - balanced / aggressive 同样按原题语义生成

5. **新增测试覆盖**
   - "基于 PINN 的机构数字孪生" → 期望 baseline 不再是 ResNet, 期望数据集**显示缺失**而不是硬编码 NEU-DET
   - "基于 GNN 的推荐系统" → 同上
   - "基于 LLM 的代码生成" → 期望 baseline 命中 `BERT/HuggingFace` 路径或新增 `Code-Llama` 等
   - "智能交通" → 已在 test_keyword_breakdown_always_has_query_keywords 覆盖

### 5.3 用户面立即可做的 (不改代码, 1 行前端)

在前端 **#block-understanding** (Block 1 题目理解) 加一个**红色 banner**:
```html
${!tu.is_specific_object ? `<div class="warn-banner">
  ⚠️ 原题对象偏抽象 (没命中具象对象词典: 钢/桥/叶/...), 
  arXiv 命中质量可能较差, 建议在 #input-topic 改成具体对象
</div>` : ""}
```

— 这是**用户提示**, 不是修复, 不动业务逻辑, **不在 "修 bug" 范围内**, 但能马上减轻用户困惑。

### 5.4 不建议的临时修复 (会被 Session 5 推翻)

- ❌ 把 conservative 路线改成"按原题 method 走, 不指定对象" → 仍然硬编码不通用
- ❌ 在 `_heuristic_baselines` 加 if "pinn": return [...] → Session 5 评分机制上线后会重写这里
- ❌ 在 `_heuristic_datasets` 加 if "机构": return [...] → 同样, Session 5 才是正确位置

---

## 6. 引用

- 代码位置:
  - `apps/api/app/services/one_topic.py:441-474` `_heuristic_baselines`
  - `apps/api/app/services/one_topic.py:622-649` `conservative 路线硬编码`
  - `apps/api/app/services/one_topic.py:431-437` `_heuristic_datasets` 兜底
  - `apps/api/app/services/one_topic.py:156-228` `_heuristic_breakdown`
- 验收报告:
  - [Session_04_Pivot_Routes_验收报告.md §6](file:///G:/PaperAgent/Plan/reports/Session_04_Pivot_Routes_验收报告.md) — 明确说 Session 5 做评分
  - [TopicPilot-CN_MVP_总报告.md](file:///G:/PaperAgent/Plan/reports/TopicPilot-CN_MVP_总报告.md) — Session 范围
- SOP 改造计划: `Plan/Faraway/PaperAgent_*.md` §7 (retrieval_scoring)

---

**待办已记入 Session 5**, 不在本次 commit 改代码. 用户已确认: 审核到是 Session 暂未做到, 写 report 待做.
