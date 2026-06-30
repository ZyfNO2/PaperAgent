# Session 64 - T1: candidate_cleaner.py 报告

## 目标

在用户可见展示之前剔除明显不相关的候选 (AGN / 天文 / 德语 survey / 医学影像 / MLPerf / 死链), 防止 S58 的 `thesis_eval` 和 RAG Eval 拿到一堆噪声候选。

## 产物

- `apps/api/app/services/retrieval/candidate_cleaner.py` (新文件, ~220 行)
- `apps/api/tests/test_session64_t1_candidate_cleaner.py` (13 个测试, 全绿)

## 硬规则 (按顺序短路)

| # | 条件 | clean_status | mismatch_type |
|---|------|--------------|---------------|
| 1 | `retrieval_score < 0.20` 且 `matched_atoms` 为空 | `reject` | `low_relevance` |
| 2 | civil 题目 (concrete/crack/bridge/damage 或 domain=`vision_2d`/`civil`) 且标题命中跑题模式 | `reject` | `wrong_domain` |
| 3 | `source_status ∈ {fetch_failed, redirect_offtopic, dead}` | `quarantine` | `wrong_url` |
| 4 | survey-only 且 abstract 无任务对象 | `quarantine` | `not_paper` |
| 4b | 标题/摘要含 MLPerf / leaderboard 等 benchmark 模式 | `reject` | `wrong_domain` |

LLM 仅在硬规则未命中时细化分类, 且 LLM 输出 `reject` 时降级为 `needs_manual` (规则优先).

## 跑题模式 (case-insensitive, 已统一小写)

AGN, Active Galactic Nuclei, astronomy, astrophysics, galaxy/galaxies, cosmology,
German survey, German coding, survey motivation, MLPerf, benchmarking ML,
medical imaging, X-ray, CT scan, MRI, radiolog, protein fold, drug discovery,
leaderboard.

## 输出排序

`keep (0) → quarantine (1) → needs_manual (2) → reject (3)`, 同状态内按 `confidence` 降序.

## 测试覆盖 (13 个用例)

- `is_irrelevant_title`: AGN / 德语 survey / 医学 / MLPerf → True; 混凝土裂缝 → False
- `clean_candidates`:
  - 低分无 atom → reject (low_relevance)
  - AGN + civil → reject (wrong_domain)
  - 德语 survey + civil → reject
  - 医学影像 + civil → reject
  - MLPerf + civil → reject
  - 死链 (source_status=fetch_failed) → quarantine (wrong_url)
  - survey-only 无 civil object → quarantine
  - 排序: quarantine 在 reject 之前

## 已知简化

- LLM prompt 固定 schema, 不做 retry; 失败降级 keep, 不阻塞主流程
- 跑题模式以英文为主, 中文跑题词未列入 (后续如遇到再扩)
- `clean_candidates` 同步遍历, 未并发; 候选量在 100 量级不需要并行

## 升级时机

- 候选量 > 1000 / run: 改并行 (asyncio.gather)
- LLM 调用频率变高: 加 LRU 缓存 (title+abstract → result)
- 跑题模式漏判: 加 false positive 反例回归

## 不在本次范围

- 不接 EvidenceLedger / Orchestrator 主流程 (留给 T2)
- 不改 ranker / dedup (本次只新增模块)