"""Session 51: 题录页 HTML 解析 + 启发式字段抽取.

只做 HTML → title/year/abstract_snippet 的解析, 不做网络请求.
CNKI cdmd 题录页结构: <title> 含题名, 正文含年份/摘要片段.

设计原则 (SOP §7):
- 只抽题录页能看到的字段, 不编造全文/作者结论.
- 抽不到的字段返回 None, 不填默认值假装抓到.
- 抽取结果由 crawler 决定 verified_status.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedRecord:
    """parser 抽出的题录字段 (可能部分缺失)."""

    title: str | None = None
    year: int | None = None
    abstract_snippet: str | None = None


# CNKI cdmd 题录页常见模式
_YEAR_RE = re.compile(r"(20[01]\d|19[89]\d)\s*年?")
# 题名标签: CNKI 用 <h1> 或 <title> 或 class=xxx
_TITLE_TAG_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
# 摘要片段: 关键词后跟一段文字
_ABSTRACT_RE = re.compile(
    r"(?:摘要|Abstract)[：:\s]*(.*?)(?:</(?:p|div|td)>|关键词|Key\s*words|<br\s*/?>|$)",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """去 HTML 标签 + 折叠空白."""
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_cnki_html(html: str) -> ParsedRecord:
    """从 CNKI cdmd 题录页 HTML 抽取 title/year/abstract_snippet.

    Args:
        html: 题录页 HTML 文本 (可能是空串 / 错误页).

    Returns:
        ParsedRecord: 抽到的字段, 缺失为 None. 绝不编造.
    """
    if not html or not html.strip():
        return ParsedRecord()

    # --- title: 优先 <h1>, 其次 <title> ---
    title: str | None = None
    m = _TITLE_TAG_RE.search(html)
    if m:
        candidate = _strip_html(m.group(1))
        if candidate and len(candidate) >= 2 and "CNKI" not in candidate:
            title = candidate
    if not title:
        tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if tm:
            candidate = _strip_html(tm.group(1))
            # CNKI 标题页常含「-- 中国知网」/「CNKI」后缀, 去掉
            candidate = re.split(r"[-–—]\s*(中国知网|CNKI|cdmd)", candidate)[0].strip()
            if candidate and len(candidate) >= 2:
                title = candidate

    # --- year: 第一个 4 位年份 (排除 4 位编号如 1021xxxx — 要求上下文含「年」或在合理学位年份范围) ---
    year: int | None = None
    if html:
        ym = _YEAR_RE.search(html)
        if ym:
            try:
                yv = int(ym.group(1))
                if 1990 <= yv <= 2030:
                    year = yv
            except ValueError:
                pass

    # --- abstract_snippet: 摘要/Abstract 后的一段文字, 截断到 ≤ 500 字 ---
    abstract_snippet: str | None = None
    am = _ABSTRACT_RE.search(html)
    if am:
        snippet = _strip_html(am.group(1))
        if snippet and len(snippet) >= 4:
            abstract_snippet = snippet[:500]

    return ParsedRecord(title=title, year=year, abstract_snippet=abstract_snippet)
