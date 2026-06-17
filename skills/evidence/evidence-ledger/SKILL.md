---
name: evidence-ledger
description: 证据池状态机 + 去重 + 评分汇总 (SOP §4.4 + §4.5 + §8). 整个 evidence pool 的总控.
metadata:
  type: evidence
  scope: internal
---

# evidence-ledger Skill

## 触发条件

- 任何 evidence 入池 / 审核 / 查询 / 重新评分 / 摘要 / 去重检查
- 可行性 5 档 (GO/NARROW/PIVOT/PARK/STOP) 决策前
- 退化路线 (PivotRoute) 生成前

## 输入结构

```python
EvidenceItem:  # Pydantic (apps/api/app/schemas_evidence.py)
    evidence_id: str
    project_id: str
    evidence_type: Literal["paper", "dataset", "repo", "note", "custom"]
    source_mode: Literal["auto_search", "manual", "upload", "import"]
    title: str
    relevance_score: float | None  # paper 评分 (0-1)
    quality_score: float | None    # dataset / repo 评分 (0-1)
    paper_type: Literal[...] = "unknown"
    dataset_status: Literal[...] = "unverified"
    repo_type: Literal[...] = "unknown"
    review_status: Literal["pending", "accepted", "core", "background", "rejected", "needs_check"]
    ...
```

## 输出结构

```python
# SOP §4.4 去重: 重复不新增, 返回 existing_evidence_id
DedupCheckResponse = {
    "is_duplicate": bool,
    "existing_evidence_id": str | None,
    "reason": str | None,  # "same_doi" / "same_arxiv_id" / "similar_title" / "same_github_repo" / "same_dataset_name"
}

# SOP §8.1 rescore
RescoreResponse = {
    "project_id": str,
    "paper_count": int, "dataset_count": int, "repo_count": int,
    "updated_count": int,
    "summary": {"avg_paper_score": float, "avg_dataset_score": float, "avg_repo_score": float},
}

# SOP §8.2 score-summary
ScoreSummaryResponse = {
    "project_id": str,
    "usable_papers": int,     # relevance_score >= 0.3 + type != irrelevant + review != rejected
    "usable_datasets": int,   # quality_score >= 0.4 + status in (ready, needs_preprocess) + review != rejected
    "usable_repos": int,      # quality_score >= 0.4 + type in (official, reproduction, baseline_framework) + review != rejected
    "low_quality_evidence": int,  # score < 0.3
    "rejected_evidence": int,
    "feasibility_inputs": {"paper_quality": "强/中/弱", "dataset_quality": ..., "repo_quality": ...},
}
```

## 评分规则 (SOP §4.4)

### 去重

- **Paper**:
  - DOI 完全相同
  - arxiv_id 完全相同
  - 标题归一化后完全相同
  - 标题 jaccard > 0.92 且年份相同
- **Repo**:
  - GitHub owner/name canonical key 相同 (e.g. ultralytics/ultralytics)
- **Dataset**:
  - canonical name 相同

### 评分汇总 (SOP §4.5 喂入可行性)

- 论文可用: relevance_score ≥ 0.3 + paper_type ≠ irrelevant + review ≠ rejected
- 数据集可用: quality_score ≥ 0.4 + dataset_status ∈ {ready, needs_preprocess} + review ≠ rejected
- 仓库可用: quality_score ≥ 0.4 + repo_type ∈ {official, reproduction, baseline_framework} + review ≠ rejected

### 5 档决策 (SOP §4.5 升级版)

```
niche + 无 dataset → "暂缓"
无可用 dataset 且 无可用 repo → "不建议" (或 "可转向")
可用 papers ≥ 3 + 平均分 ≥ 0.5 + dataset ≥ 1 + repo ≥ 1 + 有 metrics → "可做"
仅 1 缺 → "可转向" (看 3 条 PivotRoute)
其它 → "收缩后可做"
```

## 禁止事项

- 不要让 rejected 证据进入 feasibility 决策 (`usable_*` 过滤已 reject)
- 不要在 rescore 时改 review_status (用户决定)
- 不要重复入池 (DOI / repo owner / dataset name 一致)
- 不要让 `irrelevant` 论文进入 usable_papers

## 测试样例

- rescore 不会让 rejected 状态变成 accepted
- score-summary 中 rejected_evidence 与 usable_* 不重叠
- 同一 DOI 重复 add → 返回 existing_evidence_id

## 参考

- SOP §4.4 + §4.5 + §8 (Plan/PaperAgent_Session05_*.md)
- `apps/api/app/services/evidence.py:rescore_project/score_summary/dedup_check`
- `apps/api/app/services/one_topic.py:judge_feasibility` (5 档决策)
