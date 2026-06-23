# PaperAgent Session 17 SOP：Demo 数据固化与回归基线

> 日期：2026-06-19  
> 阶段定位：Session 16 已完成作品化、Demo 文档、测试矩阵与边界声明。本轮不扩功能，专门把 Demo Case 固化为可重复测试的回归基线。  
> 本轮目标：把 1-2 个 Demo 的输入、检索候选、证据状态、报告结构、质量审核结果和 Trace 关键事件固化成 fixture / baseline，并建立自动化断言，防止后续改动破坏主流程。

---

## 1. Session 16 验收判断

已审阅：

```text
Plan/reports/Session_16_Productization_Demo_验收报告.md
docs/demo/Demo_Cases.md
docs/demo/OneTopic_Demo_Script.md
docs/testing/Test_Matrix.md
```

判断：

```text
Session 16 可过验收；
可以进入 Session 17。
```

依据：

```text
1. README / Demo / Test Matrix / Runbook / Scope / Resume 已完成；
2. Demo_Cases.md 已定义 2 个样例：YOLO 钢材（可行）与 MLLM 通用工业缺陷（高风险）；
3. OneTopic_Demo_Script.md 已有 11 步主流程；
4. 后端回归 192 passed, 1 skipped；
5. Playwright Session 15 主路径 10 passed；
6. Session 16 明确未改证据规则，未新增核心功能。
```

当前缺口：

```text
Demo_Cases.md 仍是“预期形态”，不是可执行基线；
当前没有 apps/api/tests/test_session17_demo_baseline.py；
当前没有 apps/web/e2e/test_one_topic_session17_demo_baseline.py；
当前没有 docs/demo/baselines/ 基线数据。
```

因此 S17 的核心任务是把 Demo 从“文档演示”升级为“可回归测试资产”。

---

## 2. Session 17 名称

```text
Demo 数据固化与回归基线
```

一句话目标：

```text
把 YOLO 钢材和高风险 MLLM 两个 Demo 固化成稳定 fixture，用结构化断言验证主流程不退化。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不新增业务功能 | 当前重点是稳定回归 |
| 不比较 Markdown 全文逐字一致 | 自然语言输出可能有合理波动 |
| 不依赖真实外部 API | OpenAlex / GitHub / HF 网络不稳定，基线必须 mock |
| 不要求 LLM 输出完全一致 | LLM 不适合作硬基线 |
| 不引入大文件 fixture | Demo 基线应小、可读、可维护 |
| 不做视频 / 图片 / OCR 基线 | 非当前稳定化重点 |
| 不修改 EvidenceRef / Verification 硬规则 | 防止为了通过基线降低证据约束 |

---

## 4. 基线设计原则

S17 的比较对象不是完整文本，而是结构化合同：

```text
1. 输入题目和用户约束；
2. 关键词拆解关键字段；
3. mock 检索候选数量与类型；
4. 导入后的 evidence 状态；
5. verification / review / lane 规则；
6. EvidenceRef supports / warns / background 分布；
7. FinalPackage 必备章节；
8. ReportQuality verdict 与关键维度范围；
9. Trace 关键 action 是否出现；
10. rejected / pending / failed 是否被正确排除。
```

硬断言：

```text
rejected 不得 supports；
pending + unverified 不得 supports；
failed verification 不得 supports；
FinalPackage 必须有引用清单；
ReportQuality 必须输出 verdict 和 revision_checklist；
Trace 必须记录检索、导入、验证、报告生成、质量审核关键事件。
```

软断言：

```text
coverage_score 在允许区间内；
引用数量在允许区间内；
ReportQuality score 不低于最低阈值；
章节标题存在即可，不比较正文逐字。
```

---

## 5. 建议新增文件

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
```

新增测试：

```text
apps/api/tests/test_session17_demo_baseline.py
apps/web/e2e/test_one_topic_session17_demo_baseline.py
```

新增报告：

```text
Plan/reports/Session_17_Demo_Baseline_验收报告.md
```

---

## 6. Demo Case 1：YOLO 钢材缺陷检测

### 6.1 输入基线

`docs/demo/baselines/yolo_steel_defect_input.json`

建议字段：

```json
{
  "case_id": "yolo_steel_defect",
  "raw_topic": "基于 YOLO 的钢材表面缺陷检测",
  "goal_level": "保毕业",
  "degree_type": "硕士",
  "advisor_direction": "工业质检",
  "expected_keyword_contract": {
    "method_keywords_any": ["YOLO", "YOLOv5", "YOLOv8"],
    "task_keywords_any": ["缺陷检测", "目标检测"],
    "object_keywords_any": ["钢材表面", "钢材", "带钢", "金属表面"],
    "query_keywords_min": 3
  }
}
```

### 6.2 Mock source 基线

`yolo_steel_defect_mock_sources.json` 固化：

```text
OpenAlex paper candidates: 4-6 条；
arXiv paper candidates: 2-4 条；
HuggingFace dataset candidates: 2-3 条；
GitHub repo candidates: 2-3 条；
materials: 1 条 manual_note；
```

必须包含：

```text
至少 1 个 verified paper；
至少 1 个 partial dataset；
至少 1 个 verified/partial repo；
至少 1 个 rejected 候选；
至少 1 个 pending + unverified 候选。
```

### 6.3 Expected contract

`yolo_steel_defect_expected.json`

建议断言：

```json
{
  "verdict_allowed": ["可做", "GO", "PASS", "有条件通过"],
  "min_papers": 3,
  "min_datasets": 1,
  "min_repos": 1,
  "min_verified_or_partial": 3,
  "final_package_required_sections": [
    "研究背景",
    "国内外研究现状",
    "研究内容",
    "技术路线",
    "实验方案",
    "风险预案",
    "引用清单"
  ],
  "report_quality_allowed": ["通过", "有条件通过", "PASS", "WARN"],
  "trace_actions_required": [
    "retrieval_run_started",
    "retrieval_run_completed",
    "retrieval_candidate_imported",
    "verify_evidence",
    "final_package_build"
  ],
  "forbidden_supports": [
    "review_status=rejected",
    "review_status=pending AND verification_status=unverified",
    "verification_status=failed"
  ]
}
```

---

## 7. Demo Case 2：高风险 MLLM 通用工业缺陷

### 7.1 输入基线

`risky_mllm_industrial_input.json`

建议字段：

```json
{
  "case_id": "risky_mllm_industrial",
  "raw_topic": "基于多模态大模型的通用工业缺陷智能诊断",
  "goal_level": "冲高水平",
  "degree_type": "博士",
  "advisor_direction": "工业 AI",
  "expected_keyword_contract": {
    "method_keywords_any": ["多模态大模型", "MLLM", "Vision-Language"],
    "risk_terms_any": ["通用", "智能", "高精度", "实时", "跨场景"],
    "risk_terms_min": 2
  }
}
```

### 7.2 Expected contract

高风险 Case 不应强行变成 PASS。

断言：

```json
{
  "verdict_allowed": ["暂缓", "可转向", "PARK", "PIVOT", "WARN", "需修改"],
  "must_have_missing_evidence_any": [
    "公开数据集",
    "可复现 baseline",
    "统一基准",
    "推理资源",
    "评价指标"
  ],
  "must_have_pivot_routes_min": 2,
  "report_quality_allowed": ["有条件通过", "需修改", "WARN", "FAIL"],
  "must_not_have": [
    "无证据支持但 verdict=通过",
    "没有 dataset/repo 仍生成 supports",
    "未验证资料提升关键维度"
  ]
}
```

这个 Case 的价值是防止系统为了“看起来好”而把高风险题目错误判为可做。

---

## 8. 后端测试设计

新增：

```text
apps/api/tests/test_session17_demo_baseline.py
```

至少覆盖：

```text
1. baseline fixture 文件存在且 JSON 可解析；
2. YOLO case 输入能生成符合 contract 的关键词；
3. mock retrieval 能导入 paper / dataset / repo；
4. 导入后 evidence 状态符合 pending / accepted / rejected 规则；
5. auto_verify 后 verified / partial / failed 状态符合预期；
6. EvidenceRef 不包含 rejected / pending-unverified / failed supports；
7. FinalPackage 包含 required_sections；
8. Citation table 包含 evidence_id / verification / skill / source；
9. ReportQuality verdict 在 allowed 范围；
10. Trace 包含 required actions；
11. MLLM risky case 不得直接 PASS；
12. MLLM risky case 必须出现 missing_evidence 或 pivot_routes；
13. 两个 case 均不依赖真实外部 API；
14. expected_report.md 只校验章节和关键占位，不逐字比较。
```

建议实现一个测试 helper：

```python
def assert_demo_contract(actual: dict, expected: dict) -> None:
    ...
```

重点检查结构，不检查长文本。

---

## 9. Playwright 测试设计

新增：

```text
apps/web/e2e/test_one_topic_session17_demo_baseline.py
```

至少覆盖：

```text
1. 从 UI 输入 YOLO Demo；
2. 页面能生成 project_id；
3. 多源检索面板能显示候选或 mock 候选；
4. 用户能导入候选；
5. URLVerified 状态可见；
6. FinalPackage 面板能生成 Markdown；
7. ReportQuality 面板能显示 verdict；
8. Trace 面板能看到关键事件；
9. 关键 UI 文案 / 面板 selector 稳定；
10. 高风险 Case 显示 WARN / PIVOT / 缺证据提示。
```

Playwright 不应断言完整 Markdown 文本，只断言：

```text
章节标题；
引用清单存在；
verdict badge 存在；
trace action 出现；
没有 rejected supports 的可见证据。
```

---

## 10. Baseline 更新规则

新增 `docs/demo/baselines/README.md` 说明：

```text
1. 基线不是产品文案，是测试合同；
2. 修改基线必须说明原因；
3. 只有业务规则变更或 Demo 设计变更时才能更新 expected；
4. 外部 API 输出变化不能直接更新 expected，应通过 mock 固化；
5. LLM 文本波动不能作为更新基线理由；
6. 如果 supports 规则变化，必须同步更新 Scope_And_Compliance。
```

建议基线版本字段：

```json
{
  "baseline_version": "0.1.0",
  "created_at": "2026-06-19",
  "source_session": "Session 17",
  "contract_type": "structural"
}
```

---

## 11. 与现有文档联动

需要更新：

```text
docs/demo/Demo_Cases.md
docs/testing/Test_Matrix.md
docs/demo/OneTopic_Demo_Script.md
README.md
```

更新内容：

```text
1. Demo_Cases.md 说明 Case 1 / Case 2 已有 baseline fixture；
2. Test_Matrix.md 增加 Session 17 后端 / Playwright 测试；
3. Demo Script 增加“如何运行基线回归”步骤；
4. README 测试结果中加入 Session 17。
```

---

## 12. 验收标准

通过条件：

```text
1. docs/demo/baselines/ 目录存在；
2. YOLO Case 输入 / mock source / expected contract 完成；
3. MLLM Risky Case 输入 / mock source / expected contract 完成；
4. expected_report.md 至少记录必备章节与引用清单形态；
5. 后端 Session17 baseline 测试通过；
6. Playwright Session17 主路径通过；
7. Test_Matrix 已加入 Session17；
8. README 或 Demo 文档说明如何运行基线；
9. 基线比较不依赖真实外部 API；
10. 基线比较不要求自然语言逐字一致；
11. rejected / pending-unverified / failed 不进 supports 的断言被覆盖；
12. 新增 Session17 验收报告。
```

最低可接受 MVP：

```text
YOLO Case 一套完整 baseline；
MLLM Risky Case 至少输入 + expected contract；
后端 baseline 测试；
Test_Matrix 更新；
Session17 验收报告。
```

如果 Playwright 基线耗时过长，可先做：

```text
Playwright smoke：只跑 YOLO Case 的 UI 主路径；
高风险 Case 先由后端 contract 覆盖。
```

---

## 13. 测试要求

### 13.1 后端

必须运行：

```text
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py -v
```

建议回归：

```text
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session10_verification.py apps/api/tests/test_session11_trace_persistence.py apps/api/tests/test_session12_report_quality.py apps/api/tests/test_session13_skill_registry.py apps/api/tests/test_session14_multi_source_retrieval.py apps/api/tests/test_session15_material_card_intake.py apps/api/tests/test_session17_demo_baseline.py -v
```

### 13.2 Playwright

必须运行：

```text
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session17_demo_baseline.py -v
```

如果耗时过长，报告必须说明：

```text
跑了哪些 case；
是否使用 mock；
哪些测试延期；
是否影响主路径验收。
```

---

## 14. 完工报告要求

完成后新增：

```text
Plan/reports/Session_17_Demo_Baseline_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围；
2. 新增 baseline 文件清单；
3. YOLO Case contract；
4. MLLM Risky Case contract；
5. mock source 策略；
6. baseline 比较规则；
7. 后端测试结果；
8. Playwright 测试结果；
9. 更新的 README / Demo / Test Matrix；
10. 未做项；
11. 下一 Session 建议。
```

报告必须明确：

```text
是否依赖真实外部 API；
是否比较 Markdown 全文；
是否改变证据规则；
是否覆盖 rejected / pending / failed 不进 supports。
```

---

## 15. 下一 Session 预告

Session 18 建议：

```text
错误处理、空状态与可观测性整理
```

进入条件：

```text
S17 已有稳定 Demo baseline；
后续再整理错误码、空状态和 health endpoint 时，可以通过 baseline 判断是否破坏主流程。
```

边界：

```text
不引入复杂监控平台；
不扩展业务能力；
只提高本地 MVP 的可诊断性。
```

