"""Session 14: 多源检索增强 - 服务层入口.

模块结构:
- models: 内部 dataclass / dict 形态的中转模型
- query_plan: 题目 -> 查询计划
- normalizer: 不同 source 的原始 dict -> RetrievalCandidate
- dedup: 候选去重
- ranker: 候选评分
- adapters.openalex / arxiv / github / huggingface / semantic_scholar / kaggle: source 适配器
- orchestrator: 多源协调 + 持久化

设计要点:
- 所有外部 IO 走 ``fetch_with_timeout`` + ``safe_call`` 包装, 失败不阻塞其他 source
- 所有 source 在 tests 中必须能 mock, 不依赖真实网络
- source 适配器签名统一为 ``async def search(queries, top_k) -> list[dict]``
"""

from __future__ import annotations

from .normalizer import normalize_candidate
from .query_plan import build_query_plan
from .dedup import dedup_candidates, is_duplicate_in_ledger
from .ranker import score_paper, score_dataset, score_repo
from .orchestrator import (
    run_retrieval,
    get_last_run,
    get_run_by_id,
    list_runs,
    import_candidates,
    get_summary,
    reset_retrieval_state,
)

__all__ = [
    "build_query_plan",
    "normalize_candidate",
    "dedup_candidates",
    "is_duplicate_in_ledger",
    "score_paper",
    "score_dataset",
    "score_repo",
    "run_retrieval",
    "get_last_run",
    "get_run_by_id",
    "list_runs",
    "import_candidates",
    "get_summary",
    "reset_retrieval_state",
]
