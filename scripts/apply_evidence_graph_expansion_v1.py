from __future__ import annotations

from pathlib import Path


ADAPTER = Path("src/paperagent/literature/adapter.py")
ARXIV = Path("src/paperagent/literature/providers/arxiv.py")
METHOD = Path("src/paperagent/method_design_draft.py")
ADAPTER_TEST = Path("tests/literature/test_exact_identity_and_dataset_candidates.py")
METHOD_TEST = Path("tests/nodes/test_method_design_baseline_anchor.py")
ARXIV_TEST = Path("tests/literature/test_arxiv_title_query.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{path}: missing {label}")
    path.write_text(source, encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    source = path.read_text(encoding="utf-8")
    if marker not in source:
        source += addition
    path.write_text(source, encoding="utf-8")


def patch_adapter() -> None:
    replace_once(
        ADAPTER,
        "    ProviderResult,\n    QueryLane,\n)",
        "    ProviderResult,\n    QueryLane,\n    QueryPurpose,\n)",
        "QueryPurpose import",
    )
    replace_once(
        ADAPTER,
        '''def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    names: list[str] = []
    context = re.compile(
        r"(?P<names>[A-Za-z][A-Za-z0-9._-]*(?:\\s*(?:/|,|and)\\s*"
        r"[A-Za-z][A-Za-z0-9._-]*)*)\\s+(?:datasets?|benchmarks?|corpus|corpora)\\b",
        re.IGNORECASE,
    )
    for match in context.finditer(query):
        for raw_name in re.split(r"\\s*(?:/|,|and)\\s*", match.group("names")):
            name = raw_name.strip(".,;:()[]{}")
            if name.casefold() not in _DATASET_GENERIC and name not in names:
                names.append(name)
    return tuple(names)


def _paper_dataset_mentions(query: str, paper: PaperRecord) -> tuple[str, ...]:
    text = f"{paper.canonical_title}\\n{paper.abstract or ''}".casefold()
    return tuple(name for name in _dataset_names_from_query(query) if name.casefold() in text)
''',
        '''def _dataset_names_from_text(text: str) -> tuple[str, ...]:
    names: list[str] = []
    context = re.compile(
        r"(?P<names>[A-Za-z][A-Za-z0-9._-]*(?:\\s*(?:/|,|and)\\s*"
        r"[A-Za-z][A-Za-z0-9._-]*)*)\\s+(?:datasets?|benchmarks?|corpus|corpora)\\b",
        re.IGNORECASE,
    )
    for match in context.finditer(text):
        for raw_name in re.split(r"\\s*(?:/|,|and)\\s*", match.group("names")):
            name = raw_name.strip(".,;:()[]{}")
            if name.casefold() not in _DATASET_GENERIC and name not in names:
                names.append(name)
    return tuple(names)


def _dataset_names_from_query(query: str) -> tuple[str, ...]:
    return _dataset_names_from_text(query)


def _paper_dataset_mentions(query: str, paper: PaperRecord) -> tuple[str, ...]:
    paper_text = f"{paper.canonical_title}\\n{paper.abstract or ''}"
    normalized = paper_text.casefold()
    names = list(_dataset_names_from_text(paper_text))
    for name in _dataset_names_from_query(query):
        if name.casefold() in normalized and name not in names:
            names.append(name)
    return tuple(names)


def _dataset_relation_names(
    query: str,
    papers: Iterable[PaperRecord],
) -> tuple[str, ...]:
    names = list(_dataset_names_from_query(query))
    for paper in papers:
        for name in _dataset_names_from_text(
            f"{paper.canonical_title}\\n{paper.abstract or ''}"
        ):
            if name not in names:
                names.append(name)
    return tuple(names)
''',
        "dataset relation helpers",
    )
    replace_once(
        ADAPTER,
        "        policy = review_search_query(query)\n        required_title = _quoted_title(query.query)\n",
        "        policy = review_search_query(query)\n        required_title = _quoted_title(query.query)\n",
        "search identity prelude",
    )
    replace_once(
        ADAPTER,
        '        stop_reason = "academic_budget_exhausted"\n',
        '        stop_reason = "academic_budget_exhausted"\n'
        '        relation_paper_ids: set[str] = set()\n'
        '        dataset_links: dict[str, set[str]] = {}\n',
        "relation tracking",
    )
    replace_once(
        ADAPTER,
        '''            bundle = await self._service.retrieve(
                self._build_plan(query, [provider_name], lane_suffix=provider_name)
            )
''',
        '''            bundle = await self._service.retrieve(
                self._build_plan(
                    query,
                    [provider_name],
                    lane_suffix=provider_name,
                    query_text=required_title or query.query,
                    purpose="baseline" if required_title is not None else "method",
                    priority=95 if required_title is not None else 80,
                )
            )
''',
        "identity-focused initial plan",
    )
    replace_once(
        ADAPTER,
        '''        fallback_used = False
        if (
''',
        '''        relation_names = _dataset_relation_names(query.query, papers_by_id.values())
        if relation_names:
            dataset_name = relation_names[0]
            relation_provider = self._relation_provider(academic_order)
            relation_query = (
                f'"{dataset_name}" dataset benchmark baseline method comparison'
            )
            bundle = await self._service.retrieve(
                self._build_plan(
                    query,
                    [relation_provider],
                    lane_suffix=f"dataset-{dataset_name.casefold()}",
                    query_text=relation_query,
                    purpose="benchmark_dataset",
                    priority=75,
                )
            )
            attempted.append(f"{relation_provider}:dataset_relation")
            provider_results.extend(bundle.provider_results)
            for paper in bundle.papers:
                if self._passes_relation_relevance(paper):
                    relation_paper_ids.add(paper.paper_id)
                    dataset_links.setdefault(paper.paper_id, set()).add(dataset_name)
            self._merge_papers(papers_by_id, bundle.papers)

        fallback_used = False
        if (
''',
        "bounded dataset relation expansion",
    )
    replace_once(
        ADAPTER,
        '''        filtered = [
            paper for paper in papers_by_id.values() if self._passes_return_relevance(paper, policy)
        ]
        if required_title is not None:
            filtered = [
                paper
                for paper in filtered
                if _exact_title_match(paper.canonical_title, required_title)
            ]
''',
        '''        filtered = [
            paper
            for paper in papers_by_id.values()
            if self._passes_return_relevance(paper, policy)
            or paper.paper_id in relation_paper_ids
        ]
        if required_title is not None:
            filtered = [
                paper
                for paper in filtered
                if _exact_title_match(paper.canonical_title, required_title)
                or paper.paper_id in relation_paper_ids
            ]
''',
        "identity plus relation filtering",
    )
    replace_once(
        ADAPTER,
        '''            key=lambda paper: (
                paper.rank_features.score if paper.rank_features else 0.0,
                paper.paper_id,
            ),
''',
        '''            key=lambda paper: (
                int(
                    required_title is not None
                    and _exact_title_match(paper.canonical_title, required_title)
                ),
                int(paper.paper_id in relation_paper_ids),
                paper.rank_features.score if paper.rank_features else 0.0,
                paper.paper_id,
            ),
''',
        "identity-prioritized sorting",
    )
    replace_once(
        ADAPTER,
        '''        for paper in selected:
            candidates.extend(self._candidates(query, paper, fallback_used))
''',
        '''        for paper in selected:
            relation = (
                "declared_identity"
                if required_title is not None
                and _exact_title_match(paper.canonical_title, required_title)
                else (
                    "parallel_via_dataset"
                    if paper.paper_id in relation_paper_ids
                    else "direct_query"
                )
            )
            candidates.extend(
                self._candidates(
                    query,
                    paper,
                    fallback_used,
                    relation=relation,
                    linked_dataset_names=tuple(sorted(dataset_links.get(paper.paper_id, set()))),
                )
            )
''',
        "relation-aware candidate construction",
    )
    replace_once(
        ADAPTER,
        '''    def _academic_order(self, policy: SearchSourcePolicy, available: set[str]) -> tuple[str, ...]:
        policy_order = (policy.primary_provider, *policy.escalation_providers)
        allowed = set(self._academic_sources).intersection(_ACADEMIC_PROVIDERS)
        return tuple(
            provider
            for provider in dict.fromkeys(policy_order)
            if provider in available and provider in allowed
        )
''',
        '''    def _academic_order(self, policy: SearchSourcePolicy, available: set[str]) -> tuple[str, ...]:
        policy_order = (policy.primary_provider, *policy.escalation_providers)
        allowed = set(self._academic_sources).intersection(_ACADEMIC_PROVIDERS)
        return tuple(
            provider
            for provider in dict.fromkeys(policy_order)
            if provider in available and provider in allowed
        )

    @staticmethod
    def _relation_provider(academic_order: tuple[str, ...]) -> str:
        for preferred in ("semantic_scholar", "openalex", "arxiv"):
            if preferred in academic_order:
                return preferred
        return academic_order[0]
''',
        "relation provider selection",
    )
    replace_once(
        ADAPTER,
        '''    @staticmethod
    def _passes_return_relevance(paper: PaperRecord, policy: SearchSourcePolicy) -> bool:
        features = paper.rank_features
        if features is None:
            return False
        relevance_floor = max(0.25, policy.minimum_relevance * 0.8)
        score_floor = max(0.50, policy.minimum_rank_score * 0.85)
        return features.relevance >= relevance_floor and features.score >= score_floor
''',
        '''    @staticmethod
    def _passes_return_relevance(paper: PaperRecord, policy: SearchSourcePolicy) -> bool:
        features = paper.rank_features
        if features is None:
            return False
        relevance_floor = max(0.25, policy.minimum_relevance * 0.8)
        score_floor = max(0.50, policy.minimum_rank_score * 0.85)
        return features.relevance >= relevance_floor and features.score >= score_floor

    @staticmethod
    def _passes_relation_relevance(paper: PaperRecord) -> bool:
        features = paper.rank_features
        return (
            paper.verification_status == "verified"
            and features is not None
            and features.relevance >= 0.20
            and features.score >= 0.40
        )
''',
        "relation relevance floor",
    )
    replace_once(
        ADAPTER,
        '''    def _candidates(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
    ) -> list[SearchCandidate]:
        candidates = [self._candidate(query, paper, fallback_used)]
''',
        '''    def _candidates(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
        *,
        relation: str = "direct_query",
        linked_dataset_names: tuple[str, ...] = (),
    ) -> list[SearchCandidate]:
        candidates = [self._candidate(query, paper, fallback_used, relation=relation)]
''',
        "candidate relation signature",
    )
    replace_once(
        ADAPTER,
        '''        if "dataset" in query.source_types:
            parent_locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
            for dataset_name in _paper_dataset_mentions(query.query, paper):
                identity = f"{dataset_name.casefold()}|{paper.paper_id}"
                digest = sha256(identity.encode("utf-8")).hexdigest()[:20]
                candidates.append(
                    SearchCandidate(
                        candidate_id=f"dataset-{digest}",
                        query_id=query.query_id,
                        gap_id=query.gap_id,
                        source_type="dataset",
                        title=dataset_name,
                        locator=parent_locator,
                        snippet=(
                            f"Dataset {dataset_name!r} is explicitly named in the title "
                            "or abstract "
                            f"of the verified paper {paper.canonical_title!r}. This verifies the "
                            "dataset mention, not an official download page or split manifest."
                        ),
                        provider=self.provider_name,
                        metadata={
                            "query_text": query.query,
                            "verification_status": "verified",
                            "providers": ",".join(providers),
                            "provider_classes": "academic-linked-dataset-mention",
                            "source_kind": "dataset",
                            "rank_score": f"{score:.6f}",
                            "relevance_score": f"{relevance:.6f}",
                            "relation": "dataset_named_in_verified_paper",
                            "parent_paper_id": paper.paper_id,
                            "parent_paper_title": paper.canonical_title,
                            "dataset_ref": dataset_name,
                            "fallback_used": "true" if fallback_used else "false",
                            "web_supplement": "false",
                        },
                    )
                )
''',
        '''        if "dataset" in query.source_types:
            parent_locator = self._locator(paper.doi, paper.arxiv_id, paper.urls)
            explicit_mentions = _paper_dataset_mentions(query.query, paper)
            dataset_names = list(explicit_mentions)
            for linked_name in linked_dataset_names:
                if linked_name not in dataset_names:
                    dataset_names.append(linked_name)
            for dataset_name in dataset_names:
                identity = f"{dataset_name.casefold()}|{paper.paper_id}"
                digest = sha256(identity.encode("utf-8")).hexdigest()[:20]
                explicitly_named = dataset_name in explicit_mentions
                dataset_relation = (
                    "dataset_named_in_verified_paper"
                    if explicitly_named
                    else "dataset_linked_by_focused_retrieval"
                )
                snippet = (
                    f"Dataset {dataset_name!r} is explicitly named in the title or abstract "
                    f"of the verified paper {paper.canonical_title!r}. This verifies the "
                    "dataset mention, not an official download page or split manifest."
                    if explicitly_named
                    else (
                        f"Dataset {dataset_name!r} was the explicit anchor of a focused academic "
                        f"retrieval that returned verified paper {paper.canonical_title!r}. "
                        "This is a paper-dataset relation for discovery, not verification of an "
                        "official download page, license, or split manifest."
                    )
                )
                candidates.append(
                    SearchCandidate(
                        candidate_id=f"dataset-{digest}",
                        query_id=query.query_id,
                        gap_id=query.gap_id,
                        source_type="dataset",
                        title=dataset_name,
                        locator=parent_locator,
                        snippet=snippet,
                        provider=self.provider_name,
                        metadata={
                            "query_text": query.query,
                            "verification_status": "verified",
                            "verification_scope": (
                                "paper_mention" if explicitly_named else "retrieval_relation"
                            ),
                            "providers": ",".join(providers),
                            "provider_classes": "academic-linked-dataset-relation",
                            "source_kind": "dataset",
                            "rank_score": f"{score:.6f}",
                            "relevance_score": f"{relevance:.6f}",
                            "relation": dataset_relation,
                            "parent_paper_id": paper.paper_id,
                            "parent_paper_title": paper.canonical_title,
                            "dataset_ref": dataset_name,
                            "fallback_used": "true" if fallback_used else "false",
                            "web_supplement": "false",
                        },
                    )
                )
''',
        "dataset relation candidates",
    )
    replace_once(
        ADAPTER,
        '''    def _candidate(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
    ) -> SearchCandidate:
''',
        '''    def _candidate(
        self,
        query: SearchQuery,
        paper: PaperRecord,
        fallback_used: bool,
        *,
        relation: str = "direct_query",
    ) -> SearchCandidate:
''',
        "paper candidate relation signature",
    )
    replace_once(
        ADAPTER,
        '''                "source_kind": source_kind,
                "rank_score": f"{score:.6f}",
''',
        '''                "source_kind": source_kind,
                "relation": relation,
                "baseline_candidate": (
                    "declared" if relation == "declared_identity" else "inferred"
                ),
                "rank_score": f"{score:.6f}",
''',
        "paper relation metadata",
    )
    replace_once(
        ADAPTER,
        '''    def _build_plan(
        query: SearchQuery,
        source_preferences: list[str],
        *,
        lane_suffix: str,
    ) -> LiteratureQueryPlan:
        lane = QueryLane(
            lane_id=f"{query.query_id}-{lane_suffix}",
            purpose="method",
            query=query.query,
            source_preferences=list(source_preferences),
            gap_ids=[query.gap_id],
            priority=80,
        )
        return LiteratureQueryPlan(
            question=query.query,
            scope="literature retrieval",
            query_lanes=[lane],
            required_gap_ids=[query.gap_id],
            max_rounds=1,
        )
''',
        '''    def _build_plan(
        query: SearchQuery,
        source_preferences: list[str],
        *,
        lane_suffix: str,
        query_text: str | None = None,
        purpose: QueryPurpose = "method",
        priority: int = 80,
    ) -> LiteratureQueryPlan:
        effective_query = query_text or query.query
        lane = QueryLane(
            lane_id=f"{query.query_id}-{lane_suffix}",
            purpose=purpose,
            query=effective_query,
            source_preferences=list(source_preferences),
            gap_ids=[query.gap_id],
            priority=priority,
        )
        return LiteratureQueryPlan(
            question=effective_query,
            scope="literature retrieval and bounded evidence relation expansion",
            query_lanes=[lane],
            required_gap_ids=[query.gap_id],
            max_rounds=1,
        )
''',
        "configurable build plan",
    )


def patch_arxiv() -> None:
    replace_once(
        ARXIV,
        '''        params: dict[str, str | int] = {
            "search_query": f"all:{lane.query}",
            "start": 0,
            "max_results": min(limit, 10),
            "sortBy": "relevance",
        }
''',
        '''        normalized_query = " ".join(lane.query.split())
        escaped_query = normalized_query.replace('"', r'\\"')
        search_query = (
            f'ti:"{escaped_query}"'
            if lane.purpose == "baseline"
            else f"all:{normalized_query}"
        )
        params: dict[str, str | int] = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(limit, 10),
            "sortBy": "relevance",
        }
''',
        "arxiv title field query",
    )


def patch_method() -> None:
    replace_once(
        METHOD,
        '''def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    return _select_declared_baseline_evidence(references, candidates) or candidates[0]
''',
        '''def _baseline_evidence_rank(item: EvidenceItem) -> tuple[int, int, float, str]:
    if item.source_type != "paper":
        return (-1, -1, -1.0, item.evidence_id)
    marker = item.metadata.get("baseline_candidate", "")
    relation = item.metadata.get("relation", "")
    marker_rank = {"declared": 3, "inferred": 2}.get(marker, 1)
    relation_rank = {
        "declared_identity": 3,
        "parallel_via_dataset": 2,
        "direct_query": 1,
    }.get(relation, 0)
    try:
        rank_score = float(item.metadata.get("rank_score", "0"))
    except ValueError:
        rank_score = 0.0
    return (marker_rank, relation_rank, rank_score, item.evidence_id)


def _select_inferred_baseline_evidence(
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem | None:
    papers = tuple(item for item in candidates if item.source_type == "paper")
    return max(papers, key=_baseline_evidence_rank, default=None)


def _select_primary_evidence(
    references: list[str],
    candidates: tuple[EvidenceItem, ...],
) -> EvidenceItem:
    if not candidates:
        raise ValueError("primary evidence selection requires candidates")
    declared = _select_declared_baseline_evidence(references, candidates)
    return declared or _select_inferred_baseline_evidence(candidates) or candidates[0]


def _question_declares_dataset(question: str) -> bool:
    return bool(
        re.search(r"\\b(?:datasets?|benchmarks?|corpus|corpora|data[ -]?set)\\b", question, re.I)
    )


def _dataset_plan_value(
    question: str,
    *,
    readiness_confirmed: bool,
) -> str:
    if readiness_confirmed:
        return "user-declared frozen dataset; preserve the exact identifier and fingerprint"
    if _question_declares_dataset(question):
        return (
            "declared dataset identity unresolved; verify the exact dataset, split, license, "
            "and fingerprint before the pilot"
        )
    return (
        "no public dataset is required at discovery time; use task-appropriate user-owned, "
        "synthetic, simulated, or newly collected data and freeze provenance, split, license, "
        "and fingerprint before execution"
    )
''',
        "inferred baseline and optional dataset helpers",
    )
    replace_once(
        METHOD,
        '''    method_evidence = attributed if attributed else accepted
    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    )
    primary = baseline_evidence or method_evidence[0]
''',
        '''    method_evidence = attributed if attributed else accepted
    declared_baseline_titles = _declared_baseline_titles(list(request.user_material_refs))
    baseline_evidence = _select_declared_baseline_evidence(
        list(request.user_material_refs), method_evidence
    )
    primary = baseline_evidence or _select_inferred_baseline_evidence(method_evidence)
    if primary is None:
        raise ValueError("method canonicalization requires accepted paper evidence")
''',
        "paper-only inferred primary",
    )
    replace_once(
        METHOD,
        '''    dataset = grounded_dataset or (
        "user-declared frozen dataset; preserve the exact identifier and fingerprint"
        if readiness_confirmed
        else (
            "unresolved task-matched public dataset; select and freeze the dataset, split, "
            "and data fingerprint before the pilot"
        )
    )
''',
        '''    dataset = grounded_dataset or _dataset_plan_value(
        request.question,
        readiness_confirmed=readiness_confirmed,
    )
''',
        "optional dataset plan value",
    )
    replace_once(
        METHOD,
        '''    baseline_source_evidence_id = (
        baseline_evidence.evidence_id
        if baseline_evidence is not None
        else (None if baseline_unresolved else primary.evidence_id)
    )
''',
        '''    baseline_source_evidence_id = (
        baseline_evidence.evidence_id
        if baseline_evidence is not None
        else (None if baseline_unresolved else primary.evidence_id)
    )
    baseline_inferred = not declared_baseline_titles and baseline_evidence is None
''',
        "inferred baseline state",
    )
    replace_once(
        METHOD,
        '''            else (
                "user-declared frozen implementation; preserve the exact version or commit"
                if readiness_confirmed
                else (
                    f"review source {primary.stable_identifier}; implementation baseline unresolved"
                    if review_primary
                    else (
                        f"published source {primary.stable_identifier}; "
                        "implementation commit unresolved"
                    )
                )
            )
''',
        '''            else (
                "user-declared frozen implementation; preserve the exact version or commit"
                if readiness_confirmed
                else (
                    (
                        f"inferred from evidence relation at {primary.stable_identifier}; "
                        "reproduce and freeze an implementation before module integration"
                    )
                    if baseline_inferred
                    else (
                        f"review source {primary.stable_identifier}; implementation baseline unresolved"
                        if review_primary
                        else (
                            f"published source {primary.stable_identifier}; "
                            "implementation commit unresolved"
                        )
                    )
                )
            )
''',
        "inferred baseline version semantics",
    )
    replace_once(
        METHOD,
        '''            "implementation and evidence licenses must be resolved before code reuse",
''',
        '''            "implementation and evidence licenses must be resolved before code reuse",
            (
                "a public dataset is optional for niche tasks, but any user-owned, synthetic, "
                "simulated, or newly collected data must be frozen with provenance before execution"
            ),
''',
        "optional dataset risk",
    )


def patch_tests() -> None:
    replace_once(
        ADAPTER_TEST,
        '''    _exact_title_match,
    _quoted_title,
)
''',
        '''    _dataset_relation_names,
    _exact_title_match,
    _quoted_title,
)
''',
        "adapter helper import",
    )
    append_once(
        ADAPTER_TEST,
        "test_dataset_can_be_discovered_from_parallel_paper_text",
        '''


def test_dataset_can_be_discovered_from_parallel_paper_text() -> None:
    names = _dataset_relation_names(
        "compare robust anomaly detection methods",
        (
            _paper(
                "A Parallel Industrial Anomaly Method",
                "We evaluate the method on the MIMII dataset and report low-SNR results.",
            ),
        ),
    )
    assert names == ("MIMII",)


def test_dataset_relation_candidate_survives_missing_provider_abstract() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-linked-dataset",
        gap_id="g-linked-dataset",
        query="Evaluate PANNs on the MIMII dataset under low SNR",
        source_types=["paper", "dataset"],
    )
    candidates = adapter._candidates(
        query,
        _paper("A verified MIMII benchmark paper"),
        False,
        relation="parallel_via_dataset",
        linked_dataset_names=("MIMII",),
    )
    datasets = [item for item in candidates if item.source_type == "dataset"]
    assert len(datasets) == 1
    assert datasets[0].title == "MIMII"
    assert datasets[0].metadata["relation"] == "dataset_linked_by_focused_retrieval"
    assert datasets[0].metadata["verification_scope"] == "retrieval_relation"
''',
    )
    replace_once(
        METHOD_TEST,
        '''    _select_dataset_evidence,
    _select_declared_baseline_evidence,
    _select_primary_evidence,
)
''',
        '''    _dataset_plan_value,
    _select_dataset_evidence,
    _select_declared_baseline_evidence,
    _select_primary_evidence,
)
''',
        "method helper import",
    )
    replace_once(
        METHOD_TEST,
        '''def _item(evidence_id: str, title: str) -> EvidenceItem:
''',
        '''def _item(
    evidence_id: str,
    title: str,
    *,
    metadata: dict[str, str] | None = None,
) -> EvidenceItem:
''',
        "method test metadata helper signature",
    )
    replace_once(
        METHOD_TEST,
        '''        content_hash=f"sha256:{evidence_id}",
    )
''',
        '''        content_hash=f"sha256:{evidence_id}",
        metadata=metadata or {},
    )
''',
        "method test metadata helper body",
    )
    append_once(
        METHOD_TEST,
        "test_inferred_baseline_prefers_dataset_linked_parallel_paper",
        '''


def test_inferred_baseline_prefers_dataset_linked_parallel_paper() -> None:
    direct = _item(
        "direct",
        "A Broad Survey-like Method Candidate",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "direct_query",
            "rank_score": "0.91",
        },
    )
    linked = _item(
        "linked",
        "A Task-Matched Parallel Baseline",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.72",
        },
    )
    selected = _select_primary_evidence([], (direct, linked))
    assert selected.evidence_id == "linked"


def test_niche_task_can_defer_public_dataset_selection() -> None:
    value = _dataset_plan_value(
        "Design a method for a rare proprietary sensor failure mode",
        readiness_confirmed=False,
    )
    assert "no public dataset is required at discovery time" in value
    assert "freeze provenance" in value


def test_explicit_dataset_request_remains_a_verification_gate() -> None:
    value = _dataset_plan_value(
        "Evaluate the method on the MIMII dataset",
        readiness_confirmed=False,
    )
    assert "declared dataset identity unresolved" in value
''',
    )
    if not ARXIV_TEST.exists():
        ARXIV_TEST.write_text(
            '''from __future__ import annotations

import asyncio

from paperagent.literature.providers.arxiv import ArxivProvider
from paperagent.literature.providers.base import HTTPResponse
from paperagent.schemas.literature import LiteratureFilters, QueryLane


class _CapturingTransport:
    def __init__(self) -> None:
        self.params: dict[str, str | int] | None = None

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HTTPResponse:
        del url, headers, timeout
        self.params = params
        return HTTPResponse(
            status_code=200,
            headers={},
            json_data=None,
            text=(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
            ),
        )



def test_baseline_identity_uses_arxiv_title_field_query() -> None:
    transport = _CapturingTransport()
    provider = ArxivProvider(transport=transport)
    lane = QueryLane(
        lane_id="identity",
        purpose="baseline",
        query="USAD: UnSupervised Anomaly Detection on Multivariate Time Series",
        source_preferences=["arxiv"],
        gap_ids=["g1"],
        priority=95,
    )
    asyncio.run(provider.search(lane=lane, filters=LiteratureFilters(), limit=5))
    assert transport.params is not None
    assert transport.params["search_query"] == (
        'ti:"USAD: UnSupervised Anomaly Detection on Multivariate Time Series"'
    )



def test_non_identity_arxiv_query_remains_full_text() -> None:
    transport = _CapturingTransport()
    provider = ArxivProvider(transport=transport)
    lane = QueryLane(
        lane_id="dataset-relation",
        purpose="benchmark_dataset",
        query='"MIMII" dataset benchmark baseline method comparison',
        source_preferences=["arxiv"],
        gap_ids=["g1"],
        priority=75,
    )
    asyncio.run(provider.search(lane=lane, filters=LiteratureFilters(), limit=5))
    assert transport.params is not None
    assert transport.params["search_query"] == (
        'all:"MIMII" dataset benchmark baseline method comparison'
    )
''',
            encoding="utf-8",
        )


def main() -> int:
    patch_adapter()
    patch_arxiv()
    patch_method()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
