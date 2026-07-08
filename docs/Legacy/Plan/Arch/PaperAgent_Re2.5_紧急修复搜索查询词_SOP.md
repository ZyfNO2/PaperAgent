# PaperAgent Re2.5 紧急修复：搜索查询词被过滤导致全垃圾 SOP

> 承接：Re2.4 完工（前端重做 + graph 优化 + 截图验证）
> **紧急修复 — 用户测试发现"基于yolo的农作物识别"返回全是 Deep Learning 垃圾。**
> 预计总时长：1-2 小时。
> 模型：DeepSeek (主)。

## 0. 根因分析

用户输入"基于yolo的农作物识别"，系统返回 14 篇全是"Deep Learning"通用论文 + keras/教程仓库。**0 篇与 YOLO 或农作物相关。**

### 完整失败链条

```
topic_parser: method=["YOLO"], object=["crop"], task=["recognition"]  ← 正确

retrieve._run_direct_adapter_retrieval:
  head = method[:2] + obj[:2] = ["YOLO", "crop"]
  queries = ["YOLO", "crop"]
  # 过滤: len(q) > 5
  # "YOLO" 长度 4 → 被过滤!
  # "crop" 长度 4 → 被过滤!
  queries = []  ← 空!
  
  # fallback: domain_map 没有 "vision_2d" → 返回 "deep learning"
  queries = ["deep learning"]  ← 垃圾查询!
  
  # 所有适配器搜 "deep learning" → 返回 keras/教程/通用论文
```

### 三个 bug 叠加

| # | Bug | 位置 | 影响 |
|---|---|---|---|
| 1 | `len(q) > 5` 过滤太严格 | retrieve.py L72 | "YOLO"(4)、"crop"(4)、"SLAM"(4) 等短关键词被丢弃 |
| 2 | `domain_map` 缺少 `"vision_2d"` key | retrieve.py L82 | vision_2d 领域 fallback 到 `"deep learning"` |
| 3 | 第一次 retrieve 不传 search_plan | retrieve.py L243 | `search_plan = state.get("search_plan") if repair_rounds > 0 else None` → 第一次跑不用 search_planner 生成的精确查询词 |

### search_planner 生成的查询词是正确的

```
openalex: "YOLO crop"  ← 正确! (不会被 len>5 过滤, 长度 8)
arxiv: "YOLO crop recognition"  ← 正确! (长度 22)
```

但 retrieve 第一次跑时 `repair_rounds=0` → `search_plan=None` → 不用这些查询词，自己从 atoms 构建 head → 被过滤 → fallback 到 "deep learning"。

## 1. 修复计划

### Fix 1: retrieve.py — 第一次也用 search_plan 的查询词

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**当前代码**（L243）：

```python
search_plan = state.get("search_plan") if repair_rounds > 0 else None
```

**改为**：

```python
search_plan = state.get("search_plan")  # 始终使用 search_planner 生成的查询词
```

这样第一次 retrieve 也会用 search_planner 生成的 `"YOLO crop"` 和 `"YOLO crop recognition"`，而不是自己构建 head。

### Fix 2: retrieve.py — 降低 len 过滤阈值

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**当前代码**（L72）：

```python
queries = [q for q in dict.fromkeys(queries).keys() if len(q) > 5][:6]
```

**改为**：

```python
queries = [q for q in dict.fromkeys(queries).keys() if len(q) >= 3][:6]
```

`len(q) >= 3` 保留 "YOLO"(4)、"crop"(4)、"SLAM"(4) 等短关键词。

### Fix 3: retrieve.py — domain_map 补全

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**当前代码**（L78-86）：

```python
domain_map = {
    "medical_ai": "deep learning medical AI",
    "computer_vision": "deep learning computer vision",
    "nlp": "large language model NLP",
    "slam": "visual SLAM deep learning",
    "civil_engineering": "deep learning structural health monitoring",
}
```

**改为**（补全 vision_2d 和其他缺失的 domain）：

```python
domain_map = {
    "medical_ai": "deep learning medical AI",
    "computer_vision": "deep learning computer vision",
    "vision_2d": "object detection deep learning",
    "nlp": "large language model NLP",
    "slam": "visual SLAM deep learning",
    "civil_engineering": "deep learning structural health monitoring",
    "industrial_defect": "defect detection deep learning",
    "autonomous_driving": "autonomous driving perception",
    "power_inspection": "power line inspection deep learning",
    "remote_sensing": "remote sensing object detection",
    "robotics": "robot manipulation deep learning",
    "energy_equipment": "fault diagnosis deep learning",
}
```

### Fix 4: retrieve.py — head 构建用组合查询而非拆开

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**当前代码**（L65-69）：

```python
head = (method[:2] + obj[:2]) or [topic.split()[0] if topic else "deep learning"]
queries = []
for h in head:
    queries.append(f"{h}")
```

这把 method 和 object 拆开作为独立查询（"YOLO" 和 "crop" 分别搜）。

**改为**（组合查询）：

```python
head = (method[:2] + obj[:2]) or [topic.split()[0] if topic else "deep learning"]
queries = []
# 组合 method + object 作为一条查询（更精确）
if method and obj:
    queries.append(" ".join(method[:1] + obj[:1]))
elif method:
    queries.extend(method[:2])
elif obj:
    queries.extend(obj[:2])
else:
    queries.extend(head)
```

这样即使不用 search_plan，head 也会生成 `"YOLO crop"` 而非 `["YOLO", "crop"]`。

## 2. 验证

### 3-case 验证

| Case | 题目 | 预期 |
|---|---|---|
| V-YOLO | 基于yolo的农作物识别 | arxiv/GitHub 搜 "YOLO crop" → 有 YOLO 农作物相关论文 |
| V-SLAM | 基于深度学习的视觉SLAM语义地图的研究 | 不退化 |
| V-MED | 基于大语言模型的医学问答可信度评估方法研究 | 不退化 |

### 通过标准

| 检查项 | 通过标准 |
|---|---|
| retrieve 不搜 "deep learning" | ≥2/3 case 的 queries 不含 "deep learning" |
| paper_candidates 有相关论文 | V-YOLO 的 verified_papers 中有标题含 "YOLO" 或 "crop" 的论文 |
| graph 完成 | ≥2/3 has_final=True |
| V-SLAM/V-MED 不退化 | accept 数不减少 |

## 3. 禁止事项

- 禁止同时改多个文件。
- 禁止改完代码不跑 3-case 验证。
- 禁止用 VOAPI / MiniMax。

## 4. 交付物

代码：

- `apps/api/app/services/agents/graph/nodes/retrieve.py` 🔧 (4 个 fix)

数据：

- `tmp_re25_eval/verify/` (3-case 验证结果)
- `tmp_re25_eval/changelog.md`

报告：

- `Plan/PaperAgent_Re2.5_完工报告.md`

## 5. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | retrieve 不搜 "deep learning" | trace 的 queries 不含 "deep learning" |
| 2 | V-YOLO 有相关论文 | verified/weak 中有标题含 "YOLO" 或 "crop" |
| 3 | V-SLAM 不退化 | accept ≥ Re2.4 |
| 4 | V-MED 不退化 | accept ≥ Re2.4 |
| 5 | graph 完成 | ≥2/3 |
| 6 | changelog 记录 | 文件检查 |
| 7 | VOAPI/MiniMax = 0 | 全程 |
