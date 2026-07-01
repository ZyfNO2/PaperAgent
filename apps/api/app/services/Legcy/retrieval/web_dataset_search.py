"""Session 64 T2: WebSearch fallback for datasets.

When specialized dataset APIs (HuggingFace, Kaggle) return too few results,
fall back to URL-pattern recognition against a curated list of known
public dataset hosts (Mendeley, Zenodo, Roboflow, Kaggle, PapersWithCode,
USU Digital Commons). Pure heuristic — no LLM, no live HTTP fetch in
the hot path. The orchestrator is expected to feed HTML/JSON it already
obtained; this module extracts dataset metadata from those payloads and
folds them into ``RetrievalCandidate`` shape.

Ponytail: no real network in this module. ``search_web_datasets`` is a
synchronous URL-pattern scanner that operates on whatever the caller hands
it (raw text fragments from a WebSearch response, cached HTML, or
hard-coded seed URLs). A separate ``seed_known_datasets`` helper returns
the curated fallback list so callers can use it as a safety net.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


WebDatasetSource = Literal[
    "websearch", "mendeley", "zenodo", "roboflow", "kaggle", "paperswithcode",
]


# ---------- 数据结构 ---------- #


class WebDatasetResult(BaseModel):
    """WebSearch fallback 找到的单个 dataset 候选项."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    name: str
    source: WebDatasetSource
    url: str
    scale: str | None = None
    license: str | None = None
    task_type: str | None = None
    matched_query: str
    is_downloadable: bool = False
    needs_auth: bool = False


# ---------- 查询模板 ---------- #


DATASET_QUERY_TEMPLATES: list[str] = [
    "{object_cn} 数据集",
    "{object_cn} 缺陷 检测 数据集",
    "{object_cn} 裂缝 数据集",
    "{object_en} dataset",
    "{object_en} crack detection dataset",
    "{object_en} defect detection dataset",
    "site:data.mendeley.com {object_en} crack dataset",
    "site:zenodo.org {object_en} defect dataset",
    "site:kaggle.com {object_en} crack detection dataset",
    "site:universe.roboflow.com {object_en} crack detection",
    "site:paperswithcode.com {object_en} dataset",
]


# ---------- 已知 dataset URL 模板 (fallback 兜底) ---------- #


_KNOWN_DATASET_URLS: list[dict] = [
    {
        "name": "SDNET2018",
        "url": "https://digitalcommons.usu.edu/all_datasets/48/",
        "source": "websearch",
        "scale": "~56000 images",
        "task_type": "concrete crack detection",
    },
    {
        "name": "Mendeley Concrete Crack Images",
        "url": "https://data.mendeley.com/datasets/5y9wdsg2zt/2",
        "source": "mendeley",
        "license": "CC BY 4.0",
        "scale": "40000 images",
        "task_type": "concrete crack classification",
    },
    {
        "name": "Mendeley Concrete Crack Segmentation",
        "url": "https://data.mendeley.com/datasets/bs2cfzrk4p/1",
        "source": "mendeley",
        "license": "CC BY 4.0",
        "scale": "500 images (segmentation masks)",
        "task_type": "concrete crack segmentation",
    },
    {
        "name": "CODEBRIM",
        "url": "https://zenodo.org/records/2620293",
        "source": "zenodo",
        "license": "CC BY 4.0",
        "scale": "7700 images",
        "task_type": "concrete defect detection (multi-class)",
    },
    {
        "name": "Roboflow Concrete Crack Detection",
        "url": "https://universe.roboflow.com/concrete-crack-detection",
        "source": "roboflow",
        "task_type": "concrete crack detection",
    },
    {
        "name": "Kaggle SDNET2018 Mirror",
        "url": "https://www.kaggle.com/datasets/aniruddhsharma/structural-defects-network-concrete-crack-images",
        "source": "kaggle",
        "task_type": "concrete crack detection",
    },
    {
        "name": "Concrete Crack Images for Classification (Mendeley)",
        "url": "https://data.mendeley.com/datasets/5y9wdsg2zt/2",
        "source": "mendeley",
        "license": "CC BY 4.0",
        "task_type": "concrete crack classification",
    },
]


# ---------- URL -> source 推断 ---------- #


_SOURCE_URL_PATTERNS: list[tuple[re.Pattern, WebDatasetSource]] = [
    (re.compile(r"^https?://data\.mendeley\.com/", re.I), "mendeley"),
    (re.compile(r"^https?://zenodo\.org/", re.I), "zenodo"),
    (re.compile(r"^https?://universe\.roboflow\.com/", re.I), "roboflow"),
    (re.compile(r"^https?://www\.kaggle\.com/", re.I), "kaggle"),
    (re.compile(r"^https?://paperswithcode\.com/", re.I), "paperswithcode"),
    (re.compile(r"^https?://digitalcommons\.usu\.edu/", re.I), "websearch"),
    (re.compile(r"^https?://github\.com/", re.I), "websearch"),
    (re.compile(r"^https?://huggingface\.co/datasets/", re.I), "websearch"),
]


def _infer_source(url: str) -> WebDatasetSource:
    for pat, src in _SOURCE_URL_PATTERNS:
        if pat.match(url):
            return src
    return "websearch"


# ---------- 工具函数 ---------- #


def _build_dataset_queries(topic_atoms: dict) -> list[str]:
    """从 topic_atoms 生成 query 列表.

    ``topic_atoms`` 至少包含 ``object_cn`` 和 ``object_en``; 缺哪个
    就跳过对应的模板.
    """
    obj_cn = (topic_atoms.get("object_cn") or "").strip()
    obj_en = (topic_atoms.get("object_en") or "").strip()

    queries: list[str] = []
    for tmpl in DATASET_QUERY_TEMPLATES:
        try:
            if "{object_cn}" in tmpl and not obj_cn:
                continue
            if "{object_en}" in tmpl and not obj_en:
                continue
            q = tmpl.format(object_cn=obj_cn or obj_en, object_en=obj_en or obj_cn)
            if q and q not in queries:
                queries.append(q)
        except (KeyError, IndexError):
            continue
    return queries


def _needs_auth_for_source(source: WebDatasetSource) -> bool:
    """某些 host 必须登录 (kaggle download, roboflow private)."""
    return source in {"kaggle", "roboflow"}


def _parse_web_result(url: str, html: str) -> WebDatasetResult | None:
    """从 WebSearch 返回的 HTML/JSON 片段里抽 dataset 元数据.

    不做真正的网络请求, 由调用方喂入片段. 抽不到就返回 None.
    """
    if not url:
        return None
    source = _infer_source(url)

    # name: <title> 优先, 否则 <h1>, 否则 URL 最后一段
    name: str | None = None
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    if m:
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        # 去掉 host 前缀 / 通用尾巴
        for noise in (" | Mendeley Data", " | Zenodo", " - Kaggle",
                      " | Roboflow", " | Papers with Code"):
            if name.endswith(noise):
                name = name[: -len(noise)].strip()
    if not name:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.I | re.S)
        if m:
            name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    if not name:
        slug = re.sub(r"^https?://[^/]+/", "", url).rstrip("/")
        name = slug.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ").title() or url

    if not name:
        return None

    # scale: 找 "X images" / "X samples" 之类的数字
    scale: str | None = None
    m = re.search(r"(\d[\d,\s]*)\s*(images?|samples?|records?|entries?)", html or "", re.I)
    if m:
        scale = f"{m.group(1).strip()} {m.group(2).lower()}"

    # license: CC BY / MIT / Apache
    license_: str | None = None
    m = re.search(r"\b(CC\s*BY[^\s<]*|MIT|Apache\s*2\.0|GPL[^\s<]*)\b", html or "", re.I)
    if m:
        license_ = m.group(1).strip()

    return WebDatasetResult(
        dataset_id=f"wd_{uuid.uuid4().hex[:10]}",
        name=name[:200],
        source=source,
        url=url,
        scale=scale,
        license=license_,
        task_type=None,
        matched_query="",
        is_downloadable=source in {"mendeley", "zenodo", "websearch"},
        needs_auth=_needs_auth_for_source(source),
    )


def _should_trigger(
    topic_atoms: dict,
    current_candidates: list[dict],
    *,
    min_results: int = 2,
    min_top_score: float = 0.45,
) -> bool:
    """判断是否需要 WebSearch 兜底.

    触发条件 (任一):
    1. dataset 候选数 < 2
    2. dataset top score < 0.45
    3. 题目包含工程对象 + 当前 dataset 候选包含 HF "未匹配公开数据集" 占位
    """
    dataset_cands = [c for c in current_candidates if c.get("candidate_type") == "dataset"]
    n = len(dataset_cands)

    # 条件 1: 数量不足
    if n < min_results:
        return True

    # 条件 2: top score 不足
    if n > 0:
        top = max((float(c.get("retrieval_score") or 0.0) for c in dataset_cands), default=0.0)
        if top < min_top_score:
            return True

    # 条件 3: placeholder "未匹配公开数据集" 出现
    placeholder = (topic_atoms.get("placeholder") or "").strip()
    if placeholder and any(placeholder in (c.get("title") or "") for c in dataset_cands):
        return True

    # 条件 4: 题目含工程对象 + dataset 候选空
    engineering_objects = topic_atoms.get("engineering_objects") or []
    if engineering_objects and n == 0:
        return True

    return False


# ---------- 公共入口 ---------- #


def seed_known_datasets(
    topic_atoms: dict,
    *,
    limit: int = 5,
) -> list[WebDatasetResult]:
    """返回与 topic_atoms 匹配的已知 dataset 列表 (兜底).

    用法: 真正的 WebSearch API 失败时, 至少给前端几个真实 URL.
    """
    obj_en = (topic_atoms.get("object_en") or "").lower()
    obj_cn = (topic_atoms.get("object_cn") or "").lower()
    want_concrete = any(
        t in (obj_en + " " + obj_cn)
        for t in ("concrete", "crack", "混凝土", "裂缝", "损伤", "damage")
    )
    if not want_concrete:
        return []

    out: list[WebDatasetResult] = []
    for spec in _KNOWN_DATASET_URLS[:limit]:
        out.append(WebDatasetResult(
            dataset_id=f"wd_{uuid.uuid4().hex[:10]}",
            name=spec["name"],
            source=spec["source"],
            url=spec["url"],
            scale=spec.get("scale"),
            license=spec.get("license"),
            task_type=spec.get("task_type"),
            matched_query="seed:concrete-crack",
            is_downloadable=spec["source"] in {"mendeley", "zenodo"},
            needs_auth=_needs_auth_for_source(spec["source"]),
        ))
    return out


def search_web_datasets(
    topic_atoms: dict,
    domain: str = "",
    min_results: int = 2,
    *,
    search_payloads: list[tuple[str, str]] | None = None,
) -> list[WebDatasetResult]:
    """WebSearch 兜底检索.

    Parameters
    ----------
    topic_atoms: 包含 object_cn / object_en / engineering_objects 等键.
    domain: 可选 domain 标签, 用于 trace.
    min_results: 最少返回几条.
    search_payloads: 调用方已抓到的 (url, html_or_text) 列表; 缺省时
        退化为 ``seed_known_datasets`` 兜底, 至少给前端几个真实 URL.

    Returns
    -------
    去重 + 限长后的 ``WebDatasetResult`` 列表.
    """
    # 1) 决定 query
    queries = _build_dataset_queries(topic_atoms)

    # 2) 解析调用方喂入的 payload, 缺则走 seed
    results: list[WebDatasetResult] = []
    if search_payloads:
        seen_urls: set[str] = set()
        for url, payload in search_payloads:
            if not url or url in seen_urls:
                continue
            parsed = _parse_web_result(url, payload or "")
            if parsed is None:
                continue
            # 用最近的 query 标记 matched_query
            parsed.matched_query = queries[0] if queries else ""
            results.append(parsed)
            seen_urls.add(url)
    else:
        results = seed_known_datasets(topic_atoms, limit=min_results * 2)

    # 3) 按 object 关键词过滤 (title / task_type 命中即留)
    obj_en = (topic_atoms.get("object_en") or "").lower()
    obj_cn = (topic_atoms.get("object_cn") or "").lower()
    if obj_en or obj_cn:
        keep: list[WebDatasetResult] = []
        for r in results:
            hay = (r.name + " " + (r.task_type or "")).lower()
            tokens = [t for t in (obj_en, obj_cn) if t]
            if any(t and t in hay for t in tokens):
                keep.append(r)
        if keep:  # 仅在过滤后非空时覆盖, 避免误伤 seed
            results = keep

    # 4) 去重 (by url) + 限长
    seen: set[str] = set()
    deduped: list[WebDatasetResult] = []
    for r in results:
        if r.url in seen:
            continue
        seen.add(r.url)
        deduped.append(r)
        if len(deduped) >= max(min_results * 2, 4):
            break

    return deduped


# ---------- trace hook ---------- #


def trace_search(
    project_id: str,
    topic_atoms: dict,
    results: list[WebDatasetResult],
    *,
    actor: str = "system",
) -> None:
    """把一次 web search 写进 trace (import-by-need, 防循环)."""
    try:
        from ..trace_store import append_trace  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return
    append_trace(
        project_id,
        action="web_dataset_search",
        target_type="dataset_search",
        target_id="websearch",
        actor=actor,
        after={
            "queries": _build_dataset_queries(topic_atoms)[:3],
            "result_count": len(results),
            "sources": sorted({r.source for r in results}),
        },
        reason="websearch fallback triggered" if results else "no websearch results",
    )


if __name__ == "__main__":
    # ponytail: self-check, fail loud if logic breaks
    atoms = {
        "object_cn": "混凝土",
        "object_en": "concrete",
        "engineering_objects": ["concrete", "crack"],
        "placeholder": "(未匹配公开数据集)",
    }

    # 1) _should_trigger: 空候选 -> True
    assert _should_trigger(atoms, []) is True
    # 2) _should_trigger: placeholder 命中 -> True
    fake = [{"candidate_type": "dataset", "title": "(未匹配公开数据集)", "retrieval_score": 0.9}]
    assert _should_trigger(atoms, fake) is True
    # 3) _should_trigger: 足够候选 + 高分 + 无 placeholder -> False
    good = [
        {"candidate_type": "dataset", "title": "Concrete Crack Dataset", "retrieval_score": 0.8},
        {"candidate_type": "dataset", "title": "Bridge Damage Dataset", "retrieval_score": 0.7},
    ]
    assert _should_trigger(atoms, good) is False
    # 4) _build_dataset_queries: 至少返回 5 条
    qs = _build_dataset_queries(atoms)
    assert len(qs) >= 5, qs
    # 5) seed 兜底: concrete 命中 -> 至少 2 条
    seed = seed_known_datasets(atoms, limit=4)
    assert len(seed) >= 2, seed
    # 6) _infer_source: mendeley URL -> mendeley
    assert _infer_source("https://data.mendeley.com/datasets/x/1") == "mendeley"
    assert _infer_source("https://zenodo.org/records/123") == "zenodo"
    assert _infer_source("https://universe.roboflow.com/foo") == "roboflow"
    # 7) _parse_web_result: 无 url -> None
    assert _parse_web_result("", "<title>X</title>") is None
    # 8) _parse_web_result: 有 title + scale + license
    html = "<title>Concrete Crack</title> 5000 images CC BY 4.0"
    p = _parse_web_result("https://data.mendeley.com/datasets/abc/1", html)
    assert p is not None
    assert p.source == "mendeley"
    assert p.scale == "5000 images"
    assert p.license and "CC" in p.license
    # 9) search_web_datasets: 无 payload 走 seed
    out = search_web_datasets(atoms)
    assert out, "search_web_datasets returned empty"
    assert all(r.url for r in out)

    print(
        f"OK web_dataset_search self-check passed "
        f"(queries={len(qs)} seed={len(seed)} parsed={len(out)})"
    )
