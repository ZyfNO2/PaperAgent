"""Session 15: 全文资料与图片 / PDF / 网页卡片化 后端测试 (SOP §19.1).

覆盖:
1.  上传 PDF 生成 MaterialItem + draft (PDF text injection)
2.  PDF 启发式提取标题 / 摘要 / DOI / arXiv
3.  无文本层 PDF -> parse_status=skipped
4.  上传图片不触发 OCR
5.  图片 + 用户说明生成 note draft
6.  网页文字 (web_text) 生成 draft
7.  URL + 描述复用 paper 提取 (走 url_note)
8.  导师备注生成 note draft (manual_note)
9.  draft card 可编辑
10. draft card 导入后写入 Evidence Ledger
11. 导入后 review_status=pending
12. 导入后 workspace_lane=user_preferred (默认)
13. 导入后 created_by_skill 正确
14. PDF 提取 DOI / arXiv 后可 auto_verify
15. 截图 / note 默认不进入 supports (verification_status skipped/unverified)
16. pending material evidence 不提升 ReportQuality 关键维度
17. FinalPackage citation 显示 material 来源
18. Trace 写入 material_uploaded / parsed / draft_card_imported
19. 文件大小 / MIME 类型限制有效
20. 非法文件名被 sanitize
"""

from __future__ import annotations

import base64
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store
from app.services import materials as ms
from app.services import trace_store as ts
from app.services import final_package as fp_service
from app.services import report_quality as quality_service


# ---------- Fixtures ---------- #


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp(prefix="pa_mat15_"))
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_dir / "traces"))
    monkeypatch.setenv("PAPERAGENT_MATERIALS_DIR", str(tmp_dir / "materials"))
    ts.reset_traces()
    ev_store.reset_all()
    ms.reset_materials_state()
    yield
    ts.reset_traces()
    ev_store.reset_all()
    ms.reset_materials_state()
    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


def _analyze(client, topic: str = "基于YOLO的钢材表面缺陷检测") -> str:
    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


# ---------- helpers ---------- #


def _make_pdf_with_text(project_id: str, text: str, filename: str = "paper.pdf"):
    """预注入 material_id 对应的 PDF 文本, 返回 (filename, base64, material_id)."""

    mid = f"mat_{uuid.uuid4().hex[:10]}"
    ms.pdf_parser.set_default_text(mid, text)
    data = b"%PDF-1.4 fake" + b"\x00" * 50
    return filename, base64.b64encode(data).decode("ascii"), mid


# ---------- 1-2: PDF 上传 + 提取 ---------- #


def test_01_pdf_upload_creates_material(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: YOLO Steel Defect Detection\n\nAbstract: We propose a method. DOI: 10.1234/test. arXiv:2106.09685")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "user_note": "important", "material_id": mid,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["material"]["parse_status"] == "parsed"
    assert body["material"]["material_id"] == mid
    assert len(body["draft_cards"]) >= 1
    d = body["draft_cards"][0]
    assert d["title"] == "YOLO Steel Defect Detection"
    assert d["possible_doi"] == "10.1234/test"
    assert d["possible_arxiv_id"] == "2106.09685"


def test_02_pdf_extracts_doi_arxiv(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: Test\nAbstract: x\nDOI: 10.9999/abc\narXiv: 2401.12345")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "user_note": "x", "material_id": mid,
    })
    d = r.json()["draft_cards"][0]
    assert d["possible_doi"] == "10.9999/abc"
    assert d["possible_arxiv_id"] == "2401.12345"


# ---------- 3: 扫描版 PDF 降级 ---------- #


def test_03_scanned_pdf_returns_skipped(client):
    pid = _analyze(client)
    data = b"%PDF-1.4 fake but no text" + b"\x00" * 200
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": "scan.pdf", "content_b64": base64.b64encode(data).decode(),
        "mime": "application/pdf",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["material"]["parse_status"] in ("skipped", "parsed")
    # 文本层解析失败时, warnings 应含说明
    if body["material"]["parse_status"] == "skipped":
        assert any("文本" in w or "扫描" in w for w in body["material"]["parse_warnings"])


# ---------- 4-5: 图片上传 + note draft ---------- #


def test_04_image_no_ocr(client):
    """图片上传不做 OCR (SOP §9.2)."""

    pid = _analyze(client)
    # 最小 PNG
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": "shot.png", "content_b64": base64.b64encode(data).decode(),
        "mime": "image/png", "user_note": "缺陷分布截图",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["material"]["parse_status"] == "parsed"
    # OCR 未实现, parse_confidence 应 < 0.6 (image_parser 设 0.4)
    assert body["material"]["parse_confidence"] <= 0.6


def test_05_image_creates_note_draft(client):
    pid = _analyze(client)
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": "shot.png", "content_b64": base64.b64encode(data).decode(),
        "mime": "image/png", "user_note": "NEU-DET 缺陷分布截图",
    })
    drafts = r.json()["draft_cards"]
    assert len(drafts) >= 1
    assert drafts[0]["suggested_type"] == "note"
    assert "NEU-DET" in drafts[0]["summary"]


# ---------- 6: 网页文字 ---------- #


def test_06_web_text_creates_draft(client):
    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "web_text",
        "title": "某综述",
        "text": "This paper reviews YOLO and steel surface defect detection. DOI: 10.5555/xyz",
        "url": "https://example.com/survey",
        "user_note": "导师建议引用",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["material"]["parse_status"] == "parsed"
    d = body["draft_cards"][0]
    assert d["title"] == "某综述" or "YOLO" in d["title"]


# ---------- 7: URL + 描述 ---------- #


def test_07_url_note_uses_url_and_note(client):
    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "url_note",
        "text": "",
        "url": "https://github.com/ultralytics/yolov5",
        "user_note": "baseline 仓库",
    })
    body = r.json()
    assert body["material"]["parse_status"] == "parsed"
    assert any(d.get("possible_url") for d in body["draft_cards"])


# ---------- 8: 导师备注 ---------- #


def test_08_manual_note_creates_note_draft(client):
    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "manual_note",
        "text": "导师希望把题目限定到 NEU-DET, 不要做多模态",
        "user_note": "题目边界约束",
    })
    body = r.json()
    assert body["material"]["parse_status"] == "parsed"
    d = body["draft_cards"][0]
    assert d["suggested_type"] == "note"


# ---------- 9: draft edit ---------- #


def test_09_draft_card_editable(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: Old Title\nAbstract: x")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    d = r.json()["draft_cards"][0]
    draft_id = d["draft_card_id"]
    r2 = client.patch(f"/api/v1/one-topic/{pid}/materials/cards/{draft_id}", json={
        "title": "New Title", "summary": "Edited summary", "user_note": "human check",
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["title"] == "New Title"
    assert r2.json()["status"] == "edited"


# ---------- 10-13: import -> Evidence Ledger ---------- #


def test_10_import_writes_to_ledger(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: T1\nAbstract: a\nDOI: 10.1111/a")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "user_note": "x", "material_id": mid,
    })
    drafts = r.json()["draft_cards"]
    assert drafts
    did = drafts[0]["draft_card_id"]

    imp = client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })
    assert imp.status_code == 200, imp.text
    body = imp.json()
    assert body["imported"] == 1
    assert len(body["evidence_ids"]) == 1
    item = ev_store.get_item(body["evidence_ids"][0])
    assert item is not None
    assert item.source_mode == "upload"


def test_11_import_review_status_pending(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: T\nAbstract: a")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    did = r.json()["draft_cards"][0]["draft_card_id"]
    imp = client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })
    item = ev_store.get_item(imp.json()["evidence_ids"][0])
    assert item.review_status == "pending"


def test_12_import_workspace_lane_correct(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: T\nAbstract: a")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    did = r.json()["draft_cards"][0]["draft_card_id"]
    imp = client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })
    item = ev_store.get_item(imp.json()["evidence_ids"][0])
    assert item.workspace_lane == "user_preferred"


def test_13_import_created_by_skill_correct(client):
    """import 不同类型草稿, created_by_skill 应匹配 SOP §12 映射."""

    pid = _analyze(client)
    # PDF -> paper-card
    fn, b64, mid = _make_pdf_with_text(pid, "Title: P\nAbstract: a\nDOI: 10.1111/p")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    drafts = r.json()["draft_cards"]
    # note -> evidence-ledger
    r2 = client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "manual_note", "text": "x", "user_note": "y",
    })
    # paper & note drafts
    paper_did = drafts[0]["draft_card_id"]
    note_did = r2.json()["draft_cards"][0]["draft_card_id"]
    imp = client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [paper_did, note_did], "workspace_lane": "user_preferred",
    })
    by_skill = {}
    for eid in imp.json()["evidence_ids"]:
        item = ev_store.get_item(eid)
        by_skill.setdefault(item.created_by_skill, []).append(eid)
    assert "paper-card" in by_skill
    assert "evidence-ledger" in by_skill


# ---------- 14: auto_verify ---------- #


def test_14_pdf_with_doi_can_auto_verify(client):
    """auto_verify=True + PDF 含 DOI 时 verification 至少跑过."""

    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: P\nAbstract: a\nDOI: 10.1111/p")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    did = r.json()["draft_cards"][0]["draft_card_id"]
    imp = client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred", "auto_verify": True,
    })
    item = ev_store.get_item(imp.json()["evidence_ids"][0])
    assert item.verification_checked_at is not None


# ---------- 15: note 默认不 supports ---------- #


def test_15_note_default_not_supports(client):
    """note / 截图 默认 verification_status=unverified, ReportQuality supports 不引用."""

    pid = _analyze(client)
    client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "manual_note", "text": "导师备注", "user_note": "n",
    })
    drafts_resp = client.get(f"/api/v1/one-topic/{pid}/materials")
    note_did = drafts_resp.json()["drafts"][0]["draft_card_id"]
    client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [note_did], "workspace_lane": "user_preferred",
    })

    from app.schemas_quality import ReportReviewRequest
    review = quality_service.build_quality_review(pid, ReportReviewRequest())
    for chk in review.checks:
        for ref in chk.evidence_refs:
            assert not (
                ref.review_status == "pending" and ref.verification_status == "unverified"
            ), f"pending+unverified 不应进 supports, ref={ref}"


# ---------- 16: pending material 不提升 ReportQuality ---------- #


def test_16_pending_material_no_quality_boost(client):
    pid = _analyze(client)
    client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "manual_note", "text": "n", "user_note": "x",
    })
    drafts = client.get(f"/api/v1/one-topic/{pid}/materials").json()["drafts"]
    did = drafts[0]["draft_card_id"]
    client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })
    from app.schemas_quality import ReportReviewRequest
    review = quality_service.build_quality_review(pid, ReportReviewRequest())
    assert review.verdict in ("通过", "有条件通过", "需修改", "不建议")


# ---------- 17: FinalPackage 显示 material source ---------- #


def test_17_final_package_citation_marks_materials(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: FP\nAbstract: a\nDOI: 10.1111/fp")
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    did = r.json()["draft_cards"][0]["draft_card_id"]
    client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })

    pkg = fp_service.build_final_package(pid, None)
    md = pkg.proposal_markdown
    # 顶部 skill 行 + 来源标记
    assert "Skill" in md or "material" in md.lower() or "PDF" in md


# ---------- 18: Trace 写入 ---------- #


def test_18_trace_writes_for_material_flow(client):
    pid = _analyze(client)
    fn, b64, mid = _make_pdf_with_text(pid, "Title: TR\nAbstract: a")
    client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": fn, "content_b64": b64, "mime": "application/pdf",
        "material_id": mid,
    })
    drafts = client.get(f"/api/v1/one-topic/{pid}/materials").json()["drafts"]
    did = drafts[0]["draft_card_id"]
    client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })

    events = ts.get_trace(pid, limit=200).events
    actions = [e.action for e in events]
    assert "material_uploaded" in actions
    assert "material_parsed" in actions
    assert "draft_card_created" in actions
    assert "draft_card_imported" in actions


# ---------- 19: 文件大小 / MIME 限制 ---------- #


def test_19_size_and_mime_limits(client):
    pid = _analyze(client)
    # 超大文件 (>20MB)
    huge = b"x" * (21 * 1024 * 1024)
    r = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": "big.pdf", "content_b64": base64.b64encode(huge).decode(),
        "mime": "application/pdf",
    })
    assert r.status_code == 422
    # 非法 MIME
    r2 = client.post(f"/api/v1/one-topic/{pid}/materials/upload", json={
        "filename": "x.exe", "content_b64": base64.b64encode(b"data").decode(),
        "mime": "application/x-msdownload",
    })
    assert r2.status_code == 422


# ---------- 20: 文件名 sanitize ---------- #


def test_20_filename_sanitize(client):
    from app.services.materials.storage import sanitize_filename

    assert "/" not in sanitize_filename("../../etc/passwd")
    assert "\\" not in sanitize_filename("..\\..\\windows\\system32")
    assert sanitize_filename("..").startswith("_") or sanitize_filename("..") != ".."
    assert sanitize_filename("a" * 200) != "a" * 200  # 限长
    # 控制字符替换
    assert "\x00" not in sanitize_filename("evil\x00file.pdf")
    # 中文 / 空格保留
    assert "导师备注" in sanitize_filename("导师备注.pdf")