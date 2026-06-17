# TopicPilot-CN OneTopic MVP 修改 SOP

> 目标：把当前 8 Phase 流程先收缩成一个更人性化的 MVP：用户只输入一个选题，系统完成关键词拆解、论文/数据集/工程证据检索、可行性判断、开题方向推荐和低门槛模拟审核。

---

## 1. 下一步主线

当前主线从：

> 用户填写完整建档表 → Phase 01-08 全流程

调整为：

> 用户只输入一个题目 → 系统先判断这个题目能不能做

示例输入：

```text
基于 YOLO 的钢材表面缺陷检测
```

系统应输出：

```text
关键词拆解：
- YOLO
- 检测
- 钢材表面缺陷

证据检索：
- 论文是否足够
- 数据集是否存在
- baseline / GitHub 工程是否可复现

可行性判断：
- 可做
- 收缩后可做
- 暂缓
- 不建议

后续建议：
- 推荐题目
- 推荐工作包
- 开题报告骨架
- 低门槛模拟审核意见
```

---

## 2. 修改原则

### 2.1 先做人性化入口

不要一开始要求用户填写完整建档信息。

第一屏只保留：

```text
请输入你的选题：
[ 基于YOLO的XXX检测 ]

可选：
- 专业方向
- 目标档位：保毕业 / 稳中求新 / 冲高水平
```

推荐提示语：

```text
先不用填完整开题信息，我先帮你判断这个题目有没有论文、数据集和 baseline。
```

### 2.2 先判断能不能做，再生成完整开题报告

不要一开始就生成完整报告。

先完成：

1. 题目理解
2. 关键词拆解
3. 检索证据
4. 可行性判断
5. 推荐收缩方向
6. 初步审核

---

## 3. OneTopic MVP 流程

```text
Step 1：输入一个题目
↓
Step 2：关键词拆解
↓
Step 3：论文 / 数据集 / 工程三线检索
↓
Step 4：可行性判断
↓
Step 5：推荐题目与工作包
↓
Step 6：低门槛模拟审核
↓
Step 7：进入后续开题报告生成
```

---

## 4. Phase 01 修改：一题输入 + 默认建档

### 4.1 新定位

Phase 01 不再要求完整建档，而是做“一题输入”。

输入最小化：

```json
{
  "raw_topic": "基于YOLO的钢材表面缺陷检测",
  "goal_level": "保毕业"
}
```

可选字段：

```json
{
  "major": "计算机科学与技术",
  "advisor_direction": "工业质检",
  "degree_type": "硕士"
}
```

### 4.2 默认策略

如果用户没有填写专业、导师、时间，不直接 D 阻断，而是进入“预评估模式”。

```text
缺少毕业时间：使用“保守毕业周期”估计
缺少导师方向：只做题目可行性，不做导师匹配
缺少专业：默认按计算机 / AI / 工科视觉方向预评估
```

### 4.3 Phase 01 输出

```json
{
  "raw_topic": "基于YOLO的钢材表面缺陷检测",
  "goal_level": "保毕业",
  "intake_mode": "quick_topic_only",
  "missing_fields": ["major", "advisor_direction", "deadline"],
  "allow_keyword_decompose": true
}
```

---

## 5. Phase 02 修改：关键词拆解 + 题目意图理解

### 5.1 新定位

Phase 02 的重点不是直接生成完整 TopicSpec，而是先帮用户拆题。

示例：

```text
基于YOLO的钢材表面缺陷检测
```

拆成：

```json
{
  "method_keywords": ["YOLO", "YOLOv8", "object detection"],
  "task_keywords": ["检测", "目标检测", "defect detection"],
  "object_keywords": ["钢材", "钢材表面", "steel surface"],
  "scenario_keywords": ["工业质检", "surface defect inspection"],
  "risk_terms": ["基于", "检测"],
  "query_keywords_zh": [
    "YOLO 钢材表面缺陷检测",
    "钢材表面缺陷 数据集",
    "工业缺陷检测 YOLO"
  ],
  "query_keywords_en": [
    "YOLO steel surface defect detection",
    "steel surface defect dataset",
    "industrial defect detection YOLO"
  ],
  "intent_zh": "该题目希望使用 YOLO 系列目标检测方法，对钢材表面缺陷进行识别和定位，适合工业质检方向。"
}
```

### 5.2 关键词类别

| 类别 | 说明 | 示例 |
|---|---|---|
| 方法词 | 使用的模型、算法、技术路线 | YOLO、YOLOv8、Transformer |
| 任务词 | 要完成的任务 | 检测、分类、分割、预测 |
| 对象词 | 研究对象 | 钢材表面缺陷、桥梁裂缝、叶片病害 |
| 场景词 | 应用场景 | 工业质检、医学影像、农业检测 |
| 指标词 | 可能评价指标 | mAP、Recall、FPS、Params |
| 风险词 | 需要收缩或解释的词 | 智能、高精度、实时、全场景 |

### 5.3 Phase 02 输出

```json
{
  "raw_topic": "基于YOLO的钢材表面缺陷检测",
  "normalized_topic": "基于YOLOv8的钢材表面缺陷检测方法研究",
  "keywords": {
    "method": ["YOLO", "YOLOv8"],
    "task": ["目标检测", "缺陷检测"],
    "object": ["钢材表面缺陷"],
    "scenario": ["工业质检"]
  },
  "query_keywords_zh": [],
  "query_keywords_en": [],
  "risk_terms": [],
  "allow_search": true
}
```

---

## 6. Phase 03 修改：论文 / 数据集 / 工程三线检索计划

### 6.1 新定位

Phase 03 不只是生成检索词，而是把检索分成三条线：

```text
论文线：有没有相关论文
数据集线：有没有可用数据
工程线：有没有 baseline / GitHub / YOLO 实现
```

### 6.2 检索计划

#### 论文线

```text
YOLO steel surface defect detection
YOLOv8 industrial defect detection
steel surface defect detection deep learning
surface defect detection survey
```

#### 数据集线

```text
steel surface defect dataset
NEU-DET dataset
GC10-DET dataset
KolektorSDD dataset
industrial defect detection dataset
```

#### 工程线

```text
YOLOv8 steel defect GitHub
YOLO defect detection GitHub
ultralytics YOLO defect detection
NEU-DET YOLO baseline
```

### 6.3 Phase 03 输出

```json
{
  "paper_queries": [],
  "dataset_queries": [],
  "engineering_queries": [],
  "baseline_queries": [],
  "query_total": 20,
  "allow_evidence_search": true
}
```

---

## 7. Phase 04 修改：证据采集 + 可行性判断

### 7.1 新定位

Phase 04 不只是 EvidenceLedger，而是直接回答：

> 这个题目能不能做？

### 7.2 证据类型

| 类型 | 最小要求 | 说明 |
|---|---|---|
| 论文 | 至少 5 篇相关论文 | 判断方向是否成熟 |
| 数据集 | 至少 1-2 个候选 | 判断实验能否开始 |
| Baseline | 至少 1 个可复现方案 | 判断是否能跑第一张表 |
| 工程代码 | 至少 1 个 GitHub / 官方实现 | 判断实现成本 |
| 指标 | 至少 1 套评价指标 | 判断实验是否可评价 |

### 7.3 可行性四档

| 结论 | 条件 | 含义 |
|---|---|---|
| 可做 | 论文、数据集、baseline、指标都存在 | 可进入开题报告推荐 |
| 收缩后可做 | 方向大，但能收缩到成熟任务 | 推荐改题或限定场景 |
| 暂缓 | 有论文，但数据或 baseline 不稳定 | 需要补证据 |
| 不建议 | 没有数据、指标或可复现 baseline | 不适合作为当前毕业题目 |

### 7.4 输出示例

```json
{
  "feasibility": "收缩后可做",
  "reason": "YOLO 缺陷检测方向成熟，但题目中的 XXX 对象需要确认是否有公开数据集。",
  "papers": [],
  "datasets": [],
  "baselines": [],
  "engineering_repos": [],
  "missing_evidence": [
    "缺少明确数据集",
    "缺少可复现 baseline"
  ],
  "recommended_next_action": "优先确认数据集，再决定是否保留 XXX 场景。"
}
```

---

## 8. 开题报告推荐

当 Phase 04 判断为“可做”或“收缩后可做”时，生成开题方向推荐。

### 8.1 推荐题目

```text
基于轻量化 YOLOv8 的钢材表面缺陷检测方法研究
```

### 8.2 推荐理由

```text
1. YOLO 系列 baseline 成熟，工程实现丰富。
2. 钢材表面缺陷方向有公开数据集可用。
3. 可拆成两个工作包：baseline 复现 + 模块改进。
4. 可使用 mAP、Recall、FPS、参数量等指标评价。
```

### 8.3 推荐工作包

```text
WP1：基于公开数据集复现 YOLOv8 baseline
WP2：引入轻量化模块或注意力机制，并进行消融实验
```

### 8.4 推荐开题结构

```text
1. 研究背景与意义
2. 国内外研究现状
3. 研究内容与目标
4. 技术路线
5. 实验方案
6. 预期创新点
7. 进度计划
8. 风险预案
```

---

## 9. 低门槛模拟审核

### 9.1 审核定位

不要做顶会式审稿。

只做“开题前初步审核”。

### 9.2 五项审核

| 维度 | 审核问题 |
|---|---|
| 题目边界 | 是否明确研究对象和任务 |
| 数据集 | 是否有可获得数据 |
| Baseline | 是否有可复现方法 |
| 工作量 | 是否能拆成 1-2 个章节 |
| 开题表达 | 是否能讲清楚背景、方法和实验 |

### 9.3 审核结论

```text
通过
有条件通过
需修改
不建议
```

### 9.4 输出示例

```json
{
  "verdict": "有条件通过",
  "summary": "题目方向可行，但需要先确认具体数据集和 baseline。",
  "checks": [
    {
      "dimension": "题目边界",
      "result": "通过",
      "comment": "研究对象和任务较明确。"
    },
    {
      "dimension": "数据集",
      "result": "需补充",
      "comment": "需要明确使用 NEU-DET、GC10-DET 或其他公开数据集。"
    },
    {
      "dimension": "Baseline",
      "result": "通过",
      "comment": "YOLOv8 baseline 工程成熟。"
    }
  ],
  "revision_checklist": [
    "明确数据集名称",
    "补充 3-5 篇 YOLO 缺陷检测论文",
    "说明改进模块如何消融验证"
  ]
}
```

---

## 10. 前端修改 SOP

### 10.1 首页

从 8 Phase 大流程入口改成 OneTopic 输入。

第一屏：

```text
你的选题是什么？
[ 基于YOLO的XXX检测 ]

按钮：
[ 开始判断能不能做 ]
```

### 10.2 结果页面

采用 5 个区块：

```text
1. 题目理解
2. 关键词拆解
3. 证据检索
4. 可行性判断
5. 开题建议 / 初步审核
```

### 10.3 Trace 面板

Trace 不要只显示技术步骤，要显示用户能懂的话：

```text
正在拆出方法词：YOLO
正在拆出任务词：检测
正在拆出对象词：钢材表面缺陷
正在搜索相关论文
正在搜索公开数据集
正在检查是否有 GitHub 工程
正在生成可行性结论
```

---

## 11. Playwright 验收需求

### 11.1 Happy Path

文件名：

```text
one-topic-happy-path.spec.ts
```

测试流程：

```text
输入：基于YOLO的钢材表面缺陷检测
点击：开始判断能不能做

期望：
- 页面展示关键词：YOLO
- 页面展示关键词：检测
- 页面展示关键词：钢材表面缺陷
- 页面展示论文证据区
- 页面展示数据集证据区
- 页面展示工程 / baseline 证据区
- 页面展示可行性结论
- 页面展示推荐题目
- 页面展示至少 1 个工作包建议
```

### 11.2 数据集不足路径

文件名：

```text
one-topic-no-dataset.spec.ts
```

测试流程：

```text
输入：基于XXX的极小众对象检测
点击：开始判断能不能做

期望：
- 页面提示数据集证据不足
- 页面给出收缩建议
- 页面不直接生成完整开题报告
- 页面展示“暂缓”或“收缩后可做”
```

### 11.3 初步审核路径

文件名：

```text
one-topic-review.spec.ts
```

测试流程：

```text
完成证据采集后
点击：初步审核

期望：
- 页面展示 5 项审核维度
- 页面展示审核结论
- 页面展示修改清单
- 审核条件较低，不使用顶会式严格审稿标准
```

### 11.4 Trace 验收

文件名：

```text
one-topic-trace.spec.ts
```

测试流程：

```text
输入题目并启动分析

期望：
- trace 面板出现“关键词拆解”
- trace 面板出现“搜索论文”
- trace 面板出现“搜索数据集”
- trace 面板出现“搜索工程”
- trace 面板出现“生成可行性判断”
```

---

## 12. 后端修改 SOP

### 12.1 新增或调整端点

建议新增一个 OneTopic 聚合端点：

```text
POST /api/v1/one-topic/analyze
```

输入：

```json
{
  "raw_topic": "基于YOLO的钢材表面缺陷检测",
  "goal_level": "保毕业"
}
```

输出：

```json
{
  "topic_understanding": {},
  "keyword_breakdown": {},
  "search_plan": {},
  "evidence_summary": {},
  "feasibility": {},
  "proposal_recommendation": {},
  "light_review": {}
}
```

MVP 阶段可以内部复用 Phase 01-04 的函数，不必完全重写。

### 12.2 流式端点

建议新增：

```text
POST /api/v1/one-topic/analyze/stream
```

SSE 事件：

```text
start
keyword_decompose
paper_search
dataset_search
engineering_search
feasibility
proposal_recommendation
light_review
result
end
```

### 12.3 保留旧 8 Phase

旧的 8 Phase 不删。

OneTopic MVP 是一个“更友好的入口”，不是替代所有后续流程。

---

## 13. 数据结构建议

### 13.1 KeywordBreakdown

```python
class KeywordBreakdown(BaseModel):
    raw_topic: str
    method_keywords: list[str]
    task_keywords: list[str]
    object_keywords: list[str]
    scenario_keywords: list[str]
    metric_keywords: list[str]
    risk_terms: list[str]
    query_keywords_zh: list[str]
    query_keywords_en: list[str]
    intent_zh: str
```

### 13.2 FeasibilitySummary

```python
class FeasibilitySummary(BaseModel):
    verdict: Literal["可做", "收缩后可做", "暂缓", "不建议"]
    reason: str
    paper_status: str
    dataset_status: str
    baseline_status: str
    engineering_status: str
    missing_evidence: list[str]
    recommended_next_action: str
```

### 13.3 LightReview

```python
class LightReview(BaseModel):
    verdict: Literal["通过", "有条件通过", "需修改", "不建议"]
    checks: list[ReviewCheck]
    revision_checklist: list[str]
```

---

## 14. 执行顺序

### 第一步：写 OneTopic MVP Plan

输出：

```text
Plan/TopicPilot-CN_OneTopic_MVP_修改SOP.md
```

内容包括：

```text
目标
用户流程
数据结构
接口设计
前端页面
Playwright 验收
后续接入 05-08 的方式
```

### 第二步：改 Phase 01-04 SOP

目标：

```text
Phase 01：一题输入 + 默认建档
Phase 02：关键词拆解 + 意图理解
Phase 03：论文 / 数据集 / 工程检索计划
Phase 04：证据采集 + 可行性判断
```

### 第三步：改前端

目标：

```text
首页只输入一个题目
右侧 trace 讲人话
结果分为关键词 / 证据 / 可行性 / 推荐 / 审核
```

### 第四步：补 OneTopic 后端入口

目标：

```text
一个端点跑通 OneTopic MVP
一个 SSE 端点跑通可视化 trace
```

### 第五步：补 Playwright

目标：

```text
happy path
no dataset path
light review path
trace path
```

### 第六步：验收后再改 05-08

不要现在重写 05-08。

等 OneTopic MVP 通过后，再把后续 Phase 改成：

```text
Phase 05：收缩 / Pivot 推荐
Phase 06：开题报告骨架
Phase 07：低门槛模拟审核
Phase 08：导出与归档
```

---

## 15. 不建议现在做的事

| 不建议 | 原因 |
|---|---|
| 继续扩写完整 8 Phase | 当前痛点是入口不自然 |
| 一开始要求完整建档 | 用户只想先判断题目能不能做 |
| 直接生成长篇开题报告 | 没有证据前容易空泛 |
| 让 LLM 凭记忆说有数据集 | 必须搜索或标记未验证 |
| 一开始做复杂多 Agent | 先跑通 OneTopic 人性化体验 |
| 顶会式严格审稿 | 当前目标是低门槛开题初审 |

---

## 16. MVP 验收标准

OneTopic MVP 通过条件：

```text
1. 用户只输入一个题目即可启动
2. 系统能拆出方法词、任务词、对象词
3. 系统能展示论文 / 数据集 / 工程三类证据
4. 系统能给出可行性四档判断
5. 系统能给出推荐题目和工作包
6. 系统能进行低门槛模拟审核
7. Playwright 覆盖 happy path、证据不足 path、审核 path、trace path
```

---

## 17. 一句话总结

下一步不要继续堆完整 8 Phase。

先把 TopicPilot-CN 改成：

> 我只输入一个题目，你先帮我拆关键词、查论文、查数据集、查工程代码，然后告诉我这个题目能不能开题，怎么改更稳。

这个体验跑通后，再把 Phase 05-08 接回完整毕业论文工作流。

