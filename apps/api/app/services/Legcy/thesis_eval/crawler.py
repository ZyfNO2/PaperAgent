"""Session 51: 题录抓取 (URL → 题录页 HTML → ThesisRecord).

三态降级 (SOP §7):
    成功 → verified_status=verified
    部分成功 (只有 title) → verified_status=partial, 缺字段标 None
    失败 (403/超时/反爬) → verified_status=failed
            ↓
    降级: 用测试集已给的 title/year/abstract_snippet 做题录级证据
            ↓
    绝不编造全文 / 摘要 / 作者结论

设计原则:
- httpx GET, 超时 15s, UA 伪装.
- 网络不通时降级为题录级证据, fallback_used=True.
- LLM 不参与抓取 (抓取是事实层, 不是推断层).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ...schemas_thesis_eval import ThesisRecord
from .parser import ParsedRecord, parse_cnki_html

logger = logging.getLogger(__name__)

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = 15.0


def _build_record(
    thesis_id: str,
    source_url: str,
    parsed: ParsedRecord,
    *,
    fallback: dict[str, Any] | None = None,
) -> ThesisRecord:
    """根据 parser 结果 + 测试集降级字段组装 ThesisRecord.

    优先用 parser 抓到的真实字段; parser 缺的字段用 fallback 补 (标 fallback_used).
    全都缺 → verified_status=failed, 但 source_url 仍保真.
    """

    fallback = fallback or {}
    fallback_used = False

    title = parsed.title
    if not title and fallback.get("title"):
        title = fallback["title"]
        fallback_used = True

    year = parsed.year
    if year is None and fallback.get("year"):
        try:
            year = int(fallback["year"])
            fallback_used = True
        except (TypeError, ValueError):
            pass

    abstract = parsed.abstract_snippet
    if not abstract and fallback.get("abstract_snippet"):
        abstract = fallback["abstract_snippet"]
        fallback_used = True

    domain = fallback.get("domain")

    # 三态判定
    has_title = bool(title)
    has_abstract = bool(abstract)
    if has_title and has_abstract:
        verified_status = "verified"
    elif has_title:
        verified_status = "partial"
    else:
        # 标题都抓不到 → failed; 若 fallback 给了标题, 仍标 partial (题录级降级证据)
        if fallback.get("title"):
            verified_status = "partial"
        else:
            verified_status = "failed"

    return ThesisRecord(
        thesis_id=thesis_id,
        title=title or "",
        year=year,
        source_url=source_url,
        domain=domain,
        abstract_snippet=abstract,
        verified_status=verified_status,
        fallback_used=fallback_used,
    )


def crawl_thesis_record(
    thesis_id: str,
    source_url: str,
    *,
    fallback: dict[str, Any] | None = None,
    http_client: httpx.Client | None = None,
) -> ThesisRecord:
    """抓取一条题录页 → ThesisRecord.

    Args:
        thesis_id: ENG-THESIS-001
        source_url: 原始题录链接 (必须保真, 不替换)
        fallback: 测试集已给字段 {title, year, abstract_snippet, domain}, 网络失败时降级用
        http_client: 可注入 httpx.Client (测试 mock 用)

    Returns:
        ThesisRecord: verified/partial/failed 三态之一. source_url 永远保真.
    """
    if not source_url or not source_url.startswith("http"):
        # 无效 URL: 直接 failed, 用 fallback 做题录级证据 (不崩)
        return _build_record(thesis_id, source_url or "", ParsedRecord(), fallback=fallback)

    owns_client = http_client is None
    if owns_client:
        http_client = httpx.Client(
            timeout=_TIMEOUT,
            headers={"User-Agent": _DEFAULT_UA, "Accept": "text/html,*/*"},
            follow_redirects=True,
        )

    try:
        resp = http_client.get(source_url)
        if resp.status_code >= 400:
            # 403/404/超时 → 降级为题录级证据 (不崩, 不编造)
            logger.warning("thesis %s crawl failed: http %s, degrade to record-level", thesis_id, resp.status_code)
            return _build_record(thesis_id, source_url, ParsedRecord(), fallback=fallback)
        html = resp.text
    except (httpx.HTTPError, OSError) as exc:
        # 网络异常: 降级为题录级证据 (不崩)
        logger.warning("thesis %s crawl error: %s, degrade to record-level", thesis_id, exc)
        return _build_record(thesis_id, source_url, ParsedRecord(), fallback=fallback)
    finally:
        if owns_client and http_client is not None:
            http_client.close()

    parsed = parse_cnki_html(html)
    # parser 抓到的字段优先, 缺的用 fallback 补
    merged_fallback = fallback or {}
    return _build_record(thesis_id, source_url, parsed, fallback=merged_fallback)
