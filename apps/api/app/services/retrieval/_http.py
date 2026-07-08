"""检索模块内部工具: HTTP 调用 + 归一化辅助 + 测试 hook."""

from __future__ import annotations

import os
import re
import socket
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse


# 标题标准化工具 (SOP §9)

_NOISE_WORDS = (
    "arxiv",
    "github",
    "dataset",
    "datasets",
    "paper",
    "papers",
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
)


def normalize_title(title: str) -> str:
    """标题标准化: 小写 + 去标点 + 压缩空白 + 去掉来源噪声词."""

    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^a-z0-9一-鿿\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    parts: list[str] = []
    for p in t.split(" "):
        if p and p not in _NOISE_WORDS:
            parts.append(p)
    return " ".join(parts)


def title_similarity(a: str, b: str) -> float:
    """两个标题的相似度 (0..1). 使用 token Jaccard + 子串覆盖."""

    a2 = set(normalize_title(a).split())
    b2 = set(normalize_title(b).split())
    if not a2 or not b2:
        return 0.0
    jacc = len(a2 & b2) / len(a2 | b2)
    short = min(len(a2), len(b2))
    if short == 0:
        return jacc
    contain = len(a2 & b2) / short
    return round((jacc + contain) / 2, 4)


def normalize_url(url: str | None) -> str | None:
    """URL 标准化: 去尾斜杠 / 强制小写 host / 去 fragment."""

    if not url:
        return None
    try:
        u = urlparse(url)
    except Exception:
        return url
    if not u.scheme or not u.netloc:
        return url
    host = u.netloc.lower()
    path = u.path.rstrip("/")
    if not path:
        path = ""
    return f"{u.scheme.lower()}://{host}{path}"


# HTTP 调用包装 (带超时 + 失败捕获)


class HttpError(Exception):
    """网络/HTTP 错误统一包装."""

    def __init__(self, message: str, source: str | None = None):
        super().__init__(message)
        self.message = message
        self.source = source


async def fetch_with_timeout(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    timeout: float = 8.0,
    client: Any | None = None,
) -> dict | list | str:
    """轻量 HTTP 调用, 优先使用 httpx, 缺失时降级 urllib.

    失败时抛 ``HttpError``, 由 orchestrator 捕获后降级.
    测试可通过 ``client`` 参数注入 mock.
    """

    env_timeout = os.environ.get("PAPERAGENT_HTTP_TIMEOUT_S", "").strip()
    if env_timeout:
        try:
            timeout = min(timeout, max(1.0, float(env_timeout)))
        except ValueError:
            pass

    if client is not None:
        # 测试用 mock client, 期望有 ``.request(method, url, headers=...) -> (status, body)``
        try:
            status, body = await client.request(method, url, headers=headers or {})
        except Exception as e:  # noqa: BLE001
            raise HttpError(f"mock client error: {e!s}") from e
        if status >= 400:
            raise HttpError(f"HTTP {status} for {url}")
        return body

    try:
        import httpx
    except ImportError:
        raise HttpError("httpx is required but not installed") from None

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, proxy=None, verify=False) as client_:
            resp = await client_.request(method, url, headers=headers or {})
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "")
            raise HttpError(f"HTTP 429 retry-after={retry_after} for {url}")
        if resp.status_code >= 400:
            raise HttpError(f"HTTP {resp.status_code} for {url}")
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:
            return resp.json()
        return resp.text
    except (httpx.HTTPError, socket.gaierror, TimeoutError, OSError) as e:
        raise HttpError(f"{type(e).__name__}: {e}") from e


async def safe_call(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    default: Any = None,
    error_message: str = "call failed",
) -> tuple[Any, str | None]:
    """协程包装, 异常时返回 (default, message)."""

    try:
        return await coro_factory(), None
    except Exception as e:  # noqa: BLE001
        return default, f"{error_message}: {type(e).__name__}: {e}"
