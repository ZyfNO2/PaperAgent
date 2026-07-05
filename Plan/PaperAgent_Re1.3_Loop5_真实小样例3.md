# PaperAgent Re1.3 Loop 5 — 真实 3 样例测试报告

> 日期: 2026-07-06
> 执行者: Codely CLI (执行 AI)
> 模型: step-3.7-flash (StepFun, RPM=10)

## 第一轮 E2E 结果 (修复前)

### 各 case 数据汇总

| Case | 候选 | filter dropped | verified | seeds | expanded | survey | repo | baseline | work_pkg | 耗时 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| steel-yolov5 | 31 | 8 | 6 | **0** | **0** | 0 | 0 | 4 | 0 | 554s | blocked |
| semantic-slam | 24 | 0 | 14 | **0** | **0** | 0 | 0 | 10 | 0 | 878s | blocked |
| medical-llm | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 105s | interrupted (quota) |

### 发现的 Bug

#### Bug 1: verify_node 丢失标识符 (导致 citation_expander 无种子)

verify_node 构建输出 item 时，只保留了 `title/verdict/hit_keywords/relation_to_topic/reason` 等字段，**丢掉了原始候选的 `doi`/`paper_id`/`arxiv_id`/`url`/`source`**。

citation_expander 的 `_select_seeds` 函数要求种子论文必须有 `paper_id` 或 `doi` 或 `arxiv_id`，否则跳过。结果：
- steel-yolov5: 6 篇 verified_papers 全部无标识符 → 0 种子 → 0 扩展
- semantic-slam: 14 篇 verified_papers 全部无标识符 → 0 种子 → 0 扩展

**修复**: verify_node 构建 item 时从原始候选携带 `doi, url, source, paper_id, arxiv_id, citation_count, abstract`。

#### Bug 2: quality_filter 误杀真实 arxiv 论文

quality_filter LLM 把 8 篇来自 arxiv 的真实论文误判为 "GitHub repository"：

被误杀的论文:
- YOLOv5s-GTB: light-weighted and improved YOLOv5s for bridge crack detection (arxiv)
- HIC-YOLOv5: Improved YOLOv5 For Small Object Detection (arxiv)
- TPH-YOLOv5: Improved YOLOv5 Based on Transformer Prediction Head (arxiv)
- ... 共 8 篇全部是 arxiv 真实论文

LLM 的判断 reason 全是 "This is a GitHub repository..." — 把 `source: arxiv` 的论文混淆了。

**修复**: quality_filter prompt 增加 "Papers from arxiv.org/doi.org ARE real academic papers" 的明确指示。

#### Bug 3: StepFun 配额耗尽

steel-yolov5 + semantic-slam 两个 case 跑完后，StepFun 返回 HTTP 402 `quota_exceeded`，medical-llm case 在 verify 阶段因 LLM 不可用而全部失败。

### quality_filter 效果 (steel-yolov5)

成功过滤 8 条候选：
- 被 filter 正确过滤的：Figure/Table 标题等
- 被 filter 误杀的：8 篇 arxiv 真实论文（Bug 2）

### verify 仍然接受非论文 (steel-yolov5)

6 篇 verified 中仍有非论文：
- "YOLOv5 Reference Entry" — 仍是词条
- "YOLOv5 Object Detection Technology Overview" — 仍是概述
- "YOLOv5 Object Detection Model Reference" — 仍是参考条目

说明 verify prompt 的 `is_real_paper` 条件还未被严格执行。

## 第二轮 E2E (修复后, 进行中)

修复了 Bug 1 (verify 携带标识符) 和 Bug 2 (quality_filter 保护 arxiv 论文) 后重跑。

预期改善：
- verify 输出的 verified_papers 包含 doi/paper_id/arxiv_id
- citation_expander 能找到种子论文标识符
- S2 API 引文扩展产出 expanded_papers

## 性能数据

| 阶段 | steel-yolov5 | semantic-slam |
|---|---|---|
| topic_parser | 22.1s | 58.3s |
| retrieve | 13.4s | 12.9s |
| quality_filter | 60.9s | 79.8s |
| verify (第一轮) | 310.0s | 657.2s |
| citation_expander | 0.0s (无种子) | 0.0s (无种子) |
| dataset_repo | 72.6s | 67.4s |
| work_package | 74.4s | 2.5s |
| **总计** | **553.5s (9.2min)** | **878.2s (14.6min)** |

注: RPM=10 限制下，31 篇候选 × 6s/call = 186s 最少 verify 时间，实际 310s (含重试)。
