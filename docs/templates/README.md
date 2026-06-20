# 开题报告模板（Opening Report Templates）

> Session 19 新增。提供 3 种轻量 Markdown 开题报告模板，供 FinalPackage 按模板组织章节。

---

## 模板清单

| template_key | 文件 | 适用场景 | 必备章节 |
|---|---|---|---|
| `default` | `opening_report_default.md` | 通用（本科/硕士/博士） | 背景 / 现状 / 目标 / 技术路线 / 实验 / 可行性 / 创新 / 进度 / 风险 / 引用 |
| `engineering` | `opening_report_engineering.md` | 专业硕士 / 工程类 | 背景 / 需求 / 数据 / 架构 / 算法 / 实现 / 测试 / 风险 / 进度 / 证据 |
| `cv_ai` | `opening_report_cv_ai.md` | CV / NLP / 多模态 | 背景 / 相关工作 / 数据集 / Baseline / 方法 / 实验 / 消融 / 创新 / 风险 / 引用 |

---

## 模板元数据

每个模板文件头部用 YAML frontmatter 声明：

```yaml
template_key: cv_ai
name: 计算机视觉 / AI 开题报告模板
version: 0.1.0
applies_to: CV / NLP / 多模态 / AI 方向课题
required_sections: [...]
evidence_required: true
placeholders: [topic, background, related_work, datasets, baselines, work_packages, risks, citations]
```

---

## 占位符

所有模板共用 8 个占位符：

| 占位符 | 含义 |
|---|---|
| `{{topic}}` | 推荐题目 |
| `{{background}}` | 研究背景 / 项目背景 |
| `{{related_work}}` | 国内外研究现状 / 相关工作 |
| `{{datasets}}` | 数据集清单 |
| `{{baselines}}` | Baseline 清单 |
| `{{work_packages}}` | 工作包设计 |
| `{{risks}}` | 风险预案 |
| `{{citations}}` | 参考文献与证据清单 |

---

## FinalPackage 联动

```
POST /api/v1/one-topic/{project_id}/final-package/build
body: { ..., template_key: "cv_ai" }
```

- `template_key` 缺省或未知 → 回退 `default`，不报错。
- 模板只能重排章节标题与顺序；**不能绕过 citation**。
- 模板**不能引用 rejected / pending+unverified / failed 证据**。
- 模板必须保留 `evidence_id` / `verification` / `skill` / `source` 字段。

---

## 前端选择

FinalPackage 面板提供模板选择控件：

```
模板：[通用 default] [工程实现 engineering] [CV/AI cv_ai]
```

- 展示：模板说明、适用场景、必备证据项、缺失项提示。
- CV/AI 模板缺 dataset/repo 时提示"先补数据集和 baseline"。

---

## 测试

- 后端：`apps/api/tests/test_session19_report_templates.py`
- e2e：`apps/web/e2e/test_one_topic_session19_report_templates.py`

---

## 不做的事

- 不做 DOCX / PPT 精排（留后续独立阶段）。
- 不做学校模板像素级适配。
- 不生成完整毕业论文正文。
- 不绕过证据引用规则。
