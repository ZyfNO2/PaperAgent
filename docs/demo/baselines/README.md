# Demo Baselines（回归基线维护规则）

> 本目录是 PaperAgent 主流程的**结构化回归基线**，不是产品文案。
> Session 17 落地，用于在每次代码改动后自动判断主流程是否破坏。

---

## 1. 基线不是产品文案

- 基线是**测试合同**（contract），用于机器自动断言；
- Demo_Cases.md / OneTopic_Demo_Script.md 才是产品文案（给人看的演示文档）；
- 两个文件用 `case_id` 互相引用，但表达目的不同。

## 2. 目录结构

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

每个 Case 三件套：

```text
<input>.json             输入题目 + 用户约束 + 关键词合同
<mock_sources>.json     mock 检索 / 验证 / 资料来源 (固化, 不依赖真实网络)
<expected>.json         结构化合同: verdict 范围 / min 证据数 / 必含章节 / 必含 trace action / 禁用 supports
<expected_report>.md    章节骨架 + 引用清单占位, 只比对标题与占位符, 不逐字
```

## 3. 硬断言 vs 软断言

### 硬（必须 100% 通过）

- `rejected` 不得 `supports`；
- `pending + unverified` 不得 `supports`；
- `failed verification` 不得 `supports`；
- FinalPackage 必须有引用清单；
- ReportQuality 必须输出 `verdict` + `revision_checklist`；
- Trace 必须出现关键 action 子集。

### 软（区间内即可）

- `coverage_score` 落在 `[low, high]`；
- 引用数量落在 `[low, high]`；
- ReportQuality 总分不低于 `min_score`；
- 章节标题存在即可，不比较正文逐字。

## 4. 更新基线的合法理由

| 情况 | 是否可改基线 | 同步更新 |
|---|---|---|
| 业务规则变化（supports 条件、检索源） | ✅ 可改 | Scope_And_Compliance.md + Demo_Cases.md |
| Demo 设计调整（题目、目标档位） | ✅ 可改 | Demo_Cases.md + OneTopic_Demo_Script.md |
| 外部 API 输出变化 | ❌ **不应改基线** | 通过 mock_sources 固化 |
| LLM 自然语言输出波动 | ❌ **不应改基线** | 软断言允许区间 |
| 章节标题调整 | ⚠️ 仅章节级别 | expected.json + expected_report.md |
| 报告结构小修 | ⚠️ 同步 Test_Matrix.md |

## 5. 基线版本字段

每个 `*_expected.json` 必须含：

```json
{
  "baseline_version": "0.1.0",
  "created_at": "2026-06-19",
  "source_session": "Session 17",
  "contract_type": "structural"
}
```

更新基线时：

1. `baseline_version` 末位 +1（`0.1.0` → `0.1.1`）；
2. `created_at` 更新为改动日期；
3. `source_session` 改写为改动发生的 Session 号。

## 6. 运行基线回归

```bash
# 后端基线测试
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py -v

# 完整 Session 10-17 回归
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_session10_verification.py \
  apps/api/tests/test_session11_trace_persistence.py \
  apps/api/tests/test_session12_report_quality.py \
  apps/api/tests/test_session13_skill_registry.py \
  apps/api/tests/test_session14_multi_source_retrieval.py \
  apps/api/tests/test_session15_material_card_intake.py \
  apps/api/tests/test_session17_demo_baseline.py -v

# Playwright 主路径 (YOLO 单一 Case, 高风险 Case 由后端 contract 覆盖)
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session17_demo_baseline.py -v
```

## 7. Mock 策略

| 源 | 是否 mock | 说明 |
|---|---|---|
| OpenAlex | ✅ | 测试内 inline 候选；不访问真实 API |
| arXiv | ✅ | 同上 |
| GitHub | ✅ | 同上 |
| HuggingFace | ✅ | 同上 |
| LLM (MiniMax) | ✅ | 默认 mock；只走 heuristic |
| 材料解析 | 部分真实 | 上传 fixture PDF 入 `.runtime/materials/` 测试目录 |

mock 候选通过 `mock_sources.json` 加载，测试在 `conftest.py` 里 `monkeypatch` 注入。

## 8. 已知基线外行为

以下情况**预期**会触发基线失败，由人工判断是否需要更新基线：

- 真实 OpenAlex / arXiv 返回结构变化（应改 mock_sources）；
- LLM 路径评分波动超过软断言区间（应放宽区间）；
- 新增 trace action（应在 expected.json 加 `trace_actions_required`）；
- 新增章节（应在 expected.json 加 `final_package_required_sections`）。

如确认是系统破坏：

- 修复代码 → 基线继续通过；
- 修复基线 → 必须有业务或 Demo 变更理由 + 更新 README §4。
