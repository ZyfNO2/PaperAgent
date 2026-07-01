"""Session 15: 全文资料与图片 / PDF / 网页卡片化 服务入口.

模块结构:
- storage: 本地文件保存 + sanitize + 大小 / MIME 校验
- pdf_parser: 文本层 PDF 解析 (pypdf 优先, 缺则返回 skipped)
- image_parser: 不做 OCR, 仅记录元数据 + 用户说明
- web_text_parser: 纯文本 / URL + 描述 拆段
- card_builder: 从解析结果生成 DraftEvidenceCard
- dedup: 同项目内 / 跨 ledger dedup
- orchestrator: 顶层入口, 串接 storage -> parse -> build -> dedup

设计原则:
- 所有解析结果默认 pending, 不直接进 supports
- OCR 缺, 不报错, 仅记录 warning
- 大小 / MIME 白名单强制
- 文件名 sanitize 防路径穿越
"""

from __future__ import annotations

from .orchestrator import (
    accept_upload,
    accept_text,
    build_draft_cards,
    edit_draft_card,
    get_material,
    get_summary,
    import_drafts,
    list_materials,
    reset_materials_state,
)

__all__ = [
    "accept_upload",
    "accept_text",
    "build_draft_cards",
    "edit_draft_card",
    "get_material",
    "get_summary",
    "import_drafts",
    "list_materials",
    "reset_materials_state",
]