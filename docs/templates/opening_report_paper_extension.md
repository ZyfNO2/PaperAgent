---
template_key: paper_extension
name: 已有小论文扩展报告 (Track B)
version: 0.1.0
applies_to: 已有 1 篇小论文, 需要扩成大论文 (Track B 路径)
required_sections:
  - 小论文贡献摘要
  - 大论文章节映射
  - 缺口分析
  - 扩展实验建议
  - 重复风险提示
  - 工作包规划
  - 复用现有 chunk 引用
evidence_required: true
placeholders:
  - paper_info
  - contributions
  - chapter_mappings
  - gap_analysis
  - extension_experiments
  - repeat_risks
  - work_packages
  - chunk_refs
  - thesis_outline
---

# 大论文扩展规划：基于小论文 {{paper_info}}

> 模板：已有小论文扩展报告 (Track B)
> 适用：用户已有 1 篇小论文, 需要扩成大论文.
> 占位符：{{paper_info}} {{contributions}} {{chapter_mappings}} {{gap_analysis}} {{extension_experiments}} {{repeat_risks}} {{work_packages}} {{chunk_refs}} {{thesis_outline}}

---

## 一、小论文贡献摘要

{{contributions}}

---

## 二、大论文章节映射

{{chapter_mappings}}

---

## 三、缺口分析

{{gap_analysis}}

---

## 四、扩展实验建议

{{extension_experiments}}

---

## 五、重复风险提示

{{repeat_risks}}

---

## 六、工作包规划 (第二 / 第三工作包)

{{work_packages}}

---

## 七、复用现有 chunk 引用

{{chunk_refs}}

---

## 八、大论文目录建议

{{thesis_outline}}
