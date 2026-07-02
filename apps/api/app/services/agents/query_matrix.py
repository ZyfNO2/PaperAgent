"""query_matrix — Re03 SOP §3 Round 0: structured query families.

Inputs:
  raw_topic        — user-issued raw topic (verbatim)
  topic_atoms      — parsed_topic dict from parse_topic()
                    (must contain: method_terms, task_terms, object_terms,
                     query_atoms_en, query_atoms_zh, domain_route)

Output (per Re03 SOP §3):
  {
    "query_families": {
      "core":          [...],   # method + task OR method + object
      "method_task":   [...],   # method_terms × task_terms
      "object_task":   [...],   # object_terms × task_terms
      "dataset":       [...],   # task + dataset-name hint
      "repo":          [...],   # task + implementation hint
      "survey":        [...],   # task + survey
      "benchmark":     [...],   # task + benchmark
      "baseline":      [...]    # method + baseline classic name
    },
    "axes": {
      "method_terms":  [...],
      "task_terms":    [...],
      "object_terms":  [...],
      "domain_route":  str
    }
  }

Constraints (Re03 SOP §3.0):
  - NO network calls.
  - NO LLM calls.
  - NO candidate generation.
  - NO Chinese-to-English fallback that produces 'machine learning'.
  - NO single-`if "检测" in topic` routing.

Ponytail: ~150 lines, pure string assembly. The LLM still gets to refine
at Re03 Round 2 (result_expander); query_matrix just gives it a richer
seed.
"""

from __future__ import annotations

from typing import Any


def _join(*parts: str | None) -> str:
    return " ".join((p or "").strip() for p in parts if (p or "").strip())


def _strip_topic(topic: str) -> str:
    return " ".join((topic or "").split())


def _pick_first(terms: list[str], fallback: str = "") -> str:
    for t in terms:
        if t and t.strip():
            return t.strip()
    return fallback


def build_query_matrix(raw_topic: str, topic_atoms: dict[str, Any]) -> dict[str, Any]:
    """Build the 8-family query matrix for one parsed topic.

    Re04 SOP §1.2 修复 3: 删除 `machine learning` fallback。无法解析时
    在结果里标 ``needs_clarification=True``，由 orchestrator 走「先
    提示用户澄清」路径，不允许 LLM-dead-path 用泛化词骗过。

    Falls back to raw_topic (verbatim) when method/task/object are empty,
    so a partial parse still produces non-empty query families.
    """
    raw_topic = _strip_topic(raw_topic)
    method = list(topic_atoms.get("method_terms") or [])
    task = list(topic_atoms.get("task_terms") or [])
    obj = list(topic_atoms.get("object_terms") or [])
    atoms_en = list(topic_atoms.get("query_atoms_en") or [])
    domain = (topic_atoms.get("domain_route") or "unknown").strip()

    # No more 'machine learning' fallback. Use raw_topic verbatim if
    # atoms_en is empty; if THAT is also empty, signal needs_clarification.
    needs_clarification = False
    if atoms_en:
        fb_atom = _pick_first(atoms_en, raw_topic) or raw_topic
    elif raw_topic:
        # Verbatim raw topic as the single fallback atom; this is the
        # user's own words, not a generic ML term.
        fb_atom = raw_topic
    else:
        # Nothing to fall back on — orchestrator should ask user.
        fb_atom = ""
        needs_clarification = True

    core: list[str] = []
    if method and task:
        core.append(_join(_pick_first(method), _pick_first(task)))
        core.append(_join(_pick_first(method, fb_atom), _pick_first(task, fb_atom)))
    if method and obj:
        core.append(_join(_pick_first(method), _pick_first(obj)))
    if not core and fb_atom:
        core.append(fb_atom)

    method_task: list[str] = []
    for m in method[:2] or [None]:
        for t in task[:2] or [None]:
            q = _join(m, t) or fb_atom
            if q and q not in method_task:
                method_task.append(q)

    object_task: list[str] = []
    for o in obj[:2] or [None]:
        for t in task[:2] or [None]:
            q = _join(o, t) or fb_atom
            if q and q not in object_task:
                object_task.append(q)

    dataset_family: list[str] = []
    if task:
        dataset_family.append(_join(_pick_first(task), "dataset"))
    if obj:
        dataset_family.append(_join(_pick_first(obj), "dataset"))

    repo_family: list[str] = []
    if task:
        repo_family.append(_join(_pick_first(task), "github"))
        repo_family.append(_join(_pick_first(task), "implementation"))
    if method:
        repo_family.append(_join(_pick_first(method), _pick_first(task, fb_atom)))

    survey_family: list[str] = []
    benchmark_family: list[str] = []
    if task:
        survey_family.append(_join(_pick_first(task), "survey"))
        benchmark_family.append(_join(_pick_first(task), "benchmark"))
    if domain and domain != "unknown":
        survey_family.append(_join(domain.replace("_", " "), "survey"))

    # Re04-fix SOP §2 — four-layer fallback for baseline_family.
    # Layer 1: method × task (most precise — what we want).
    # Layer 2: method-only (no task terms to combine with).
    # Layer 3: task-only (Chinese topic where LLM parse dropped method).
    # Layer 4: fb_atom (verbatim raw_topic — last resort, MUST be flagged).
    #
    # The old code required `if method:` and appended a "classic" suffix.
    # That broke Case 027 (pure Chinese topic → method_terms=[]) and left
    # Case 016 with "visual SLAM classic" — a non-term suffix that the
    # English APIs treat as noise. Reference: AutoResearchClaw search.py
    # search_papers() uses plain terminology, no semantic-label suffix.
    baseline_family: list[str] = []
    baseline_fallback_reason: str | None = None
    # Re05 task B (SOP §3): canonical baseline registry feeds queries ONLY.
    # S66v: entries must never enter the candidate pool; they only seed
    # baseline queries that get fetched from real adapters.
    try:
        from .data.canonical_baselines import load_canonical_baselines
        _canonical_baselines = load_canonical_baselines(domain)
    except Exception:  # noqa: BLE001
        _canonical_baselines = []
    if _canonical_baselines:
        first_task = _pick_first(task, "")
        for _cb in _canonical_baselines[:4]:
            q = _join(_cb, first_task) if first_task else _cb
            if q and q not in baseline_family:
                baseline_family.append(q)
        if baseline_family:
            baseline_fallback_reason = None  # exact canonical, no degradation
    if not baseline_family and method and task:
        for m in method[:2]:
            for t in task[:2]:
                q = _join(m, t)
                if q and q not in baseline_family:
                    baseline_family.append(q)
    if not baseline_family and method:
        baseline_fallback_reason = baseline_fallback_reason or "no_task_terms_use_method_only"
        for m in method[:2]:
            if m and m not in baseline_family:
                baseline_family.append(m)
    if not baseline_family and task:
        baseline_fallback_reason = baseline_fallback_reason or "no_method_terms_use_task_only"
        for t in task[:2]:
            if t and t not in baseline_family:
                baseline_family.append(t)
    if not baseline_family:
        baseline_fallback_reason = baseline_fallback_reason or "no_lexical_terms_use_raw_topic_fallback"
        if fb_atom and fb_atom not in baseline_family:
            baseline_family.append(fb_atom)

    return {
        "raw_topic": raw_topic,
        "domain_route": domain,
        "needs_clarification": needs_clarification,
        "query_families": {
            "core": _dedup(core)[:6],
            "method_task": _dedup(method_task)[:6],
            "object_task": _dedup(object_task)[:6],
            "dataset": _dedup(dataset_family)[:4],
            "repo": _dedup(repo_family)[:4],
            "survey": _dedup(survey_family)[:4],
            "benchmark": _dedup(benchmark_family)[:4],
            "baseline": _dedup(baseline_family)[:4],
        },
        "axes": {
            "method_terms": method,
            "task_terms": task,
            "object_terms": obj,
            "domain_route": domain,
        },
        "fb_atom": fb_atom,
        "baseline_fallback_reason": baseline_fallback_reason,
    }


def _dedup(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out
