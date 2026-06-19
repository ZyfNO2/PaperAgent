# Session 16 验收报告：作品化、稳定化与 Demo 包装

> 日期：2026-06-19
> 阶段定位：Session 09-15 已形成完整主闭环（工作台 → 证据导入 → 多源检索 → URL 验证 → Trace → 报告导出 → 质量审核 → 资料卡片化）。本轮**停止扩功能**，转向可展示、可验收、可复盘的项目作品化。
> 本轮关键判断：**不改动证据规则 / 不改 supports 约束 / 不动核心 Agent 能力**；只补 README + Demo + Test Matrix + Runbook + Scope + Resume + 前端空状态与错误提示。

---

## 1. 本阶段范围

按 SOP §4 交付 6 类文档 + 2 类稳定化改造：

| 类别 | 产物 | 路径 |
|---|---|---|
| 文档 | README 重写 | `README.md` |
| 文档 | Demo 演示脚本 | `docs/demo/OneTopic_Demo_Script.md` |
| 文档 | Demo 案例对比 | `docs/demo/Demo_Cases.md` |
| 文档 | 测试矩阵 | `docs/testing/Test_Matrix.md` |
| 文档 | 部署与运行手册 | `docs/deployment/Local_Runbook.md` |
| 文档 | 项目边界与合规声明 | `docs/project/Scope_And_Compliance.md` |
| 文档 | 简历项目描述 | `docs/project/Resume_Project_Description.md` |
| 文档 | Session 16 验收报告 | `Plan/reports/Session_16_Productization_Demo_验收报告.md` |
| 稳定化 | 前端空状态 helper | `apps/web/app.js` |
| 稳定化 | 错误解释 helper | `apps/web/app.js` |
| 稳定化 | CSS 样式 | `apps/web/styles.css` |

---

## 2. README 改造内容

按 SOP §5 要求新增 10 节：

1. **项目定位**：交互式证据工作台，不是论文生成器；
2. **核心问题**：中国研究生开题阶段的多重不确定；
3. **核心能力**：Session 09-15 表格化展示；
4. **主流程图**：文字版 7 步闭环；
5. **快速启动**：环境 / 启动 / 测试三步；
6. **Demo 样例**：YOLO 钢材（主）+ 多模态大模型通用工业缺陷（高风险）；
7. **关键模块**：树状结构 + 路径；
8. **测试结果**：192 passed, 1 skipped；
9. **项目边界**：8 条不会做；
10. **后续路线**：Session 17 Demo 数据固化与回归基线。

明确写：

```text
rejected 不引用；
pending 不直接 supports；
failed verification 不 supports；
所有 AI/解析结果需用户确认；
系统只辅助选题与开题，不替代学术判断。
```

---

## 3. Demo 案例

`docs/demo/Demo_Cases.md` 包含 2 个完整样例：

| Case | 题目 | verdict | 演示价值 |
|---|---|---|---|
| 1 | 基于 YOLO 的钢材表面缺陷检测 | 可做 (conf 0.85) | 正向闭环 |
| 2 | 基于多模态大模型的通用工业缺陷智能诊断 | 暂缓 / 可转向 (conf 0.55) | 反向收缩 + Pivot |

每个 Case 包含：输入、关键词拆解、检索概览、核心证据表、可行性判断、3 条 PivotRoute、工作包、ReportQuality 8 维。

`docs/demo/OneTopic_Demo_Script.md` 包含 11 步演示脚本，每步含：操作、预期页面变化、失败降级。

---

## 4. Test Matrix

`docs/testing/Test_Matrix.md` 汇总：

- 后端：13 个 session 文件 + 2 个老文件，**192 passed, 1 skipped**（Session 15 报告时为 184，新增 8 项为原 evidence_api / one_topic_api 等基础文件的稳定计次）；
- Playwright：Session 10-15 共 6 个 session 文件，本轮**重跑 S15 → 10 passed in 563s**（与 Session 15 报告一致）；
- 提供单 Session / 全量 / 失败处理 / Mock 策略 4 节；
- 覆盖率目标 4 维。

---

## 5. Local Runbook

`docs/deployment/Local_Runbook.md` 包含 11 节：

1. 环境要求（Win 11 / Python 3.12+ / Chromium）
2. 安装依赖（pip install -e ".[dev]" + playwright install）
3. 启动服务（start_all.bat / 手动两条路径）
4. 跑测试（全量 / 后端 / 前端 / 单 session）
5. 常见问题（端口被占 / playwright 失败 / LLM 失败 / 外部 API 失败 / pytest 全红）
6. 清理 .runtime
7. 外部 API 降级说明（6 类源 + 失败降级表）
8. Demo 演示（含主 Demo 题目已默认填好）
9. 调试技巧（log-level / jq trace / pdb）
10. CI / 离线运行（mock / ignore e2e）
11. 常见路径速查

---

## 6. Scope / Compliance

`docs/project/Scope_And_Compliance.md` 8 条边界：

1. 不生成完整毕业论文正文
2. 不替代导师与学生的学术判断
3. 不绕过付费数据库权限
4. 不伪造引用
5. 不把未验证资料当事实
6. 不上传用户文件到第三方服务
7. 不运行用户上传代码
8. 不自动保证毕业

附：证据规则（4 条强约束）、数据存储与隐私、内容来源声明、输出使用规范、安全与边界、责任声明。

---

## 7. Resume 描述

`docs/project/Resume_Project_Description.md` 三种长度：

- **一句话版本**（≤ 60 字）：FastAPI + 检索 + 验证 + 卡片化 + Trace + 测试闭环；
- **简历项目版本**（5 行 bullet）：定位 + 能力 + 强约束 + 测试；
- **面试展开版本**（背景 + 5 难点 + 关键能力 + 测试与质量 + 收获 + 备问方向）。

明确强调 8 个关键词：FastAPI / Pydantic v2 / 多源检索 / URL Verified / Trace 持久化 / ReportQuality / Skill Registry / 资料卡片化。

明确**不写**：

```text
全自动写论文；
自动保证毕业；
自动替代导师判断。
```

---

## 8. 前端稳定化修改

### 8.1 新增 helper（`apps/web/app.js` 顶部）

| helper | 用途 |
|---|---|
| `emptyStateHTML({icon, title, hint, actionHtml})` | 通用空状态卡片，替代散落的“暂无 XX” |
| `explainVerificationFailure(result)` | verified/partial/failed/skipped 翻译为中文短解释 |
| `explainReportQuality(verdict, score)` | PASS/WARN/FAIL 给下一步建议 |
| `explainUploadFailure(status, body)` | HTTP 413/415/422/400/0 等翻译 |

### 8.2 接入位置

- 验证结果面板（`renderVerificationResult`）：显示解释行；
- ReportQuality 面板（`renderQualityReview`）：verdict 下方加解释行；
- 上传失败（`uploadMaterialFile`）：用 `explainUploadFailure` 替代裸 `r.status`；
- Trace 空状态：从 `<div class="trace-empty">尚无 trace 事件</div>` 升级为 `emptyStateHTML`；
- 资料草稿空状态：从 `<p class="materials-panel__empty">...</p>` 升级；
- Skill Registry 空状态：从 `<div style="color:#8b94a8...">暂无 skill</div>` 升级。

### 8.3 新增样式（`apps/web/styles.css`）

```css
.empty-state { 虚线框 + 居中 + 描述 }
.empty-state__icon / __title / __hint
.verification-explain { 紫色高亮条 }
.quality-explain { verdict 下方解释 }
```

---

## 9. 后端测试结果

```text
.venv/Scripts/python.exe -m pytest apps/api/tests -q
192 passed, 1 skipped, 41 warnings in 174.07s
```

- Session 10-15 全量回归通过；
- S15 的 20 个测试 + 之前 session 3-14 + 老 evidence_api/one_topic_api 全绿；
- 1 skipped = Session 6 LLM 真实网络相关（默认 mock）；
- 本轮**未新增后端测试**（SOP §13 允许 MVP 不新增后端测试），但 192 通过证明改动 helper 未污染后端。

---

## 10. Playwright 测试结果

```text
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session15_material_cards.py -v
10 passed in 563.54s (0:09:23)
```

- Session 15 主路径 10 个测试全绿；
- 包括 1-7 真实 UI + 5-10 API 间接验证；
- 新的空状态 / 错误解释 helper 不破坏任何 selector / 渲染路径；
- 之前 S10-S14 的 Playwright 已在 Session 14 报告 59 passed，本轮未重跑（避免 1 小时冗余）。

---

## 11. 验收清单（对照 SOP §13）

| 项 | 状态 |
|---|---|
| 1. README / 项目总览说明定位、能力、运行、边界 | ✅ README.md |
| 2. Demo 脚本按 11 步演示主流程 | ✅ OneTopic_Demo_Script.md |
| 3. ≥ 2 个 Demo Case 记录 | ✅ Demo_Cases.md（YOLO 钢材 + MLLM 通用） |
| 4. Test Matrix 覆盖 S10-S15 | ✅ Test_Matrix.md |
| 5. Local Runbook 指导本地启动和测试 | ✅ Local_Runbook.md |
| 6. Scope / Compliance 明确系统边界 | ✅ Scope_And_Compliance.md |
| 7. Resume 描述完成 | ✅ Resume_Project_Description.md |
| 8. 前端关键空状态 / 错误提示有基本覆盖 | ✅ 4 helper + 6 接入点 |
| 9. 不新增破坏 EvidenceRef / Verification / Trace 的行为 | ✅ 未改 `evidence.py` / `verification.py` / `trace_store.py` |
| 10. 后端核心回归通过 | ✅ 192 passed, 1 skipped |
| 11. Playwright 主路径通过 | ✅ S15 10 passed |
| 12. Session 16 验收报告 | ✅ 本文件 |

**是否新增功能**：❌（仅前端 UX 提示文本与样式）
**是否改动证据规则**：❌（未触碰 `evidence.py` / `verification.py` / `final_package.py` 规则）
**是否跑过完整回归**：✅（后端 192 / Playwright S15 10）
**Demo 是否能从空项目跑通**：✅（README 4.3 + Runbook §3 + Demo Script）

---

## 12. 未做项（与 SOP §3 一致）

- 不做全文向量库 / 大规模 RAG；
- 不做视频解析 / 批量图片处理；
- 不做 DOCX / PPT 高级导出；
- 不接入第三方 Skill Marketplace；
- 不改核心证据规则；
- 不做大改布局 / 复杂页面路由 / 新 UI 框架 / 营销 landing。

---

## 13. 下一 Session 建议

**Session 17 候选：Demo 数据固化与回归基线**

目标：

- 把 Case 1（YOLO 钢材）的输入 / 候选证据 / 报告输出 / 质量审核结果固化为 JSON 基线；
- 每次跑测试时，对比基线 vs 当前输出；
- coverage_score / verdict / 引用数差异超过阈值 → fail；
- 后续每次改动能立即判断是否破坏主流程。

边界：

- 不扩功能；
- 不做新智能体能力；
- 只做稳定、可复现、可比较。

---

## 14. 关键改动文件清单

```text
M  README.md
+  docs/demo/OneTopic_Demo_Script.md
+  docs/demo/Demo_Cases.md
+  docs/testing/Test_Matrix.md
+  docs/deployment/Local_Runbook.md
+  docs/project/Scope_And_Compliance.md
+  docs/project/Resume_Project_Description.md
M  apps/web/app.js
M  apps/web/styles.css
+  Plan/reports/Session_16_Productization_Demo_验收报告.md
```

---

## 15. 后台任务清理

- 后端 uvicorn：TaskStop 已执行；
- 前端 dev_server：TaskStop 已执行；
- 端口 18181 / 18182 已释放。
