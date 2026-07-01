"""Local PDF upload handler (Session 46).

base64 PDF → bytes → sha256 → 校验.
复用 materials/storage.check_allowed / sanitize_filename.
"""

from __future__ import annotations

import base64
import hashlib
import re

from ..materials import storage as mat_storage


# MIME / 扩展名白名单 (复用 materials/storage, 这里只允许 PDF)
_ALLOWED_MIMES_PDF = frozenset({"application/pdf"})
_ALLOWED_EXT_PDF = frozenset({".pdf"})


class UploadValidationError(ValueError):
    """上传文件校验失败."""


def decode_pdf_base64(content_b64: str) -> bytes:
    """从 base64 字符串解码 PDF bytes; 失败抛 UploadValidationError."""

    if not content_b64:
        raise UploadValidationError("content_b64 为空")
    try:
        # 兼容 data URI 前缀: data:application/pdf;base64,xxxxx
        if "," in content_b64 and content_b64.lstrip()[:5] == "data:":
            content_b64 = content_b64.split(",", 1)[1]
        return base64.b64decode(content_b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise UploadValidationError(f"base64 解码失败: {exc}") from exc


def validate_pdf_upload(filename: str, data: bytes, mime: str | None = None) -> tuple[bool, str]:
    """校验 PDF 文件名 + 字节 + MIME.

    Returns: (ok, message). 复用 materials/storage 的白名单.
    """

    safe_name = mat_storage.sanitize_filename(filename)
    ext_ok = "." in safe_name and safe_name.rsplit(".", 1)[-1].lower() == "pdf"
    if not ext_ok:
        return False, f"文件名必须是 .pdf, 当前: {safe_name}"

    if mime and mime not in _ALLOWED_MIMES_PDF:
        return False, f"不支持的 MIME: {mime}"

    # 复用 materials/storage 的 check_allowed
    ok, msg = mat_storage.check_allowed("application/pdf", ".pdf")
    if not ok:
        return False, msg

    if len(data) < 8:
        return False, "PDF 字节过短, 不像合法文件"

    # PDF 文件 magic header: %PDF-
    if not data.startswith(b"%PDF-"):
        return False, "PDF 文件 magic header 缺失"

    return True, "ok"


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive_title_from_filename(filename: str) -> str:
    """从 PDF 文件名启发式生成候选 title."""

    name = mat_storage.sanitize_filename(filename)
    stem = re.sub(r"\.[Pp][Dd][Ff]$", "", name)
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem or "untitled"
