"""Session 60: Local RAG 最小闭环 tests.

覆盖 (SOP §6.1):
1. manual ingest 成功生成 PaperRecord
2. manual ingest 成功生成 PaperChunk
3. index project 后 index/status 显示 chunk_count > 0
4. local-ask 命中已入库文本
5. local-ask 无命中时不编造答案
6. 空 title / 空 text 返回 400
7. schema 拒绝多余字段
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _tmp_library(monkeypatch, tmp_path):
    """每个测试用独立 .runtime/paper_library + 清 evidence + 清 vocab."""

    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(tmp_path / "paper_library"))
    from app.services import evidence as ev_store
    from app.services.paper_library import embedding
    ev_store.reset_all()
    embedding.reset_vocab()
    yield
    ev_store.reset_all()
    embedding.reset_vocab()


@pytest.fixture()
def client():
    return TestClient(app)


PROJECT = "s60-test"


def _sample_text() -> str:
    return (
        "This paper studies steel surface defect detection using YOLO. "
        "The experiment uses the NEU-DET dataset and reports that lightweight "
        "YOLO variants can detect scratches, patches and crazing defects. "
        "The method section describes data augmentation and evaluation."
    )


# ---------------------------------------------------------------------------
# 1) manual ingest → PaperRecord
# ---------------------------------------------------------------------------


def test_manual_ingest_creates_paper_record(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={
            "title": "YOLO Steel Defect Test 1",
            "text": _sample_text(),
            "url": None,
            "tags": ["方法参考"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ingested"
    assert body["is_duplicate"] is False
    assert body["parse_status"] == "parsed"
    assert body["chunk_count"] >= 1
    paper_id = body["paper_id"]
    assert paper_id.startswith("paper_mn_")

    # 验证 GET /paper-library 能列到
    list_resp = client.get(f"/api/v1/projects/{PROJECT}/paper-library")
    assert list_resp.status_code == 200
    listed = list_resp.json()["papers"]
    assert any(p["paper_id"] == paper_id for p in listed)


# ---------------------------------------------------------------------------
# 2) manual ingest → PaperChunk (从 GET /{paper_id} 看)
# ---------------------------------------------------------------------------


def test_manual_ingest_creates_chunks(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "Chunk Test", "text": _sample_text()},
    )
    paper_id = resp.json()["paper_id"]
    detail = client.get(f"/api/v1/projects/{PROJECT}/paper-library/{paper_id}").json()
    # chunk_total > 0
    assert detail["chunk_total"] >= 1
    # parse_status 是 parsed
    assert detail["paper"]["parse_status"] == "parsed"


# ---------------------------------------------------------------------------
# 3) index project → index/status 显示 chunk_count > 0
# ---------------------------------------------------------------------------


def test_project_index_status_after_ingest(client):
    client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "Index Status Test", "text": _sample_text()},
    )
    # 触发索引
    idx_resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/index",
        json={"force": False},
    )
    assert idx_resp.status_code == 200
    idx_body = idx_resp.json()
    assert idx_body["chunk_count"] >= 1
    assert idx_body["indexed"] >= 1

    # 查 status
    st_resp = client.get(f"/api/v1/projects/{PROJECT}/paper-library/index/status")
    assert st_resp.status_code == 200
    st = st_resp.json()
    assert st["total_papers"] >= 1
    assert st["total_chunks"] >= 1
    assert st["indexed_chunks"] >= 1
    assert st["embedding_provider"] in ("mock", "openai", "huggingface")
    # papers 列表中至少 1 个 is_indexed=True
    assert any(p["is_indexed"] for p in st["papers"])


# ---------------------------------------------------------------------------
# 4) local-ask 命中已入库文本
# ---------------------------------------------------------------------------


def test_local_ask_hits_ingested_text(client):
    text = (
        "This paper studies steel surface defect detection using YOLO. "
        "The experiment uses the NEU-DET dataset."
    )
    ingest = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "Hit Test", "text": text},
    )
    assert ingest.status_code == 200
    client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/index",
        json={"force": False},
    )

    ask = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/local-ask",
        json={"question": "NEU-DET dataset", "top_k": 3},
    )
    assert ask.status_code == 200, ask.text
    body = ask.json()
    assert body["retrieval_mode"] == "local_embedding"
    assert body["no_hit"] is False
    assert len(body["evidence_refs"]) >= 1
    # quote 必须包含 NEU-DET (从用户原文摘抄)
    first_quote = body["evidence_refs"][0]["quote"]
    assert "NEU-DET" in first_quote or "neu" in first_quote.lower()


# ---------------------------------------------------------------------------
# 5) local-ask 无命中时不编造答案
# ---------------------------------------------------------------------------


def test_local_ask_no_hit_no_fabrication(client):
    # 先入库一篇文章但 question 完全无关
    client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "YOLO Steel", "text": _sample_text()},
    )
    client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/index",
        json={"force": False},
    )

    ask = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/local-ask",
        json={"question": "completely unrelated quantum entanglement telescope", "top_k": 3},
    )
    assert ask.status_code == 200
    body = ask.json()
    # 应明确返回 no_hit
    assert body["no_hit"] is True
    assert body["retrieval_mode"] == "no_hit"
    assert body["evidence_refs"] == []
    assert body["confidence"] == 0.0
    assert "未在本地文献库中找到证据" in body["answer"]


# ---------------------------------------------------------------------------
# 6) 空 title / 空 text → 400
# ---------------------------------------------------------------------------


def test_manual_ingest_rejects_empty_title(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "", "text": _sample_text()},
    )
    # Pydantic validation → 422
    assert resp.status_code in (400, 422)


def test_manual_ingest_rejects_empty_text(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "Some Title", "text": ""},
    )
    assert resp.status_code in (400, 422)


def test_manual_ingest_rejects_short_text(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={"title": "Some Title", "text": "too"},
    )
    assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 7) schema 拒绝多余字段 (extra="forbid")
# ---------------------------------------------------------------------------


def test_manual_schema_rejects_extra_fields(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/manual",
        json={
            "title": "Extra Field Test",
            "text": _sample_text(),
            "evil": "should-be-rejected",
        },
    )
    assert resp.status_code == 422


def test_local_ask_schema_rejects_extra_fields(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/paper-library/local-ask",
        json={
            "question": "anything",
            "top_k": 3,
            "evil": "should-be-rejected",
        },
    )
    assert resp.status_code == 422