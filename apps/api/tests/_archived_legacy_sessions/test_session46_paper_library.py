"""Session 46: Paper Library MVP tests.

覆盖范围 (SOP §10):
- arXiv ID 解析 (真实 + 假 ID 兜底)
- PDF 上传落盘
- 切块 (abstract/method 命中, reference 丢弃)
- 重复检测四类
- 4 端点形状
- Evidence Ledger 联动
"""

from __future__ import annotations

import base64
import os

import pytest

# ---------- Fixtures ---------- #


@pytest.fixture(autouse=True)
def _tmp_library(monkeypatch, tmp_path):
    """每个测试用独立 .runtime/paper_library 目录 + 清 evidence."""

    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(tmp_path / "paper_library"))
    # 重置 evidence store
    from app.services import evidence as ev_store
    ev_store.reset_all()
    yield
    ev_store.reset_all()


def _fake_pdf_bytes() -> bytes:
    """生成一个最小 PDF-like bytes (有 %PDF- magic header).

    不要求是合法 PDF, 测试用 pypdf mock / materials 降级路径都行.
    """

    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%%%EOF"


# ============================================================================
# 1. arXiv ID 解析
# ============================================================================


class TestArxivIdParser:
    def test_new_style_id(self):
        from app.services.paper_library.arxiv_downloader import parse_arxiv_id
        assert parse_arxiv_id("2409.13740") == "2409.13740"

    def test_new_style_with_version(self):
        from app.services.paper_library.arxiv_downloader import parse_arxiv_id
        assert parse_arxiv_id("2409.13740v2") == "2409.13740v2"

    def test_url_form(self):
        from app.services.paper_library.arxiv_downloader import parse_arxiv_id
        assert parse_arxiv_id("https://arxiv.org/abs/2409.13740") == "2409.13740"

    def test_old_style_id(self):
        from app.services.paper_library.arxiv_downloader import parse_arxiv_id
        assert parse_arxiv_id("cs/0123456") == "cs/0123456"

    def test_invalid_returns_none(self):
        from app.services.paper_library.arxiv_downloader import parse_arxiv_id
        assert parse_arxiv_id("not-an-id") is None or "not" not in (parse_arxiv_id("not-an-id") or "")

    def test_empty_returns_none(self):
        from app.services.paper_library.arxiv_downloader import parse_arxiv_id
        assert parse_arxiv_id("") is None


# ============================================================================
# 2. Chunker 切块
# ============================================================================


class TestChunker:
    def test_detect_abstract_section(self):
        from app.services.paper_library.chunker import chunk_text
        text = (
            "Title: Test Paper\n\n"
            "Authors: Alice, Bob\n\n"
            "Abstract\n"
            "This is the abstract of the paper. " * 30 + "\n\n"
            "1 Introduction\n"
            "This is the introduction. " * 30
        )
        chunks = chunk_text(text, paper_id="p1", project_id="proj1")
        assert len(chunks) >= 1
        types = {c.chunk_type for c in chunks}
        assert "abstract" in types or "title" in types

    def test_method_section(self):
        from app.services.paper_library.chunker import chunk_text
        text = (
            "Title: Test\n\nAbstract\n" + ("abstract text. " * 30) + "\n\n"
            "3 Method\n" + ("our method. " * 200) + "\n\n"
            "4 Experiments\n" + ("experiments. " * 30) + "\n\n"
            "5 Conclusion\n" + ("conclusion. " * 30)
        )
        chunks = chunk_text(text, paper_id="p1", project_id="proj1")
        types = {c.chunk_type for c in chunks}
        assert "method" in types

    def test_reference_dropped(self):
        from app.services.paper_library.chunker import chunk_text
        text = (
            "Title: T\n\n"
            "Abstract\n" + ("abs. " * 30) + "\n\n"
            "1 Introduction\n" + ("intro. " * 30) + "\n\n"
            "References\n" + ("[1] Citation. " * 50)
        )
        chunks = chunk_text(text, paper_id="p1", project_id="proj1")
        # References 不应出现
        types = {c.chunk_type for c in chunks}
        assert "reference" not in types
        # 全部 chunk 不应包含 "[1] Citation"
        for c in chunks:
            assert "[1] Citation" not in c.text

    def test_token_estimation(self):
        from app.services.paper_library.chunker import _estimate_tokens
        assert _estimate_tokens("hello world") == 2
        assert _estimate_tokens("") == 0
        # 中文字符估算 (4 个中文 = 4 token)
        assert _estimate_tokens("你好世界") >= 4

    def test_chunk_size_within_range(self):
        from app.services.paper_library.chunker import chunk_text
        body = " ".join(["word"] * 2500)  # ~2500 tokens
        text = (
            "Title: T\n\n"
            "Abstract\n" + ("abs. " * 200) + "\n\n"
            "1 Introduction\n" + body + "\n\n"
            "References\n" + ("[1] x. " * 20)
        )
        chunks = chunk_text(text, paper_id="p1", project_id="proj1")
        assert len(chunks) >= 2
        # 大部分块 token 应该在合理范围 (允许误差)
        for c in chunks:
            assert c.token_count > 0
            assert c.token_count <= 1500  # 不应超过 chunk_max + overlap

    def test_no_sections_chunks_unknown(self):
        from app.services.paper_library.chunker import chunk_text
        text = "Just some text. " * 200
        chunks = chunk_text(text, paper_id="p1", project_id="proj1")
        assert len(chunks) >= 1
        # 无章节应至少出一个 unknown 块
        assert any(c.chunk_type == "unknown" for c in chunks)


# ============================================================================
# 3. Dedup 四类
# ============================================================================


class TestDedup:
    def _make(self, **kw):
        from app.schemas_paper_library import PaperRecord
        defaults = dict(
            paper_id="p1", project_id="proj1", title="A Title",
            source_mode="local_upload", parse_status="parsed",
            metadata_status="resolved",
        )
        defaults.update(kw)
        return PaperRecord(**defaults)

    def test_sha256_duplicate(self):
        from app.services.paper_library.dedup import find_duplicate
        existing = [self._make(paper_id="p_old", sha256="abc123")]
        dup = find_duplicate(
            new_sha256="abc123", new_doi=None, new_arxiv_id=None,
            new_title="A Title", new_year=2024, existing=existing,
        )
        assert dup is not None
        assert dup.paper_id == "p_old"

    def test_arxiv_id_duplicate(self):
        from app.services.paper_library.dedup import find_duplicate
        existing = [self._make(paper_id="p_old", arxiv_id="2409.13740")]
        dup = find_duplicate(
            new_sha256=None, new_doi=None, new_arxiv_id="2409.13740",
            new_title="New Title", new_year=2024, existing=existing,
        )
        assert dup is not None

    def test_doi_duplicate(self):
        from app.services.paper_library.dedup import find_duplicate
        existing = [self._make(paper_id="p_old", doi="10.1109/foo.2024")]
        dup = find_duplicate(
            new_sha256=None, new_doi="10.1109/foo.2024", new_arxiv_id=None,
            new_title="Different Title", new_year=2024, existing=existing,
        )
        assert dup is not None

    def test_title_jaccard_duplicate(self):
        from app.services.paper_library.dedup import find_duplicate
        existing = [self._make(paper_id="p_old", title="YOLO for Steel Defect Detection in Real-time")]
        dup = find_duplicate(
            new_sha256=None, new_doi=None, new_arxiv_id=None,
            new_title="YOLO for Steel Defect Detection in Real time",
            new_year=2024, existing=existing,
        )
        assert dup is not None

    def test_no_duplicate(self):
        from app.services.paper_library.dedup import find_duplicate
        existing = [self._make(paper_id="p_old", title="Foo Bar", arxiv_id="1111.1111")]
        dup = find_duplicate(
            new_sha256="zzz", new_doi="10.999/zzz", new_arxiv_id="2222.2222",
            new_title="Completely Different Topic", new_year=2024, existing=existing,
        )
        assert dup is None

    def test_different_year_no_jaccard(self):
        from app.services.paper_library.dedup import find_duplicate
        existing = [self._make(paper_id="p_old", title="YOLO for Steel Defect Detection", year=2024)]
        dup = find_duplicate(
            new_sha256=None, new_doi=None, new_arxiv_id=None,
            new_title="YOLO for Steel Defect Detection",
            new_year=2025,  # 不同年份
            existing=existing,
        )
        # 不同年份不应触发 jaccard 重复 (年份过滤)
        assert dup is None


# ============================================================================
# 4. Local upload (decode + validate + parse)
# ============================================================================


class TestLocalUpload:
    def test_decode_pdf_base64(self):
        from app.services.paper_library.local_upload import decode_pdf_base64
        original = b"%PDF-1.4\ntest content"
        b64 = base64.b64encode(original).decode()
        out = decode_pdf_base64(b64)
        assert out == original

    def test_decode_with_data_uri(self):
        from app.services.paper_library.local_upload import decode_pdf_base64
        original = b"%PDF-test"
        b64 = base64.b64encode(original).decode()
        data_uri = f"data:application/pdf;base64,{b64}"
        assert decode_pdf_base64(data_uri) == original

    def test_decode_empty_fails(self):
        from app.services.paper_library.local_upload import decode_pdf_base64, UploadValidationError
        with pytest.raises(UploadValidationError):
            decode_pdf_base64("")

    def test_validate_pdf_ok(self):
        from app.services.paper_library.local_upload import validate_pdf_upload
        ok, msg = validate_pdf_upload("test.pdf", b"%PDF-1.4\nhello", "application/pdf")
        assert ok, msg

    def test_validate_pdf_missing_magic(self):
        from app.services.paper_library.local_upload import validate_pdf_upload
        ok, _msg = validate_pdf_upload("test.pdf", b"not a pdf", "application/pdf")
        assert not ok

    def test_validate_pdf_wrong_ext(self):
        from app.services.paper_library.local_upload import validate_pdf_upload
        ok, _msg = validate_pdf_upload("test.txt", b"%PDF-1.4", "application/pdf")
        assert not ok

    def test_compute_sha256(self):
        from app.services.paper_library.local_upload import compute_sha256
        sha = compute_sha256(b"hello")
        assert len(sha) == 64
        # 确定性
        assert sha == compute_sha256(b"hello")


# ============================================================================
# 5. End-to-end ingest (arXiv mock + upload)
# ============================================================================


class TestIngestArxiv:
    def test_ingest_arxiv_with_mock_pdf(self, monkeypatch, _tmp_library):
        """Mock arXiv metadata + PDF 下载, 验证完整 ingest 流程."""

        from app.services.paper_library import arxiv_downloader

        # Mock arXiv metadata
        class _FakePaper:
            arxiv_id = "2409.13740"
            title = "Test Paper Title"
            authors = ["Alice", "Bob"]
            year = 2024
            summary = "This is the summary."
            abs_url = "https://arxiv.org/abs/2409.13740"
            pdf_url = "https://arxiv.org/pdf/2409.13740.pdf"
            categories = ["cs.AI"]

        # 注入解析文本, 模拟 pypdf 抽到的 PDF 全文
        paper_text = (
            "Title: Mock Paper\n\n"
            "Abstract\nThis paper proposes a new method. " * 30 + "\n\n"
            "1 Introduction\nIntroduction text here. " * 30 + "\n\n"
            "3 Method\nOur method is novel. " * 30 + "\n\n"
            "4 Experiments\nExperiments show. " * 30 + "\n\n"
            "References\n" + ("[1] Ref. " * 30)
        )

        def _fake_dl(url, timeout=30.0):
            return b"%PDF-1.4\n" + b"x" * 500  # > 100 bytes to pass size check

        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: _FakePaper())
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", _fake_dl)

        from app.services.paper_library import ingest_arxiv
        # 先抓 raw PDF 落盘拿到 material_id, 然后再让 pdf_parser 注入 default text
        # 简化做法: 直接 monkey-patch pdf_parser.parse 让它返回真实文本
        from app.services.paper_library import pdf_parser as pl_pdf
        monkeypatch.setattr(pl_pdf, "parse", lambda data, material_id=None: {
            "text": paper_text, "page_count": 10, "page_refs": [f"p{i}" for i in range(10)],
            "status": "parsed", "confidence": 0.85, "warnings": [],
        })

        outcome = ingest_arxiv("proj1", "2409.13740")

        assert outcome.paper_id.startswith("paper_ax_")
        assert outcome.is_duplicate is False
        assert outcome.parse_status == "parsed"
        assert outcome.chunk_count >= 1
        assert outcome.evidence_id is not None

    def test_ingest_arxiv_failure_fallback(self, monkeypatch, _tmp_library):
        """PDF 下载失败应返回 parse_status=failed 但不崩."""

        from app.services.paper_library import arxiv_downloader
        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: None)
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", lambda url, timeout=30.0: None)

        from app.services.paper_library import ingest_arxiv
        outcome = ingest_arxiv("proj1", "2409.99999")
        assert outcome.paper_id.startswith("paper_ax_")
        assert outcome.parse_status == "failed"
        assert outcome.chunk_count == 0

    def test_ingest_arxiv_duplicate_detection(self, monkeypatch, _tmp_library):
        """同一 arxiv_id 第二次 ingest 应识别为重复."""

        from app.services.paper_library import arxiv_downloader

        class _FakePaper:
            arxiv_id = "2409.13740"
            title = "Same Paper"
            authors = ["X"]
            year = 2024
            summary = "summary"
            abs_url = "https://arxiv.org/abs/2409.13740"
            pdf_url = "https://arxiv.org/pdf/2409.13740.pdf"
            categories = []

        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: _FakePaper())
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", lambda url, timeout=30.0: b"%PDF-fake")

        from app.services.paper_library import ingest_arxiv
        o1 = ingest_arxiv("proj1", "2409.13740")
        o2 = ingest_arxiv("proj1", "2409.13740")
        assert o1.paper_id == o2.paper_id
        assert o2.is_duplicate is True


class TestIngestUpload:
    def test_ingest_upload_happy(self, _tmp_library):
        from app.services.paper_library import ingest_upload
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        outcome = ingest_upload("proj1", "test.pdf", content, "application/pdf")
        assert outcome.paper_id.startswith("paper_up_")
        assert outcome.is_duplicate is False
        assert outcome.evidence_id is not None

    def test_ingest_upload_invalid_base64(self, _tmp_library):
        from app.services.paper_library import ingest_upload
        with pytest.raises(ValueError):
            ingest_upload("proj1", "test.pdf", "not-base64-!!!")

    def test_ingest_upload_not_pdf(self, _tmp_library):
        from app.services.paper_library import ingest_upload
        content = base64.b64encode(b"plain text").decode()
        with pytest.raises(ValueError):
            ingest_upload("proj1", "test.txt", content)

    def test_ingest_upload_duplicate_sha256(self, _tmp_library):
        from app.services.paper_library import ingest_upload
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        o1 = ingest_upload("proj1", "test.pdf", content, "application/pdf")
        o2 = ingest_upload("proj1", "test_renamed.pdf", content, "application/pdf")
        assert o1.paper_id == o2.paper_id
        assert o2.is_duplicate is True


# ============================================================================
# 6. List / Get
# ============================================================================


class TestListAndGet:
    def test_list_empty(self, _tmp_library):
        from app.services.paper_library import list_papers
        assert list_papers("empty_proj") == []

    def test_get_paper_not_found(self, _tmp_library):
        from app.services.paper_library import get_paper
        assert get_paper("proj1", "paper_xx_999") is None

    def test_list_after_ingest(self, _tmp_library):
        from app.services.paper_library import ingest_upload, list_papers
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        ingest_upload("proj1", "a.pdf", content, "application/pdf")
        ingest_upload("proj1", "b.pdf", base64.b64encode(b"%PDF-other").decode(), "application/pdf")
        papers = list_papers("proj1")
        assert len(papers) == 2


# ============================================================================
# 7. Evidence Ledger 联动
# ============================================================================


class TestEvidenceLinkage:
    def test_ingest_creates_pending_evidence(self, monkeypatch, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import arxiv_downloader, ingest_arxiv

        class _FakePaper:
            arxiv_id = "2401.00001"
            title = "Evidence Linkage Test"
            authors = ["A"]
            year = 2024
            summary = "summary"
            abs_url = "https://arxiv.org/abs/2401.00001"
            pdf_url = "https://arxiv.org/pdf/2401.00001.pdf"
            categories = []

        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: _FakePaper())
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", lambda url, timeout=30.0: b"%PDF-fake")

        outcome = ingest_arxiv("proj1", "2401.00001")
        assert outcome.evidence_id is not None
        # Evidence Ledger 里能查到
        item = ev_store.get_item(outcome.evidence_id)
        assert item is not None
        assert item.evidence_type == "paper"
        assert item.review_status == "pending"
        # 应被打上 paper_library 标签
        assert "paper_library" in (item.tags or [])

    def test_duplicate_evidence_dedup(self, monkeypatch, _tmp_library):
        from app.services import evidence as ev_store
        from app.services.paper_library import arxiv_downloader, ingest_arxiv

        class _FakePaper:
            arxiv_id = "2401.00002"
            title = "Dup Evidence Test"
            authors = ["A"]
            year = 2024
            summary = "s"
            abs_url = "https://arxiv.org/abs/2401.00002"
            pdf_url = "https://arxiv.org/pdf/2401.00002.pdf"
            categories = []

        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: _FakePaper())
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", lambda url, timeout=30.0: b"%PDF-fake")

        o1 = ingest_arxiv("proj1", "2401.00002")
        o2 = ingest_arxiv("proj1", "2401.00002")
        assert o1.evidence_id is not None
        # 重复 ingest 不应生成第二条 evidence
        assert o2.is_duplicate is True
        ledger = ev_store.get_ledger("proj1")
        assert len(ledger.papers) == 1


# ============================================================================
# 8. Storage 落盘
# ============================================================================


class TestStorage:
    def test_save_and_load_record(self, _tmp_library):
        from app.schemas_paper_library import PaperRecord
        from app.services.paper_library import storage
        rec = PaperRecord(
            paper_id="p1", project_id="proj1", title="T",
            source_mode="local_upload", parse_status="parsed",
            metadata_status="resolved",
        )
        path = storage.save_paper_record(rec)
        assert os.path.exists(path)
        loaded = storage.load_record("proj1", "p1")
        assert loaded is not None
        assert loaded.title == "T"

    def test_save_and_load_chunks(self, _tmp_library):
        from app.schemas_paper_library import PaperChunk
        from app.services.paper_library import storage
        chunks = [
            PaperChunk(
                chunk_id=f"c{i}", paper_id="p1", project_id="proj1",
                text=f"chunk {i}", token_count=2, chunk_type="unknown",
            )
            for i in range(3)
        ]
        path = storage.save_chunks(chunks)
        assert path != ""
        assert os.path.exists(path)
        loaded = storage.load_chunks("proj1", "p1")
        assert len(loaded) == 3

    def test_manifest_updated(self, _tmp_library):
        from app.schemas_paper_library import PaperRecord
        from app.services.paper_library import storage
        rec = PaperRecord(
            paper_id="p1", project_id="proj1", title="T",
            source_mode="arxiv_download", parse_status="parsed",
            metadata_status="resolved", arxiv_id="2401.12345", chunk_count=5,
        )
        storage.save_paper_record(rec)
        storage.save_chunks([])
        storage.update_manifest(
            project_id="proj1", paper_id="p1",
            record_path="/x", chunks_path="/y", chunk_count=5,
            parse_status="parsed", source_mode="arxiv_download",
            sha256="abc", arxiv_id="2401.12345",
        )
        mf = storage.read_manifest("proj1")
        assert "p1" in mf["papers"]
        assert mf["papers"]["p1"]["chunk_count"] == 5


# ============================================================================
# 9. API endpoints
# ============================================================================


class TestApiEndpoints:
    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_health(self):
        client = self._client()
        r = client.get("/health")
        assert r.status_code == 200

    def test_list_endpoint_empty(self):
        client = self._client()
        r = client.get("/api/v1/projects/proj_new/paper-library")
        assert r.status_code == 200
        data = r.json()
        assert data["total_papers"] == 0
        assert data["total_chunks"] == 0
        assert data["papers"] == []

    def test_get_paper_404(self):
        client = self._client()
        r = client.get("/api/v1/projects/proj1/paper-library/paper_xx_nope")
        assert r.status_code == 404

    def test_upload_endpoint_happy(self):
        client = self._client()
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        r = client.post(
            "/api/v1/projects/proj1/paper-library/upload",
            json={"filename": "test.pdf", "content_b64": content, "mime": "application/pdf"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["paper_id"].startswith("paper_up_")
        assert data["is_duplicate"] is False
        assert data["evidence_id"] is not None

    def test_upload_endpoint_invalid(self):
        client = self._client()
        r = client.post(
            "/api/v1/projects/proj1/paper-library/upload",
            json={"filename": "test.pdf", "content_b64": "not-base64", "mime": "application/pdf"},
        )
        assert r.status_code == 400

    def test_upload_endpoint_then_list(self):
        client = self._client()
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        client.post(
            "/api/v1/projects/proj1/paper-library/upload",
            json={"filename": "test.pdf", "content_b64": content, "mime": "application/pdf"},
        )
        r = client.get("/api/v1/projects/proj1/paper-library")
        assert r.status_code == 200
        data = r.json()
        assert data["total_papers"] == 1

    def test_upload_endpoint_then_get_detail(self):
        client = self._client()
        content = base64.b64encode(_fake_pdf_bytes()).decode()
        r1 = client.post(
            "/api/v1/projects/proj1/paper-library/upload",
            json={"filename": "test.pdf", "content_b64": content, "mime": "application/pdf"},
        )
        pid = r1.json()["paper_id"]
        r2 = client.get(f"/api/v1/projects/proj1/paper-library/{pid}")
        assert r2.status_code == 200
        data = r2.json()
        assert data["paper"]["paper_id"] == pid
        assert "chunk_total" in data

    def test_arxiv_endpoint_request_validation(self):
        client = self._client()
        r = client.post(
            "/api/v1/projects/proj1/paper-library/arxiv",
            json={"arxiv_id_or_url": ""},
        )
        # Pydantic 验证失败
        assert r.status_code in (400, 422)

    def test_arxiv_endpoint_invalid_id(self, monkeypatch):
        from app.services.paper_library import arxiv_downloader
        monkeypatch.setattr(arxiv_downloader, "_lookup_metadata", lambda x: None)
        monkeypatch.setattr(arxiv_downloader, "_download_pdf", lambda url, timeout=30.0: None)
        client = self._client()
        r = client.post(
            "/api/v1/projects/proj1/paper-library/arxiv",
            json={"arxiv_id_or_url": "9999.99999"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["parse_status"] in ("failed", "skipped")


# ============================================================================
# 10. Schemas 可序列化
# ============================================================================


class TestSchemas:
    def test_paper_record_serialize(self):
        from app.schemas_paper_library import PaperRecord
        rec = PaperRecord(
            paper_id="p1", project_id="proj1", title="T",
            source_mode="arxiv_download", parse_status="parsed",
            metadata_status="resolved",
        )
        d = rec.model_dump()
        assert d["paper_id"] == "p1"
        assert d["source_mode"] == "arxiv_download"

    def test_paper_chunk_serialize(self):
        from app.schemas_paper_library import PaperChunk
        c = PaperChunk(
            chunk_id="c1", paper_id="p1", project_id="proj1",
            text="hello", token_count=1, chunk_type="abstract",
        )
        d = c.model_dump()
        assert d["chunk_type"] == "abstract"
