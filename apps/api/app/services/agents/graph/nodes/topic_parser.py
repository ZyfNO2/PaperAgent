"""LangGraph node A1 — topic_parser_node.

Parses the topic string into structured `topic_atoms`. Idempotent: if state
already carries a non-empty topic_atoms we return {} (no-op).

Patch fields:
  topic_atoms        required (+ normalized: every list[str], domain is str)
  trace_events       appended
  errors             appended  (only on LLMUnavailable — partial patch persists)
  provider_profile   "fast_json"
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re11_parser as P
from apps.api.app.services.llm_router import call_json, LLMUnavailable

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Allowed domain values — single string (see ResearchState docstring & prompt).
_ALLOWED_DOMAINS = frozenset({
    "signal_timeseries", "vision_2d", "vision_3d", "nlp_llm", "remote_sensing",
    "medical_ai", "energy_power", "control_monitoring", "robotics_control",
    "civil_infra", "unknown",
})

# Fallback skeleton — every value list[str] except domain which is str.
_EMPTY_ATOMS: dict[str, Any] = {
    "method": [], "object": [], "task": [], "scenario": [],
    "domain": "unknown",
    "dataset_terms": [], "baseline_terms": [], "avoid_terms": [],
}





from ._util import emit_trace as _emit


def _as_str_list(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    try:
        return [str(x) for x in v]
    except TypeError:
        return []


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce loose LLM output into the contract shape."""
    out: dict[str, Any] = dict(_EMPTY_ATOMS)
    for key in ("method", "object", "task", "scenario",
                "dataset_terms", "baseline_terms", "avoid_terms"):
        out[key] = _as_str_list(raw.get(key))
    # domain must be one allowed string; reject lists and unknown values.
    dom = raw.get("domain", "unknown")
    if isinstance(dom, list):
        dom = next((str(x).strip().lower() for x in dom if str(x).strip()), "unknown")
    dom = str(dom).strip().lower()
    out["domain"] = dom if dom in _ALLOWED_DOMAINS else "unknown"
    return out


def _contains_negation(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("non-", "without ", "w/o ", "no ", "not "))


def _enforce_literal_topic_guards(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Preserve literal topic signals when the LLM drifts into adjacent terms."""
    out = dict(atoms)
    topic_text = (topic or "").strip()
    lowered = topic_text.lower()

    # If the topic itself is positive-form, drop invented negations.
    if topic_text and not _contains_negation(topic_text):
        for key in ("method", "object", "task", "scenario", "avoid_terms"):
            cleaned = []
            for item in out.get(key) or []:
                text = str(item).strip()
                if text and not _contains_negation(text):
                    cleaned.append(text)
            out[key] = cleaned

    explicit_rag = (
        "retrieval-augmented generation" in lowered
        or "检索增强生成" in topic_text
        or ("检索增强" in topic_text and "生成" in topic_text)
        or re.search(r"\brag\b", lowered) is not None
    )
    if explicit_rag:
        method = list(out.get("method") or [])
        if not any("retrieval-augmented generation" in str(x).lower() for x in method):
            method.insert(0, "retrieval-augmented generation")
        out["method"] = method
        baseline = list(out.get("baseline_terms") or [])
        if not any("retrieval-augmented generation" in str(x).lower() for x in baseline):
            baseline.insert(0, "retrieval-augmented generation")
        out["baseline_terms"] = baseline
        out["avoid_terms"] = [
            x for x in (out.get("avoid_terms") or [])
            if "retrieval" not in str(x).lower() or _contains_negation(str(x))
        ]
        object_terms = list(out.get("object") or [])
        if not any("knowledge base" in str(x).lower() for x in object_terms) and "知识库" in topic_text:
            object_terms.insert(0, "knowledge base")
        out["object"] = object_terms
        if out.get("domain") == "unknown":
            out["domain"] = "nlp_llm"

    if "question answering" in lowered or "问答" in topic_text or re.search(r"\bqa\b", lowered):
        task = list(out.get("task") or [])
        if not any("question answering" in str(x).lower() for x in task):
            task.insert(0, "question answering")
        out["task"] = task
        if out.get("domain") == "unknown":
            out["domain"] = "nlp_llm"

    if "knowledge base" in lowered or "知识库" in topic_text:
        scenario = list(out.get("scenario") or [])
        if not any("knowledge base" in str(x).lower() for x in scenario):
            scenario.insert(0, "knowledge base question answering")
        out["scenario"] = scenario

    if "enterprise" in lowered or "企业" in topic_text:
        scenario = list(out.get("scenario") or [])
        if not any("enterprise" in str(x).lower() for x in scenario):
            scenario.insert(0, "enterprise deployment")
        out["scenario"] = scenario

    return out


def _heuristic_parse(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Extract keywords from Chinese/English topic when LLM returns empty atoms.

    Splits Chinese topics on common delimiters (基于、的、研究、方法) and
    extracts technical English terms from mixed-language topics.
    """
    out = dict(atoms)
    text = (topic or "").strip()
    if not text:
        return out

    # Check for medical/LLM keywords to set domain
    lowered = text.lower()
    if any(kw in text for kw in ("医学", "医疗", "临床", "病历")) or "medical" in lowered:
        out["domain"] = "medical_ai"
        out.setdefault("scenario", []).append("medical AI")
    if any(kw in text for kw in ("大语言模型", "LLM", "GPT", "语言模型")):
        out["domain"] = "nlp_llm" if out["domain"] == "unknown" else out["domain"]
        out["method"] = list(out.get("method") or [])
        if not any("large language model" in str(m).lower() for m in out["method"]):
            out["method"].append("large language model")

    # Extract English technical terms (sequences of ASCII letters, >=2 chars)
    en_terms = re.findall(r'[A-Za-z][A-Za-z0-9\-]{1,}', text)
    for term in en_terms:
        tl = term.lower()
        if tl in ("based", "on", "via", "using", "for", "the", "and", "of", "research", "study", "method"):
            continue
        if tl not in [str(m).lower() for m in (out.get("method") or [])]:
            out["method"] = list(out.get("method") or []) + [term]

    # Extract Chinese technical keywords by splitting on common delimiters
    # e.g. "基于大语言模型的医学问答可信度评估方法研究"
    # → ["大语言模型", "医学问答", "可信度", "评估", "方法"]
    parts = re.split(r'[基于的了吗呢在以及和与和和]', text)
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]

    # If we still have no method, extract the main technical phrase
    if not out.get("method") and parts:
        # Use the longest part as a fallback method keyword
        longest = max(parts, key=len) if parts else ""
        if longest and len(longest) >= 2:
            out["method"] = [longest]

    return out


def _has_chinese(s: str) -> bool:
    return any(ord(c) > 127 for c in str(s))


def _force_translate_keywords(atoms: dict[str, Any]) -> dict[str, Any]:
    """Re3.9.4: Post-process — force-translate any non-ASCII keywords to English."""
    translated = dict(atoms)

    for key in ("method", "object", "task", "scenario", "domain"):
        vals = translated.get(key) or []
        if isinstance(vals, str):
            vals = [vals]
        new_vals: list[str] = []
        for v in vals:
            if _has_chinese(v):
                try:
                    prompt = (
                        f"Translate the following Chinese academic term to English. "
                        f"Output ONLY the English translation, no explanation.\n\n"
                        f"Chinese: {v}\nEnglish:"
                    )
                    result = call_json(
                        prompt,
                        system="You are a translator. Output only the English term.",
                        profile="fast_json",
                        max_tokens=50,
                        timeout=10,
                        expected="dict",
                    )
                    if isinstance(result, dict):
                        en = (
                            result.get("translation", "")
                            or result.get("english", "")
                            or result.get("output", "")
                            or str(result)
                        )
                    else:
                        en = str(result)
                    en = en.strip().strip('"').strip("'").strip()
                    if en and not _has_chinese(en):
                        new_vals.append(en)
                        logger.info("topic_parser: force-translated '%s' -> '%s'", v, en)
                    else:
                        new_vals.append(v)
                except Exception as exc:
                    logger.warning("topic_parser: translate failed for '%s': %s", v, exc)
                    new_vals.append(v)
            else:
                new_vals.append(v)
        translated[key] = new_vals

    return translated


def topic_parser_node(state: ResearchState) -> dict[str, Any]:
    """Parse topic -> topic_atoms. Skips LLM call if atoms already present."""
    topic = state.get("topic") or ""
    existing = state.get("topic_atoms")
    t0 = time.time()

    # Idempotency: a non-empty atom set means we already parsed this case.
    if existing and any(
        existing.get(k) for k in
        ("method", "object", "task", "scenario", "dataset_terms", "baseline_terms")
    ) and isinstance(existing.get("domain"), str):
        trace = _emit("topic_parser", t0,
                      {"topic_len": len(topic)}, {"skipped": True,
                                                   "n_method": len(existing.get("method", []))},
                      [{"tool": "re11_parser.llm", "mode": "skipped"}], "none", [],
                      state_keys=["trace_events"])
        return {"trace_events": [trace]}

    errors_out: list[dict[str, Any]] = []
    atoms: dict[str, Any] = dict(_EMPTY_ATOMS)
    tries = 0

    try:
        built = P.build(topic)
        tries += 1
        raw = call_json(
            built["user"],
            system=built["system"],
            profile="fast_json",
            max_tokens=2500,
            timeout=max(5, _env_int("TOPIC_PARSER_TIMEOUT_S", 60)),
            expected="dict",
            schema_hint=(
                'JSON object with keys: method/object/task/scenario/'
                'domain/dataset_terms/baseline_terms/avoid_terms; '
                'domain is a single string.'
            ),
        )
        atoms = _enforce_literal_topic_guards(
            topic,
            _normalize(raw if isinstance(raw, dict) else {}),
        )
    except Exception as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("topic_parser_node LLM call failed (%s); using empty atoms", kind)
        errors_out.append({"node": "topic_parser", "error": kind})

    # Heuristic fallback: if LLM returned empty or garbage atoms, extract keywords from topic
    # "Garbage" = method contains CJK characters (valid method keywords should be English)
    #   or method is the raw topic verbatim, or method list is empty
    _all_lists_empty = (
        not atoms.get("method") and not atoms.get("object") and not atoms.get("task")
    )
    _has_cjk = any(
        any('\u4e00' <= ch <= '\u9fff' for ch in str(m))
        for m in (atoms.get("method") or [])
    )
    _method_is_garbage = bool(atoms.get("method")) and (
        _has_cjk
        or any(str(m).strip() == topic.strip() or len(str(m).strip()) > 30
               for m in atoms.get("method") or [])
    )
    logger.info("topic_parser heuristic check: all_empty=%s, has_cjk=%s, is_garbage=%s, method=%s",
                _all_lists_empty, _has_cjk, _method_is_garbage, atoms.get("method"))
    if _all_lists_empty or _method_is_garbage:
        atoms = _heuristic_parse(topic, dict(_EMPTY_ATOMS))
        if atoms.get("method") or atoms.get("object") or atoms.get("task"):
            logger.info("topic_parser: heuristic fallback extracted atoms from topic (LLM returned %s)",
                        "garbage" if _method_is_garbage else "empty")

    # Re3.9.4: Force-translate any remaining Chinese keywords to English
    atoms = _force_translate_keywords(atoms)

    trace = _emit("topic_parser", t0,
                  {"topic_len": len(topic)},
                  {"n_method": len(atoms.get("method", [])),
                   "n_object": len(atoms.get("object", [])),
                   "domain": atoms.get("domain")},
                  [{"tool": "re11_parser.llm", "attempts": tries}],
                  "fast_json", errors_out,
                  state_keys=["topic_atoms", "trace_events", "errors",
                              "provider_profile"])

    return {
        "topic_atoms": atoms,
        "trace_events": [trace],
        "errors": errors_out,
        "provider_profile": "fast_json",
    }
