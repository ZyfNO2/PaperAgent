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

    Falls back to raw_topic (verbatim) when method/task/object are empty,
    so a partial parse still produces non-empty query families.
    """
    raw_topic = _strip_topic(raw_topic)
    method = list(topic_atoms.get("method_terms") or [])
    task = list(topic_atoms.get("task_terms") or [])
    obj = list(topic_atoms.get("object_terms") or [])
    atoms_en = list(topic_atoms.get("query_atoms_en") or [])
    domain = (topic_atoms.get("domain_route") or "unknown").strip()

    fb_atom = _pick_first(atoms_en, raw_topic) or raw_topic or "machine learning"

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

    baseline_family: list[str] = []
    if method:
        for m in method[:2]:
            baseline_family.append(_join(m, "classic"))

    return {
        "raw_topic": raw_topic,
        "domain_route": domain,
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
    }


def _dedup(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out
