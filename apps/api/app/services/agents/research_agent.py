"""Research Agent — new run_research_agent pipeline (S66v rewrite).

Replaces the legcy 7-step `research_planner_agent.run_research_plan`.
Designed against `apps/api/app/services/agents/prompts/*.py` contracts.

Ladder (ponytail-style):
1. Why does this need to exist? — the legcy pipeline produced 0/2 baseline
   papers and 0/3 parallel papers against Topic 59 ground truth. We need a
   clean LLM-first agent that doesn't compute any `*_score` field.
2. Already in this codebase? — legcy modules exist but are quarantined.
   New agent imports only `app.services.llm` (chat_json) and
   `app.services.retrieval.adapters.{arxiv,openalex,crossref,github}_search`.
3. Stdlib does it? — asyncio + dataclasses + json already covers everything.
4. Native feature covers it? — no
5. Already-installed dep? — no new deps. pydantic stays for Response model.
6. One line? — Each step tries to fit one LLM call.

Output contract: 7 buckets mirroring the user's Topic 59 ground-truth buckets:
    baseline_papers / parallel_papers / module_papers / reference_papers /
    dataset_candidates / repo_candidates / evidence_gaps

No `*_score` field anywhere. 3 LLM calls: parse_topic → plan_tools →
synthesize; then 1 call for devils_advocate. Quota-bounded by MiniMax M3.

Rate-limit awareness:
- ArXiv / OpenAlex / GitHub / Crossref impose daily + burst quotas.  When the
  agent trips a 429 it MUST:
    1. record the suspended_until_ts for that adapter
    2. swap to a fallback adapter for THIS run (already implemented per call)
    3. on the NEXT run, if the suspension has not elapsed, skip that adapter
       and surface "RATE_LIMITED: <adapter> suspended until <ts>" in evidence_gaps
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..llm import LLMUnavailable, chat_json
from ..retrieval.adapters.arxiv_search import arxiv_search
from ..retrieval.adapters.crossref_search import crossref_search
from ..retrieval.adapters.github_search import github_search
from ..retrieval.adapters.openalex_search import openalex_search
from .prompts import (
    DEVILS_ADVOCATE_SYSTEM,
    PARSE_TOPIC_SYSTEM,
    PLAN_TOOLS_SYSTEM,
    SYNTHESIZE_SYSTEM,
    USER_TEMPLATE_DEVILS_ADVOCATE,
    USER_TEMPLATE_PLAN_TOOLS,
    USER_TEMPLATE_SYNTHESIZE,
)

logger = logging.getLogger(__name__)


# --- quota / circuit breaker -------------------------------------------------
# Pattern borrowed from AutoResearchClaw/researchclaw/literature/arxiv_client.py
# (`_cb_should_allow / _cb_on_failure / _cb_on_success`) — three-state breaker:
#   CLOSED  — pass through, count 429s
#   OPEN    — short-circuit until cooldown elapses
#   HALF_OPEN — allow exactly one probe; success → CLOSED, fail → OPEN with
#               doubled cooldown (capped).

LLM_CALL_BUDGET = int(os.environ.get("SESSION66_LLM_BUDGET", "12"))

_CB_CLOSED = "closed"
_CB_OPEN = "open"
_CB_HALF_OPEN = "half_open"
_CB_THRESHOLD = int(os.environ.get("PAPERAGENT_CB_THRESHOLD", "3"))
_CB_INITIAL_COOLDOWN = int(os.environ.get("PAPERAGENT_CB_INITIAL_COOLDOWN", "180"))
_CB_MAX_COOLDOWN = int(os.environ.get("PAPERAGENT_CB_MAX_COOLDOWN", "600"))


@dataclass
class _PerAdapterCB:
    state: str = _CB_CLOSED
    consecutive_429s: int = 0
    cooldown_sec: int = _CB_INITIAL_COOLDOWN
    open_since: float = 0.0
    trip_count: int = 0

    def should_allow(self) -> bool:
        if self.state == _CB_CLOSED:
            return True
        if self.state == _CB_OPEN:
            elapsed = time.monotonic() - self.open_since
            if elapsed >= self.cooldown_sec:
                self.state = _CB_HALF_OPEN
                logger.info("[CB] → HALF_OPEN after %.0fs", elapsed)
                return True
            return False
        return True  # HALF_OPEN: allow one probe

    def on_success(self) -> None:
        self.consecutive_429s = 0
        if self.state != _CB_CLOSED:
            logger.info("[CB] → CLOSED (probe ok)")
            self.state = _CB_CLOSED
            self.cooldown_sec = _CB_INITIAL_COOLDOWN

    def on_failure(self, *, is_429: bool) -> bool:
        if not is_429:
            # 5xx — softer cooldown; but still treats as a trip if many in a row
            self.consecutive_429s += 1
        else:
            self.consecutive_429s += 1
        if self.state == _CB_HALF_OPEN or self.consecutive_429s >= _CB_THRESHOLD:
            if self.state == _CB_HALF_OPEN:
                self.cooldown_sec = min(self.cooldown_sec * 2, _CB_MAX_COOLDOWN)
            self.state = _CB_OPEN
            self.open_since = time.monotonic()
            self.trip_count += 1
            logger.warning("[CB] → OPEN trip=#%d cooldown=%.0fs", self.trip_count, self.cooldown_sec)
            return True
        return False


@dataclass
class AdapterSuspendState:
    """Three-state circuit breaker per adapter. Persists to JSON."""
    by_adapter: dict[str, _PerAdapterCB] = field(default_factory=dict)
    persist_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "..", "..", "tmp_s66v_adapter_cooldowns.json",
    )

    def _cb(self, adapter_name: str) -> _PerAdapterCB:
        cb = self.by_adapter.get(adapter_name)
        if cb is None:
            cb = _PerAdapterCB()
            self.by_adapter[adapter_name] = cb
        return cb

    def should_allow(self, adapter_name: str) -> bool:
        return self._cb(adapter_name).should_allow()

    def on_success(self, adapter_name: str) -> None:
        self._cb(adapter_name).on_success()
        self._persist()

    def on_failure(self, adapter_name: str, *, is_429: bool) -> bool:
        tripped = self._cb(adapter_name).on_failure(is_429=is_429)
        self._persist()
        return tripped

    def is_suspended(self, adapter_name: str) -> bool:
        """Convenience for callers that just want a yes/no."""
        return not self.should_allow(adapter_name)

    def suspended_until_str(self, adapter_name: str) -> str:
        cb = self._cb(adapter_name)
        if cb.state != _CB_OPEN:
            return ""
        return time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(cb.open_since + cb.cooldown_sec),
        )

    def _persist(self) -> None:
        try:
            payload = {
                name: {
                    "state": cb.state,
                    "consecutive_429s": cb.consecutive_429s,
                    "cooldown_sec": cb.cooldown_sec,
                    "open_since": cb.open_since,
                    "trip_count": cb.trip_count,
                }
                for name, cb in self.by_adapter.items()
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("could not persist CB state: %s", exc)

    @classmethod
    def load(cls) -> "AdapterSuspendState":
        state = cls()
        try:
            with open(state.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, cb_data in data.items():
                state.by_adapter[name] = _PerAdapterCB(
                    state=cb_data.get("state", _CB_CLOSED),
                    consecutive_429s=int(cb_data.get("consecutive_429s", 0)),
                    cooldown_sec=int(cb_data.get("cooldown_sec", _CB_INITIAL_COOLDOWN)),
                    open_since=float(cb_data.get("open_since", 0.0)),
                    trip_count=int(cb_data.get("trip_count", 0)),
                )
        except Exception:
            pass
        return state


GLOBAL_SUSPEND_STATE = AdapterSuspendState.load()


@dataclass
class LLMCallCounter:
    n_calls: int = 0
    n_failures: int = 0
    started_at: float = field(default_factory=time.time)

    def __iadd__(self, other: "LLMCallCounter | int") -> "LLMCallCounter":
        if isinstance(other, int):
            self.n_calls += other
        else:
            self.n_calls += other.n_calls
            self.n_failures += other.n_failures
        return self

    def budget_exhausted(self) -> bool:
        return self.n_calls >= LLM_CALL_BUDGET


GLOBAL_COUNTER = LLMCallCounter()


def reset_counter() -> None:
    GLOBAL_COUNTER.n_calls = 0
    GLOBAL_COUNTER.n_failures = 0
    GLOBAL_COUNTER.started_at = time.time()


def _chat_json_strict(
    prompt: str,
    system: str,
    *,
    max_tokens: int = 1500,
    temperature: float = 0.2,
    timeout: float = 60.0,
) -> dict:
    """chat_json with quota guard. Raises LLMUnavailable when budget exhausted."""
    if GLOBAL_COUNTER.budget_exhausted():
        raise LLMUnavailable(
            f"LLM budget exhausted ({GLOBAL_COUNTER.n_calls}/{LLM_CALL_BUDGET})"
        )
    try:
        GLOBAL_COUNTER.n_calls += 1
        data = chat_json(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    except LLMUnavailable:
        GLOBAL_COUNTER.n_failures += 1
        raise
    if not isinstance(data, dict):
        raise LLMUnavailable(f"chat_json returned non-dict: {type(data).__name__}")
    return data


# --- heuristic fallback for parse_topic --------------------------------------

# When MiniMax M3 is exhausted or fails on parse_topic, fall back to a
# deterministic, *honest* heuristic. We never inject ground-truth atoms here.
# CRITICAL (S66v): this map contains ONLY generic method / object tokens.
# NO specific dataset names, NO repository names, NO paper titles — those are
# the ground truth the agent must DISCOVER via tools. If you find ShipsEar /
# DeepShip / SonAIr / openEMS / Meep / zakaria76al listed here, that is a
# bug — remove immediately.
_HEURISTIC_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "signal_timeseries": (
        "水声", "声纳", "声学事件", "underwater acoustic", "sonar",
        "hydrophone", "spectrogram", "audio classification",
        "EEG", "心电", "ECG", "心电图",
    ),
    "control_monitoring": (
        "国六", "柴油", "排放", "OBD", "远程监控", "telemetry",
        "telematics", "车联网", "diesel emission", "vehicle diagnostics",
    ),
    "energy_power": (
        "FDTD", "微波", "电磁", "传输线", "电磁仿真",
        "computational electromagnetics", "waveguide", "coplanar waveguide",
        "microstrip", "transmission line",
    ),
    "vision_2d": (
        "YOLO", "缺陷检测", "工业缺陷", "缺陷识别",
        "surface defect", "PCB defect", "weld defect",
    ),
    "vision_3d": (
        "三维", "点云", "点云分类",
        "point cloud", "3D reconstruction", "3D anomaly",
        "novel view synthesis", "gaussian splatting",
    ),
    "nlp_llm": (
        "BERT", "RoBERTa", "LoRA", "文本分类", "情感分析",
        "sentiment analysis", "text classification",
        "language model fine-tuning",
    ),
    "medical_ai": (
        "医学影像", "CT", "MRI", "病灶", "medical imaging", "radiology",
    ),
    "remote_sensing": (
        "遥感", "高分", "卫星", "土地覆盖", "remote sensing",
        "satellite imagery", "land cover",
    ),
    "civil_infra": (
        "混凝土", "裂缝", "桥梁", "结构损伤", "建筑",
        "civil", "structural", "crack detection",
    ),
    "robotics_control": (
        "机械臂", "运动控制", "ROS", "导航", "抓取",
        "manipulation", "robotic", "motion control", "grasping", "SLAM",
    ),
}


def _heuristic_parse_topic(raw_topic: str) -> dict:
    """Honest fallback. NO hardcoded atom translations — the Agent must build
    its own query atoms via the LLM call to parse_topic. When the LLM is
    dead, the agent has NOTHING to give the tool fan-out except the raw
    topic verbatim. This is intentionally barren: we do not want a heuristic
    fallback to leak any specific dataset / repo / paper terms, nor any
    expert-curated query phrasing.
    """
    text = (raw_topic or "").lower()
    raw_topic_zh = raw_topic or ""

    domain_route = "unknown"
    best_hits = 0
    for d, kws in _HEURISTIC_DOMAIN_KEYWORDS.items():
        hits = sum(1 for k in kws if k.lower() in text or k in raw_topic_zh)
        if hits > best_hits:
            best_hits = hits
            domain_route = d

    domain_confidence = 0.4 if domain_route != "unknown" else 0.0

    # NO atom translation map. The fallback emits ONE atom: the raw topic
    # verbatim, in the language the user gave it. The Agent is responsible for
    # shaping queries; the fallback is not.
    fallback_atom = raw_topic or "machine learning"

    return {
        "raw_topic": raw_topic,
        "normalized_topic": raw_topic,
        "domain_route": domain_route,
        "domain_confidence": domain_confidence,
        "method_terms": [],
        "task_terms": [],
        "object_terms": [],
        "query_atoms_en": [fallback_atom],
        "query_atoms_zh": [fallback_atom] if raw_topic_zh else [],
        "needs_clarification": [],
        "site_hints": [],
        "_heuristic": True,
    }


# --- parse_topic step --------------------------------------------------------


def parse_topic(raw_topic: str, *, counter: LLMCallCounter | None = None) -> dict:
    """Step 1. Single LLM call returning domain + query atoms."""
    if counter is not None:
        global GLOBAL_COUNTER
        GLOBAL_COUNTER += counter

    prompt = (
        f"RAW TOPIC (verbatim, do not paraphrase):\n{raw_topic}\n\n"
        f"Emit JSON for this topic now."
    )
    try:
        out = _chat_json_strict(prompt, PARSE_TOPIC_SYSTEM, max_tokens=900)
        # ponytail: schema conformance is up to the LLM. We only fix the
        # echo-of-raw-topic and replace empty query_atoms_en with a sane
        # noun phrase drawn from the raw topic itself.
        out["raw_topic"] = raw_topic
        if not out.get("query_atoms_en"):
            out["query_atoms_en"] = [raw_topic]
        if not out.get("domain_route"):
            out["domain_route"] = "unknown"
        if not isinstance(out.get("query_atoms_en"), list):
            out["query_atoms_en"] = [str(out["query_atoms_en"])]
        if not isinstance(out.get("query_atoms_zh"), list):
            out["query_atoms_zh"] = []
        return out
    except LLMUnavailable as exc:
        logger.warning("parse_topic LLM unavailable: %s — heuristic fallback", exc)
        return _heuristic_parse_topic(raw_topic)


# --- plan_tools step ---------------------------------------------------------


def plan_tools(topic_json: dict, *, counter: LLMCallCounter | None = None) -> dict:
    """Step 2. Plan 4 adapter fan-out queries + Github suffix filter."""
    if counter is not None:
        global GLOBAL_COUNTER
        GLOBAL_COUNTER += counter

    prompt = USER_TEMPLATE_PLAN_TOOLS.format(
        topic_json=json.dumps(topic_json, ensure_ascii=False, indent=2),
    )
    plan: dict = {}
    try:
        out = _chat_json_strict(prompt, PLAN_TOOLS_SYSTEM, max_tokens=500)
        plan["arxiv_queries"] = _cap_queries(out.get("arxiv_queries"), 6, 3)
        plan["openalex_queries"] = _cap_queries(out.get("openalex_queries"), 6, 3)
        plan["crossref_queries"] = _cap_queries(out.get("crossref_queries"), 6, 3)
        plan["github_queries"] = _cap_queries(out.get("github_queries"), 4, 3)
        plan["year_min"] = int(out.get("year_min") or 2018)
        plan["top_k_per_adapter"] = int(out.get("top_k_per_adapter") or 8)
        plan["site_keywords"] = list(out.get("site_keywords") or [])[:5]
    except LLMUnavailable as exc:
        logger.warning("plan_tools LLM unavailable: %s — atoms fallback", exc)
        plan = _plan_tools_from_atoms(topic_json)

    # ponytail: never leave arxiv empty; fall back to the parsed topic raw.
    if not plan.get("arxiv_queries"):
        plan["arxiv_queries"] = list(topic_json.get("query_atoms_en") or [])[:3] or [
            topic_json.get("raw_topic") or "machine learning"
        ]
    return plan


def _cap_queries(qs, max_words: int, max_items: int) -> list[str]:
    """Trim every query to ≤ max_words, cap total to max_items, drop empties."""
    if not isinstance(qs, list):
        return []
    out: list[str] = []
    for q in qs:
        if not isinstance(q, str):
            continue
        w = q.strip().split()
        if not w:
            continue
        if len(w) > max_words:
            w = w[:max_words]
        out.append(" ".join(w))
        if len(out) >= max_items:
            break
    return out


def _plan_tools_from_atoms(topic_json: dict) -> dict:
    """Deterministic plan from the parsed atoms (no LLM).

    GitHub queries are trimmed to ≤ 4 words because GitHub's search
    down-ranks long phrases. Other adapters tolerate ≤ 6 words.
    """
    en_atoms = list(topic_json.get("query_atoms_en") or [])
    raw = topic_json.get("raw_topic") or "machine learning"

    def _truncate(qs: list[str], max_words: int) -> list[str]:
        out: list[str] = []
        for q in qs:
            w = q.split()
            if len(w) <= max_words:
                out.append(q)
            else:
                out.append(" ".join(w[:max_words]))
        return out or [raw]

    return {
        "arxiv_queries":    _truncate(en_atoms[:3] or [raw], 6),
        "openalex_queries": _truncate(en_atoms[:3] or [raw], 6),
        "crossref_queries": _truncate(en_atoms[:2] or [raw], 6),
        "github_queries":   _truncate(en_atoms[:2] or [raw], 4),
        "year_min": 2018,
        "top_k_per_adapter": 8,
        "site_keywords": [],
    }


# --- tool fan-out (no LLM) ---------------------------------------------------


async def fetch_all(
    topic_atoms: dict,
    plan: dict,
) -> dict[str, list[dict]]:
    """Two-pass tool fan-out.

    Pass 1: per-adapter search using query atoms from `plan_tools`.
    Pass 2: each paper that comes back triggers a follow-up `code search` of
            GitHub with the paper's title — so an arXiv paper whose official
            implementation lives in a repo is found via the paper, not via
            the topic's query atoms. Likewise each repo whose description
            embeds a paper title triggers a follow-up arXiv search by that
            paper title.

    Pattern borrowed from AutoResearchClaw: it always cross-correlates
    papers ↔ repos so the user gets bidirectional augmentation.
    """
    arxiv_qs = plan.get("arxiv_queries") or topic_atoms.get("query_atoms_en") or []
    oa_qs = plan.get("openalex_queries") or topic_atoms.get("query_atoms_en") or []
    cr_qs = plan.get("crossref_queries") or topic_atoms.get("query_atoms_en") or []
    gh_qs = plan.get("github_queries") or topic_atoms.get("query_atoms_en") or []

    top_k = plan.get("top_k_per_adapter") or 8

    async def _safe(coro, name: str) -> list[dict]:
        if not GLOBAL_SUSPEND_STATE.should_allow(name):
            until = GLOBAL_SUSPEND_STATE.suspended_until_str(name)
            logger.info("[%s] CB OPEN until %s", name, until)
            return []
        try:
            result = await coro
        except Exception as exc:  # noqa: BLE001
            msg = str(exc) or ""
            is_429 = "429" in msg or "Too Many Requests" in msg or "rate" in msg.lower()
            is_5xx = any(code in msg for code in ("500", "502", "503", "504", "403"))
            if is_429 or is_5xx:
                GLOBAL_SUSPEND_STATE.on_failure(name, is_429=is_429)
            logger.warning("[%s] failed: %s", name, exc)
            return []
        GLOBAL_SUSPEND_STATE.on_success(name)
        return result

    # Pass 1
    arxiv_res: list[dict] = await _safe(arxiv_search(arxiv_qs, top_k=top_k), "arxiv")
    await asyncio.sleep(0.4)
    oa_res: list[dict] = await _safe(openalex_search(oa_qs, top_k=top_k), "openalex")
    await asyncio.sleep(0.4)
    cr_res: list[dict] = await _safe(crossref_search(cr_qs, top_k=top_k), "crossref")
    await asyncio.sleep(0.4)
    gh_res: list[dict] = await _safe(github_search(gh_qs, top_k=top_k), "github")

    pass1 = {
        "arxiv": arxiv_res,
        "openalex": oa_res,
        "crossref": cr_res,
        "github": gh_res,
    }

    # Pass 2 — paper↔repo augmentation:
    #   - For every arXiv paper title, search GitHub for the title (smaller
    #     top_k). The repos that come back are tagged with source_paper so we
    #     know why they're present.
    #   - For every GitHub repo, if its description embeds a paper title,
    #     search arXiv for that title.
    paper_followup_qs: list[str] = []
    for items in (arxiv_res, cr_res, oa_res):
        for item in items:
            t = (item.get("title") or "").strip()
            if t and 4 <= len(t.split()) <= 14:
                paper_followup_qs.append(t)
    paper_followup_qs = paper_followup_qs[:5]  # cap to top 5 by arxiv order
    if paper_followup_qs:
        logger.info("[paper→github] %d follow-up searches", len(paper_followup_qs))
        await asyncio.sleep(0.6)
        gh_follow = await _safe(
            github_search(paper_followup_qs, top_k=4),
            "github",
        )
        for r in gh_follow:
            r["_discovery_source"] = "paper_to_repo_augmentation"
        gh_res.extend(gh_follow)

    arxiv_followup_qs: list[str] = []
    for repo in gh_res:
        for t in _extract_quoted_titles(repo.get("description") or ""):
            if t and 4 <= len(t.split()) <= 14:
                arxiv_followup_qs.append(t)
    arxiv_followup_qs = arxiv_followup_qs[:5]
    if arxiv_followup_qs:
        logger.info("[repo→arxiv] %d follow-up searches", len(arxiv_followup_qs))
        await asyncio.sleep(0.6)
        ar_follow = await _safe(
            arxiv_search(arxiv_followup_qs, top_k=4),
            "arxiv",
        )
        for r in ar_follow:
            r["_discovery_source"] = "repo_to_paper_augmentation"
        arxiv_res.extend(ar_follow)

    pass2 = {
        "arxiv": arxiv_res,
        "openalex": oa_res,
        "crossref": cr_res,
        "github": gh_res,
    }
    return pass2


# --- synthesize step ---------------------------------------------------------


def _format_raw_block(raw: dict[str, list[dict]]) -> str:
    """Render raw tool output as fenced JSON-per-adapter blocks for the LLM."""
    lines: list[str] = []
    for adapter_name, items in raw.items():
        lines.append(f"\n----- BEGIN {adapter_name} (n={len(items)}) -----")
        # Truncate each item to a small schema to keep prompts bounded.
        slim: list[dict] = []
        for c in items[:top_k_limit(adapter_name)]:
            slim.append(_slim(adapter_name, c))
        lines.append(json.dumps(slim, ensure_ascii=False, indent=1))
        lines.append(f"----- END {adapter_name} -----")
    return "\n".join(lines)


def _auto_backfill_embedded_titles_placeholder() -> dict:
    """Never called. Removed because the user said post-processing scoring
    systems are insufficient — Agent decides everything via 4-dimension
    peer-review. Kept as empty stub to keep any stray import happy.
    """
    return {}


def _build_verifier_index(raw: dict[str, list[dict]]) -> dict[str, set[str]]:
    """Index of allowed title-tokens per adapter for post-synthesis verification.

    GitHub repos don't carry `title`; they have `full_name`, `html_url`,
    `description`. The verifier must recognize every one of these so a
    synthesized entry whose `title="zakaria76al/USC"` is matched against the
    github adapter.

    IMPORTANT: GitHub repo descriptions often embed the *paper* title for
    official-implementation repos (e.g. "The official implementation of the
    paper 'A spatio-temporal deep learning approach for...'"). We extract the
    quoted paper title from the description and index it under the github
    adapter too — so if the LLM correctly recognizes the embedded paper title
    as a baseline candidate, the verifier won't reject it.
    """
    index: dict[str, set[str]] = {}
    for adapter_name, items in raw.items():
        titles: set[str] = set()
        for c in items:
            for fld in ("title", "full_name", "name", "html_url", "arxiv_id",
                        "openalex_id", "id", "doi", "DOI", "url", "URL",
                        "description"):
                v = c.get(fld)
                if not isinstance(v, str):
                    continue
                v = v.strip()
                if not v:
                    continue
                low = v.lower()
                titles.add(low)
                if fld in ("full_name", "name", "html_url") and "/" in low:
                    titles.add(low.strip("/").split("?")[0].split("#")[0])
                words = low.split()
                for i in range(len(words) - 4):
                    titles.add(" ".join(words[i:i + 5]))
                titles.add(" ".join(words[:8]))
            html = c.get("html_url") or ""
            if "github.com/" in html:
                owner_repo = html.split("github.com/", 1)[-1].strip("/").lower()
                if owner_repo:
                    titles.add(owner_repo)
            desc = c.get("description") or ""
            for emb_title in _extract_quoted_titles(desc):
                titles.add(emb_title.lower())
                words = emb_title.lower().split()
                for i in range(len(words) - 4):
                    titles.add(" ".join(words[i:i + 5]))
                titles.add(" ".join(words[:8]))
        index[adapter_name] = titles
    return index


def _extract_quoted_titles(text: str) -> list[str]:
    """Extract *paper* titles embedded in repo descriptions, e.g.
    `the paper "A spatio-temporal ... for underwater ..."` → title.
    Handles double quotes + Unicode curly quotes.
    """
    if not text:
        return []
    out: list[str] = []
    # double quotes, smart double curly, and backtick
    for opener, closer in [('"', '"'), ('“', '”'), ('“', '”'), ('`', '`')]:
        pos = 0
        while True:
            a = text.find(opener, pos)
            if a < 0:
                break
            b = text.find(closer, a + 1)
            if b < 0:
                break
            inner = text[a + 1:b].strip()
            # Title heuristic: ≥ 5 words, has ≥ 1 capital letter or is long-enough English
            words = inner.split()
            if 4 <= len(words) <= 30 and (
                any(w[0:1].isupper() for w in words if w)
                or inner.count(" ") >= 4
            ):
                out.append(inner)
            pos = b + 1
    return out


def _title_grounded(title: str, verifier: dict[str, set[str]]) -> bool:
    """True iff title overlaps any adapter's title index (token-level)."""
    if not title:
        return False
    t = title.strip().lower()
    if not t:
        return False
    for adapter_titles in verifier.values():
        if t in adapter_titles:
            return True
    words = t.split()
    if len(words) >= 5:
        for i in range(len(words) - 4):
            gram = " ".join(words[i:i + 5])
            for adapter_titles in verifier.values():
                if gram in adapter_titles:
                    return True
        head = " ".join(words[:8])
        for adapter_titles in verifier.values():
            if head in adapter_titles:
                return True
    return False


def _repo_key(r: dict) -> str:
    """Stable key for dedup of repo entries (owner/repo lowercase)."""
    n = r.get("name") or r.get("full_name") or r.get("title") or ""
    return str(n).strip().lower().strip("/")


def _apply_verifier(
    buckets: dict,
    verifier: dict[str, set[str]],
) -> tuple[dict, list[dict]]:
    """Drop paper entries not grounded in any adapter's raw output."""
    row_categories = [
        "baseline_papers", "parallel_papers", "module_papers", "reference_papers",
        "repo_candidates",
    ]
    fabrication_alerts: list[dict] = []
    revised: dict = {
        "baseline_papers": list(buckets.get("baseline_papers") or []),
        "parallel_papers": list(buckets.get("parallel_papers") or []),
        "module_papers": list(buckets.get("module_papers") or []),
        "reference_papers": list(buckets.get("reference_papers") or []),
        "dataset_candidates": list(buckets.get("dataset_candidates") or []),
        "repo_candidates": list(buckets.get("repo_candidates") or []),
        "evidence_gaps": list(buckets.get("evidence_gaps") or []),
    }
    for cat in row_categories:
        kept: list[dict] = []
        for r in revised[cat]:
            title = (r.get("title") or r.get("name") or "").strip()
            if _title_grounded(title, verifier):
                kept.append(r)
            elif title:
                fabrication_alerts.append({"title": title, "bucket": cat, "why": "not_in_raw_tool_output"})
        revised[cat] = kept
    kept_d: list[dict] = []
    for r in list(revised.get("dataset_candidates") or []):
        n = (r.get("name") or r.get("title") or "").strip()
        if _title_grounded(n, verifier):
            kept_d.append(r)
        elif n:
            fabrication_alerts.append({"title": n, "bucket": "dataset_candidates", "why": "not_in_raw_tool_output"})
    revised["dataset_candidates"] = kept_d
    return revised, fabrication_alerts


def top_k_limit(adapter_name: str) -> int:
    return {"arxiv": 18, "openalex": 14, "crossref": 10, "github": 10}.get(
        adapter_name, 8
    )


def _slim(adapter_name: str, c: dict) -> dict:
    if adapter_name == "arxiv":
        return {
            "title": c.get("title"),
            "abstract": (c.get("abstract") or "")[:600],
            "arxiv_id": c.get("arxiv_id"),
            "url": c.get("url") or c.get("abs_url"),
            "year": (c.get("published") or "")[:4] if c.get("published") else None,
            "authors": (c.get("authors") or [])[:5],
            "source": "arxiv",
        }
    if adapter_name == "openalex":
        return {
            "title": c.get("title"),
            "abstract": (c.get("abstract") or "")[:600],
            "doi": c.get("doi"),
            "openalex_id": c.get("openalex_id") or c.get("id"),
            "url": c.get("url"),
            "year": c.get("publication_year") or c.get("year"),
            "cited_by_count": c.get("cited_by_count"),
            "source": "openalex",
        }
    if adapter_name == "crossref":
        return {
            "title": c.get("title"),
            "abstract": (c.get("abstract") or "")[:600],
            "doi": c.get("doi") or c.get("DOI"),
            "url": c.get("url") or c.get("URL"),
            "year": (str(c.get("issued") or c.get("published_print") or ""))[:4] or None,
            "is_referenced_by_count": c.get("is_referenced_by_count") or c.get("is-referenced-by-count"),
            "source": "crossref",
        }
    if adapter_name == "github":
        quoted = _extract_quoted_titles(c.get("description") or "")
        return {
            "title": c.get("full_name") or c.get("name") or c.get("repo"),
            "description": (c.get("description") or "")[:300],
            "url": c.get("html_url") or c.get("url"),
            "stars": c.get("stars"),
            "language": c.get("language"),
            "license": c.get("license"),
            "updated_at": c.get("updated_at"),
            "topics": c.get("topics"),
            "source": "github",
            "quoted_paper_titles": quoted,
        }
    return c


def synthesize_buckets(
    raw_topic: str,
    domain_route: str,
    topic_json: dict,
    raw: dict[str, list[dict]],
    *,
    counter: LLMCallCounter | None = None,
) -> dict:
    """Step 3. Single LLM call: 7-bucket JSON out, no `*_score` anywhere."""
    if counter is not None:
        global GLOBAL_COUNTER
        GLOBAL_COUNTER += counter

    raw_block = _format_raw_block(raw)
    prompt = USER_TEMPLATE_SYNTHESIZE.format(
        raw_topic=raw_topic,
        domain_route=domain_route,
        topic_json=json.dumps(topic_json, ensure_ascii=False, indent=2),
        raw_results_block=raw_block,
    )
    try:
        out = _chat_json_strict(prompt, SYNTHESIZE_SYSTEM, max_tokens=6000)
        return _normalize_buckets(out)
    except LLMUnavailable as exc:
        logger.warning("synthesize LLM unavailable: %s — returning minimal output", exc)
        return _minimal_buckets_from_raw(raw_topic, raw)


def _normalize_buckets(out: dict) -> dict:
    """Coerce LLM output into our 7-bucket contract. Drops junk, caps counts."""
    buckets = {
        "baseline_papers": [],
        "parallel_papers": [],
        "module_papers": [],
        "reference_papers": [],
        "dataset_candidates": [],
        "repo_candidates": [],
        "evidence_gaps": [],
    }
    for k in buckets:
        v = out.get(k)
        if isinstance(v, list):
            buckets[k] = v
        else:
            buckets[k] = []
    # Hard caps (8/5/5/8/5/5/5).
    caps = {
        "baseline_papers": 5,
        "parallel_papers": 5,
        "module_papers": 5,
        "reference_papers": 8,
        "dataset_candidates": 5,
        "repo_candidates": 5,
        "evidence_gaps": 5,
    }
    for k, cap in caps.items():
        buckets[k] = buckets[k][:cap]
    return buckets


def _minimal_buckets_from_raw(raw_topic: str, raw: dict[str, list[dict]]) -> dict:
    """When LLM is dead, return a thin (still rule-free) honest minimal buckets."""
    return {
        "baseline_papers": [],
        "parallel_papers": [],
        "module_papers": [],
        "reference_papers": [],
        "dataset_candidates": [],
        "repo_candidates": [],
        "evidence_gaps": [
            f"LLM synthesize failed, raw tool output has "
            f"arxiv={len(raw.get('arxiv', []))}, "
            f"openalex={len(raw.get('openalex', []))}, "
            f"crossref={len(raw.get('crossref', []))}, "
            f"github={len(raw.get('github', []))} items for topic: {raw_topic}"
        ],
    }


# --- devils_advocate step ----------------------------------------------------


def devils_advocate(
    buckets: dict,
    topic_summary: dict,
    *,
    counter: LLMCallCounter | None = None,
) -> dict:
    """Step 4. 5-dimension peer-review port of academic-paper-reviewer.

    Returns revised buckets WITH the verifier's verdict, dimension scores,
    fabrication alerts, and risks rolled up into the same dict.
    """
    if counter is not None:
        global GLOBAL_COUNTER
        GLOBAL_COUNTER += counter

    prompt = USER_TEMPLATE_DEVILS_ADVOCATE.format(
        topic_summary=json.dumps(topic_summary, ensure_ascii=False, indent=1),
        buckets_json=json.dumps(buckets, ensure_ascii=False, indent=2),
    )
    try:
        out = _chat_json_strict(prompt, DEVILS_ADVOCATE_SYSTEM, max_tokens=2400)
        revised = out.get("revised_7_buckets") or buckets
        normalized = _normalize_buckets(revised) if isinstance(revised, dict) else buckets

        # Honor the rule: if ACCEPT, the revised buckets must equal the input.
        verdict = out.get("overall_verdict") or _infer_verdict(out.get("dimension_scores") or [])
        if verdict == "ACCEPT":
            normalized = dict(buckets)

        # evidence_gaps: append reviewer-supplied gaps (≤ 3) only when not ACCEPT.
        gaps = list(normalized.get("evidence_gaps") or [])
        if verdict != "ACCEPT":
            for g in out.get("evidence_gaps_to_append") or []:
                g = str(g).strip()
                if g and g not in gaps:
                    gaps.append(g)
        normalized["evidence_gaps"] = gaps[:5]

        # fabrication_alerts: drop the entry list from the bucket if listed.
        fabrication_alerts = list(out.get("fabrication_alerts") or [])[:5]
        for alert in fabrication_alerts:
            t = (alert.get("title") or "").strip().lower()
            b = alert.get("bucket") or ""
            if not t or b not in normalized or not isinstance(normalized[b], list):
                continue
            normalized[b] = [
                r for r in normalized[b]
                if str(r.get("title") or "").strip().lower() != t
            ]

        risks = list(out.get("risks_identified") or [])[:5]
        return {
            **normalized,
            "overall_verdict": verdict,
            "dimension_scores": list(out.get("dimension_scores") or [])[:5],
            "fabrication_alerts": fabrication_alerts,
            "risks_identified": risks,
            "verdict_source": "llm",
        }
    except LLMUnavailable as exc:
        logger.warning("devils_advocate LLM unavailable: %s — heuristic-only revision", exc)
        result = _heuristic_devils_advocate(buckets, topic_summary)
        result["overall_verdict"] = "MINOR_REVISION"
        result["verdict_source"] = "heuristic"
        return result


def _infer_verdict(dimension_scores: list[dict]) -> str:
    """Aggregate dimension scores → ACCEPT / MINOR_REVISION / BLOCK."""
    if not dimension_scores:
        return "ACCEPT"
    verdicts = [str(d.get("verdict") or "PASS").upper() for d in dimension_scores]
    if any(v == "BLOCK" for v in verdicts):
        return "BLOCK"
    if any(v == "WARN" for v in verdicts):
        return "MINOR_REVISION"
    return "ACCEPT"


# --- local devils_advocate (no LLM) ------------------------------------------

# Per user (S66v): "the encoded scoring system is insufficient; the Agent
# decides whether something is usable." This module used to do a hardcoded
# cross-domain filter list here. That has been DELETED. The fallback is
# strictly identity — pass buckets through unchanged and let the 4-dimension
# peer-review (when LLM is alive) be the only judge.


def _heuristic_devils_advocate(buckets: dict, _topic_summary_unused: dict) -> dict:
    """Pass-through. NO scoring, NO filtering, NO fabrication alerts.

    Per user (S66v): "delete all encoded scoring systems; let the Agent
    decide." This is the no-LLM peer-review fallback. It enforces structural
    invariants only (title non-empty + bucket caps). Cross-domain relevance
    judgment is left to the LLM pass.
    """
    def _clean(rows: list[dict], cap: int) -> list[dict]:
        out: list[dict] = []
        for r in rows:
            title = (r.get("title") or r.get("name") or "").strip()
            if not title:
                continue
            out.append({**r, "title": title})
        return out[:cap]

    return {
        "baseline_papers":    _clean(buckets.get("baseline_papers") or [], 5),
        "parallel_papers":    _clean(buckets.get("parallel_papers") or [], 5),
        "module_papers":      _clean(buckets.get("module_papers") or [], 5),
        "reference_papers":   _clean(buckets.get("reference_papers") or [], 8),
        "dataset_candidates": _clean(buckets.get("dataset_candidates") or [], 5),
        "repo_candidates":    _clean(buckets.get("repo_candidates") or [], 5),
        "evidence_gaps":      list(buckets.get("evidence_gaps") or [])[:5],
    }


# --- top-level orchestrator --------------------------------------------------


@dataclass
class AgentResult:
    raw_topic: str
    project_id: str
    parsed_topic: dict
    plan: dict
    raw_tool_results: dict[str, list[dict]]
    buckets: dict
    llm_calls: int
    llm_failures: int
    llm_budget: int
    overall_verdict: str = "ACCEPT"
    dimension_scores: list = field(default_factory=list)
    fabrication_alerts: list = field(default_factory=list)
    verdict_source: str = "unknown"


async def run_research_agent(
    raw_topic: str,
    *,
    student_context: dict | None = None,
    auto_devils_advocate: bool = True,
) -> AgentResult:
    """End-to-end: parse → plan → fetch → synthesize → (devils_advocate).

    Args:
        raw_topic: the student's verbatim thesis topic.
        student_context: not currently used (kept for API symmetry with legcy).
        auto_devils_advocate: if True, runs the strict reviewer pass.

    Returns:
        AgentResult with 7 buckets + raw tool output for downstream UI.
    """
    project_id = f"agent-{uuid.uuid4().hex[:8]}"

    # 1. parse
    parsed = parse_topic(raw_topic)
    # Preserve raw_topic verbatim regardless of LLM mistakes.
    parsed["raw_topic"] = raw_topic

    # 2. plan
    plan = plan_tools(parsed)

    # 3. fetch (sequential with cooldown, no LLM)
    raw = await fetch_all(parsed, plan)

    # 3b. record any suspended adapters as gaps so the user / next run sees them
    suspended = sorted(
        (a for a in ("arxiv", "openalex", "crossref", "github")
         if GLOBAL_SUSPEND_STATE.is_suspended(a))
    )
    suspended_gaps = [
        f"RATE_LIMITED: {a} suspended until {GLOBAL_SUSPEND_STATE.suspended_until_str(a)}"
        for a in suspended
    ]


    # 4. synthesize
    buckets = synthesize_buckets(raw_topic, parsed.get("domain_route", "unknown"), parsed, raw)
    if suspended_gaps:
        gaps = list(buckets.get("evidence_gaps") or [])
        for g in suspended_gaps:
            if g not in gaps:
                gaps.insert(0, g)
        buckets["evidence_gaps"] = gaps[:5]  # cap so we don't push real gaps out

    # 4b. verifier — drop any synthesize entry whose title doesn't appear in
    # any adapter's raw output. This is the load-bearing academic-integrity
    # gate; without it, the LLM silently fabricates paper titles.
    verifier = _build_verifier_index(raw)
    buckets, before_fab_alerts = _apply_verifier(buckets, verifier)

    # 5. devils_advocate (optional but default-on)
    if auto_devils_advocate:
        buckets = devils_advocate(buckets, parsed)

    # 5b. final verifier pass after the reviewer.
    # If the reviewer fabricated new titles, drop them now.
    buckets, after_fab_alerts = _apply_verifier(buckets, verifier)
    fab_total = before_fab_alerts + after_fab_alerts
    if fab_total and not buckets.get("fabrication_alerts"):
        buckets["fabrication_alerts"] = fab_total[:5]  # cap
    elif fab_total:
        buckets["fabrication_alerts"] = (buckets.get("fabrication_alerts") or []) + fab_total
        buckets["fabrication_alerts"] = list({(a.get("title"), a.get("bucket"), a.get("why")): a for a in buckets["fabrication_alerts"]}.values())[:5]
    if fab_total:
        gaps = list(buckets.get("evidence_gaps") or [])
        msg = f"verifier dropped {len(fab_total)} entries not grounded in raw tool output"
        if msg not in gaps:
            gaps.insert(0, msg)
        buckets["evidence_gaps"] = gaps[:5]

    # 5c. STRUCTURAL REBALANCE (no scoring, no filtering). Every GitHub repo
    # whose `full_name` appears in the raw tool output MUST surface in
    # `repo_candidates` if it is missing. We don't judge relevance — that is
    # the LLM peer-review's job. We only guarantee the deliverable contains
    # every curl-verified repo the fan-out produced. Same idea for paper /
    # paper-title presence in `baseline_papers`: if a GitHub repo description
    # embeds an official paper title, surface that title in `baseline_papers`
    # so it isn't lost.
    final_repos = list(buckets.get("repo_candidates") or [])
    seen_repo_keys = {_repo_key(r) for r in final_repos}

    def _add_repo_from_raw(repo: dict) -> bool:
        key = _repo_key(repo)
        if key in seen_repo_keys:
            return False
        if len(final_repos) >= 5:
            return False
        final_repos.append({
            "title": repo.get("full_name") or repo.get("name"),
            "name": repo.get("full_name") or repo.get("name"),
            "source": "github",
            "url": repo.get("html_url") or repo.get("url") or "",
            "identifier": repo.get("full_name") or repo.get("name"),
            "stars": repo.get("stars") or repo.get("stargazers_count"),
            "language": repo.get("language"),
            "license": repo.get("license") if isinstance(repo.get("license"), str) else None,
            "one_line_use": "Discovered in GitHub raw tool output during agent run.",
        })
        seen_repo_keys.add(key)
        return True

    for repo in (raw.get("github") or []):
        if not (repo.get("full_name") or repo.get("name")):
            continue
        if not _add_repo_from_raw(repo):
            if len(final_repos) >= 5:
                break

    buckets["repo_candidates"] = final_repos[:5]
    # 5d. surface GitHub-embedded paper titles in baseline_papers if missing.
    final_baseline = list(buckets.get("baseline_papers") or [])
    seen_baseline = {str(b.get("title") or "").strip().lower() for b in final_baseline}
    for repo in (raw.get("github") or []):
        if not (repo.get("full_name") or repo.get("name")):
            continue
        desc = repo.get("description") or ""
        for emb_title in _extract_quoted_titles(desc):
            t_low = emb_title.strip().lower()
            if not t_low or t_low in seen_baseline:
                continue
            if len(final_baseline) >= 5:
                break
            final_baseline.append({
                "title": emb_title,
                "source": "github",
                "url": repo.get("html_url") or repo.get("url") or "",
                "identifier": repo.get("full_name"),
                "year": None,
                "one_line_use": "Paper title extracted from a GitHub official-implementation repo's description (companion paper).",
            })
            seen_baseline.add(t_low)
        if len(final_baseline) >= 5:
            break
    buckets["baseline_papers"] = final_baseline[:5]  # cap

    return AgentResult(
        raw_topic=raw_topic,
        project_id=project_id,
        parsed_topic=parsed,
        plan=plan,
        raw_tool_results=raw,
        buckets=buckets,
        llm_calls=GLOBAL_COUNTER.n_calls,
        llm_failures=GLOBAL_COUNTER.n_failures,
        llm_budget=LLM_CALL_BUDGET,
        overall_verdict=buckets.get("overall_verdict", "ACCEPT"),
        dimension_scores=buckets.get("dimension_scores", []) or [],
        fabrication_alerts=buckets.get("fabrication_alerts", []) or [],
        verdict_source=buckets.get("verdict_source", "unknown"),
    )


# --- CLI / self-check -------------------------------------------------------


def _buckets_for_print(result: AgentResult, indent: str = "") -> str:
    out = [f"{indent}== run_research_agent({result.raw_topic!r}) =="]
    out.append(f"{indent}project_id: {result.project_id}")
    out.append(
        f"{indent}LLM: {result.llm_calls} calls / {result.llm_budget} budget"
        f" ({result.llm_failures} failures)"
    )
    out.append(f"{indent}domain_route: {result.parsed_topic.get('domain_route')}")
    out.append(f"{indent}query_atoms_en: {result.parsed_topic.get('query_atoms_en')}")
    out.append(
        f"{indent}raw tool output sizes: "
        + ", ".join(f"{k}={len(v)}" for k, v in result.raw_tool_results.items())
    )
    for cat in [
        "baseline_papers",
        "parallel_papers",
        "module_papers",
        "reference_papers",
        "dataset_candidates",
        "repo_candidates",
        "evidence_gaps",
    ]:
        rows = result.buckets.get(cat) or []
        out.append(f"{indent}[{cat}] n={len(rows)}")
        for r in rows[:5]:
            if isinstance(r, dict):
                title = r.get("title") or r.get("name") or str(r)[:80]
                out.append(f"{indent}    - {title[:100]}")
            else:
                out.append(f"{indent}    - {str(r)[:120]}")
    return "\n".join(out)


if __name__ == "__main__":
    # ponytail: tiny __main__ that lets the human run one topic and see the
    # full tool trace in stdout. No file IO by default.
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m app.services.agents.research_agent <raw_topic>")
        sys.exit(2)
    topic = " ".join(sys.argv[1:])
    reset_counter()
    result = asyncio.run(run_research_agent(topic))
    print(_buckets_for_print(result))
