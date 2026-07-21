from __future__ import annotations

from pathlib import Path


ADAPTER_PATH = Path("src/paperagent/literature/adapter.py")
METHOD_PATH = Path("src/paperagent/method_design_draft.py")
SCORER_PATH = Path("scripts/score_academic_tailoring_retrieval_v1.py")
ADAPTER_TEST_PATH = Path("tests/literature/test_linked_repository_candidates.py")
METHOD_TEST_PATH = Path("tests/nodes/test_method_design_baseline_anchor.py")
SCORER_TEST_PATH = Path("tests/evals/test_academic_tailoring_retrieval_v1_scorer.py")


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    if old in source:
        return source.replace(old, new, 1)
    if new in source:
        return source
    raise RuntimeError(f"{label} block not found")


def _patch_adapter() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    source = _replace_once(
        source,
        "from collections.abc import Iterable\n",
        "from collections.abc import Iterable\nfrom hashlib import sha256\nimport re\n",
        label="adapter imports",
    )
    source = _replace_once(
        source,
        "        return [self._candidate(query, paper, fallback_used) for paper in selected]\n",
        """        candidates: list[SearchCandidate] = []
        for paper in selected:
            candidates.extend(self._candidates(query, paper, fallback_used))
        return candidates
""",
        label="adapter candidate expansion",
    )

    marker = "\n\nclass LiteratureSearchAdapter:\n"
    helpers = r'''

_GITHUB_REPOSITORY_URL = re.compile(
    r"https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_REPOSITORY_RELATION_CUES = (
    "code",
    "implementation",
    "repository",
    "source",
    "available at",
    "released at",
    "github",
)


def _normalized_github_repository_urls(paper: PaperRecord) -> list[tuple[str, str]]:
    text = "\n".join([paper.abstract or "", *paper.urls])
    repositories: dict[str, str] = {}
    for match in _GITHUB_REPOSITORY_URL.finditer(text):
        owner = match.group("owner")
        repo = match.group("repo").rstrip(".,;:)]}")
        if repo.casefold().endswith(".git"):
            repo = repo[:-4]
        if not owner or not repo:
            continue
        title = f"{owner}/{repo}"
        url = f"https://github.com/{title}"
        context_start = max(0, match.start() - 100)
        context_end = min(len(text), match.end() + 100)
        context = text[context_start:context_end].casefold()
        if not any(cue in context for cue in _REPOSITORY_RELATION_CUES):
            continue
        repositories[url.casefold()] = title
    return [(url, title) for url, title in sorted(repositories.items())]
'''
    if "_normalized_github_repository_urls" not in source:
        if marker not in source:
            raise RuntimeError("adapter class marker not found")
        source = source.replace(marker, helpers + marker, 1)

    candidate_marker = "    def _candidate(\n"
    expansion = r'''    def _candidates(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
    ) -> list[SearchCandidate]:
        candidates = [self._candidate(query, paper, fallback_used)]
        if paper.verification_status != "verified":
            return candidates
        if not {"repository", "web"}.intersection(query.source_types):
            return candidates
        providers = sorted({record.provider for record in paper.source_records})
        score = paper.rank_features.score if paper.rank_features else 0.0
        relevance = paper.rank_features.relevance if paper.rank_features else 0.0
        for url, title in _normalized_github_repository_urls(paper):
            digest = sha256(url.casefold().encode("utf-8")).hexdigest()[:20]
            candidates.append(
                SearchCandidate(
                    candidate_id=f"repository-{digest}",
                    query_id=query.query_id,
                    gap_id=query.gap_id,
                    source_type="repository",
                    title=title,
                    locator=url,
                    snippet=(
                        f"Repository explicitly linked from the verified paper "
                        f"{paper.canonical_title!r}. The paper text or provider metadata "
                        f"contains the repository URL {url}."
                    ),
                    provider=self.provider_name,
                    metadata={
                        "query_text": query.query,
                        "verification_status": "verified",
                        "providers": ",".join(providers),
                        "provider_classes": "academic-linked-repository",
                        "source_kind": "repository",
                        "rank_score": f"{score:.6f}",
                        "relevance_score": f"{relevance:.6f}",
                        "relation": "author_linked_from_verified_paper",
                        "parent_paper_id": paper.paper_id,
                        "parent_paper_title": paper.canonical_title,
                        "repository_ref": url,
                        "fallback_used": "true" if fallback_used else "false",
                        "web_supplement": "false",
                    },
                )
            )
        return candidates

'''
    if "    def _candidates(" not in source:
        index = source.find(candidate_marker)
        if index < 0:
            raise RuntimeError("adapter candidate method marker not found")
        source = source[:index] + expansion + source[index:]
    ADAPTER_PATH.write_text(source, encoding="utf-8")


def _patch_method_design() -> None:
    source = METHOD_PATH.read_text(encoding="utf-8")
    helpers_marker = "\n\ndef _evidence_text(state: PaperAgentState) -> str:\n"
    helpers = r'''

_DECLARED_ROLE_SUFFIX = re.compile(r"\s*\[declared role:(?P<role>[^\]]+)\]\s*$", re.IGNORECASE)


def _title_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _titles_equivalent(left: str, right: str) -> bool:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    union = left_set | right_set
    overlap = left_set & right_set
    length_ratio = min(len(left_set), len(right_set)) / max(len(left_set), len(right_set))
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75


def _declared_baseline_titles(references: list[str]) -> tuple[str, ...]:
    titles: list[str] = []
    for reference in references:
        match = _DECLARED_ROLE_SUFFIX.search(reference)
        if match is None or "baseline" not in match.group("role").casefold():
            continue
        title = _DECLARED_ROLE_SUFFIX.sub("", reference).strip()
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)


def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    declared_titles = _declared_baseline_titles(references)
    for declared_title in declared_titles:
        for item in candidates:
            if item.source_type == "paper" and _titles_equivalent(item.title, declared_title):
                return item
    return candidates[0]
'''
    if "def _select_primary_evidence(" not in source:
        if helpers_marker not in source:
            raise RuntimeError("method design helper marker not found")
        source = source.replace(helpers_marker, helpers + helpers_marker, 1)

    old = '''    attributed = tuple(
        item for item in accepted if not _is_review_evidence(item.title, item.summary)
    )
    primary = attributed[0] if attributed else accepted[0]
'''
    new = '''    attributed = tuple(
        item for item in accepted if not _is_review_evidence(item.title, item.summary)
    )
    primary = _select_primary_evidence(
        list(request.user_material_refs),
        attributed if attributed else accepted,
    )
'''
    source = _replace_once(source, old, new, label="method primary evidence selection")
    METHOD_PATH.write_text(source, encoding="utf-8")


def _patch_scorer() -> None:
    source = SCORER_PATH.read_text(encoding="utf-8")
    old = '''def _titles_related(left: str, right: str) -> bool:
    left_normalized = _normalize(left)
    right_normalized = _normalize(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return True
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    smaller = min(len(left_tokens), len(right_tokens))
    if smaller < 3:
        return False
    overlap = len(left_tokens & right_tokens)
    return overlap / smaller >= 0.8
'''
    new = '''def _titles_related(left: str, right: str) -> bool:
    left_tokens = set(_normalize(left).split())
    right_tokens = set(_normalize(right).split())
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens
    length_ratio = min(len(left_tokens), len(right_tokens)) / max(
        len(left_tokens), len(right_tokens)
    )
    return len(overlap) >= 4 and len(overlap) / len(union) >= 0.85 and length_ratio >= 0.75
'''
    source = _replace_once(source, old, new, label="strict title relation")
    SCORER_PATH.write_text(source, encoding="utf-8")


def _write_tests() -> None:
    ADAPTER_TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADAPTER_TEST_PATH.write_text(
        r'''from __future__ import annotations

from types import SimpleNamespace

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import PaperRecord, RankFeatures, SourceRecord


def _paper(*, verified: bool = True) -> PaperRecord:
    return PaperRecord(
        paper_id="paper-patchtst",
        canonical_title="A Time Series is Worth 64 Words: Long-term Forecasting with Transformers",
        abstract=(
            "PatchTST improves forecasting accuracy. Code is available at: "
            "https://github.com/yuqinie98/PatchTST."
        ),
        doi="10.48550/arxiv.2211.14730",
        urls=["https://arxiv.org/abs/2211.14730"],
        source_records=[
            SourceRecord(provider="openalex", provider_record_id="oa", request_id="req")
        ],
        verification_status="verified" if verified else "pending",
        rank_features=RankFeatures(
            relevance=1.0,
            gap_coverage=1.0,
            metadata_verification=1.0,
            recency_fit=1.0,
            diversity=1.0,
            citation_tiebreaker=1.0,
            score=0.95,
        ),
    )


def test_verified_paper_emits_distinct_author_linked_repository_candidate() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q1",
        gap_id="g1",
        query="PatchTST official implementation repository",
        source_types=["paper", "repository", "web"],
    )

    candidates = adapter._candidates(query, _paper(), False)

    assert [candidate.source_type for candidate in candidates] == ["paper", "repository"]
    repository = candidates[1]
    assert repository.title == "yuqinie98/PatchTST"
    assert repository.locator == "https://github.com/yuqinie98/patchtst"
    assert repository.metadata["verification_status"] == "verified"
    assert repository.metadata["relation"] == "author_linked_from_verified_paper"


def test_unverified_paper_does_not_promote_repository_identity() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q1",
        gap_id="g1",
        query="PatchTST official implementation repository",
        source_types=["paper", "repository", "web"],
    )

    candidates = adapter._candidates(query, _paper(verified=False), False)

    assert [candidate.source_type for candidate in candidates] == ["paper"]
''',
        encoding="utf-8",
    )

    METHOD_TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    METHOD_TEST_PATH.write_text(
        r'''from __future__ import annotations

from datetime import UTC, datetime

from paperagent.method_design_draft import _select_primary_evidence
from paperagent.schemas import EvidenceItem


def _item(evidence_id: str, title: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"doi:10.1000/{evidence_id}",
        retrieved_at=datetime(2026, 7, 21, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["g1"],
        summary="Verified method paper with an experimental comparison.",
        content_hash=f"sha256:{evidence_id}",
    )


def test_declared_baseline_is_anchored_even_when_not_first_evidence() -> None:
    distracting = _item("distracting", "An Evaluation of Large Language Models for Sarcasm")
    bert = _item(
        "bert",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    )

    selected = _select_primary_evidence(
        [
            "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding "
            "[declared role: baseline]"
        ],
        (distracting, bert),
    )

    assert selected.evidence_id == "bert"


def test_similar_prefixed_paper_does_not_replace_declared_baseline() -> None:
    variant = _item(
        "variant",
        "Multispectral-oriented R-CNN for object detection in remote sensing images",
    )
    exact = _item("exact", "Oriented R-CNN for Object Detection")

    selected = _select_primary_evidence(
        ["Oriented R-CNN for Object Detection [declared role: reproduced baseline]"],
        (variant, exact),
    )

    assert selected.evidence_id == "exact"
''',
        encoding="utf-8",
    )

    scorer_tests = SCORER_TEST_PATH.read_text(encoding="utf-8")
    addition = r'''


def test_title_identity_is_symmetric_and_rejects_prefixed_neighbor_paper() -> None:
    assert _titles_related(
        "Oriented R-CNN for Object Detection",
        "Oriented R-CNN for Object Detection",
    )
    assert not _titles_related(
        "Multispectral-oriented R-CNN for object detection in remote sensing images",
        "Oriented R-CNN for Object Detection",
    )
'''
    if "test_title_identity_is_symmetric_and_rejects_prefixed_neighbor_paper" not in scorer_tests:
        scorer_tests += addition
    SCORER_TEST_PATH.write_text(scorer_tests, encoding="utf-8")


def main() -> int:
    _patch_adapter()
    _patch_method_design()
    _patch_scorer()
    _write_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
