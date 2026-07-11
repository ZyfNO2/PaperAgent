"""Re4.5: PDF full-text extraction using pypdf.

Downloads PDF from URL, extracts text, cleans page breaks / headers / footers.
"""
from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Any

from pypdf import PdfReader

logger = logging.getLogger(__name__)

_PAGE_HEADER_PATTERN = re.compile(r"^\s*\d+\s*$", re.MULTILINE)
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def download_pdf(url: str, *, timeout: float = 30.0) -> bytes:
    """Download PDF bytes from URL (synchronous)."""
    import httpx

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "PaperAgent/1.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            raise ValueError(
                f"URL does not appear to be a PDF (content-type: {content_type})"
            )
        return resp.content


def extract_text(pdf_bytes: bytes) -> str:
    """Extract full text from PDF bytes using pypdf.

    Returns cleaned text with page breaks normalized.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("pypdf page %d extraction failed: %s", i, exc)
            text = ""
        pages.append(text)

    raw = "\n\n".join(pages)
    return _clean_text(raw)


def _clean_text(text: str) -> str:
    """Clean extracted text: normalize whitespace, remove page numbers."""
    text = _PAGE_HEADER_PATTERN.sub("", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def extract_pdf_from_url(url: str) -> dict[str, Any]:
    """Download + extract PDF. Returns metadata + full text."""
    pdf_bytes = download_pdf(url)
    text = extract_text(pdf_bytes)
    n_pages = len(PdfReader(BytesIO(pdf_bytes)).pages)
    if not text or len(text.strip()) < 100:
        return {
            "status": "extraction_failed",
            "reason": "extracted text too short (likely scanned PDF)",
            "n_chars": len(text),
        }
    return {
        "status": "ok",
        "text": text,
        "n_chars": len(text),
        "n_pages": n_pages,
    }
