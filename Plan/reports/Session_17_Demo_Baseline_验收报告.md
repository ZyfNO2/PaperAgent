# Session 17 验收报告：Demo 数据固化与回归基线

> 日期：2026-06-19
> 阶段定位：Session 16 已完成作品化、Demo 文档、测试矩阵与边界声明。本轮**不扩功能**，专门把 Demo Case 固化为可重复测试的回归基线。
> 本轮关键判断：**不改 evidence / verification / trace 核心规则**；只固化 Demo + 加 15 项后端合同断言 + 10 项 Playwright 主路径断言。

---

## 1. 本阶段范围

按 SOP §5 交付：

```text
docs/demo/baselines/
├── README.md
├── yolo_steel_defect_input.json
├── yolo_steel_defect_mock_sources.json
├── yolo_steel_defect_expected.json
├── yolo_steel_defect_expected_report.md
├── risky_mllm_industrial_input.json
├── risky_mllm_industrial_mock_sources.json
├── risky_mllm_industrial_expected.json
└── risky_mllm_industrial_expected_report.md

apps/api/tests/test_session17_demo_baseline.py    # 15 项后端合同断言
apps/web/e2e/test_one_topic_session17_demo_baseline.py  # 10 项 Playwright 主路径
Plan/reports/Session_17_Demo_Baseline_验收报告.md
```

文档更新：

- `docs/demo/Demo_Cases.md` — 加 S17 基线入口与运行命令；
- `docs/testing/Test_Matrix.md` — 加 S17 后端 + Playwright 行；
- `docs/demo/OneTopic_Demo_Script.md` — 加 "运行基线回归" 步骤；
- `README.md` — 测试结果更新到 S17，后续路线更新到 S18 候选。

---

## 2. 新增 baseline 文件清单

| 文件 | 用途 | 字段数 |
|---|---|---|
| `yolo_steel_defect_input.json` | YOLO Case 输入 + 关键词合同 | 11 |
| `yolo_steel_defect_mock_sources.json` | YOLO Case mock 候选 (5 papers / 2 datasets / 2 repos / 1 material) | 6 类 |
| `yolo_steel_defect_expected.json` | YOLO Case 合同 (feasibility / pool / pkg / quality / trace / supports) | 7 块 |
| `yolo_steel_defect_expected_report.md` | YOLO Case 报告骨架 (7 章节) | 7 段 |
| `risky_mllm_industrial_input.json` | MLLM Case 输入 + 风险词合同 | 11 |
| `risky_mllm_industrial_mock_sources.json` | MLLM Case mock 候选 (2 papers / 1 dataset / 1 repo) | 5 类 |
| `risky_mllm_industrial_expected.json` | MLLM Case 合同 (verdict_forbidden / missing_evidence / pivot_min) | 7 块 |
| `risky_mllm_industrial_expected_report.md` | MLLM Case 报告骨架 (7 章节, 强调缺失证据) | 7 段 |
| `baselines/README.md` | 基线维护规则 + 版本字段 + mock 策略 | 8 节 |

---

## 3. YOLO Case 合同（结构化）

### 3.1 关键词合同

```json
{
  "method_keywords_any": ["YOLO", "YOLOv5", "YOLOv8"],
  "task_keywords_any": ["缺陷检测", "目标检测"],
  "object_keywords_any": ["钢材表面", "钢材", "带钢", "金属表面"],
  "risk_terms_max": 3,
  "query_keywords_min": 2
}
```

### 3.2 证据池硬约束

```text
min_papers: 3
min_datasets: 1
min_repos: 1
min_verified_or_partial: 3
must_have_rejected_candidate: true
must_have_pending_unverified_candidate: true
```

### 3.3 Feasibility 范围

```text
verdict_allowed: ["可做", "GO", "PASS", "有条件通过", "需修改"]
confidence_min: 0.60
```

### 3.4 FinalPackage 必含

```text
7 章节: 研究背景 / 国内外研究现状 / 研究内容 / 技术路线 / 实验方案 / 风险预案 / 引用清单
citation_count: [3, 30]
citation_required_fields: evidence_id, verification_status, skill_sources, source_mode
```

### 3.5 ReportQuality 范围

```text
verdict_allowed: ["通过", "有条件通过", "需修改", "PASS", "WARN"]
min_score: 40
must_have_verdict: true
must_have_revision_checklist: true
```

### 3.6 Trace 必备

```text
required: [verify_project, final_package_build]
optional: [retrieval_*, verify_evidence, material_*, draft_card_*]
```

### 3.7 Supports 硬规则

```text
forbidden:
  - review_status=rejected
  - review_status=pending AND verification_status=unverified
  - verification_status=failed
```

---

## 4. MLLM Risky Case 合同（高风险反向案例）

### 4.1 关键词合同

```json
{
  "method_keywords_any": ["多模态大模型", "MLLM", "Vision-Language", "多模态"],
  "risk_terms_any": ["通用", "智能", "高精度", "实时", "跨场景"],
  "risk_terms_min": 2,
  "query_keywords_min": 2
}
```

### 4.2 Feasibility 反向硬约束

```text
verdict_allowed: ["暂缓", "可转向", "PARK", "PIVOT", "WARN", "需修改", "不建议"]
verdict_forbidden: ["可做", "GO", "PASS", "通过"]
confidence_max: 0.70
must_have_missing_evidence_any: 公开数据集 / 可复现 baseline / 统一基准 / 推理资源 / ...
min_pivot_routes: 2
```

### 4.3 must_not_have（防作弊）

```text
无证据支持但 verdict=通过
没有 dataset/repo 仍生成 supports
未验证资料提升关键维度
```

---

## 5. Mock source 策略

| 源 | mock 方式 | 真实调用? |
|---|---|---|
| arXiv | `apps/api/tests/conftest.py` `_fast_arxiv` 全局替换 | ❌ |
| OpenAlex | 测试内 inline 候选 | ❌ |
| GitHub | 测试内 inline 候选 | ❌ |
| HuggingFace | 测试内 inline 候选 | ❌ |
| LLM | 默认 mock；只走 heuristic | ❌ |
| 材料解析 | 真实 PDF/图片走 `.runtime/materials/` 测试目录 | ✅（隔离目录） |

test_13 显式断言：conftest 已 mock arXiv，调用结果必须来自 fixture 标题，不会有真实网络。

---

## 6. Baseline 比较规则

### 6.1 硬断言（必 100% 通过）

- `rejected` 不得 `supports`（test_06）；
- `pending + unverified` 不得 `supports`；
- `failed verification` 不得 `supports`；
- FinalPackage 7 章节全在（test_07）；
- Citation 含 4 必备字段（test_07）；
- ReportQuality verdict 在 allowed 范围 + 有 revision_checklist（test_08）；
- Trace 含 required actions（test_09）；
- MLLM Case 不得直接 PASS（test_11）；
- MLLM Case 必有 missing_evidence 或 pivot_routes（test_12）。

### 6.2 软断言（区间内即可）

- `coverage_score` 落在 `[low, high]`（仅 feasibility.confidence_min/max）；
- 引用数 `[3, 30]`；
- ReportQuality `score >= 40`；
- 章节标题存在即可，不比较正文逐字（test_14）。

---

## 7. 后端测试结果

```text
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py -v
15 passed in 85.09s
```

覆盖（按 SOP §8 14 项 + fixture 检查 1 项）：

1. ✅ baseline fixture 可解析
2. ✅ expected_report.md 章节齐全
3. ✅ YOLO 关键词合同
4. ✅ YOLO 导入 mock 候选 (≥ 3 papers / 1 dataset / 1 repo)
5. ✅ YOLO rejected + pending 可见
6. ✅ YOLO auto_verify 状态
7. ✅ YOLO supports 无禁止条件
8. ✅ YOLO FinalPackage 7 章节 + 引用字段
9. ✅ YOLO ReportQuality verdict 范围
10. ✅ YOLO Trace 关键 action
11. ✅ MLLM 关键词合同 (含 risk_terms ≥ 2)
12. ✅ MLLM 不得直接 verdict=可做
13. ✅ MLLM 必有 missing_evidence 或 pivot_routes
14. ✅ 拒绝外部 API 真实调用
15. ✅ expected_report.md 章节比对

### 全量后端回归

```text
.venv/Scripts/python.exe -m pytest apps/api/tests -q
207 passed, 1 skipped, 41 warnings in 230.62s
```

S17 加 15 项，总数从 192 → 207。

---

## 8. Playwright 测试结果

```text
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session17_demo_baseline.py -v
10 passed in 415.30s (0:06:55)
```

覆盖（按 SOP §9 10 项）：

1. ✅ YOLO 题目输入 + analyze 触发
2. ✅ project_id 在 ev-pid 头部可见
3. ✅ 4 关键面板 selector 稳定 (evidence-trace / retrieval / quality / materials)
4. ✅ Trace empty-state 友好 (Session 16 稳定化)
5. ✅ Quality 面板存在
6. ✅ Materials 3 入口按钮
7. ✅ FinalPackage 生成 + 7 章节
8. ✅ ReportQuality 8 维评分可见
9. ✅ Trace 经 API 走完整流程
10. ✅ 高风险 MLLM Case UI 主路径

---

## 9. 验收清单（对照 SOP §12）

| 项 | 状态 |
|---|---|
| 1. docs/demo/baselines/ 目录存在 | ✅ 8 文件 |
| 2. YOLO Case 三件套完成 | ✅ |
| 3. MLLM Risky Case 三件套完成 | ✅ |
| 4. expected_report.md 含章节 + 占位符 | ✅ |
| 5. 后端 S17 baseline 测试通过 | ✅ 15 passed |
| 6. Playwright S17 主路径通过 | ✅ 10 passed |
| 7. Test_Matrix 加 S17 | ✅ |
| 8. README / Demo 文档说明基线运行 | ✅ |
| 9. 基线比较不依赖真实外部 API | ✅ mock + conftest 双重保险 |
| 10. 基线比较不要求自然语言逐字 | ✅ 仅比章节标题 + 必含字段 |
| 11. rejected/pending/failed 不进 supports 断言 | ✅ test_06 |
| 12. Session 17 验收报告 | ✅ 本文件 |

**是否依赖真实外部 API**：❌（conftest mock arXiv + 手动 inline 候选）
**是否比较 Markdown 全文**：❌（仅比章节标题 + 必含字段）
**是否改变证据规则**：❌（未改 `evidence.py` / `verification.py` / `trace_store.py` 规则）
**是否覆盖 supports 硬规则**：✅（test_06 显式断言 rejected/pending/failed 不进 supports）

---

## 10. 未做项（与 SOP §3 一致）

- 不新增业务功能；
- 不比较 Markdown 全文逐字；
- 不依赖真实外部 API；
- 不要求 LLM 输出完全一致；
- 不引入大文件 fixture；
- 不做视频 / 图片 / OCR 基线；
- 不修改 EvidenceRef / Verification 硬规则。

---

## 11. 下一 Session 建议

**Session 18 候选：错误处理、空状态与可观测性整理**

进入条件：

```text
S17 已有稳定 Demo baseline；
后续整理错误码、空状态和 health endpoint 时, 可用 baseline 判断是否破坏主流程。
```

目标：

- 统一 HTTP 错误码（4xx / 5xx + 错误码常量）；
- 增加 `/health` 与 `/health/detailed` 本地可观测端点；
- 整理前端空状态文案（基于 Session 16 已有 4 helper 扩展）；
- 增加最小结构化日志（request_id / project_id / action）。

边界：

```text
不引入复杂监控平台；
不扩展业务能力；
只提高本地 MVP 的可诊断性。
```

---

## 12. 关键改动文件清单

```text
M  README.md
M  docs/demo/Demo_Cases.md
M  docs/demo/OneTopic_Demo_Script.md
M  docs/testing/Test_Matrix.md
+  docs/demo/baselines/README.md
+  docs/demo/baselines/yolo_steel_defect_input.json
+  docs/demo/baselines/yolo_steel_defect_mock_sources.json
+  docs/demo/baselines/yolo_steel_defect_expected.json
+  docs/demo/baselines/yolo_steel_defect_expected_report.md
+  docs/demo/baselines/risky_mllm_industrial_input.json
+  docs/demo/baselines/risky_mllm_industrial_mock_sources.json
+  docs/demo/baselines/risky_mllm_industrial_expected.json
+  docs/demo/baselines/risky_mllm_industrial_expected_report.md
+  apps/api/tests/test_session17_demo_baseline.py
+  apps/web/e2e/test_one_topic_session17_demo_baseline.py
+  Plan/reports/Session_17_Demo_Baseline_验收报告.md
```

---

## 13. 后台任务清理

- 后端 uvicorn：TaskStop by4bwsbfs 已执行；
- 前端 dev_server：TaskStop bkdexat67 已执行；
- 端口 18181 / 18182 已释放。
