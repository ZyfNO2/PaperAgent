# Test Matrix（测试矩阵）

> PaperAgent 测试覆盖矩阵：后端 pytest + Playwright UI 验收。
> 数据基于 Session 15 完工状态；后续每次重跑以最新输出覆盖本文件。

---

## 1. 后端测试（pytest）

> 入口：`apps/api/tests/`
> 命令：`.venv/Scripts/python.exe -m pytest apps/api/tests -v`

| Session | 测试文件 | 覆盖范围 | 状态 |
|---|---|---|---|
| 01 | `test_evidence_api.py` | Evidence 数据模型 + 手动添加 | ✅ 通过 |
| 02 | `test_one_topic_api.py` | OneTopic API 基础路径 | ✅ 通过 |
| 03 | `test_session3_gates.py` | Human Gate 1+2 关键词/检索计划编辑 | ✅ 通过 |
| 04 | `test_session4_pivot.py` | PivotRoute 3 条退化路线 | ✅ 通过 |
| 05 | `test_session5_evidence_scoring.py` | 6 维论文评分 + 7 维数据集 + 8 维 repo | ✅ 通过 |
| 06 | `test_session6_llm_path.py` | LLM 路径激活 + PINN 3 症状根治 | ✅ 通过 |
| 07 | `test_session7_evidence_refs.py` | EvidenceRef 强制挂接 + 复核闭环 | ✅ 通过 |
| 08 | `test_session8_final_package.py` | FinalPackage Markdown 导出 | ✅ 通过 |
| 09 | `test_session9_workspace_board.py` | 双栏工作台 + Agent Card Intake | ✅ 通过 |
| 10 | `test_session10_verification.py` | URL 轻验证 + supports 约束 | ✅ 通过 |
| 11 | `test_session11_trace_persistence.py` | JSONL Trace 持久化 + timeline | ✅ 通过 |
| 12 | `test_session12_report_quality.py` | 8 维报告审核 + defense_questions | ✅ 通过 |
| 13 | `test_session13_skill_registry.py` | Skill 注册表 + 健康检查 | ✅ 通过 |
| 14 | `test_session14_multi_source_retrieval.py` | 多源检索 + 去重 + 导入 | ✅ 通过 |
| 15 | `test_session15_material_card_intake.py` | PDF / 图片 / 网页 / 备注卡片化 | ✅ 通过 |
| 17 | `test_session17_demo_baseline.py` | Demo 数据固化与回归基线 (YOLO + 高风险 MLLM) | ✅ 通过 |

### Session 17 后端统计

```text
后端 Session 17 baseline 测试：15 passed (含 YOLO + 高风险 MLLM 两 case 共 14 个合同断言 + 1 个 fixture 检查)
全量后端回归：212 passed, 1 skipped
```

### 运行命令

```bash
# 全量
.venv/Scripts/python.exe -m pytest apps/api/tests -v

# 单 Session
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session15_material_card_intake.py -v

# 跳过 LLM 真实网络测试
.venv/Scripts/python.exe -m pytest apps/api/tests -v -m "not llm_live"
```

---

## 2. 前端测试（Playwright）

> 入口：`apps/web/e2e/`
> 前置：后端 + 前端 dev_server 都已启动
> 命令：`.venv/Scripts/python.exe -m pytest apps/web/e2e -v`

| Session | 测试文件 | 覆盖范围 | 状态 |
|---|---|---|---|
| 01-02 | `test_one_topic_happy_path.py` | 一题 happy path | ✅ 通过 |
| 02 | `test_one_topic_no_dataset.py` | 无公开数据集分支 | ✅ 通过 |
| 02 | `test_one_topic_review.py` | 低门槛审核 UI | ✅ 通过 |
| 02-03 | `test_one_topic_trace.py` | Trace 早期版 | ✅ 通过 |
| 02 | `test_one_topic_evidence_workbench.py` | 工作台主循环 | ✅ 通过 |
| 03 | `test_one_topic_session3_gates.py` | Gates UI | ✅ 通过 |
| 04 | `test_one_topic_session4_pivot.py` | Pivot UI | ✅ 通过 |
| 05 | `test_one_topic_session5_scoring.py` | 评分可视化 | ✅ 通过 |
| 06 | `test_one_topic_session6_llm.py` | LLM 路径切换 | ✅ 通过 |
| 07 | `test_one_topic_session7_evidence_refs.py` | EvidenceRef UI | ✅ 通过 |
| 08 | `test_one_topic_session8_final_package.py` | FinalPackage UI | ✅ 通过 |
| 09 | `test_one_topic_session9_workspace_board.py` | 双栏工作台 UI | ✅ 通过 |
| 10 | `test_one_topic_session10_verification.py` | URL 验证 UI | ✅ 通过 |
| 11 | `test_one_topic_session11_trace_persistence.py` | Trace 持久化 UI + timeline 弹窗 | ✅ 通过 |
| 12 | `test_one_topic_session12_report_quality.py` | ReportQuality 8 维 UI | ✅ 通过 |
| 13 | `test_one_topic_session13_skill_registry.py` | Skill 注册 UI | ✅ 通过 |
| 14 | `test_one_topic_session14_retrieval.py` | 多源检索 UI | ✅ 通过（59 passed 含 S7-S13） |
| 15 | `test_one_topic_session15_material_cards.py` | 资料工作台 UI | ✅ 通过（10 passed） |
| 17 | `test_one_topic_session17_demo_baseline.py` | Demo 主路径 + 高风险 UI 流程 | ✅ 通过（10 passed） |

### Session 15 前端统计

```text
Playwright Session 15：10 passed in 482s
Session 14 主路径回归（S14 + S7-S13）：59 passed
```

### 运行命令

```bash
# 全量
.venv/Scripts/python.exe -m pytest apps/web/e2e -v

# 单 Session
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session15_material_cards.py -v

# 仅 Session 11（验证 trace 持久化）
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session11_trace_persistence.py -v
```

---

## 3. 回归策略

### 3.1 提交前回归

每个 Session commit 前必须跑：

```bash
# 后端 S10-S15（最新 6 个 Session）
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_session10_verification.py \
  apps/api/tests/test_session11_trace_persistence.py \
  apps/api/tests/test_session12_report_quality.py \
  apps/api/tests/test_session13_skill_registry.py \
  apps/api/tests/test_session14_multi_source_retrieval.py \
  apps/api/tests/test_session15_material_card_intake.py -v
```

### 3.2 Playwright 主路径回归

每次改动前端 / 后端 schema 后跑：

```bash
.venv/Scripts/python.exe -m pytest \
  apps/web/e2e/test_one_topic_session10_verification.py \
  apps/web/e2e/test_one_topic_session11_trace_persistence.py \
  apps/web/e2e/test_one_topic_session12_report_quality.py \
  apps/web/e2e/test_one_topic_session13_skill_registry.py \
  apps/web/e2e/test_one_topic_session14_retrieval.py \
  apps/web/e2e/test_one_topic_session15_material_cards.py -v
```

### 3.3 失败处理

| 现象 | 处理 |
|---|---|
| 单 Session 失败 | 修复代码后重跑单 Session |
| 多 Session 失败 | 检查共享服务（evidence / final_package / trace）是否被改动 |
| Playwright timeout | 检查 18181 端口是否被占 / dev_server 是否在 8080 起来 |
| LLM 路径红 | 确认 `.env` 是否填了 `MINIMAX_API_KEY`；否则走 heuristic |

---

## 4. 测试数据 / Mock 策略

| 模块 | 是否 mock 外部 API | mock 方式 |
|---|---|---|
| Evidence 评分 | 部分 | `test_session5` 用本地 fixture |
| LLM 路径 | 默认 mock | 测试内 inline stub；可选真实（需 `MINIMAX_API_KEY`） |
| OpenAlex / arXiv | mock | `httpx_mock` 或 `monkeypatch` |
| GitHub | mock | `monkeypatch` |
| HuggingFace | mock | `monkeypatch` |
| 材料解析 | 真实 | 临时写入 `.runtime/materials/` 测试目录 |

---

## 5. 覆盖率目标（当前 vs 目标）

| 模块 | 当前 | 目标 | 备注 |
|---|---|---|---|
| Pydantic schemas | ~85% | 90% | 边界 case 难覆盖 |
| Services | ~75% | 85% | trace / quality / skill 已覆盖 |
| API routers | ~70% | 80% | Playwright 已覆盖主路径 |
| 资料解析 | ~60% | 70% | OCR 不做 → 减少需求 |
| 检索 orchestrator | ~65% | 75% | 外部源多 |

---

## 6. 下一 Session 候选

Session 17 候选：**Demo 数据固化与回归基线**

- 把 Case 1（YOLO 钢材）的输入 / 候选证据 / 报告输出 / 质量审核结果固化为 JSON 基线；
- 每次跑测试时，对比基线 vs 当前输出；
- coverage_score / verdict / 引用数差异超过阈值 → fail。

不扩功能，专注**可复现、可比较**。