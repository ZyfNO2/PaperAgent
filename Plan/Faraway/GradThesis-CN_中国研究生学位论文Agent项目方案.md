# GradThesis-CN：中国研究生学位论文全流程 Agent 项目方案

## 1. 项目定位

面向“中国研究生毕业学位论文”的 GitHub 开源生态已经具备较完整的局部能力，但目前仍缺少一个将以下环节统一起来的系统：

> 开题 → 中期检查 → 论文撰写 → 格式检查 → 查重前自检 → 预答辩 → 盲审修改 → 正式答辩 → 学位材料归档

现有项目主要分为五类：

1. 高校学位论文模板
2. Word / LaTeX 格式检查
3. 中文参考文献规范
4. 开题到答辩的流程清单
5. 面向论文写作、审查和答辩的 Agent Skills

因此，ThesisFlow 可以进一步特殊化为：

# GradThesis-CN：中国研究生学位论文全流程 Agent

核心目标不是“自动生成一篇论文”，而是：

> 理解中国高校学位论文的学校差异、培养流程、材料依赖、格式规范、盲审风险和答辩流程，并将这些规则编排为可追踪、可回放、有人类审核的 Agent 工作流。

---

## 2. 最值得参考的 GitHub 项目

| 项目 | 类型 | 可借鉴内容 |
|---|---|---|
| [WEN-JY/academic-research-skills](https://github.com/WEN-JY/academic-research-skills) | 学术写作 Skills | 文献综述、论文排版、Word 流程图、DOCX 格式化、答辩材料生成、学校规则扩展 |
| [Agents365-ai/thesis-reviewer](https://github.com/Agents365-ai/thesis-reviewer) | 学位论文审查 Agent | 盲审前自检、学术型与专业型学位区分、结构化评审意见 |
| [PaperFormatDetection](https://github.com/siyuanzhou/PaperFormatDetect) | Word 格式检测 | 基于 OpenXML 对 DOCX 格式进行检测和部分自动修复 |
| [ChineseResearchLaTeX](https://github.com/huangwb8/ChineseResearchLaTeX) | 中文科研 LaTeX 工具链 | 硕博论文模板、PDF 构建、DOCX 导出、字数统计、自动验收 |
| [LaTeX-Thesis-Writing](https://github.com/zuoliangyu/LaTeX-Thesis-Writing) | 中文学位论文写作环境 | 通用 LaTeX 模板、Agent Skill、章节初始化、编译检查 |
| [ThuThesis](https://github.com/tuna/thuthesis) | 高校论文模板 | 清华大学本科、硕士、博士、博士后模板及版本维护机制 |
| [USTCThesis](https://github.com/ustctug/ustcthesis) | 高校论文模板 | 中国科学技术大学学位论文模板、学校规范适配与版本管理 |
| [UCAS Thesis](https://github.com/mohuangrui/ucasthesis) | 高校论文模板 | 中国科学院大学本科、硕士、博士和博士后论文模板 |
| [NUDT Proposal](https://github.com/TomHeaven/nudtproposal) | 开题报告模板 | 国防科技大学硕博研究生开题报告模板 |
| [zotero-chinese/styles](https://github.com/zotero-chinese/styles) | 中文参考文献样式 | 中文期刊和高校学位论文 CSL 样式 |
| [biblatex-gb7714](https://github.com/hushidong/biblatex-gb7714-2015) | 中文参考文献规范 | GB/T 7714 多版本及高校定制 BibLaTeX 样式 |
| [gzhuMasterDegreeMaterials](https://github.com/green-heart-13/gzhuMasterDegreeMaterials) | 学位流程清单 | 开题、中期、预答辩、查重、外审、答辩和归档材料 |
| [NJUST-PHD-Thesis](https://github.com/StillKeepTry/NJUST-PHD-Thesis) | 博士毕业流程 | 博士开题、系统操作、签字盖章、材料上传与归档 |

---

## 3. 各项目的参考价值

### 3.1 academic-research-skills

该项目已经覆盖多种论文相关任务：

- 文献综述
- 参考文献整理
- 论文排版
- Word 流程图
- Markdown 转 Word
- DOCX 学位论文格式化
- 答辩材料生成
- 研究流程可视化

最值得借鉴的是其“学校专用 Skill”思路：

```text
通用论文能力
+
学校专用规则
+
专业学位专用模板
```

可扩展为：

```text
skills/
├── common/
│   ├── literature-review/
│   ├── thesis-outline/
│   ├── citation-review/
│   ├── experiment-analysis/
│   └── defense-slides/
│
├── universities/
│   ├── ustc/
│   ├── tsinghua/
│   ├── zju/
│   └── custom/
│
└── degree-types/
    ├── academic-master/
    ├── professional-master/
    └── phd/
```

---

### 3.2 thesis-reviewer

该项目适合作为 `BlindReviewAgent` 的参考。

重点检查：

```text
研究问题是否明确
方法与问题是否对应
实验是否支撑结论
创新点是否被夸大
章节之间是否形成递进关系
图表与正文是否一致
摘要、结论、创新点是否一致
是否存在无来源论断
是否存在无法追溯的实验数字
专业硕士是否体现工程实践
博士论文是否体现系统性与创新性
```

建议将审查拆成两类能力。

#### LLM 负责

- 逻辑合理性
- 创新表述
- 章节衔接
- 盲审风险解释
- 工作量与贡献判断

#### 程序负责

- 编号连续性
- 图表引用
- 参考文献匹配
- 字体字号
- 页眉页脚
- 目录层级
- 数值一致性

---

### 3.3 PaperFormatDetection

该项目通过 OpenXMLSDK 读取 DOCX 内部 XML，并与标准模板进行比较。

可检测：

- 字体和字号
- 图表
- 页眉页脚
- Word XML 样式
- 模板格式差异

适合作为 `DocxFormatChecker` 的参考。

推荐工作流：

```text
上传学校官方 DOCX 模板
        ↓
提取 styles.xml / numbering.xml / section properties
        ↓
生成 SchoolFormatProfile
        ↓
解析学生论文 DOCX
        ↓
逐段、逐表、逐节比较
        ↓
生成格式差异报告
```

输出示例：

```json
{
  "rule_id": "USTC-BODY-FONT-001",
  "location": "第3章第2节第4段",
  "expected": {
    "font_cn": "宋体",
    "font_en": "Times New Roman",
    "size": "小四",
    "line_spacing": "1.5"
  },
  "actual": {
    "font_cn": "微软雅黑",
    "font_en": "Calibri",
    "size": "五号",
    "line_spacing": "single"
  },
  "severity": "major",
  "auto_fixable": true
}
```

---

### 3.4 ChineseResearchLaTeX

该项目适合作为论文输出适配层参考。

推荐输出结构：

```text
结构化论文内容
├── 导出 Markdown
├── 导出学校 DOCX
├── 导出学校 LaTeX
├── 编译 PDF
└── 视觉对比验收
```

建议将通用能力和学校规则分离。

#### 通用能力包

- 中文字体
- 标题层级
- 图表公式
- 参考文献
- 封面字段
- 声明页

#### 学校配置包

- 页边距
- 字号
- 封面
- 摘要格式
- 目录格式
- 页眉页脚
- 参考文献差异

---

### 3.5 LaTeX-Thesis-Writing

该项目主要解决：

- 模板初始化
- 章节文件自动创建
- 编译检查
- LaTeX 错误修复
- 图表和公式环境生成
- 写作与排版指令分离

适合作为 GradThesis-CN 的论文写作环境子模块。

---

## 4. 高校论文模板项目

### 4.1 ThuThesis

ThuThesis 覆盖：

- 本科论文
- 硕士论文
- 博士论文
- 博士后报告

可借鉴：

- 论文类型切换
- 元数据集中配置
- 模板版本管理
- CI 编译
- Release 发布
- 用户手册
- 学校规范更新后的同步机制

---

### 4.2 USTCThesis

USTCThesis 说明了一个关键问题：

> 学校论文格式不是永久不变的，规则包必须带版本号和生效日期。

错误设计：

```json
{
  "university": "USTC"
}
```

推荐设计：

```json
{
  "university": "USTC",
  "degree_level": "master",
  "discipline": "engineering",
  "rule_version": "2025-03-31",
  "effective_from": "2025-03-31",
  "source_document": "研究生院学位论文撰写模板",
  "citation_standard": "school_custom"
}
```

---

### 4.3 UCAS Thesis

可借鉴：

- 对 LaTeX 初学者隐藏底层复杂性
- 示例驱动
- 多学位层级支持
- 常见图表问题文档化
- 模板参数化

---

### 4.4 NUDT Proposal

该项目说明：

> 中国研究生流程中的开题报告，也是需要学校规则适配的独立文档类型。

系统应支持以下文档：

```text
proposal             开题报告
midterm              中期报告
pre_defense          预答辩材料
external_review      外审修改说明
defense              答辩材料
final_thesis         最终学位论文
archive              归档材料
```

---

## 5. 中文参考文献项目

### 5.1 zotero-chinese/styles

可作为 `CitationStyleRegistry` 的数据源。

推荐映射关系：

```text
学校
→ 学院
→ 学位类型
→ CSL 文件
→ 示例参考文献
→ 测试结果
```

系统可自动完成：

- 根据学校加载 CSL
- 检查 Zotero 数据字段
- 检查中英文语言字段
- 检查作者数量截断
- 检查引用顺序
- 检查正文引用与文后文献是否对应
- 发现未引用文献
- 发现正文孤立引用

---

### 5.2 biblatex-gb7714

可支持：

- GB/T 7714-1987
- GB/T 7714-2005
- GB/T 7714-2015
- GB/T 7714-2025
- 高校特定学位论文样式

规则选择不能只根据国家标准，还需要优先读取学校当年的正式通知。

推荐：

```python
def select_citation_standard(
    university_rule: str | None,
    submission_date: date
) -> str:
    if university_rule:
        return university_rule

    if submission_date >= date(2026, 7, 1):
        return "GB/T 7714-2025"

    return "GB/T 7714-2015"
```

优先级应为：

```text
学校当年正式规范
>
学院补充通知
>
国家推荐标准
>
默认系统配置
```

---

## 6. 学位流程类项目

### 6.1 gzhuMasterDegreeMaterials

该项目覆盖：

- 开题
- 中期
- 培养档案
- 预答辩
- 查重
- 外审
- 正式答辩
- 论文修改说明
- 学位材料归档

适合转换成 `DegreeLifecycleGraph`：

```text
入学与培养计划
       ↓
课程与学分完成
       ↓
开题申请
       ↓
开题答辩
       ↓
开题材料归档
       ↓
中期考核
       ↓
论文初稿
       ↓
预答辩
       ↓
查重
       ↓
外审 / 盲审
       ↓
评审意见修改
       ↓
正式答辩
       ↓
答辩后修改
       ↓
最终论文提交
       ↓
学位材料归档
```

建议增加跨材料一致性检查：

```text
开题日期 < 中期日期 < 预答辩日期 < 正式答辩日期

答辩申请表日期
=
答辩记录日期
=
答辩决议日期

论文题目在以下文件中必须一致：
- 开题报告
- 学位申请书
- 评阅书
- 答辩决议
- 最终论文封面
```

---

### 6.2 NJUST-PHD-Thesis

该项目记录博士从开题到离校的完整流程。

可抽象为：

```python
class AdministrativeTask:
    task_name: str
    stage: str
    online_system: str | None
    required_files: list[str]
    signatures: list[str]
    copies: int
    upload_format: str | None
    requires_seal: bool
    deadline: str | None
    prerequisite_tasks: list[str]
    status: str
```

这样项目就不仅是论文写作工具，也是研究生毕业项目管理工具。

---

## 7. 当前开源生态的能力分布

### 已有较成熟能力

| 能力 | 代表项目 |
|---|---|
| 高校 LaTeX 模板 | ThuThesis、USTCThesis、UCAS Thesis |
| 中文参考文献样式 | zotero-chinese/styles、biblatex-gb7714 |
| DOCX 格式检测 | PaperFormatDetection |
| 论文 Agent Skills | academic-research-skills |
| 盲审前检查 | thesis-reviewer |
| 开题模板 | NUDT Proposal |
| 毕业流程清单 | gzhuMasterDegreeMaterials、NJUST-PHD-Thesis |
| PDF / DOCX 构建 | ChineseResearchLaTeX |

### 尚未形成统一系统的能力

```text
学校规则自动加载
学硕 / 专硕 / 博士差异
开题到答辩状态管理
论文内容与实验数据追溯
学校 DOCX 模板逆向解析
参考文献版本自动切换
多个学位材料字段一致性
盲审意见与修改闭环
答辩 PPT 与答辩问答生成
最终归档材料清单
```

这正是 GradThesis-CN 的项目空间。

---

## 8. 特殊化后的系统架构

### 8.1 原 ThesisFlow

```text
项目建档
→ 文献分析
→ Baseline 选择
→ 实验规划
→ 章节写作
→ 引用审查
→ 导出
```

### 8.2 GradThesis-CN

```text
学校与学位类型识别
        ↓
加载学校规则包
        ↓
建立培养与毕业时间线
        ↓
开题报告生成与一致性检查
        ↓
中期成果对照
        ↓
大论文目录与工作量映射
        ↓
论文写作与证据追踪
        ↓
学校格式检查
        ↓
学术规范与盲审风险检查
        ↓
预答辩材料生成
        ↓
外审意见解析与修改闭环
        ↓
正式答辩材料生成
        ↓
答辩后修改与最终归档
```

---

## 9. 五个关键特殊化模块

### 9.1 SchoolRulePack：学校规则包

推荐目录：

```text
school_rules/
└── university_code/
    └── 2026/
        ├── metadata.yaml
        ├── thesis_structure.yaml
        ├── docx_styles.yaml
        ├── latex_template/
        ├── citation.csl
        ├── lifecycle.yaml
        ├── required_materials.yaml
        ├── review_rules.yaml
        └── test_cases/
```

`metadata.yaml` 示例：

```yaml
university: 示例大学
school: 计算机学院
degree_level: master
degree_type: academic
year: 2026

sources:
  - title: 研究生学位论文撰写规范
    published_at: 2025-09-01
  - title: 2026届硕士研究生答辩通知
    published_at: 2026-03-10

standards:
  thesis: GB/T 7713.1-2025
  citation: school-custom-2026
```

---

### 9.2 DegreeLifecycleGraph：学位流程状态机

推荐状态：

```text
PROPOSAL_PENDING
PROPOSAL_APPROVED
MIDTERM_PENDING
MIDTERM_APPROVED
THESIS_DRAFTING
PRE_DEFENSE_PENDING
PRE_DEFENSE_REVISION
SIMILARITY_CHECK
EXTERNAL_REVIEW
EXTERNAL_REVIEW_REVISION
DEFENSE_PENDING
DEFENSE_REVISION
FINAL_SUBMISSION
ARCHIVED
```

每次状态变化都应检查前置条件。

---

### 9.3 ThesisComplianceEngine：合规引擎

合规规则分为四层：

```text
国家标准层
学校规范层
学院补充规则层
导师个性要求层
```

推荐优先级：

```text
学校正式规范
>
学院当年正式通知
>
国家推荐标准
>
导师表达偏好
```

导师偏好不能覆盖正式格式要求。

---

### 9.4 BlindReviewAgent：盲审模拟器

风险分类：

| 风险等级 | 示例 |
|---|---|
| 致命风险 | 数据无法追溯、核心实验缺失、论文题目与内容不符 |
| 高风险 | 创新点与实验不对应、两章工作量重复 |
| 中风险 | 相关工作分类不清、消融实验不足 |
| 低风险 | 表达啰嗦、术语不统一 |
| 格式风险 | 图表编号、参考文献、页眉页脚错误 |

输出示例：

```json
{
  "dimension": "experiment_support",
  "risk": "high",
  "location": "第3章3.5节",
  "problem": "正文声称模型具有跨域泛化能力，但仅提供单一数据集结果",
  "required_action": "增加跨域测试，或将结论降级为域内有效",
  "evidence_required": [
    "目标域测试结果",
    "跨域指标变化",
    "失败案例"
  ]
}
```

---

### 9.5 DegreeMaterialAgent：毕业材料 Agent

负责管理：

- 开题报告
- 中期考核表
- 预答辩意见书
- 学位申请书
- 论文修改说明
- 评阅意见回复
- 答辩 PPT
- 答辩记录
- 原创性声明
- 授权声明
- 最终电子版
- 归档清单

核心能力：

```text
提醒缺失材料
检查日期冲突
检查题目不一致
检查姓名、学号、专业不一致
检查文件命名
检查 PDF 是否加密
检查是否缺页
生成打印份数清单
```

---

## 10. 推荐项目组合

| GradThesis-CN 模块 | 主要参考项目 |
|---|---|
| 学校模板适配 | ThuThesis、USTCThesis、UCAS Thesis |
| 通用论文输出 | ChineseResearchLaTeX |
| Agent Skill 组织 | academic-research-skills |
| 盲审风险检查 | thesis-reviewer |
| DOCX 格式检测 | PaperFormatDetection |
| 中文参考文献 | zotero-chinese/styles |
| LaTeX 参考文献 | biblatex-gb7714 |
| 开题文档 | NUDT Proposal |
| 学位流程状态机 | gzhuMasterDegreeMaterials、NJUST-PHD-Thesis |
| 文献与证据 RAG | ThesisFlow 的 PaperQA2 方案 |
| Agent 编排 | LangGraph |

---

## 11. 建议的 MVP

第一版只支持：

- 一所学校
- 计算机或工科硕士
- 学术型硕士与专业型硕士
- DOCX 为主要输出
- Markdown 作为中间格式
- 学校指定的参考文献规范
- 开题、论文、预答辩、盲审修改、答辩五阶段

### MVP 演示流程

```text
上传学校论文规范 DOCX / PDF
        ↓
生成学校规则包
        ↓
上传开题报告、论文初稿、实验结果
        ↓
识别当前阶段
        ↓
检查章节和工作量
        ↓
检查数字、引用和实验依据
        ↓
检查 Word 格式
        ↓
输出盲审风险报告
        ↓
生成预答辩修改清单
        ↓
生成答辩 PPT 大纲
```

---

## 12. 最适合作为论文或项目创新点的方向

推荐创新点：

> 基于学校规则包和学位流程状态机的中国研究生学位论文证据审查 Agent。

该方向可以同时体现：

- Agent 编排
- RAG
- DOCX 解析
- 规则引擎
- 工作流状态机
- 证据追溯
- 多文档一致性检查
- 人在环审核

相比“AI 论文写作助手”，这个定位更具体，也更容易形成项目壁垒。

---

## 13. 推荐实施顺序

```text
选择目标学校
→ 收集学校论文规范与答辩通知
→ 定义 SchoolRulePack
→ 建立 DegreeLifecycleGraph
→ 实现 DOCX 格式检查
→ 接入参考文献样式
→ 接入 BlindReviewAgent
→ 实现跨材料一致性检查
→ 生成预答辩和答辩材料
→ 完成 Web 产品化
```

第一阶段只需要跑通：

> 上传学校规范和论文初稿 → 自动识别学校规则 → 检查格式、引用、实验依据和盲审风险 → 输出修改清单

完成该闭环后，再扩展：

- 开题报告生成
- 中期检查
- 外审意见解析
- 答辩 PPT
- 答辩问答
- 最终归档材料管理
