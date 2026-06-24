# Session 51 验收报告：工科学位论文爬取测试集与选题可行性评估闭环

## 1. 测试集来源

来源：`docs/PaperAgent_工科学位论文爬取测试集_100篇.md` —— 100 篇公开 CNKI 工科学位论文题录链接。

**领域分布：** 三维视觉/SLAM/点云、土木交通、工业缺陷检测、自动驾驶、电力巡检、计算机视觉、机器人、遥感、能源装备、医学视觉共 10 类。

**难度分布：** 低-中 ~ 40 篇、中 ~ 25 篇、中-高 ~ 20 篇、高 ~ 15 篇。

## 2. 子集拆分

| 子集 | 数量 | 选择策略 |
|------|------|----------|
| `smoke_20` | 20 篇 | smoke_20.txt 预选 id |
| `regression_60` | 60 篇 | 非 smoke 且非 hard |
| `hard_20` | 20 篇 | gold difficulty = 高/中-高 |
| `all_100` | 100 篇 | 全部 |

## 3. 模块结构

`apps/api/app/services/thesis_eval/` 8 文件：

| 模块 | 职责 |
|------|------|
| `crawler.py` | URL → 题录页 HTML, 三态降级 |
| `parser.py` | HTML → title/year/abstract_snippet |
| `need_extractor.py` | 题名+摘要 → 9 标签, heuristic+LLM |
| `difficulty_scorer.py` | 4 档难度周期, 映射 RealityCheck |
| `report_builder.py` | 4 类信息区分, evidence_refs |
| `evaluator.py` | 4 任务指标计算 |
| `eval_pipeline.py` | 跑测试集 → 聚合 → baseline |
| `baseline.py` | baseline 存/读/对比/回归警告 |

## 4. API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/v1/thesis-eval/assess` | 单条题录评估 |
| POST | `/api/v1/thesis-eval/eval/run` | 跑子集评估 |
| GET | `/api/v1/thesis-eval/eval/baseline` | 获取 baseline |
| POST | `/api/v1/thesis-eval/eval/baseline` | 保存 baseline |

## 5. 题录抓取三态降级

```
verified  — HTTP 200 + 有 title + 有 abstract_snippet
partial   — HTTP 200 + 仅有 title 或仅部分字段
failed    — HTTP 4xx/5xx / 超时 / 反爬 → 用测试集 fallback 字段降级
```

降级原则：**绝不编造全文/摘要/作者结论**。降级时 `fallback_used=True`，`source_url` 永远保真。

## 6. 9 标签实验需求抽取规则 (heuristic)

| 标签 | 触发 |
|------|------|
| `single_gpu_ok` | YOLO/U-Net/Faster R-CNN/GAN + 无硬件词 |
| `cpu_or_light_gpu_ok` | SCADA/可靠性/传统算法 |
| `large_gpu_optional` | 点云补全/多模态融合/大规模3D |
| `h100_level_not_recommended` | 系统判必须 H100 |
| `self_collected_dataset` | 自采/现场/企业数据 |
| `public_dataset_available` | 命中 NEU-DET/KITTI 等公开数据集名 |
| `hardware_platform_required` | 机械臂/机器人/相机/Jetson/LiDAR/ROS |
| `annotation_heavy` | 缺陷/小目标/多类别 + 无公开数据 |
| `domain_data_permission_risk` | 医学/人体/电力巡检/SCADA/企业生产 |

## 7. 4 档难度周期映射 (对齐 RealityCheck)

| 难度 | RealityCheck 资源层 | 周期 | 典型 |
|------|---------------------|------|------|
| 低-中 | existing_env | 0.5–2天/轮 | YOLO/U-Net 裂缝检测 |
| 中 | existing_env / rent_compute | 1–3天/轮 | 完整训练+消融 |
| 中-高 | self_collect_data | 3–10天/轮 | 点云/SLAM/三维 |
| 高 | infeasible / hardware | 1–3周/轮 | 机械臂/医学/多模态攻防 |

## 8. 报告 4 类信息区分

1. **题录事实** — title/year/source_url/abstract_snippet, 可 URL verified
2. **模型推断** — 实验需求标签/难度/周期/可行性, 有 evidence_refs
3. **未验证信息** — 全文/作者结论/具体指标, 标 unsupported_claims, 不编造
4. **用户可操作建议** — 降级方案/审核触发/手动上传 PDF

## 9. 首次 Baseline (smoke_20, 2026-06-24)

### 4 任务指标表

| 任务 | 指标 | 值 | 合格线 | 结果 |
|------|------|----:|-------:|:----:|
| 1 题录抓取 | URL 保真率 | **1.0000** | ≥ 0.98 | PASS |
| 1 题录抓取 | 题名抽取准确率 | 1.0000 | ≥ 0.95 | PASS |
| 1 题录抓取 | 年份抽取准确率 | 1.0000 | ≥ 0.90 | PASS |
| 1 题录抓取 | 降级正确率 | 1.0000 | ≥ 0.95 | PASS |
| 2 标签抽取 | Macro-F1 | **0.7333** | ≥ 0.75 | NEEDS IMPROVEMENT |
| 2 标签抽取 | 数据风险召回率 | 1.0000 | ≥ 0.85 | PASS |
| 2 标签抽取 | 硬件风险召回率 | 1.0000 | ≥ 0.85 | PASS |
| 2 标签抽取 | H100 误判率 | 0.0000 | ≤ 0.05 | PASS |
| 3 难度评估 | 难度准确率 | 0.2500 | ≥ 0.70 | NEEDS IMPROVEMENT |
| 3 难度评估 | 邻档准确率 | 0.6500 | ≥ 0.90 | NEEDS IMPROVEMENT |
| 3 难度评估 | 周期邻档准确率 | 0.6500 | ≥ 0.85 | NEEDS IMPROVEMENT |
| 3 难度评估 | 高风险召回率 | 1.0000 | ≥ 0.85 | PASS |
| 4 报告质量 | 支撑句比例 | **1.0000** | ≥ 0.85 | PASS |
| 4 报告质量 | 幻觉率 | **0.0000** | ≤ 0.05 | PASS |
| 4 报告质量 | 降级建议可用率 | 1.0000 | ≥ 0.80 | PASS |
| 4 报告质量 | 人工审核触发率 | 0.9444 | ≥ 0.90 | PASS |

### 最重要三指标

| 指标 | 值 | 合格线 | 判定 |
|------|----:|-------:|:----:|
| 幻觉率 | **0.0000** | ≤ 0.05 | PASS |
| URL 保真率 | **1.0000** | ≥ 0.98 | PASS |
| 支撑句比例 | **1.0000** | ≥ 0.85 | PASS |

## 10. 测试结果

```
pytest: 586 passed, 1 skipped (Session 51 新增 32 tests)
```

新增 32 tests 覆盖：测试集加载、三态降级、标签抽取、难度映射、报告区分、指标计算、baseline 存读对比、端点形状。

## 11. 面试讲法

### 怎么验证可行性判断靠谱

1. **100 篇工科论文测试集**：覆盖 10 个工科领域、4 档难度，每条有 gold 真值（实验需求/难度/周期/repeatability）。
2. **4 任务 16 指标量化**：抓取保真率、标签 Macro-F1、难度准确率、报告支撑句比例各有合格线。
3. **回归基线**：每次 commit 自动对比 baseline，幻觉率上升或 URL 保真率下降 > 0.02 触发红线警告。

### 怎么防编造防错链

1. **三态降级**：抓取失败自动降级为题录级证据，`fallback_used` 标记，绝不编造全文。
2. **URL 保真**：`source_url` 永远保真不可替换，URL 保真率 ≥ 0.98 监控。
3. **支撑句比例**：每个关键判断必须挂 evidence_refs，防空口，支撑句比例 ≥ 0.85。
4. **未验证信息隔离**：`unsupported_claims` 列表隔离无法回溯的判断，不混入事实层。

## 12. 已知不足

- **标签 Macro-F1 (0.7333)** → 未达 0.75 合格线：heuristic 规则对部分样本标签覆盖不全，需迭代规则或接 LLM 路径提分。
- **难度准确率 (0.25) / 邻档准确率 (0.65)** → 未达合格线：当前 heuristic 仅凭关键词定档，缺少对数据量/实验复杂度的量化评估，需改进评分信号。
- 以上两条不阻断闭环，baseline 已记录，下次迭代可对比。
