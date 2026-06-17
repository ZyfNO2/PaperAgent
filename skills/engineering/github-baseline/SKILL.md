---
name: github-baseline
description: GitHub 工程 (baseline) 可复现性评分与类型派生 (SOP §4.3). 工程入池前必经 skill.
metadata:
  type: engineering
  scope: internal
---

# github-baseline Skill

## 触发条件

- 调用 `apps/api/app/services/scoring.py:score_repo` 时自动激活
- baseline (heuristic 或 manual) 入 evidence pool 前
- 用户点 "重新评分证据" 时 (rescore)

## 输入结构

```python
repo: dict = {
    "name": str,
    "repository_url": str | None,   # GitHub URL
    "has_readme": bool,
    "license": str | None,
    "has_training_script": bool,
    "has_eval_script": bool,
    "has_pretrained_weight": bool,
    "has_env_file": bool,           # requirements.txt / environment.yml
    "paper_year": int | None,       # 关联论文年份
}
```

## 输出结构

```python
(score: float, breakdown: dict)  # score ∈ [0, 1]
repo_type: Literal[
    "official", "reproduction", "baseline_framework",
    "demo_only", "not_reproducible", "unknown",
]
```

## 评分规则

```
RepoScore = 0.15 × readme
          + 0.15 × license_exists
          + 0.15 × train_script
          + 0.15 × eval_script
          + 0.10 × pretrained
          + 0.10 × requirements
          + 0.10 × recency
          + 0.10 × issue_health
```

- `license_exists`: 有 license → 1.0; 无 → 0.4 (heuristic 默认, 避免压分)
- `issue_health`: heuristic 默认 0.7 (无 GitHub API 实时数据)
- type 分类按 SOP §4.3 优先级 (官方框架 → official → reproduction → demo_only → not_reproducible)

## 禁止事项

- 不要在 score < 0.4 时把 repo 标 accepted
- 不要在 `repository_url` 为空时给 type="official" 或 "reproduction"
- 不要把仅有 notebook 的 repo 标 type="baseline_framework"

## 测试样例

- ultralytics/ultralytics (README + license + train + eval + pretrained) → score ≈ 0.85, type=baseline_framework
- microsoft/Swin-Transformer → score ≈ 0.75, type=official
- 用户 demo notebook (无 README) → score ≈ 0.3, type=demo_only
- 空 name + 无 URL → score < 0.2, type=not_reproducible

## 参考

- SOP §4.3 (Plan/PaperAgent_Session05_*.md)
- `apps/api/app/services/scoring.py:184-217`
- 参考 Agent Research Skills (不直接照搬)
