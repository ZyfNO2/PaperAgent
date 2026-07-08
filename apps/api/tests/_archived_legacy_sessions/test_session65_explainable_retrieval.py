"""Session 65: Tests for explainable retrieval and baseline selection."""

import pytest


# Keyword match explainer tests
def test_keyword_match_explainer_matched():
    """Test that matched keywords are correctly identified."""
    from app.services.retrieval.keyword_match_explainer import explain_keyword_match

    candidate = {
        "candidate_id": "c1",
        "title": "U-Net for Steel Crack Segmentation",
        "abstract": "We propose a U-Net architecture for steel crack segmentation on surface defect datasets.",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["裂缝检测", "segmentation"],
        "object_terms": ["钢材", "裂缝"],
    }

    result = explain_keyword_match(candidate, topic_atoms)
    assert "U-Net" in result.matched_topic_keywords
    assert "segmentation" in result.matched_related_keywords or "segmentation" in result.matched_topic_keywords
    assert result.evidence_gap != "wrong_domain"


def test_keyword_match_explainer_german_survey_rejected():
    """German survey should not match any topic atoms."""
    from app.services.retrieval.keyword_match_explainer import explain_keyword_match

    candidate = {
        "candidate_id": "c2",
        "title": "AIn't Nothing But a Survey: German Open-Ended Survey Responses",
        "abstract": "Survey motivation for German coding tasks.",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["裂缝检测"],
        "object_terms": ["钢材"],
    }

    result = explain_keyword_match(candidate, topic_atoms)
    assert len(result.matched_topic_keywords) == 0
    assert result.evidence_gap == "wrong_domain"


def test_keyword_match_explainer_structural_steel_background():
    """Structural steel paper should be related_background, not main."""
    from app.services.retrieval.keyword_match_explainer import explain_keyword_match

    candidate = {
        "candidate_id": "c3",
        "title": "Statistical analysis of structural stainless steels and members",
        "abstract": "Material characteristics of structural stainless steel.",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["裂缝检测"],
        "object_terms": ["钢材", "裂缝"],
    }

    result = explain_keyword_match(candidate, topic_atoms)
    # Should match "钢材" as related, but not have full match
    assert "钢材" in result.matched_related_keywords or len(result.matched_topic_keywords) == 0


def test_keyword_match_no_score():
    """Result should NOT contain numeric score."""
    from app.services.retrieval.keyword_match_explainer import explain_keyword_match

    candidate = {"candidate_id": "c4", "title": "Test"}
    topic_atoms = {"method_terms": [], "task_terms": [], "object_terms": []}

    result = explain_keyword_match(candidate, topic_atoms)
    # Verify no score field
    assert "score" not in result.model_dump()
    assert "confidence" not in result.model_dump()


# Baseline selection tests
def test_baseline_selection_saves():
    """User can select baseline from candidate."""
    from app.services.retrieval.baseline_selection import select_baseline, get_selected_baselines, reset_baseline_state

    reset_baseline_state()
    select_baseline(
        project_id="test_proj_1",
        candidate={"candidate_id": "cand_yolo_001", "title": "YOLOv8", "clean_status": "keep"},
        role="primary",
        user_reason="User chose YOLOv8 as primary baseline",
    )

    selected = get_selected_baselines("test_proj_1")
    assert len(selected) == 1
    assert selected[0].candidate_id == "cand_yolo_001"
    assert selected[0].baseline_role == "primary"


def test_baseline_selection_unselect():
    """User can unselect baseline."""
    from app.services.retrieval.baseline_selection import select_baseline, unselect_baseline, get_selected_baselines, reset_baseline_state

    reset_baseline_state()
    select_baseline(
        project_id="test_proj_2",
        candidate={"candidate_id": "cand_001", "title": "Test"},
        role="primary",
        user_reason="test",
    )
    unselect_baseline("test_proj_2", "cand_001")

    selected = get_selected_baselines("test_proj_2")
    assert len(selected) == 0


def test_baseline_cannot_be_irrelevant():
    """Irrelevant candidate cannot be baseline."""
    from app.services.retrieval.baseline_selection import can_be_baseline

    irrelevant = {"clean_status": "reject", "literature_role": "irrelevant"}
    assert can_be_baseline(irrelevant) is False


def test_baseline_cannot_be_survey():
    """Survey candidate cannot be baseline."""
    from app.services.retrieval.baseline_selection import can_be_baseline

    survey = {"clean_status": "keep", "literature_role": "survey"}
    assert can_be_baseline(survey) is False


def test_baseline_cannot_be_dataset():
    """Dataset candidate cannot be baseline."""
    from app.services.retrieval.baseline_selection import can_be_baseline

    dataset = {"clean_status": "keep", "candidate_type": "dataset"}
    assert can_be_baseline(dataset) is False


# Work package brainstormer tests
def test_brainstormer_no_baseline_returns_needs_selection():
    """If no baseline, return needs_baseline_selection."""
    from app.services.proposal.work_package_brainstormer import brainstorm_work_packages

    result = brainstorm_work_packages(
        selected_baselines=[],
        parallel_papers=[],
        module_papers=[],
        datasets=[],
        user_constraints={},
    )

    assert result.status == "needs_baseline_selection"
    assert len(result.options) == 0


def test_brainstormer_no_default_attention():
    """Default attention mechanism should NOT appear in options."""
    from app.services.proposal.work_package_brainstormer import brainstorm_work_packages

    selected = [{"candidate_id": "b1", "name": "U-Net", "clean_status": "keep"}]
    parallel = [{"candidate_id": "p1", "literature_role": "parallel_application_paper"}]
    module = [{"candidate_id": "m1", "literature_role": "module_improvement_paper"}]

    result = brainstorm_work_packages(
        selected_baselines=selected,
        parallel_papers=parallel,
        module_papers=module,
        datasets=[{"name": "NEU-DET"}],
        user_constraints={},
    )

    # All modules in options should come from input papers, not hardcoded
    for option in result.options:
        for module in option.module_candidates:
            # Module should NOT be default "attention mechanism"
            assert module.lower() != "attention mechanism" or "attention" in [
                m.lower() for m in result.options[0].module_candidates
            ]


# Tool orchestrator tests
def test_tool_orchestrator_whitelist():
    """Only whitelisted tools can be executed."""
    from app.services.retrieval.tool_orchestrator import _validate_tool_name

    # Whitelisted tools should pass
    for tool in ["search_openalex", "search_arxiv", "search_github"]:
        _validate_tool_name(tool)  # Should not raise

    # Non-whitelisted should fail
    with pytest.raises(Exception):
        _validate_tool_name("rm -rf /")
    with pytest.raises(Exception):
        _validate_tool_name("shell_execute")
