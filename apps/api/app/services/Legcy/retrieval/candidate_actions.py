"""S61 M7 (backend): 候选 → 具体动作.

将 ``RetrievalCandidate`` 路由到三种去向:
- evidence ledger (paper / dataset / repo 均可, 走 evidence.add_*_manual)
- paper library (仅 paper, 走 paper_library.manual_ingest.ingest_manual_text, M1 from S60)
- 不相关 (no-op, S61 不做持久化)
- 重新检索 (返回 3 个衍生查询)
"""

from __future__ import annotations

from typing import Any

from .orchestrator import get_run_by_id


# ---------- helpers ---------- #


def _find_candidate(project_id: str, candidate_id: str):
    """在最近一次 run 里找候选; 找不到就遍历所有 run."""

    from .orchestrator import _RUNS, _LOCK

    with _LOCK:
        runs = list(_RUNS.get(project_id, []))
    for run in reversed(runs):
        for cand in run.candidates:
            if cand.candidate_id == candidate_id:
                return cand, run
    return None, None


def _abstract_snippet(abstract: str | None, max_chars: int = 1500) -> str:
    if not abstract:
        return ""
    s = abstract.strip()
    return s[:max_chars]


def _has_training_signal(raw: dict) -> bool:
    """根据 github 描述或 topics 启发式判断是否有训练脚本."""

    blob_parts: list[str] = []
    for k in ("description", "topics", "readme_excerpt"):
        v = raw.get(k)
        if isinstance(v, str):
            blob_parts.append(v.lower())
        elif isinstance(v, list):
            blob_parts.append(" ".join(str(x) for x in v).lower())
    blob = " ".join(blob_parts)
    if not blob:
        return False
    keywords = ("train.py", "training script", "finetune", "fine-tune", "pretrain")
    return any(kw in blob for kw in keywords)


# ---------- a) to evidence ledger ---------- #


def add_candidate_to_evidence(project_id: str, candidate_id: str) -> dict:
    """从 run 找到候选, 写入 Evidence Ledger.

    Returns:
        {"ok": True/False, "evidence_id": "...", "candidate_id": "...", "message": "..."}
    """

    cand, _run = _find_candidate(project_id, candidate_id)
    if cand is None:
        return {"ok": False, "evidence_id": "", "candidate_id": candidate_id, "message": "候选不存在"}

    from .. import evidence as _ev
    from ...schemas_evidence import (
        DatasetManualCreate,
        PaperManualCreate,
        RepoManualCreate,
    )

    try:
        if cand.candidate_type == "paper":
            body = PaperManualCreate(
                title=cand.title,
                authors=list(cand.authors or []),
                year=cand.year,
                url=cand.url,
                doi=cand.doi,
                arxiv_id=cand.arxiv_id,
                abstract=cand.abstract,
                tags=[cand.source],
                review_status="pending",
            )
            resp = _ev.add_paper_manual(project_id, body)
        elif cand.candidate_type == "dataset":
            body = DatasetManualCreate(
                name=cand.title,
                scale=None,
                license=cand.license,
                download=cand.url,
                modality=[],
                annotation=None,
                review_status="pending",
            )
            resp = _ev.add_dataset_manual(project_id, body)
        elif cand.candidate_type == "repo":
            raw = cand.raw or {}
            desc = raw.get("description") or ""
            body = RepoManualCreate(
                name=cand.repo_full_name or cand.title,
                repository_url=cand.url,
                paper_title=None,
                license=cand.license,
                has_readme=bool(desc),
                has_env_file=False,
                has_training_script=_has_training_signal(raw),
                has_eval_script=False,
                review_status="pending",
            )
            resp = _ev.add_repo_manual(project_id, body)
        else:
            # project_page / note 退化到 paper 通道
            body = PaperManualCreate(
                title=cand.title,
                url=cand.url,
                year=cand.year,
                abstract=cand.abstract,
                tags=[cand.source, cand.candidate_type],
                review_status="pending",
            )
            resp = _ev.add_paper_manual(project_id, body)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "evidence_id": "", "candidate_id": candidate_id, "message": f"构造请求失败: {type(e).__name__}: {e}"}

    if not resp.ok:
        return {"ok": False, "evidence_id": resp.evidence_id, "candidate_id": candidate_id, "message": resp.message}

    return {
        "ok": True,
        "evidence_id": resp.evidence_id,
        "candidate_id": candidate_id,
        "message": f"候选已写入 Evidence Ledger ({resp.evidence_id})",
    }


# ---------- b) to paper library ---------- #


def add_candidate_to_paper_library(project_id: str, candidate_id: str) -> dict:
    """仅对 paper 候选生效, 走 paper_library.manual_ingest.ingest_manual_text."""

    cand, _run = _find_candidate(project_id, candidate_id)
    if cand is None:
        return {"ok": False, "paper_id": "", "candidate_id": candidate_id, "message": "候选不存在"}
    if cand.candidate_type != "paper":
        return {
            "ok": False,
            "paper_id": "",
            "candidate_id": candidate_id,
            "message": f"该候选类型为 {cand.candidate_type}, 仅 paper 可加入 Paper Library",
        }

    title = (cand.title or "").strip()
    abstract = _abstract_snippet(cand.abstract)
    if not title:
        return {"ok": False, "paper_id": "", "candidate_id": candidate_id, "message": "候选 title 为空, 无法入库"}

    body_text = title
    if abstract:
        body_text = f"{title}\n\nAbstract: {abstract}"

    from ..paper_library.manual_ingest import ingest_manual_text

    try:
        outcome = ingest_manual_text(
            project_id=project_id,
            title=title,
            text=body_text,
            url=cand.url,
            tags=[cand.source] if cand.source else None,
        )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "paper_id": "", "candidate_id": candidate_id, "message": f"manual_ingest 抛错: {type(e).__name__}: {e}"}

    ok = outcome.status in ("ingested", "duplicate")
    return {
        "ok": ok,
        "paper_id": outcome.paper_id,
        "candidate_id": candidate_id,
        "message": outcome.message or f"入库结果: {outcome.status}",
    }


# ---------- c) mark irrelevant ---------- #


def mark_candidate_irrelevant(project_id: str, candidate_id: str) -> dict:
    """S61 no-op: 不持久化标记, 仅返回成功占位.

    ponytail: 标记不相关不持久化, S61 不做 relevance feedback storage;
    留空操作不写 hidden store, 后续真需要再加.
    """

    return {"ok": True, "candidate_id": candidate_id, "message": "已标记不相关"}


# ---------- d) retry plan ---------- #


def plan_candidate_retry(project_id: str, candidate_id: str) -> dict:
    """基于候选 title/abstract 生成 3 条衍生检索查询."""

    cand, _run = _find_candidate(project_id, candidate_id)
    title = (cand.title if cand is not None else "") or ""
    abstract = (cand.abstract if cand is not None else "") or ""
    title = title.strip() or "(untitled)"

    queries = [
        f"{title} implementation",
        f"{title} baseline github",
        f"{title} survey 2024",
    ]
    msg = f"已为候选 {candidate_id} 生成 {len(queries)} 条衍生查询"
    if abstract.strip():
        msg += f" (基于 title='{title[:40]}...' + abstract 长度 {len(abstract)})"
    return {"ok": True, "candidate_id": candidate_id, "queries": queries, "message": msg}


# ---------- 内部: 兼容 import 路径 ---------- #


def _ensure_orchestrator_ref() -> Any:
    return get_run_by_id


__all__ = [
    "add_candidate_to_evidence",
    "add_candidate_to_paper_library",
    "mark_candidate_irrelevant",
    "plan_candidate_retry",
]


# ---------- self-check ---------- #


def _self_check() -> None:
    """Ponytail: 一个最小可运行检查, 没有 candidates 时返回 False."""

    from datetime import datetime, timezone

    from .. import evidence as _ev
    from .. import paper_library  # noqa: F401
    from ...schemas_retrieval import (
        QueryPlan,
        QueryPlanLayer,
        RetrievalCandidate,
        RetrievalRun,
        SourceResult,
    )

    # 清空 ledger + runs, 保证干净
    try:
        _ev.reset_evidence_state()
    except Exception:
        pass
    try:
        from . import orchestrator
        orchestrator.reset_retrieval_state()
    except Exception:
        pass

    plan = QueryPlan(
        project_id="proj_self_check",
        raw_topic="self check topic",
        paper_queries=[QueryPlanLayer(layer="L1", queries=["t"])],
        dataset_queries=[QueryPlanLayer(layer="L1", queries=["t"])],
        repo_queries=[QueryPlanLayer(layer="L1", queries=["t"])],
    )
    paper = RetrievalCandidate(
        candidate_id="cand_paper_1",
        project_id="proj_self_check",
        candidate_type="paper",
        source="arxiv",
        title="A Novel Survey on Topic Modeling",
        abstract="We survey topic modeling methods.",
        url="https://arxiv.org/abs/0000.0000",
        year=2024,
    )
    repo = RetrievalCandidate(
        candidate_id="cand_repo_1",
        project_id="proj_self_check",
        candidate_type="repo",
        source="github",
        title="topic-model-toolkit",
        url="https://github.com/example/topic-model-toolkit",
        repo_full_name="example/topic-model-toolkit",
        raw={"description": "A toolkit with train.py and README."},
    )
    run = RetrievalRun(
        run_id="ret_selfcheck",
        project_id="proj_self_check",
        query_plan=plan,
        sources=["arxiv", "github"],
        source_results=[SourceResult(source="arxiv", status="completed", candidate_count=1)],
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        status="completed",
        total_candidates=2,
        candidates=[paper, repo],
    )
    from . import orchestrator as _orch
    with _orch._LOCK:
        _orch._RUNS["proj_self_check"] = [run]

    # a) evidence
    r_a = add_candidate_to_evidence("proj_self_check", "cand_paper_1")
    assert r_a.get("ok") is True, r_a
    assert r_a.get("evidence_id", "").startswith("man_paper_"), r_a
    assert r_a.get("candidate_id") == "cand_paper_1"

    r_b = add_candidate_to_evidence("proj_self_check", "cand_repo_1")
    assert r_b.get("ok") is True, r_b
    assert r_b.get("evidence_id", "").startswith("man_repo_"), r_b

    # 重复 evidence (会有 ok=False)
    r_dup = add_candidate_to_evidence("proj_self_check", "cand_repo_1")
    assert r_dup.get("ok") is False, r_dup

    # b) paper library
    r_c = add_candidate_to_paper_library("proj_self_check", "cand_paper_1")
    assert r_c.get("ok") is True, r_c
    assert r_c.get("paper_id", "").startswith("paper_mn_"), r_c

    r_c_repo = add_candidate_to_paper_library("proj_self_check", "cand_repo_1")
    assert r_c_repo.get("ok") is False, r_c_repo
    assert "仅 paper" in r_c_repo.get("message", "")

    # c) mark irrelevant
    r_d = mark_candidate_irrelevant("proj_self_check", "cand_paper_1")
    assert r_d.get("ok") is True, r_d
    assert r_d.get("candidate_id") == "cand_paper_1"

    # d) retry plan
    r_e = plan_candidate_retry("proj_self_check", "cand_paper_1")
    assert r_e.get("ok") is True, r_e
    assert isinstance(r_e.get("queries"), list) and len(r_e["queries"]) == 3, r_e
    assert all("Novel Survey on Topic Modeling" in q for q in r_e["queries"]), r_e

    # 缺失候选
    r_missing = add_candidate_to_evidence("proj_self_check", "nope")
    assert r_missing.get("ok") is False, r_missing

    print("[candidate_actions] self-check OK")


if __name__ == "__main__":
    _self_check()
