"""图片 / 截图解析 (SOP §9): 不做 OCR, 仅记录元数据 + 用户说明.

MVP: 提取图片大小 / MIME, 把 user_note + 文件名作为 summary.
可延后: OCR / 截图自动识别 (SOP §21 列入延期项).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def parse_image(storage_path: str, *, user_note: str | None = None, filename: str | None = None) -> dict[str, Any]:
    """读取已保存图片元数据. 不做 OCR (SOP §9)."""

    warnings: list[str] = ["图片证据需要人工确认"]
    p = Path(storage_path) if storage_path else None

    metadata: dict[str, Any] = {"ocr_attempted": False}
    width: int | None = None
    height: int | None = None
    mime: str | None = None

    if p and p.exists():
        mime = _guess_mime_from_suffix(p.suffix)
        # 尝试读 PNG/JPEG header, 不依赖 PIL
        try:
            head = p.read_bytes()[:64]
            if head.startswith(b"\x89PNG\r\n\x1a\n"):
                mime = mime or "image/png"
                width, height = _png_dims(head)
            elif head.startswith(b"\xff\xd8\xff"):
                mime = mime or "image/jpeg"
                # JPEG 尺寸解析复杂, 留空
            elif head.startswith(b"RIFF") and head[8:12] == b"WEBP":
                mime = mime or "image/webp"
        except OSError:
            pass
        if width and height:
            metadata.update({"width": width, "height": height})

    summary_parts: list[str] = []
    if user_note:
        summary_parts.append(user_note.strip())
    if filename:
        summary_parts.append(f"(来源文件: {filename})")
    summary = "\n".join(summary_parts).strip() or "图片资料 (无说明)"

    return {
        "text": "",
        "page_count": 0,
        "page_refs": [],
        "status": "parsed",
        "confidence": 0.4,  # SOP §9.3
        "warnings": warnings,
        "summary": summary,
        "mime": mime,
        "metadata": metadata,
    }


def _guess_mime_from_suffix(suffix: str) -> str | None:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix.lower())


def _png_dims(head: bytes) -> tuple[int | None, int | None]:
    """读 PNG IHDR 的宽高 (偏移 16..23)."""

    if len(head) < 24:
        return None, None
    import struct

    try:
        w, h = struct.unpack(">II", head[16:24])
        return int(w), int(h)
    except Exception:
        return None, None