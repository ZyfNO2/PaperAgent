"""Re4.5: Text chunking — 500 char windows with 100 char overlap.

Paragraph-aligned: chunks break at paragraph boundaries when possible.
"""
from __future__ import annotations

from typing import Any

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def chunk_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Split text into overlapping chunks.

    Each chunk:
      - chunk_id: "chunk-0", "chunk-1", ...
      - text: the chunk content
      - start_char: start position in original text
      - end_char: end position in original text
    """
    if not text or not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[dict[str, Any]] = []
    current = ""
    current_start = 0
    pos = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            pos += 1
            continue

        if not current:
            current_start = pos

        candidate = para if not current else f"{current}\n\n{para}"

        if len(candidate) >= chunk_size and current:
            chunks.append(
                {
                    "chunk_id": f"chunk-{len(chunks)}",
                    "text": current,
                    "start_char": current_start,
                    "end_char": current_start + len(current),
                }
            )
            if overlap > 0 and len(current) > overlap:
                overlap_text = current[-overlap:]
                current = overlap_text + "\n\n" + para
                current_start = pos - overlap
            else:
                current = para
                current_start = pos
        else:
            current = candidate

        pos += len(para) + 2

    if current and current.strip():
        chunks.append(
            {
                "chunk_id": f"chunk-{len(chunks)}",
                "text": current,
                "start_char": current_start,
                "end_char": current_start + len(current),
            }
        )

    return chunks
