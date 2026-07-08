"""arXiv full-text PDF fetcher.

Downloads PDF from arxiv.org, extracts text with pypdf.
Used for more accurate dataset/repo extraction from paper full text
(not just abstract).
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_MAX_PAGES = 10
_MAX_CHARS = 5000
_TIMEOUT_S = 30.0


async def fetch_arxiv_fulltext(arxiv_id: str) -> str:
    """Download arXiv PDF and extract text.

    arxiv_id format: 2106.12345 or 2106.12345v1
    PDF URL: https://arxiv.org/pdf/{arxiv_id}.pdf

    Returns extracted text (up to 5000 chars), or "" on failure.
    Never raises — failures are logged and return empty string.
    """
    import httpx
    import pypdf

    aid = (arxiv_id or "").strip()
    if not aid:
        return ""

    url = f"https://arxiv.org/pdf/{aid}.pdf"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "PaperAgent/1.0 (research assistant)"},
            )
            if resp.status_code != 200:
                logger.debug("arxiv fulltext %s: HTTP %d", aid, resp.status_code)
                return ""
            pdf_bytes = resp.content
    except Exception as exc:
        logger.debug("arxiv fulltext %s: fetch failed: %s", aid, type(exc).__name__)
        return ""

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages[:_MAX_PAGES]:
            text += page.extract_text() or ""
            if len(text) >= _MAX_CHARS:
                break
        return text[:_MAX_CHARS]
    except Exception as exc:
        logger.debug("arxiv fulltext %s: PDF parse failed: %s", aid, type(exc).__name__)
        return ""


def fetch_arxiv_fulltext_sync(arxiv_id: str) -> str:
    """Synchronous wrapper for use in ThreadPoolExecutor contexts."""
    import asyncio

    try:
        return asyncio.run(fetch_arxiv_fulltext(arxiv_id))
    except Exception:
        return ""
