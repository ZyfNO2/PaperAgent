---
template_key: cv_ai
name: 计算机视觉 / AI 开题报告模板
version: 0.1.0
applies_to: CV / NLP / 多模态 / AI 方向课题
required_sections:
  - 研究背景
  - 相关工作分类
  - 数据集与评价指标
  - Baseline 与复现计划
  - 方法设计
  - 实验设计
  - 消融与误差分析计划
  - 创新点与预期贡献
  - 风险预案
  - 引用清单
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

# 开题报告（CV/AI）：{{topic}}

> 模板：计算机视觉 / AI（cv_ai）
> 适用：以模型/算法实验为核心的 CV / NLP / 多模态课题。
> 强调：数据集 → baseline → 方法 → 实验 → 消融 的科研链路。

---

## 一、研究背景

{{background}}

## 二、相关工作分类

{{related_work}}

按方法族聚类（如 two-stage / one-stage / transformer-based），标注 SOTA 与不足。

## 三、数据集与评价指标

- 数据集：{{datasets}}
- 划分：train / val / test
- 评价指标：mAP@0.5 / mAP@0.5:0.95 / Recall / FPS / Params / FLOPs

## 四、Baseline 与复现计划

{{baselines}}

- 复现目标指标（来自原论文）
- 复现环境（GPU / 框架版本）
- 复现风险（代码缺失 / 数据私有）

## 五、方法设计

给出方法图与关键模块，标注与 baseline 的差异点。

## 六、实验设计

- 主实验：在目标数据集上与 baseline 对比
- 跨数据集泛化（如有）
- 效率实验：Params / FLOPs / FPS

## 七、消融与误差分析计划

- 消融：逐模块移除验证贡献
- 误差分析：按类别 / 困难度 / 尺寸 统计失败案例

## 八、创新点与预期贡献

基于证据，给出可量化的创新点与预期提升幅度。

## 九、风险预案

{{risks}}

CV 类重点：数据集 license、复现失败、指标不达预期时的退化路线。

## 十、引用清单

{{citations}}

> 模板约束：所有实验结论必须绑定 Evidence ID；baseline 复现指标须可追溯到原论文或仓库 README。
