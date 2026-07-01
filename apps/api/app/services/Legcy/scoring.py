"""Evidence scoring (SOP §7.3-7.5).

公式 (SOP §7.3 Step 5 + §7.4 + §7.5):
- PaperRelevance = 0.25*title_match + 0.25*abstract_match + 0.15*task_match
                 + 0.15*object_match + 0.10*method_match + 0.10*recency
- DatasetScore = 0.20*existence + 0.20*accessibility + 0.15*annotation_match
                + 0.15*task_match + 0.10*license_clarity + 0.10*baseline_available
                + 0.10*scale
- RepoScore = 0.15*readme + 0.15*license + 0.15*train_script + 0.15*eval_script
             + 0.10*pretrained + 0.10*requirements + 0.10*recency + 0.10*issue_health

论文类型分类 (SOP §7.3 Step 6): survey / baseline_method / application /
dataset_paper / benchmark / case_study / irrelevant

每个评分函数返回 (score, breakdown_dict) 方便前端可视化.
"""

from __future__ import annotations

import re
from typing import Any


# ---------- 通用工具 ---------- #


def _tokenize(s: str) -> set[str]:
    """分词: 小写 + 拆 a-z0-9 + 中文."""

    if not s:
        return set()
    return set(re.findall(r"[a-z0-9一-龥]+", s.lower()))


def _match_score(text: str, words: list[str]) -> float:
    """text 与 words 列表的重合度: |text ∩ words| / |words|.

    兼顾子串匹配 (YOLO vs YOLOv8): 任一 word 的 token 出现在 text token 里
    或 text 里含 word 子串, 算命中.
    """

    if not words:
        return 0.0
    text_tokens = _tokenize(text or "")
    if not text_tokens:
        return 0.0
    text_low = (text or "").lower()
    matched = 0
    for w in words:
        w_tokens = _tokenize(w)
        if w_tokens and (w_tokens & text_tokens):
            matched += 1
            continue
        # 子串匹配: 任一 word token 在 text_low 中出现
        if any(w_t in text_low for w_t in w_tokens if w_t):
            matched += 1
    return matched / len(words)


def _recency_score(year: int | None, current_year: int = 2026) -> float:
    """3 年内=1.0 / 6 年=0.6 / 10 年=0.3 / 更老=0.1 / 未知=0.3."""

    if year is None:
        return 0.3
    age = current_year - year
    if age <= 3:
        return 1.0
    if age <= 6:
        return 0.6
    if age <= 10:
        return 0.3
    return 0.1


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------- 论文 (PaperRelevance) ---------- #


def score_paper_relevance(
    paper: dict[str, Any], keywords: dict[str, list[str]],
) -> tuple[float, dict[str, float]]:
    """SOP §7.3 Step 5: 6 维度加权评分 (0-1)."""

    title = paper.get("title", "")
    summary = paper.get("summary", "") or paper.get("summary_zh", "")
    year = paper.get("year")

    title_match = _match_score(title, (keywords.get("method_keywords") or []) + (keywords.get("object_keywords") or []))
    abstract_match = _match_score(summary, (keywords.get("object_keywords") or []) + (keywords.get("task_keywords") or []))
    task_match = _match_score(title + " " + summary, keywords.get("task_keywords") or [])
    object_match = _match_score(title + " " + summary, keywords.get("object_keywords") or [])
    method_match = _match_score(title + " " + summary, keywords.get("method_keywords") or [])
    recency = _recency_score(year)

    score = (
        0.25 * title_match
        + 0.25 * abstract_match
        + 0.15 * task_match
        + 0.15 * object_match
        + 0.10 * method_match
        + 0.10 * recency
    )
    return _clip01(score), {
        "title_match": round(title_match, 3),
        "abstract_match": round(abstract_match, 3),
        "task_match": round(task_match, 3),
        "object_match": round(object_match, 3),
        "method_match": round(method_match, 3),
        "recency": round(recency, 3),
    }


# ---------- 论文类型分类 (§7.3 Step 6) ---------- #


PaperType = str  # "survey" | "baseline_method" | "application" | "dataset_paper" | "benchmark" | "case_study" | "irrelevant" | "unknown"


def classify_paper_type(paper: dict[str, Any]) -> PaperType:
    """基于标题/摘要启发式分类."""

    text = (paper.get("title", "") + " " + (paper.get("summary") or "")).lower()
    if any(k in text for k in ("survey", "review", "综述", "overview", "meta-analysis")):
        return "survey"
    if any(k in text for k in ("benchmark", "leaderboard", "evaluation suite")):
        return "benchmark"
    if any(k in text for k in ("dataset", "benchmark dataset", "数据集", "corpus")):
        return "dataset_paper"
    if any(k in text for k in ("baseline", "propose", "introduce a", "we present", "novel method", "提出", "本文提出", "新方法")):
        return "baseline_method"
    if any(k in text for k in ("case study", "case-study", "field study", "案例", "industrial application")):
        return "case_study"
    if any(k in text for k in ("apply", "applied", "deploy", "application of", "应用", "实践")):
        return "application"
    if _match_score(text, paper.get("_keywords_flat", [])) < 0.1 if paper.get("_keywords_flat") else False:
        return "irrelevant"
    return "unknown"


# ---------- 数据集 (DatasetScore) ---------- #


def score_dataset(
    dataset: dict[str, Any], keywords: dict[str, list[str]],
) -> tuple[float, dict[str, float]]:
    """SOP §7.4: 7 维度加权 (0-1)."""

    name = dataset.get("name", "")
    scale = dataset.get("scale", "") or ""
    license_text = dataset.get("license", "") or ""
    download = dataset.get("download", "") or ""
    annotation = dataset.get("annotation", "") or ""
    fit = dataset.get("fit", "中")
    source = dataset.get("source", "")

    existence = 1.0 if (name and name != "(未匹配公开数据集)") else 0.0
    accessibility = 1.0 if download else (0.6 if source == "public-known" else 0.2)
    annotation_match = _match_score(name + " " + annotation, (keywords.get("object_keywords") or []) + (keywords.get("task_keywords") or []))
    task_match = _match_score(name, keywords.get("task_keywords") or [])
    license_clarity = 1.0 if license_text else 0.3
    baseline_available = 0.8 if source == "public-known" else 0.3
    scale_score = 0.8 if (scale and any(c.isdigit() for c in scale)) else 0.2

    # fit 评级 (高/中/低/未知) 调整 annotation_match 上限
    fit_modifier = {"高": 1.0, "中": 0.7, "低": 0.3, "未知": 0.4}.get(fit, 0.4)
    annotation_match = min(annotation_match, fit_modifier) if annotation_match > 0 else annotation_match

    score = (
        0.20 * existence
        + 0.20 * accessibility
        + 0.15 * annotation_match
        + 0.15 * task_match
        + 0.10 * license_clarity
        + 0.10 * baseline_available
        + 0.10 * scale_score
    )
    return _clip01(score), {
        "existence": round(existence, 3),
        "accessibility": round(accessibility, 3),
        "annotation_match": round(annotation_match, 3),
        "task_match": round(task_match, 3),
        "license_clarity": round(license_clarity, 3),
        "baseline_available": round(baseline_available, 3),
        "scale": round(scale_score, 3),
    }


# ---------- Repo (RepoScore) ---------- #


def score_repo(
    repo: dict[str, Any], paper_year: int | None = None,
) -> tuple[float, dict[str, float]]:
    """SOP §7.5: 8 维度加权 (0-1)."""

    readme = 1.0 if repo.get("has_readme") else 0.0
    license_exists = 1.0 if repo.get("license") else 0.4
    train_script = 1.0 if repo.get("has_training_script") else 0.0
    eval_script = 1.0 if repo.get("has_eval_script") else 0.0
    pretrained = 1.0 if repo.get("has_pretrained_weight") else 0.0
    requirements = 1.0 if repo.get("has_env_file") else 0.0
    recency = _recency_score(paper_year)
    issue_health = 0.7  # heuristic 数据源无 GitHub API, 默认中上 (没有 GitHub API 实时拉)

    score = (
        0.15 * readme
        + 0.15 * license_exists
        + 0.15 * train_script
        + 0.15 * eval_script
        + 0.10 * pretrained
        + 0.10 * requirements
        + 0.10 * recency
        + 0.10 * issue_health
    )
    return _clip01(score), {
        "readme": round(readme, 3),
        "license": round(license_exists, 3),
        "train_script": round(train_script, 3),
        "eval_script": round(eval_script, 3),
        "pretrained": round(pretrained, 3),
        "requirements": round(requirements, 3),
        "recency": round(recency, 3),
        "issue_health": round(issue_health, 3),
    }


# ---------- 批量跑 (整合到 collect_evidence) ---------- #


def _derive_dataset_status(score: float, d: dict[str, Any]) -> str:
    """SOP §7.4 Step 5 状态派生."""

    if d.get("download") and d.get("annotation") and score >= 0.6:
        return "ready"
    if d.get("download") and score >= 0.4:
        return "needs_preprocess"
    if d.get("name") and (d.get("name", "").endswith(")") or d.get("name", "").startswith("(未匹配")):
        return "unverified"
    if score < 0.3:
        return "weak_match"
    if d.get("license") is None or d.get("license") == "":
        return "needs_permission"
    return "unverified"


def _derive_repo_type(r: dict[str, Any]) -> str:
    """SOP §7.5 工程类型派生."""

    url = (r.get("repository_url") or "").lower()
    name = (r.get("name") or "").lower()
    has_readme = r.get("has_readme", False)
    has_train = r.get("has_training_script", False)
    has_eval = r.get("has_eval_script", False)
    if any(k in name + url for k in ("ultralytics", "pytorch", "tensorflow", "huggingface", "openmmlab", "transformers")):
        return "baseline_framework"
    if any(k in url for k in ("github.com/official", "official")):
        return "official"
    if has_readme and has_train and has_eval:
        return "reproduction"
    if "demo" in name or "notebook" in name:
        return "demo_only"
    if not has_readme and not has_train:
        return "not_reproducible"
    return "unknown"


def attach_scores_to_evidence(
    papers: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    repos: list[dict[str, Any]],
    keywords: dict[str, list[str]],
) -> None:
    """给每条 paper/dataset/repo 加 relevance_score / quality_score / paper_type.

    原地修改 (mutate). 0-1 浮点.
    """

    for p in papers:
        s, bd = score_paper_relevance(p, keywords)
        p["relevance_score"] = round(s, 3)
        p["paper_type"] = classify_paper_type(p)
        p["score_breakdown"] = bd
    for d in datasets:
        s, bd = score_dataset(d, keywords)
        d["quality_score"] = round(s, 3)
        d["dataset_status"] = _derive_dataset_status(s, d)
        d["score_breakdown"] = bd
    for r in repos:
        s, bd = score_repo(r, r.get("paper_year") or r.get("year"))
        r["quality_score"] = round(s, 3)
        r["repo_type"] = _derive_repo_type(r)
        r["score_breakdown"] = bd
