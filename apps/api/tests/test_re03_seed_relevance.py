"""Re03 SOP §6.1: seed_relevance gate tests (SOP §1.3 noise regression case)."""


from app.services.agents.seed_relevance import evaluate_seed, filter_seeds


def test_cosmic_ray_paper_rejected_by_seed_gate():
    """The canonical noise regression case from Re03 SOP §6.3.

    A "cosmic ray at CERN" paper must be REJECTED as citation seed even
    though it has an arxiv_id. It only overlaps the topic's method_terms
    loosely and has no task/object match.
    """
    cosmic_ray = {
        "candidate_id": "c-cosmic",
        "title": "A study of the link between cosmic rays and clouds with a cloud chamber at the CERN PS",
        "abstract": "We study cosmic ray interactions with a cloud chamber at CERN PS-T7.",
    }
    parsed_topic = {
        "method_terms": ["U-Net", "point cloud"],
        "task_terms": ["damage detection", "crack segmentation"],
        "object_terms": ["steel surface", "bridge"],
        "query_atoms_en": ["3D point cloud damage", "U-Net steel crack"],
        "domain_route": "vision_3d",
    }
    v = evaluate_seed(candidate=cosmic_ray, parsed_topic=parsed_topic)
    assert v["seed_eligible"] is False
    assert v["matched_axis"] == "none"
    assert "no relevance match" in v["rejected_reason"]


def test_casualty_detection_3d_paper_accepted_by_seed_gate():
    """Strong-hit 3D damage paper (Case A) must be eligible."""
    paper = {
        "candidate_id": "c-casualty",
        "title": "Casualty Detection from 3D Point Cloud Data for Autonomous Ground Mobile Rescue Robots",
        "abstract": "We propose a 3D point cloud detection method for casualty identification on damaged surfaces.",
    }
    parsed_topic = {
        "method_terms": ["3D point cloud", "deep learning"],
        "task_terms": ["damage detection", "anomaly detection"],
        "object_terms": ["3D point cloud", "rescue robots"],
        "query_atoms_en": ["3D point cloud damage"],
        "domain_route": "vision_3d",
    }
    v = evaluate_seed(candidate=paper, parsed_topic=parsed_topic)
    assert v["seed_eligible"] is True
    assert v["matched_axis"] in {"method_task", "method_object"}


def test_filter_seeds_splits_eligible_rejected():
    seeds = [
        {"candidate_id": "c-ok", "title": "U-Net steel crack segmentation",
         "abstract": "Crack segmentation on steel plates using U-Net."},
        {"candidate_id": "c-cosmic", "title": "Cosmic ray at CERN cloud chamber",
         "abstract": "Astrophysics with cloud chamber."},
        {"candidate_id": "c-brown", "title": "Brown dwarf survey in Taurus",
         "abstract": "Survey of brown dwarfs in Taurus Molecular Cloud."},
    ]
    parsed_topic = {
        "method_terms": ["U-Net"],
        "task_terms": ["crack segmentation"],
        "object_terms": ["steel plate"],
        "query_atoms_en": ["U-Net steel crack"],
        "domain_route": "vision_2d",
    }
    eligible, rejected = filter_seeds(seeds, parsed_topic)
    assert len(eligible) == 1
    assert eligible[0]["candidate_id"] == "c-ok"
    rejected_ids = {r["candidate_id"] for r in rejected}
    assert "c-cosmic" in rejected_ids
    assert "c-brown" in rejected_ids


def test_seed_gate_with_no_anchors_falls_back_to_atoms():
    """If method/task/object are empty, atoms must give the gate a basis."""
    paper = {
        "candidate_id": "c-1",
        "title": "Time-series satellite crop mapping",
        "abstract": "Multi-temporal Sentinel-2 crop classification with LSTM.",
    }
    parsed_topic = {
        "method_terms": [],
        "task_terms": [],
        "object_terms": [],
        "query_atoms_en": ["multi-temporal satellite crop", "Sentinel-2 LSTM"],
        "domain_route": "remote_sensing",
    }
    v = evaluate_seed(candidate=paper, parsed_topic=parsed_topic)
    # Should match at least 2 atom groups; 1.0 hit (everything in haystack)
    # is fine.
    assert v["seed_eligible"] is True
