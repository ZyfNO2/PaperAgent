# Demo Cases（案例对比）

> 两个样例覆盖**典型可行** + **典型高风险**两个开题档位。
> 每个 Case 记录：输入 → 关键词拆解 → 检索概览 → 核心证据 → 可行性 → 建议收缩 → 工作包 → 报告质量审核。
> 这些不是真实历史结果，是**预期形态**；实际演示时由系统在启发式 / LLM 路径下生成。

---

## Case 1：基于 YOLO 的钢材表面缺陷检测（典型可行）

### 1.1 输入

```text
raw_topic = "基于 YOLO 的钢材表面缺陷检测"
goal_level = "保毕业"
degree_type = "硕士"
advisor_direction = "工业质检"
```

### 1.2 关键词拆解（预期）

| 类型 | 关键词 |
|---|---|
| method_keywords | `YOLO`, `YOLOv5`, `YOLOv8` |
| task_keywords | `缺陷检测`, `目标检测` |
| object_keywords | `钢材表面`, `金属板材`, `带钢` |
| scenario_keywords | `工业质检`, `产线在线检测` |
| metric_keywords | `mAP`, `Recall`, `FPS` |
| risk_terms | `智能`, `实时`, `高精度` |
| query_keywords_en | `yolo steel surface defect detection`, `yolov8 neudet` |
| query_keywords_zh | `YOLO 钢材 缺陷 检测`, `YOLOv8 工业 表面` |

### 1.3 检索概览（预期）

| 类型 | 数量 | 主要源 |
|---|---|---|
| papers | 8-15 | arXiv / OpenAlex（YOLOv8 + 工业检测） |
| datasets | 3-5 | HuggingFace（NEU-DET, GC10-DET, Severstal Steel） |
| baselines | 2-4 | GitHub（ultralytics/yolov5, ultralytics/ultralytics） |
| has_public_dataset | True |
| has_repro_baseline | True |
| has_metrics | True |

### 1.4 核心证据（预期）

| evidence_id | type | title | source | verification |
|---|---|---|---|---|
| P1 | paper | YOLOv8: Better, Faster, Stronger | openalex | verified |
| P2 | paper | Steel Surface Defect Detection with Improved YOLO | arxiv | verified |
| D1 | dataset | NEU-DET (Steel Surface Defects) | huggingface | verified |
| D2 | dataset | GC10-DET (Galvanized Steel) | huggingface | partial |
| R1 | repo | ultralytics/ultralytics | github | verified |
| R2 | repo | yolov5 steel defect fork | github | partial |

### 1.5 可行性判断（预期）

```text
verdict: 可做
confidence: 0.85
reason: 方法成熟、公开数据集充足、可复现 baseline 多
paper_status:    充足 (≥ 8 篇相关)
dataset_status:  充足 (≥ 3 个公开)
baseline_status: 充足 (≥ 2 个含训练脚本)
engineering_status: 充足 (硬件需求适中)
missing_evidence: []
recommended_next_action: 选定 YOLOv8 + NEU-DET 基线, 加 1 项轻量改进
```

### 1.6 建议收缩方向

- **不要做**：通用工业缺陷检测（对象过宽，跨域）；
- **聚焦**：带钢表面划痕 / 夹杂（NEU-DET 子集）；
- **加分点**：轻量化（适配产线边缘设备）或解释性（Grad-CAM 热力图）。

### 1.7 工作包（预期）

| wp_id | title | chapter |
|---|---|---|
| WP-1 | NEU-DET 数据预处理与基线 YOLOv8 复现 | 第 3 章 |
| WP-2 | 轻量化 backbone 改进 + 边缘部署实验 | 第 4 章 |
| WP-3 | 解释性可视化（Grad-CAM）+ 答辩材料 | 第 5 章 |

### 1.8 报告质量审核（预期）

```text
verdict: PASS
coverage:          0.78
verification:      0.85
provenance:        0.90
skill_sources:     0.80
contradictions:    通过 (无冲突)
unsupported_claims: 1 条 (建议补充)
trace_consistency: 通过
format:            通过
defense_questions:
  - 数据集是否覆盖你目标场景的全部缺陷类型？
  - FPS 是否满足产线节拍？
revision_checklist:
  - 在“数据集划分”章节补充 5-fold 交叉验证细节
  - 在“实验设计”章节补充 FPS 测量方法
```

---

## Case 2：基于多模态大模型的通用工业缺陷智能诊断（典型高风险）

### 2.1 输入

```text
raw_topic = "基于多模态大模型的通用工业缺陷智能诊断"
goal_level = "冲高水平"
degree_type = "博士"
advisor_direction = "工业 AI"
```

### 2.2 关键词拆解（预期）

| 类型 | 关键词 |
|---|---|
| method_keywords | `多模态大模型`, `MLLM`, `Vision-Language` |
| task_keywords | `缺陷诊断`, `缺陷分类`, `异常检测` |
| object_keywords | `工业缺陷`（**过宽**，跨域） |
| scenario_keywords | `通用工业`, `跨场景`（**过宽**） |
| metric_keywords | `zero-shot accuracy`, `AUROC`, `F1` |
| risk_terms | `智能`, `通用`, `高精度`, `实时`, `跨场景`（**5 条**） |
| query_keywords_en | `multimodal llm industrial defect`, `vision-language anomaly detection` |
| query_keywords_zh | `多模态大模型 工业 缺陷 通用` |

### 2.3 检索概览（预期）

| 类型 | 数量 | 主要源 |
|---|---|---|
| papers | 5-10 | arXiv（MLLM + 工业）数量少 |
| datasets | 1-3 | 公开统一基准几乎没有 |
| baselines | 0-1 | 几乎无可复现 baseline |
| has_public_dataset | False |
| has_repro_baseline | False |
| has_metrics | True（但缺少标准） |

### 2.4 核心证据（预期，可能为空）

| evidence_id | type | title | source | verification |
|---|---|---|---|---|
| P1 | paper | AnomalyGPT / Industrial Anomaly Detection MLLM Survey | openalex | verified |
| P2 | paper | MLLM for Visual Inspection: A Survey | arxiv | partial |
| D1 | dataset | MVTec AD（异常检测常用，但与工业缺陷**不直接等同**） | huggingface | verified |
| R1 | repo | Industrial Anomaly Detection Baseline (Anomalib) | github | partial |

**关键问题**：

- 没有**针对工业缺陷**的统一公开基准；
- 没有可直接复现的 MLLM baseline；
- “通用”与“缺陷”定义在论文间不一致 → `contradictions` 维度会扣分。

### 2.5 可行性判断（预期）

```text
verdict: 暂缓 / 可转向
confidence: 0.55
reason: 关键词过宽 + 公开基准缺失 + 缺乏可复现 baseline
paper_status:    偏少 (≤ 10 篇)
dataset_status:  缺失
baseline_status: 缺失
engineering_status: 未知（需要 MLLM 推理资源）
missing_evidence:
  - 工业缺陷统一基准
  - MLLM 推理硬件成本估算
recommended_next_action: 收缩到具体场景（如半导体晶圆缺陷）+ MLLM 微调
```

### 2.6 建议收缩方向（3 条 PivotRoute）

| level | new_topic | tradeoff |
|---|---|---|
| conservative | 基于 MLLM 的**半导体晶圆**缺陷分类 | 保留 MLLM，缩场景 |
| balanced | 基于**视觉-语言预训练**的工业缺陷**少样本**学习 | 保留多模态，缩任务 |
| aggressive | 基于 CLIP 微调的**钢材表面**异常检测 | 放弃 MLLM，回到 Case 1 场景 |

### 2.7 工作包（保守路线示例）

| wp_id | title | chapter |
|---|---|---|
| WP-1 | MLLM 在工业异常检测的 benchmark 复现 | 第 3 章 |
| WP-2 | 半导体晶圆缺陷数据集构建 + 标注规范 | 第 4 章 |
| WP-3 | MLLM 轻量化微调 + 推理延迟优化 | 第 5 章 |

### 2.8 报告质量审核（预期）

```text
verdict: WARN
coverage:          0.42
verification:      0.55
provenance:        0.70
skill_sources:     0.50
contradictions:    有冲突 (3 处 "通用" 定义不一致)
unsupported_claims: 5 条 (数据集 / 推理成本 / 跨场景泛化均无证据)
trace_consistency: 通过
format:            通过
defense_questions:
  - "通用"在 5 个引用中分别指什么？
  - 没有统一基准如何对比 MLLM 与传统方法？
  - MLLM 推理资源需求与产线节拍是否冲突？
revision_checklist:
  - 明确"通用"的范围 (例如限定 5 种典型工业场景)
  - 补充工业缺陷统一基准调研章节
  - 补充 MLLM 推理硬件成本对比
  - 至少 1 条 PivotRoute 收敛到具体场景
```

---

## 案例对比小结

| 维度 | Case 1（YOLO 钢材） | Case 2（MLLM 通用） |
|---|---|---|
| verdict | 可做 | 暂缓 / 可转向 |
| confidence | 0.85 | 0.55 |
| 公开数据集 | ✅ 多 | ❌ 缺 |
| 可复现 baseline | ✅ 多 | ❌ 缺 |
| ReportQuality | PASS | WARN |
| 主演示价值 | 主闭环 OK | 收缩 / Pivot / 审核 |

这两个 Case 组合覆盖了 PaperAgent 系统的**核心展示价值**：
正向闭环 + 反向收缩 + 风险标注。

---

## Demo Case 与 Session 17 基线

Session 17 已把这两个 Case 固化为**结构化回归基线**，可重复执行：

- `docs/demo/baselines/yolo_steel_defect_*` — Case 1 三件套（input / mock_sources / expected）；
- `docs/demo/baselines/risky_mllm_industrial_*` — Case 2 三件套；
- `docs/demo/baselines/README.md` — 基线维护规则；
- `apps/api/tests/test_session17_demo_baseline.py` — 15 项后端合同断言；
- `apps/web/e2e/test_one_topic_session17_demo_baseline.py` — 10 项 Playwright 主路径断言。

每次改动代码，跑：

```bash
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session17_demo_baseline.py -v
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session17_demo_baseline.py -v
```

即可判断是否破坏主流程。

详见 [Session_17_Demo_Baseline_验收报告](../../Plan/reports/Session_17_Demo_Baseline_验收报告.md)。