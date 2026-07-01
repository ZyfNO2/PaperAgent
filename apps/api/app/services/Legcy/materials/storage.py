"""资料存储: 本地落盘 + sanitize + 大小 / MIME 校验 (SOP §7)."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO


# 安全配置
MAX_BYTES_DEFAULT = 20 * 1024 * 1024  # 20MB
ALLOWED_MIMES = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "text/plain",
    "text/markdown",
})
ALLOWED_EXTENSIONS = frozenset({
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md",
})


def _storage_root() -> Path:
    """每次读取 env, 支持测试切换."""

    return Path(os.environ.get("PAPERAGENT_MATERIALS_DIR", ".runtime/materials"))


def sanitize_filename(name: str) -> str:
    """防路径穿越 + 强制扩展名白名单 (SOP §7.1 / §19.20)."""

    if not name:
        return "untitled"
    # 取 basename, 移除路径部分
    name = name.replace("\\", "/").split("/")[-1]
    # 移除控制字符与路径分隔符
    name = re.sub(r"[\x00-\x1f\x7f/\\]", "_", name)
    name = re.sub(r"\.\.+", ".", name)
    # 限长
    if len(name) > 120:
        base, _, ext = name.rpartition(".")
        if ext and len(ext) <= 8:
            name = base[: 120 - len(ext) - 1] + "." + ext
        else:
            name = name[:120]
    return name or "untitled"


def _guess_mime(filename: str, provided: str | None) -> str:
    """从 filename 猜 MIME, fallback 到 provided."""

    if provided and provided in ALLOWED_MIMES:
        return provided
    ext = Path(filename or "").suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }.get(ext, "application/octet-stream")


def check_allowed(mime: str, ext: str) -> tuple[bool, str]:
    """检查 MIME / 扩展名是否在白名单."""

    if mime and mime not in ALLOWED_MIMES:
        return False, f"不支持的 MIME 类型: {mime}"
    if ext and ext.lower() not in ALLOWED_EXTENSIONS:
        return False, f"不支持的扩展名: {ext}"
    return True, ""


def save_upload(
    project_id: str,
    filename: str,
    data: bytes,
    *,
    mime: str | None = None,
    max_bytes: int = MAX_BYTES_DEFAULT,
) -> tuple[str, str, str, int]:
    """保存上传文件到 .runtime/materials/{project_id}/{material_id}/original.

    返回: ``(material_id, storage_path, mime, size_bytes)``.
    """

    if len(data) > max_bytes:
        raise ValueError(f"文件过大 ({len(data)} > {max_bytes} bytes)")

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    detected_mime = _guess_mime(safe_name, mime)
    ok, msg = check_allowed(detected_mime, ext)
    if not ok:
        raise ValueError(msg)

    material_id = f"mat_{uuid.uuid4().hex[:10]}"
    safe_project = re.sub(r"[^\w\-]", "_", project_id)
    root = _storage_root() / safe_project / material_id
    root.mkdir(parents=True, exist_ok=True)

    storage_path = root / f"original{ext or '.bin'}"
    storage_path.write_bytes(data)

    return material_id, str(storage_path), detected_mime, len(data)


def read_text_file(storage_path: str) -> str:
    """读取保存的文本文件."""

    p = Path(storage_path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""