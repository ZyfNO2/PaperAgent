"""Re6.4 Academic Tailor 2.0 — L0 schema + semantic validator tests."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# EvidenceContext
# ---------------------------------------------------------------------------
class TestEvidenceContext:
    def test_valid_context(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import EvidenceContext
        ctx = EvidenceContext(
            candidate_id="p1",
            snippet="uses attention mechanism",
            location="Section 3.2",
            role="method",
            source_quality="verified",
        )
        assert ctx.candidate_id == "p1"
        assert ctx.role == "method"

    def test_defaults(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import EvidenceContext
        ctx = EvidenceContext(candidate_id="p1", snippet="test", location="loc")
        assert ctx.role == "problem"
        assert ctx.source_quality == "verified"
        assert ctx.chunk_id is None


# ---------------------------------------------------------------------------
# NoveltyCandidate
# ---------------------------------------------------------------------------
class TestNoveltyCandidate:
    def test_valid_candidate(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate
        c = NoveltyCandidate(
            problem="unresolved gap in X",
            method="our method specifically addresses gap X via mechanism Y",
            insight="Condition Z must hold for mechanism Y to be effective when task T",
            evidence_ids=["ev1", "ev2", "ev3"],
            status="under_review",
        )
        assert c.status == "under_review"
        assert len(c.evidence_ids) == 3

    def test_rejects_insufficient_evidence_for_accepted(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate
        with pytest.raises(ValueError, match="3 evidence_ids"):
            NoveltyCandidate(
                problem="gap",
                method="method",
                insight="insight about mechanism",
                evidence_ids=["ev1"],
                status="accepted",
            )

    def test_performance_only_insight_downgraded(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate
        c = NoveltyCandidate(
            problem="unresolved gap",
            method="method",
            insight="F1 提高了 5% and achieves SOTA outperforms baseline by 3%",
            evidence_ids=["ev1", "ev2", "ev3"],
            status="draft",
        )
        assert c.status == "needs_evidence"

    def test_first_claim_downgraded(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate
        c = NoveltyCandidate(
            problem="首次提出 a new approach",
            method="method",
            insight="insight about mechanism",
            evidence_ids=["ev1", "ev2", "ev3"],
            status="draft",
        )
        assert c.status == "needs_literature_verification"
        assert "first_claim_unsupported" in c.pseudo_innovation_risks

    def test_has_all_evidence_roles(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate
        c = NoveltyCandidate(
            problem="gap", method="method", insight="insight",
            evidence_ids=["a", "b", "c", "d"],
        )
        assert c.has_all_evidence_roles()

    def test_is_insight_performance_only(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate
        c = NoveltyCandidate(
            problem="gap", method="method",
            insight="outperforms baseline",
            evidence_ids=["a", "b", "c"],
        )
        assert c.is_insight_performance_only()


# ---------------------------------------------------------------------------
# DifferentiationMatrix
# ---------------------------------------------------------------------------
class TestDifferentiationMatrix:
    def test_valid_matrix(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import DifferentiationMatrix
        m = DifferentiationMatrix(
            adjacent_work_id="p1",
            adjacent_work_label="Paper X",
            problem_diff="differs on scope",
            method_diff="differs on architecture",
            detail_diff="differs on attention head count",
            evidence_diff="differs on evaluation dataset",
            insight_diff="differs on why improvement happens",
        )
        assert m.adjacent_work_id == "p1"

    def test_rejects_missing_dimension(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import DifferentiationMatrix
        with pytest.raises(ValueError, match="missing dimensions"):
            DifferentiationMatrix(
                adjacent_work_id="p1",
                adjacent_work_label="X",
                problem_diff="x",
                method_diff="",
                detail_diff="x",
                evidence_diff="x",
                insight_diff="x",
            )


# ---------------------------------------------------------------------------
# FalsifiableProposition
# ---------------------------------------------------------------------------
class TestFalsifiableProposition:
    def test_valid_proposition(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import FalsifiableProposition
        p = FalsifiableProposition(
            proposition="X causes Y under condition Z",
            scoped_setting="task T with dataset D",
            observable_effect="metric M increases",
            support_condition="M > baseline + 3%",
            refute_condition="M <= baseline + 1%",
            required_test="ablation study removing X",
            evidence_ids=["ev1"],
            status="planned_not_verified",
        )
        assert p.proposition_id

    def test_rejects_missing_triad(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import FalsifiableProposition
        with pytest.raises(ValueError, match="missing"):
            FalsifiableProposition(
                proposition="claim",
                scoped_setting="setting",
                observable_effect="effect",
                support_condition="",  # Empty
                refute_condition="r",
                required_test="t",
            )

    def test_default_status_planned_not_verified(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import FalsifiableProposition
        p = FalsifiableProposition(
            proposition="claim",
            scoped_setting="s",
            observable_effect="e",
            support_condition="s",
            refute_condition="r",
            required_test="t",
        )
        assert p.status == "planned_not_verified"


# ---------------------------------------------------------------------------
# ReviewerPressurePoint
# ---------------------------------------------------------------------------
class TestReviewerPressurePoint:
    def test_valid_point(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import ReviewerPressurePoint
        pp = ReviewerPressurePoint(
            risk="repetition",
            question="How does this differ from [Paper X]?",
            severity="high",
            repair="Cite [Paper X] explicitly and show diff",
            evidence_ids=["p1"],
        )
        assert pp.risk == "repetition"
        assert pp.severity == "high"

    def test_fills_unknown_when_no_evidence(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import ReviewerPressurePoint
        pp = ReviewerPressurePoint(
            risk="motivation",
            question="Why is this problem worth solving?",
            severity="medium",
            repair="Add industry statistics",
            evidence_ids=[],
        )
        assert pp.evidence_ids == ["unknown"]


# ---------------------------------------------------------------------------
# NoveltyRevision (Evolution Log)
# ---------------------------------------------------------------------------
class TestNoveltyRevision:
    def test_valid_revision(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import (
            NoveltyRevision, NoveltyCandidate,
        )
        c = NoveltyCandidate(
            problem="gap", method="method", insight="insight",
            evidence_ids=["a", "b", "c"],
        )
        r = NoveltyRevision(
            version=2,
            reason="updated scope",
            evidence_delta=["+ev4"],
            candidate_snapshot=c,
        )
        assert r.version == 2
        assert r.parent_revision_id is None

    def test_rejects_self_reference(self):
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyRevision
        rid = "abc"
        with pytest.raises(ValueError, match="cannot reference itself"):
            NoveltyRevision(
                revision_id=rid,
                parent_revision_id=rid,
                version=1,
                reason="test",
            )


# ---------------------------------------------------------------------------
# Novelty semantic validators
# ---------------------------------------------------------------------------
class TestNoveltyValidators:
    def test_validate_novelty_candidate_valid(self):
        from apps.api.app.services.router.validators.novelty_validators import validate_novelty_candidate
        ok, err = validate_novelty_candidate({
            "candidate_id": "nc-1",
            "problem": "specific gap",
            "method": "targeted intervention",
            "insight": "Conditional finding about mechanism Z",
            "evidence_ids": ["ev1", "ev2", "ev3"],
            "status": "under_review",
        })
        assert ok, err

    def test_validate_novelty_candidate_missing_pmi(self):
        from apps.api.app.services.router.validators.novelty_validators import validate_novelty_candidate
        ok, err = validate_novelty_candidate({
            "problem": "", "method": "m", "insight": "",
        })
        assert not ok

    def test_validate_novelty_review_all_5_dimensions(self):
        from apps.api.app.services.router.validators.novelty_validators import validate_novelty_review
        pp = [
            {"risk": r, "question": "q", "severity": "medium", "repair": "r", "evidence_ids": ["e1"]}
            for r in ("repetition", "motivation", "falsifiability", "differentiation", "story")
        ]
        ok, err = validate_novelty_review({
            "verdict": "weak_reject",
            "pressure_points": pp,
        })
        assert ok, err

    def test_validate_novelty_review_missing_dimension(self):
        from apps.api.app.services.router.validators.novelty_validators import validate_novelty_review
        ok, err = validate_novelty_review({
            "verdict": "accepted",
            "pressure_points": [
                {"risk": "repetition", "question": "q", "severity": "low", "repair": "r", "evidence_ids": []},
            ],
        })
        assert not ok
        assert "missing" in err

    def test_validate_falsifiable_batch(self):
        from apps.api.app.services.router.validators.novelty_validators import validate_falsifiability_batch
        ok, err = validate_falsifiability_batch({
            "propositions": [{
                "proposition_id": "fp-1",
                "proposition": "claim",
                "support_condition": "supports",
                "refute_condition": "refutes",
                "required_test": "test X",
                "status": "planned_not_verified",
            }],
        })
        assert ok, err

    def test_validate_falsifiable_batch_empty(self):
        from apps.api.app.services.router.validators.novelty_validators import validate_falsifiability_batch
        ok, _ = validate_falsifiability_batch({"propositions": []})
        assert not ok


# ---------------------------------------------------------------------------
# Novelty Evolution Log (node)
# ---------------------------------------------------------------------------
class TestNoveltyEvolution:
    def test_init_and_append(self):
        from apps.api.app.services.agents.graph.nodes.novelty_evolution import (
            init_evolution_log, append_revision, get_evolution_log,
            EVOLUTION_LOG_KEY,
        )
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        state: dict = {}
        init_evolution_log(state)
        assert EVOLUTION_LOG_KEY in state
        assert state[EVOLUTION_LOG_KEY] == []

        c = NoveltyCandidate(
            problem="gap", method="method", insight="insight",
            evidence_ids=["a", "b", "c"],
        )
        rev = append_revision(state, c, "initial draft")
        assert rev.version == 1
        assert len(get_evolution_log(state)) == 1

    def test_version_increments(self):
        from apps.api.app.services.agents.graph.nodes.novelty_evolution import (
            init_evolution_log, append_revision,
        )
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        state: dict = {}
        init_evolution_log(state)
        c = NoveltyCandidate(
            problem="gap", method="method", insight="insight",
            evidence_ids=["a", "b", "c"],
        )
        r1 = append_revision(state, c, "v1")
        r2 = append_revision(state, c, "v2")
        assert r1.version == 1
        assert r2.version == 2
        assert r2.parent_revision_id == r1.revision_id

    def test_get_candidate_history(self):
        from apps.api.app.services.agents.graph.nodes.novelty_evolution import (
            init_evolution_log, append_revision, get_candidate_history,
        )
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        state: dict = {}
        init_evolution_log(state)
        c = NoveltyCandidate(
            problem="gap", method="method", insight="insight",
            evidence_ids=["a", "b", "c"],
        )
        append_revision(state, c, "v1")
        append_revision(state, c, "v2")

        hist = get_candidate_history(state, c.candidate_id)
        assert len(hist) == 2
        assert hist[0]["version"] == 1
        assert hist[1]["version"] == 2

    def test_export_evolution_log(self):
        from apps.api.app.services.agents.graph.nodes.novelty_evolution import (
            init_evolution_log, append_revision, export_evolution_log,
        )
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        state: dict = {}
        init_evolution_log(state)
        c = NoveltyCandidate(
            problem="gap", method="method", insight="insight",
            evidence_ids=["a", "b", "c"],
        )
        append_revision(state, c, "test")
        exported = export_evolution_log(state)
        assert "exported_at" in exported
        assert "total_revisions" in exported

    def test_mark_innovation_status(self):
        from apps.api.app.services.agents.graph.nodes.novelty_evolution import (
            init_evolution_log, mark_innovation_status,
        )
        state = {
            "innovation_points": [
                {"id": "ip-1", "status": "draft"},
                {"id": "ip-2", "status": "accepted"},
            ],
        }
        init_evolution_log(state)
        found = mark_innovation_status(state, "ip-1", "accepted", "review passed")
        assert found
        assert state["innovation_points"][0]["status"] == "accepted"
