---
template_key: default
name: 通用开题报告模板
version: 0.1.0
applies_to: 本科 / 硕士 / 博士 (通用)
required_sections:
  - 研究背景与意义
  - 国内外研究现状
  - 研究目标与研究内容
  - 技术路线
  - 实验方案与评价指标
  - 可行性分析
  - 创新点
  - 进度安排
  - 风险预案
  - 参考文献与证据清单
evidence_required: true
placeholders:
  - topic
  - background
  - related_work
  - datasets
  - baselines
  - work_packages
  - risks
  - citations
---

# 开题报告：{{topic}}

> 模板：通用开题报告（default）
> 适用：大多数学科的开题报告初稿。
> 占位符：{{topic}} {{background}} {{related_work}} {{datasets}} {{baselines}} {{work_packages}} {{risks}} {{citations}}

---

## 一、研究背景与意义

{{background}}

阐述该方向的研究意义、应用价值与毕业可行性。

## 二、国内外研究现状

{{related_work}}

按方法族 / 任务类型聚类，标注代表性工作与不足。

## 三、研究目标与研究内容

- 研究目标：{{topic}}
- 研究内容：见工作包章节。

## 四、技术路线

给出从数据 → 方法 → 实验 → 评估的主链路，标注关键决策点。

## 五、实验方案与评价指标

- 数据集：{{datasets}}
- Baseline：{{baselines}}
- 评价指标：mAP / Recall / FPS / ...

## 六、可行性分析

从数据可得性、baseline 复现难度、计算资源、时间窗口四方面论证。

## 七、创新点

基于证据清单，给出可量化的创新点（避免"首创/填补空白"等夸大表述）。

## 八、进度安排

按典型开题周期（16 周）拆分里程碑。

## 九、风险预案

{{risks}}

每条风险配一个降级方案。

## 十、参考文献与证据清单

{{citations}}

> 模板约束：所有结论必须绑定 Evidence ID；rejected / pending+unverified / failed 证据不进入正向引用。
