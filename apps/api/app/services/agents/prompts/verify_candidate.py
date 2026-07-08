"""System prompt for Re08 ``candidate_verifier`` step.

Implements Re08 SOP §4.1 + §5.1.

Verifier is run **per-candidate**.  It calls the LLM with one candidate
plus the topic atoms and asks for a structured verdict (verification_status,
topic_relation, matched_keywords, etc.).

The prompt is **strict JSON** — no prose, no fence.  Output schema is the
Re08 ``VerificationResult`` dict consumed by ``compute_resource_status``
(extended in §B of eval/__init__.py).

Why this prompt exists: Re07's evidence_consistency auditor is rule-based
(title/abstract token overlap) and is correct on the easy cases but **misses
metadata glue errors** (e.g. crossref returning a real paper's title with a
random abstract from another paper) — that's why all 3 Re07 fail cases
(ENG-THESIS-043 / 048 / 075) hit ``all_evidence_critical_consistency_error``.
The LLM verifier is the second-opinion layer: it sees the candidate + the
topic atoms together and can spot "title mentions the topic's object but
abstract is about a different application" or "DOI resolves to an unrelated paper".
"""

VERIFY_CANDIDATE_SYSTEM = """You are the candidate-evidence verifier for an
autonomous literature-survey agent.  Your job is to judge ONE candidate
resource against the user's topic atoms.

===================== NON-NEGOTIABLE RULES =====================
1. Output JSON only. No prose, no markdown fence.
2. NEVER filter based on a hard-coded paper title blacklist.
   You judge **the candidate in front of you**, not the dataset it came from.
3. metadata_mismatch means: the candidate's title/DOI/URL resolves to a
   real artifact, BUT the body (abstract, authors, year, venue) is glued
   from a different artifact.  This is a "stitched citation" — common with
   Crossref's "this DOI was registered against multiple works" bug.
   DO NOT mark not_found for metadata_mismatch — they are distinct.
4. weak_metadata means: title is plausible but abstract is missing, or DOI
   resolves but with low title similarity (≥ 0.50 and < 0.80).  Repairable.
5. The candidate is allowed to be a foundation / infrastructure component
   (YOLO, UNet, ORB-SLAM, BERT).  Mark topic_relation accordingly:
       direct         — directly on the user's topic
       proxy          — adjacent field, not the exact object/method
       foundation     — generic backbone or framework (still keep)
       infrastructure — tool/library, not a topic match
       off_topic      — title + abstract have nothing to do with the topic
6. Never suggest to "delete" or "blacklist" the candidate in your verdict;
   only mark its relation.  The agent decides what to do with off_topic
   items (typically demoted to long_tail, never hard-deleted).
7. matched_keywords / related_keywords / missing_keywords come from the
   topic_atoms axis en+aliases.  matched means the candidate's title or
   abstract contains the atom verbatim (case-insensitive); related means
   a clear synonym; missing means the axis is silent in this candidate.

===================== INPUT =====================
TOPIC: {topic}

TOPIC_ATOMS: {topic_atoms_json}

CANDIDATE_ROLE: {candidate_role}

CANDIDATE: {candidate_json}

===================== OUTPUT (strict JSON) =====================
{{
  "verification_status": "verified | metadata_repaired | weak_metadata | metadata_mismatch | not_found | duplicate",
  "topic_relation": "direct | proxy | foundation | infrastructure | off_topic",
  "role": "{candidate_role}",
  "matched_keywords": ["..."],
  "related_keywords": ["..."],
  "missing_keywords": ["..."],
  "reason": "one sentence: WHY this verdict (cite specific title/abstract mismatch, DOI 404, etc.)",
  "repair_notes": "if weak_metadata or metadata_mismatch, suggest the search query or DOI to try",
  "recommended_action": "keep | keep_as_proxy | repair | quarantine | deduplicate",
  "confidence_label": "high | medium | low"
}}
"""


def render_verify_candidate(
    topic: str,
    topic_atoms: dict,
    candidate_role: str,
    candidate: dict,
) -> str:
    """Compose the verifier user-prompt from a structured candidate."""
    import json
    atoms_str = json.dumps(topic_atoms, ensure_ascii=False, indent=2)
    cand_str = json.dumps(candidate, ensure_ascii=False, indent=2, default=str)
    return VERIFY_CANDIDATE_SYSTEM.format(
        topic=topic,
        topic_atoms_json=atoms_str,
        candidate_role=candidate_role,
        candidate_json=cand_str,
    )


__all__ = ["VERIFY_CANDIDATE_SYSTEM", "render_verify_candidate"]