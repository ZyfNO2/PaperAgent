"""PDF parser wrapper (Session 46).

复用 services/materials/pdf_parser.parse_pdf.
返回 text / page_count / page_refs / status, 不做切块.
"""

from __future__ import annotations

from typing import Any

from ..materials import pdf_parser as mat_pdf


def parse(data: bytes, material_id: str | None = None) -> dict[str, Any]:
    """从 PDF bytes 解析全文; 复用 materials/pdf_parser 的 pypdf 路径."""

    return mat_pdf.parse_pdf(data, material_id=material_id)
