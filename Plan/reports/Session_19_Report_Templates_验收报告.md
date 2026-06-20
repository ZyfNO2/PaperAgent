# Session 19 — 轻量学校模板与开题报告适配 — 验收报告

**日期**: 2026-06-20
**分支**: master
**前置依赖**: Session 18（错误处理 / 空状态 / 可观测性）
**后置交付**: Session 20（发布候选 / CHANGELOG / Roadmap）

---

## 1. 目标

> "你只有一个开题报告, 但每个学校模板不一样 — 我们加 3 个轻量模板 (default / engineering / cv_ai), 让用户选一个就出对应口味的开题报告。"

— 来源: `PaperAgent_Session19_...SOP.md`

### 1.1 范围

| 子任务 | 交付 |
| --- | --- |
| 模板系统 | 3 个轻量模板文件 (YAML frontmatter + body) |
| 模板服务 | `apps/api/app/services/report_templates.py` |
| API | `GET /api/v1/one-topic/report/templates` |
| Schema | `template_key` + `template_hints` on `FinalPackageBuildOptions` / `FinalPackageSummary` / `FinalPackage` |
| 前端 | 模板选择器 (`#report-template`) + 模板信息区 (`#report-template-info`) |
| E2E | Playwright 5 用例 (覆盖 default / engineering / cv_ai / 切换回滚) |
| 文档 | `docs/templates/README.md` |

### 1.2 不在范围

- 学校完整模板解析 (Markdown / Word 段落排版)
- 模板可视化编辑 (UI Editor)
- 模板版本管理 (rollback / diff)
- 模板导入 / 导出 / 分享

---

## 2. 关键交付物

### 2.1 模板文件 (`docs/templates/`)

| 文件 | 适用场景 | 章节顺序特征 |
| --- | --- | --- |
| `opening_report_default.md` | 通用本科 / 硕士 | 背景 → 现状 → 工作包 → 风险 → 引用 → 待补 → 决策 |
| `opening_report_engineering.md` | 专业硕士 / 工程类课题 | 工程链路 + 技术指标 + 工程验证 |
| `opening_report_cv_ai.md` | CV/NLP/多模态 | 数据 → 评测 → 训练 → 创新 → 引用 |

每个模板 frontmatter 含 `template_key / name / version / applies_to / required_sections / placeholders / evidence_required / body`。

### 2.2 后端服务 `report_templates.py`

| 函数 | 用途 |
| --- | --- |
| `list_template_keys()` | 列出全部 key |
| `normalize_template_key(k)` | 未知回退 default (不报错) |
| `load_template(k)` | 加载 frontmatter + body |
| `list_templates()` | 全部元数据 (供前端) |
| `check_template_readiness(k, paper_count, dataset_count, baseline_count)` | 缺失证据提示 |
| `reorder_sections(k, sections)` | 章节顺序 (citations / todo / decision_log 钉末尾) |
| `template_header_line(k)` | Markdown 抬头 (含 `template=default` 标注) |

### 2.3 Schema (`apps/api/app/schemas.py`)

```python
class FinalPackageBuildOptions(BaseModel):
    template_key: Literal["default", "engineering", "cv_ai"] = "default"

class FinalPackageSummary(BaseModel):
    template_key: str = "default"
    template_hints: list[str] = []

class FinalPackage(FinalPackageSummary):
    template_key: str = "default"
    template_hints: list[str] = []
```

### 2.4 API

`GET /api/v1/one-topic/report/templates` 返回:
```json
{
  "templates": [
    {"template_key": "default", "name": "通用开题报告模板", "version": "0.1.0", ...},
    {"template_key": "engineering", ...},
    {"template_key": "cv_ai", ...}
  ],
  "default_key": "default"
}
```

### 2.5 前端 (`apps/web/`)

- `#report-template` select: 3 选项 (default / engineering / cv_ai)
- `#report-template-info` div: 显示 `📄 模板: <name> (<key>)` + 缺失证据提示
- `_onTemplateSelectChange()`: 用户手动改过后, 不再被 `renderReportSummary` 自动覆盖

---

## 3. 测试结果

### 3.1 后端单元 / 集成 (`apps/api/tests/test_session19_report_templates.py`)

| # | 测试 | 结果 |
| --- | --- | --- |
| 01 | load default template | PASS |
| 02 | load engineering template | PASS |
| 03 | load cv_ai template | PASS |
| 04 | unknown template_key → normalize fallback | PASS |
| 05 | missing file → returns minimal template | PASS |
| 06 | reorder_sections (default) citations last | PASS |
| 07 | reorder_sections (cv_ai) different order | PASS |
| 08 | GET /report/templates endpoint | PASS |
| 09 | FinalPackage build (default) | PASS |
| 10 | FinalPackage build (cv_ai) | PASS |
| 11 | FinalPackage unknown → fallback default | PASS |
| 12 | FinalPackage summary 透传 template_key | PASS |
| 13 | cv_ai hints when missing dataset/baseline | PASS |
| 14 | engineering hints when missing dataset | PASS |
| 15 | default → no hints | PASS |
| 16 | YAML frontmatter parsing | PASS |
| 17 | build endpoint with template_key | PASS |

**后端 17/17 ✅**

### 3.2 前端 e2e (`apps/web/e2e/test_one_topic_session19_templates.py`)

| # | 测试 | 结果 |
| --- | --- | --- |
| 01 | 模板选择器加载 3 模板 + 默认 default | PASS |
| 02 | 默认模板 build 后 info 显示 default | PASS |
| 03 | cv_ai 模板 build 后 info 显示 cv_ai + Markdown 含标注 | PASS |
| 04 | engineering 模板 build 后 info 显示 engineering | PASS |
| 05 | cv_ai 切回 default 重新 build, info 同步回 default | PASS |

**前端 5/5 ✅**

### 3.3 S19 总计

**22 用例全绿 (17 后端 + 5 前端)**, pytest 总数较 Session 18 增加 22 条。

---

## 4. 修复

### 4.1 E2E `test_05_switch_back_to_default` — `_select_template` 改用显式 dispatch change

**症状**: Playwright `select.select_option("default")` 触发 change 事件后, 紧接着的 `rebuild` 点击读取 `templateSelect.value` 仍为旧值, POST body 仍带 `template_key: "cv_ai"`, 导致断言失败。

**修复**:
```js
// 原: select.select_option(template_key)
// 现: 显式 dispatch change
sel.value = key;
sel.dispatchEvent(new Event('change', { bubbles: true }));
```

`_build_and_wait` 也升级为支持 `expected_template` 参数, 等待模板信息区出现目标 key 后再返回。

---

## 5. 数据流

```
用户选择模板 → _onTemplateSelectChange (dataset.userChanged=1)
   ↓
点击 生成/重建 → buildReport()
   ↓
fetch POST /api/v1/one-topic/{pid}/final-package/build
       body: { template_key: <select.value> }
   ↓
fp_service.build_final_package(pid, options):
   1. normalize_template_key(options.template_key)
   2. check_template_readiness(...) → hints[]
   3. tmpl_service.reorder_sections(...)
   4. _render_markdown(template_key=...)  ← 抬头加 template=default
   ↓
pkg.template_key / pkg.template_hints → 响应
   ↓
renderReportSummary(pkg):
   - templateInfo.innerHTML = `<模板名> (<key>)` + hints list
   - 若 !userChanged → 同步 select.value = pkg.template_key
   ↓
showReportPreview(pkg.proposal_markdown)
```

---

## 6. 偏离与遗留

| 项 | 状态 | 备注 |
| --- | --- | --- |
| 模板可视化编辑 | 未做 | 范围外 |
| 学校完整模板 (含 Word 段落样式) | 未做 | 范围外 |
| 模板版本管理 | 未做 | 当前版本号在 frontmatter, 但无 UI |
| 模板导入 / 导出 / 分享 | 未做 | 当前仅内置 3 个 |
| cv_ai 缺 dataset/baseline 时仍可 build | 是 | 走 hints 提示, 不强制拦截 |

---

## 7. 结论

✅ **S19 完成** — 22 用例全绿 (17 后端 + 5 e2e)
✅ 3 模板已落到 `docs/templates/`, 含 frontmatter + body
✅ 模板 key 透传 schema → API → service → 前端 → DOM, 全链路贯通
✅ 用户切换不会被响应自动覆盖 (dataset.userChanged 机制)
✅ 缺失证据以 hints 提示, 不阻塞 build (与 MVP 兼容)

下一步: Session 20 — 发布候选 (CHANGELOG / VERSION / Roadmap / Known Limitations / Release Checklist / Architecture Overview)。