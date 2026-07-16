from __future__ import annotations

import re
from collections.abc import Iterable

from .errors import UnsupportedSourceTypeError
from .hashing import sha256_text
from .models import (
    ParsedDocument,
    ParsedParagraph,
    ParagraphLocator,
    SourceArtifact,
)

PARSER_VERSION = "1"
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")


def _normalise_newlines(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _emit_paragraph(
    *,
    lines: list[str],
    line_start: int,
    line_end: int,
    paragraph_index: int,
    heading_path: tuple[str, ...],
) -> ParsedParagraph | None:
    text = "\n".join(lines).strip()
    if not text:
        return None
    return ParsedParagraph(
        text=text,
        locator=ParagraphLocator(
            heading_path=heading_path,
            paragraph_index=paragraph_index,
            line_start=line_start,
            line_end=line_end,
        ),
    )


def _plain_paragraphs(content: str) -> tuple[ParsedParagraph, ...]:
    lines = _normalise_newlines(content).split("\n")
    paragraphs: list[ParsedParagraph] = []
    buffer: list[str] = []
    start_line = 1

    for line_number, line in enumerate(lines, start=1):
        if line.strip():
            if not buffer:
                start_line = line_number
            buffer.append(line)
            continue
        paragraph = _emit_paragraph(
            lines=buffer,
            line_start=start_line,
            line_end=line_number - 1,
            paragraph_index=len(paragraphs),
            heading_path=(),
        )
        if paragraph is not None:
            paragraphs.append(paragraph)
        buffer = []

    paragraph = _emit_paragraph(
        lines=buffer,
        line_start=start_line,
        line_end=len(lines),
        paragraph_index=len(paragraphs),
        heading_path=(),
    )
    if paragraph is not None:
        paragraphs.append(paragraph)
    return tuple(paragraphs)


def _markdown_paragraphs(content: str) -> tuple[ParsedParagraph, ...]:
    lines = _normalise_newlines(content).split("\n")
    paragraphs: list[ParsedParagraph] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    buffer_heading: tuple[str, ...] = ()
    start_line = 1
    fence_marker: str | None = None

    def flush(end_line: int) -> None:
        nonlocal buffer, start_line
        paragraph = _emit_paragraph(
            lines=buffer,
            line_start=start_line,
            line_end=end_line,
            paragraph_index=len(paragraphs),
            heading_path=buffer_heading,
        )
        if paragraph is not None:
            paragraphs.append(paragraph)
        buffer = []

    for line_number, line in enumerate(lines, start=1):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_marker is None:
                if not buffer:
                    start_line = line_number
                    buffer_heading = tuple(heading_stack)
                fence_marker = marker
                buffer.append(line)
                continue
            if marker == fence_marker:
                buffer.append(line)
                fence_marker = None
                continue

        if fence_marker is not None:
            if not buffer:
                start_line = line_number
                buffer_heading = tuple(heading_stack)
            buffer.append(line)
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush(line_number - 1)
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(title)
            continue

        if not line.strip():
            flush(line_number - 1)
            continue

        if not buffer:
            start_line = line_number
            buffer_heading = tuple(heading_stack)
        buffer.append(line)

    flush(len(lines))
    return tuple(paragraphs)


def parse_source(artifact: SourceArtifact) -> ParsedDocument:
    parser_name: str
    paragraphs: Iterable[ParsedParagraph]
    if artifact.identity.media_type == "text/markdown":
        parser_name = "markdown"
        paragraphs = _markdown_paragraphs(artifact.content)
    elif artifact.identity.media_type == "text/plain":
        parser_name = "plain_text"
        paragraphs = _plain_paragraphs(artifact.content)
    else:  # pragma: no cover - guarded by the public schema, kept fail-closed.
        raise UnsupportedSourceTypeError(
            f"unsupported media type: {artifact.identity.media_type}"
        )

    return ParsedDocument(
        identity=artifact.identity,
        parser_name=parser_name,
        parser_version=PARSER_VERSION,
        source_hash=sha256_text(artifact.content),
        byte_length=len(artifact.content.encode(artifact.encoding)),
        paragraphs=tuple(paragraphs),
    )
