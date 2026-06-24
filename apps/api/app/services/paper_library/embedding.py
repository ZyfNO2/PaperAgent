"""Session 47: Mock in-memory embedding (SOP §5).

设计目标:
- deterministic & testable: 同输入 → 同向量
- 无外部 API key 依赖
- cosine 相似度可计算
- 真实 embedding API 接口预留 (EMBEDDING_PROVIDER env, 当前默认 mock)

实现:
- tokenize: 复用 rag_pipeline._tokenize (英文按词 + 中文按字)
- 词袋向量: 取当前 input 中 top-N=256 高频 token 作为维度
  - 当 N 未确定时, embed_text 会先把所有 chunk 文本收集成 corpus, 统一建立维度表
  - 这里做一个简化: 单文档 embedding 用全局固定维度 (按 hash 排序取 top-256 from 全集)
  - 但需要确定 corpus 才能定维度 — 见 get_or_build_vocab()
- cosine: 标准 cosine (L2 norm)
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
from collections import Counter
from typing import Iterable

# ---------------------------------------------------------------------------
# Tokenize — 与 rag_pipeline._tokenize 保持一致 (英文 + 中文)
# ---------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    text_lower = text.lower()
    tokens = re.findall(r"[a-z]+", text_lower)
    chinese_chars = re.findall(r"[一-鿿]", text)
    return tokens + chinese_chars


# ---------------------------------------------------------------------------
# Vocab 管理 (corpus 级 top-N)
# ---------------------------------------------------------------------------


_VOCAB_LOCK = threading.RLock()
_VOCAB: list[str] | None = None  # 全局维度表, 第一次 embed_corpus 时建立


def reset_vocab() -> None:
    """测试用: 清空 vocab 缓存."""
    global _VOCAB
    with _VOCAB_LOCK:
        _VOCAB = None


def build_vocab(corpus: Iterable[str], top_n: int = 256) -> list[str]:
    """从 corpus 建 top-N 高频 token 表 (deterministic)."""

    counter: Counter[str] = Counter()
    for text in corpus:
        for tok in tokenize(text):
            counter[tok] += 1
    # Counter.most_common 返回 [(tok, freq)]; 同频时按 token 字符串排序 (确定性)
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [tok for tok, _ in items[:top_n]]


def get_or_build_vocab(corpus: Iterable[str], top_n: int = 256) -> list[str]:
    """获取全局 vocab, 没建过就建. corpus 用于建表 (只第一次用)."""

    global _VOCAB
    with _VOCAB_LOCK:
        if _VOCAB is not None:
            return _VOCAB
        _VOCAB = build_vocab(corpus, top_n=top_n)
        return _VOCAB


# ---------------------------------------------------------------------------
# embed_text — single-doc vector
# ---------------------------------------------------------------------------


def _hash_to_unit(text: str, dim: int) -> list[float]:
    """备选: 无 vocab 时, 用 hash 桶直接生成 unit vector (deterministic).

    适用: 单文档 embedding, 不知道 corpus.
    简化: 直接用 token count 填入固定 dim, 归一化.
    """

    toks = tokenize(text)
    if dim <= 0:
        return []
    vec = [0.0] * dim
    for tok in toks:
        # 稳定 hash: md5 头 8 位取模
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % dim] += 1.0
    return vec


def embed_text(text: str, vocab: list[str] | None = None) -> list[float]:
    """把单段文本转成 dense vector.

    Args:
        text: 输入文本
        vocab: 已建好的维度表 (None = 用 hash 桶固定 dim=256)

    Returns:
        list[float], 长度 = len(vocab) 或 256
    """

    if not text:
        if vocab:
            return [0.0] * len(vocab)
        return [0.0] * 256

    if vocab:
        # 词袋向量: vocab 中 token 的频次
        toks = tokenize(text)
        tok_set = Counter(toks)
        vec = [float(tok_set.get(t, 0)) for t in vocab]
    else:
        # 单文档模式: hash 桶 → 256 维
        vec = _hash_to_unit(text, 256)

    return vec


def embed_corpus(corpus: list[str], top_n: int = 256) -> tuple[list[list[float]], list[str]]:
    """corpus 级别 embedding: 先建 vocab, 再批量 embed.

    Returns:
        (vectors, vocab): vectors[i] = embed(corpus[i]), vocab = 实际用的维度表
    """

    vocab = get_or_build_vocab(corpus, top_n=top_n)
    vectors = [embed_text(t, vocab=vocab) for t in corpus]
    return vectors, vocab


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """标准 cosine 相似度. 零向量返回 0.0."""

    if not a or not b:
        return 0.0
    if len(a) != len(b):
        # 维度不一致: 取 min 长度, 截断
        n = min(len(a), len(b))
        a = a[:n]
        b = b[:n]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Provider 开关 (真实 embedding 接口预留)
# ---------------------------------------------------------------------------


def get_embedding_provider() -> str:
    """读取 EMBEDDING_PROVIDER env, 默认 'mock'.

    未配置真实 provider 时, 强制返回 'mock'.
    """

    provider = os.environ.get("EMBEDDING_PROVIDER", "mock").strip().lower()
    if provider not in ("mock", "openai", "huggingface"):
        return "mock"
    # 当前只支持 mock
    if provider != "mock":
        return "mock"
    return provider


__all__ = [
    "build_vocab",
    "cosine_similarity",
    "embed_corpus",
    "embed_text",
    "get_embedding_provider",
    "get_or_build_vocab",
    "reset_vocab",
    "tokenize",
]