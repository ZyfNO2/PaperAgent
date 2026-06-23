# PaperAgent Session 19 SOP：轻量学校模板与开题报告 Markdown 适配

> 日期：2026-06-19  
> 阶段定位：在 Demo baseline 和错误可诊断性之后，提供轻量开题报告模板适配。  
> 本轮目标：提供 2-3 种 Markdown 开题报告模板，让 FinalPackage 可按模板组织章节，但不做 DOCX / PPT 高级排版。

---

## 1. 低风险判断

Session 19 属于低风险，可与 Session 18-20 连续实施，前提：

```text
不改 EvidenceRef supports 规则；
不改 Verification 硬约束；
模板只影响 Markdown 章节组织；
S17 baseline 必须继续通过。
```

---

## 2. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不做 Word 精排 | 复杂度高，留后续独立阶段 |
| 不做学校模板像素级适配 | 当前只做 Markdown 结构 |
| 不生成完整毕业论文正文 | 仍聚焦开题报告 |
| 不新增论文写作 Agent | 避免偏离证据工作台 |
| 不绕过证据引用规则 | 模板不能改变 supports |

---

## 3. 核心交付

新增模板目录：

```text
docs/templates/
├── opening_report_default.md
├── opening_report_engineering.md
├── opening_report_cv_ai.md
└── README.md
```

可选代码：

```text
apps/api/app/services/report_templates.py
apps/api/tests/test_session19_report_templates.py
apps/web/e2e/test_one_topic_session19_report_templates.py
```

如果实现最小版：

```text
只新增模板文档 + FinalPackage 轻量 template_key 参数；
不做复杂模板引擎。
```

---

## 4. 模板类型

### 4.1 default

通用开题模板：

```text
1. 研究背景与意义
2. 国内外研究现状
3. 研究目标与研究内容
4. 技术路线
5. 实验方案与评价指标
6. 可行性分析
7. 创新点
8. 进度安排
9. 风险预案
10. 参考文献与证据清单
```

### 4.2 engineering

工程实现型模板：

```text
1. 项目背景与应用价值
2. 需求分析与问题定义
3. 数据来源与系统输入输出
4. 系统架构与技术路线
5. 核心算法 / 模型设计
6. 工程实现计划
7. 测试与评价指标
8. 风险与降级方案
9. 进度计划
10. 证据来源
```

### 4.3 cv_ai

计算机视觉 / AI 模板：

```text
1. 研究背景
2. 相关工作分类
3. 数据集与评价指标
4. Baseline 与复现计划
5. 方法设计
6. 实验设计
7. 消融与误差分析计划
8. 创新点与预期贡献
9. 风险预案
10. 引用清单
```

---

## 5. 模板元数据

每个模板头部建议包含：

```yaml
template_key: cv_ai
name: 计算机视觉 / AI 开题报告模板
version: 0.1.0
required_sections:
  - 研究背景
  - 相关工作
  - 数据集与评价指标
  - Baseline
  - 实验方案
evidence_required: true
```

模板中的占位符：

```text
{{topic}}
{{background}}
{{related_work}}
{{datasets}}
{{baselines}}
{{work_packages}}
{{risks}}
{{citations}}
```

---

## 6. FinalPackage 联动

新增 `template_key`：

```text
default
engineering
cv_ai
```

API 可选：

```text
POST /api/v1/one-topic/{project_id}/final-package?template_key=cv_ai
GET  /api/v1/one-topic/report/templates
```

规则：

```text
模板只能重排章节和标题；
模板不能绕过 citation；
模板不能引用 rejected / pending / failed 证据；
模板必须保留 evidence_id / verification / skill / source。
```

---

## 7. 前端联动

FinalPackage 面板新增模板选择：

```text
模板：
[通用] [工程实现] [CV/AI]
```

展示：

```text
模板说明；
适用场景；
必备证据项；
缺失项提示；
```

空状态：

```text
如果用户选择 CV/AI 模板但没有 dataset/repo，应提示先补数据集和 baseline。
```

---

## 8. 测试要求

后端新增：

```text
apps/api/tests/test_session19_report_templates.py
```

覆盖：

```text
1. 三个模板文件存在；
2. 模板 metadata 可解析；
3. required_sections 非空；
4. FinalPackage default 模板不回退；
5. cv_ai 模板包含 dataset / baseline / experiment；
6. engineering 模板包含 system / implementation / testing；
7. 模板输出保留 citation table；
8. rejected / pending / failed 不进 supports；
9. S17 baseline 继续通过。
```

Playwright 新增：

```text
apps/web/e2e/test_one_topic_session19_report_templates.py
```

覆盖：

```text
1. 模板选择控件可见；
2. 选择 CV/AI 后生成报告；
3. 报告含数据集 / baseline / 实验章节；
4. 切回 default 不报错；
5. 缺证据时出现提示。
```

---

## 9. 验收标准

通过条件：

```text
1. docs/templates/ 下至少 3 个模板；
2. 模板 metadata 清晰；
3. FinalPackage 可选择模板；
4. 模板不改变证据规则；
5. citation table 保留；
6. S17 baseline 通过；
7. 后端模板测试通过；
8. Playwright 模板测试通过或报告说明延期；
9. 新增 Session19 验收报告。
```

最低 MVP：

```text
三个 Markdown 模板；
模板 README；
FinalPackage template_key；
后端测试；
S17 baseline 通过。
```

---

## 10. 完工报告要求

完成后新增：

```text
Plan/reports/Session_19_Report_Templates_验收报告.md
```

报告必须写：

```text
模板清单；
模板字段；
FinalPackage 联动；
前端模板选择；
测试结果；
是否改证据规则；
S17 baseline 是否通过。
```

---

## 11. 下一 Session

Session 20：

```text
维护版收束与 v0.1 Release Candidate
```

