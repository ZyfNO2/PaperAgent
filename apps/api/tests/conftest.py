"""Pytest config: 默认 asyncio_mode=auto + 测试用 fast-arXiv."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _fast_arxiv(monkeypatch):
    """每个测试都跑: 替换 arxiv.search_arxiv 返回固定假数据, 避免 1 测试 1 网络请求.

    真正的 arxiv 真检索在 uvicorn smoke + Playwright e2e 走, 不在单测.
    """

    from app.services import arxiv as arxiv_client

    FAKE_PAPERS = [
        arxiv_client.ArxivPaper(
            arxiv_id="2406.12345",
            title="Lightweight YOLOv8 for Industrial Defect Detection",
            authors=["He, X.", "Wang, Y."],
            year=2024,
            summary="We propose a lightweight YOLOv8 variant for industrial defect detection on the NEU-DET dataset.",
            abs_url="https://arxiv.org/abs/2406.12345",
            pdf_url="https://arxiv.org/pdf/2406.12345",
            categories=["cs.CV"],
        ),
        arxiv_client.ArxivPaper(
            arxiv_id="2301.09876",
            title="Steel Surface Defect Detection: A Comprehensive Survey",
            authors=["Li, A.", "Zhang, B."],
            year=2023,
            summary="A survey of steel surface defect detection methods.",
            abs_url="https://arxiv.org/abs/2301.09876",
            pdf_url="https://arxiv.org/pdf/2301.09876",
            categories=["cs.CV"],
        ),
        arxiv_client.ArxivPaper(
            arxiv_id="2205.54321",
            title="Surface Defect Classification with Deep Learning",
            authors=["Chen, C."],
            year=2022,
            summary="Deep learning for surface defect classification.",
            abs_url="https://arxiv.org/abs/2205.54321",
            pdf_url="https://arxiv.org/pdf/2205.54321",
            categories=["cs.LG"],
        ),
    ]

    def fake_search_arxiv(queries, max_per_query=3, max_total=8, timeout=10.0):
        return FAKE_PAPERS[:max_total]

    monkeypatch.setattr(arxiv_client, "search_arxiv", fake_search_arxiv)
