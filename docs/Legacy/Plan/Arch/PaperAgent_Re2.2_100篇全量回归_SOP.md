# PaperAgent Re2.2 100 篇全量回归 SOP

> 承接：Re2.1 完工报告（feasibility 区分度 + innovation 65% + BLOCK 降至 58%）
> **本 SOP 设计为全程无人值守执行。**
> 预计总时长：4-6 小时（100 篇 × ~100s + 分析 + 报告）。
> 模型：DeepSeek (主)。

## 0. 前置条件

- Re2.1 审核通过。
- `docs/PaperAgent_工科学位论文爬取测试集_100篇.md` 可读（含 100 篇题目 + 领域 + 难度标注）。
- `tmp_re21_eval/smoke_20/` 有 20 篇 baseline 可对比。
- DeepSeek API key 可用。

## 1. 本轮目标

用 100 篇工科论文测试集做**全量回归**，验证系统稳定性和领域覆盖，发现 edge case，输出可交付的质量报告。

必须完成：

1. **100 篇全量跑通**：串行跑全部 100 篇，DeepSeek 主路径。
2. **按领域/难度统计分析**：输出每 个领域 × 难度档 的 accept/feasibility/review/innovation 矩阵。
3. **edge case 发现**：标记 graph 未完成 / 0 verified / 0 innovation / review=ACCEPT 的 case。
4. **与 Re2.1 smoke_20 对比**：验证 20 篇重复 case 的结果一致性。
5. **质量报告**：输出可交付的 100 篇质量报告。

不做：

- 代码修改（纯测试 + 分析）。
- prompt 调优。
- 前端改动。
- 新增功能。

## 2. 模型策略

```text
FAST_JSON_PRIMARY=deepseek
LLM_PROFILE=deepseek
```

## 3. 100 篇选题

从 `docs/PaperAgent_工科学位论文爬取测试集_100篇.md` §5 提取全部 100 篇（ENG-THESIS-001 ~ ENG-THESIS-100）。

每篇的题名、领域、难度从文档中解析。

### 领域分布（文档 §3.1）

| 领域 | 数量 |
|---|---|
| 三维视觉/SLAM/点云 | 19 |
| 土木/交通基础设施损伤检测 | 16 |
| 工业缺陷检测/机器视觉 | 15 |
| 自动驾驶/交通感知 | 13 |
| 电力/轨交巡检视觉 | 10 |
| 工科AI/计算机视觉 | 9 |
| 机器人/机械臂实验系统 | 7 |
| 遥感/无人机目标检测 | 5 |
| 能源装备/故障诊断 | 4 |
| 医学/人体三维视觉 | 2 |

### 难度分布（文档 §3.2）

| 难度 | 数量 |
|---|---|
| 低-中 | 16 |
| 中 | 46 |
| 中-高 | 26 |
| 高 | 12 |

## 4. Phase 设计

### Phase 1：100 篇全量跑 (3-4 小时, 无人值守)

#### 运行

```bash
cd G:\PaperAgent
set FAST_JSON_PRIMARY=deepseek
python apps/api/scripts/re22_batch_run.py --provider deepseek --cases all_100
```

脚本自动：
- 从 `docs/PaperAgent_工科学位论文爬取测试集_100篇.md` 解析全部 100 篇题名。
- 串行跑 100 篇（每篇 ~100-150s，总 ~3-4 小时）。
- 每篇完成后自动调 validator。
- 输出到 `tmp_re22_eval/all_100/<case_id>/`。
- 某篇 crash → 记录 error → 继续下一篇。
- 连续 3 篇 crash → 暂停 60s 后重试 1 次，仍 crash 则跳过。
- API 超时（5min）→ 记录 timeout → 跳过。
- 每篇完成后追加到 `tmp_re22_eval/all_100/summary_deepseek.json`。
- 每 10 篇输出一次进度到 `tmp_re22_eval/progress.log`。

#### 验证

- [ ] `summary_deepseek.json` 存在，含 100 个 case。
- [ ] ≥85/100 has_final=True（允许 15 篇因 API 超时/crash 失败）。
- [ ] 每篇有 `state.json` + `trace.json`。
- [ ] 连续 crash < 5 次（系统稳定性验证）。

### Phase 2：统计分析 (30min, 无人值守)

#### 运行

```bash
python apps/api/scripts/re22_analyze.py --dir tmp_re22_eval/all_100
```

输出 `tmp_re22_eval/analysis.json`，包含：

**维度 1：领域 × 指标矩阵**

```json
{
  "domain_matrix": {
    "三维视觉/SLAM": {
      "n": 19,
      "avg_accept": 5.2,
      "avg_feasibility_score": 45,
      "feasibility_verdicts": {"feasible": 3, "risky": 10, "not_recommended": 6},
      "review_verdicts": {"ACCEPT": 1, "MINOR_REVISION": 8, "BLOCK": 10},
      "innovation_rate": 0.68,
      "completion_rate": 0.95
    },
    "工业缺陷检测": { ... },
    ...
  }
}
```

**维度 2：难度 × 指标矩阵**

```json
{
  "difficulty_matrix": {
    "低-中": {
      "n": 16,
      "avg_accept": 8.5,
      "avg_feasibility_score": 55,
      "innovation_rate": 0.75,
      "block_rate": 0.25
    },
    "中": { ... },
    "中-高": { ... },
    "高": {
      "n": 12,
      "avg_accept": 1.2,
      "avg_feasibility_score": 20,
      "innovation_rate": 0.08,
      "block_rate": 0.92
    }
  }
}
```

**维度 3：edge case 标记**

```json
{
  "edge_cases": {
    "graph_not_completed": ["ENG-THESIS-046", ...],
    "zero_verified": ["ENG-THESIS-046", ...],
    "zero_innovation": ["ENG-THESIS-015", ...],
    "review_accepted": ["ENG-THESIS-018", ...],
    "feasibility_feasible": ["ENG-THESIS-018", ...],
    "high_difficulty_with_innovation": ["ENG-THESIS-066", ...]
  }
}
```

**维度 4：与 Re2.1 smoke_20 一致性对比**

```json
{
  "consistency_check": {
    "n_common": 20,
    "feasibility_consistent": 17,
    "review_consistent": 15,
    "innovation_consistent": 18,
    "inconsistency_cases": [
      {
        "case_id": "ENG-THESIS-016",
        "re21_feasibility": "risky",
        "re22_feasibility": "feasible",
        "reason": "LLM 非确定性, 不同运行可能有不同结果"
      }
    ]
  }
}
```

#### 验证

- [ ] `analysis.json` 存在。
- [ ] domain_matrix 包含全部 10 个领域。
- [ ] difficulty_matrix 包含全部 4 个难度档。
- [ ] edge_cases 的每个列表有内容（说明发现了 edge case）。

### Phase 3：自测验证 (15min, 无人值守)

#### 运行

```bash
python apps/api/scripts/re22_self_test.py --dir tmp_re22_eval/all_100
```

对全部 100 篇跑 4 个 validator：

| Validator | 检查 | 通过标准 |
|---|---|---|
| e2e_completeness | graph 完整 | ≥85/100 pass |
| paper_authenticity | 0 污染 | 100/100 pass |
| topic_relevance | ≥30% 相关 | ≥80/100 pass |
| feasibility_diversity | ≥2 verdict + spread≥20 | batch pass |

输出 `tmp_re22_eval/self_test_report.json`。

#### 验证

- [ ] `self_test_report.json` 存在。
- [ ] paper_authenticity 100/100 pass。
- [ ] e2e_completeness ≥85/100 pass。
- [ ] topic_relevance ≥80/100 pass。
- [ ] feasibility_diversity pass。

### Phase 4：质量报告生成 (15min, 无人值守)

#### 运行

```bash
python apps/api/scripts/re22_generate_report.py --dir tmp_re22_eval
```

自动生成 `Plan/PaperAgent_Re2.2_完工报告.md`，包含：

#### 报告内容

**1. 总览**

| 指标 | 值 |
|---|---|
| 总篇数 | 100 |
| graph 完成 | X/100 |
| 平均 accept | X |
| 平均 feasibility score | X |
| feasibility verdict 分布 | feasible: X, risky: X, not_recommended: X |
| review verdict 分布 | ACCEPT: X, MINOR_REVISION: X, BLOCK: X |
| innovation > 0 | X/100 |
| 平均耗时 | Xs |

**2. 领域矩阵表**

| 领域 | n | 完成 | avg accept | avg score | feasible | risky | not_rec | BLOCK | MR | innovation |
|---|---|---|---|---|---|---|---|---|---|---|
| 三维视觉/SLAM | 19 | | | | | | | | | |
| 土木/基础设施 | 16 | | | | | | | | | |
| ... | | | | | | | | | | |

**3. 难度矩阵表**

| 难度 | n | avg accept | avg score | innovation rate | block rate |
|---|---|---|---|---|---|
| 低-中 | 16 | | | | |
| 中 | 46 | | | | |
| 中-高 | 26 | | | | |
| 高 | 12 | | | | |

**4. Edge Case 分析**

| 类型 | 数量 | 典型 case | 分析 |
|---|---|---|---|
| graph 未完成 | X | | |
| 0 verified | X | | |
| 0 innovation | X | | |
| review=ACCEPT | X | | |
| feasibility=feasible | X | | |
| 高难度+有创新 | X | | |

**5. 与 Re2.1 smoke_20 一致性**

| 指标 | 一致率 | 不一致 case |
|---|---|---|
| feasibility verdict | X/20 | |
| review verdict | X/20 | |
| innovation 有无 | X/20 | |

**6. 自测结果**

| Validator | pass/total |
|---|---|
| e2e_completeness | X/100 |
| paper_authenticity | X/100 |
| topic_relevance | X/100 |
| feasibility_diversity | pass/fail |

**7. 已知限制**

**8. 建议下一步**

## 5. 脚本设计

### re22_batch_run.py

```python
"""Re2.2 100 篇全量回归。

用法:
    python apps/api/scripts/re22_batch_run.py --provider deepseek --cases all_100
"""

# 从 docs/PaperAgent_工科学位论文爬取测试集_100篇.md 解析全部 100 篇
# 或从硬编码列表加载

ALL_100 = [
    ("ENG-THESIS-001", "室内移动机器人目标搜寻与抓取研究"),
    ("ENG-THESIS-002", "基于深度学习的磁瓦在线检测技术研究"),
    # ... 全部 100 篇
]

def main():
    # 串行跑, 每篇 ~100-150s
    # 连续 3 crash → 暂停 60s → 重试 1 次
    # API 超时 5min → 跳过
    # 每 10 篇输出进度
    # 输出 summary JSON
```

### re22_analyze.py

```python
"""分析 100 篇结果, 输出领域/难度/edge case 矩阵。"""
# 读取所有 state.json
# 按领域/难度分组统计
# 标记 edge case
# 与 Re2.1 smoke_20 对比一致性
```

### re22_self_test.py

```python
"""对 100 篇跑 4 个 validator。"""
# 复用 Re1.5 的 validator
# 输出 batch self_test_report.json
```

### re22_generate_report.py

```python
"""自动生成完工报告 Markdown。"""
# 读取 analysis.json + self_test_report.json
# 生成 Plan/PaperAgent_Re2.2_完工报告.md
```

## 6. 执行者规则

### 6.1 失败处理

- 单篇 crash → 记录 → 继续下一篇。
- 连续 3 篇 crash → 暂停 60s → 重试 1 次 → 仍 crash 则跳过该篇。
- API 超时（5min）→ 记录 timeout → 跳过。
- 总失败 > 15 篇 → 停止，输出部分结果。

### 6.2 进度输出

每 10 篇输出到 `tmp_re22_eval/progress.log`：

```
[10/100] 10 完成, 0 失败, avg=112s, elapsed=1120s
[20/100] 19 完成, 1 失败 (ENG-THESIS-046), avg=108s, elapsed=2160s
...
```

### 6.3 无代码修改

本 SOP **不修改任何代码文件**。纯测试 + 分析 + 报告。

如果发现代码 bug：
- 记录到 `tmp_re22_eval/bugs_found.md`。
- 不在本次修复。
- 在完工报告的"已知限制"中列出。

## 7. 禁止事项

- 禁止修改代码（纯测试）。
- 禁止跳过 Phase 1（全量跑是核心）。
- 禁止用 mock 数据。
- 禁止用 VOAPI / MiniMax。
- 禁止覆盖旧 eval 目录。
- 禁止在发现 bug 时现场修复（记录, 不修复）。

## 8. 交付物

脚本：

- `apps/api/scripts/re22_batch_run.py` 🆕
- `apps/api/scripts/re22_analyze.py` 🆕
- `apps/api/scripts/re22_self_test.py` 🆕
- `apps/api/scripts/re22_generate_report.py` 🆕

数据：

- `tmp_re22_eval/all_100/` (100 case 目录 + summary)
- `tmp_re22_eval/analysis.json`
- `tmp_re22_eval/self_test_report.json`
- `tmp_re22_eval/progress.log`
- `tmp_re22_eval/bugs_found.md` (如有)

报告：

- `Plan/PaperAgent_Re2.2_完工报告.md`

## 9. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | 100 篇全跑 | summary 有 100 个 case |
| 2 | ≥85 完成 | has_final count |
| 3 | 连续 crash < 5 | progress.log |
| 4 | 领域矩阵 10 领域 | analysis.json |
| 5 | 难度矩阵 4 档 | analysis.json |
| 6 | edge case 已标记 | analysis.json |
| 7 | smoke_20 一致性 ≥75% | analysis.json |
| 8 | paper_authenticity 100/100 | self_test |
| 9 | e2e_completeness ≥85/100 | self_test |
| 10 | topic_relevance ≥80/100 | self_test |
| 11 | feasibility_diversity pass | self_test |
| 12 | 完工报告完整 | Phase 4 |
| 13 | bugs_found 记录（如有） | 文件检查 |
| 14 | VOAPI/MiniMax = 0 | 全程 |
