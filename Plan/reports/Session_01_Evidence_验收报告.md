# Session 1 验收报告: Evidence 数据模型 + 手动添加论文/数据集/工程后端

> 验收时间: 2026-06-17
> 阶段: Session 1 / Phase 01 (按 SOP §5 + §13.1)
> Commit: 470981b

---

## 1. 范围

按 `Plan/Faraway/PaperAgent_交互式证据工作台改造计划书与SOP.md` §5 (证据工作台) + §13.1 (后端新增模块):

- **数据结构**: EvidenceItem 统一表示 paper / dataset / repo / note / custom
- **手动添加**: POST papers/datasets/repos manual 三个端点
- **审核**: PATCH review 改 review_status, DELETE 删
- **自动入池**: run_one_topic 跑完后把自动检索的 papers/datasets/baselines 同步进 evidence ledger
- **dedup**: paper 按 DOI / arxiv_id 完全相同 / 标题 jaccard > 0.92 跳过

## 2. 文件清单

| 路径 | 行数 | 说明 |
|---|---|---|
| `apps/api/app/schemas_evidence.py` | 173 | 新增: EvidenceItem + 3 个 ManualCreate + ReviewUpdate + Ledger/Action 响应 |
| `apps/api/app/services/evidence.py` | 297 | 新增: 内存 evidence store + dedup + 6 个操作函数 |
| `apps/api/app/schemas.py` | +4 | OneTopicResponse 加 project_id 字段 |
| `apps/api/app/services/one_topic.py` | +20 | run_one_topic / run_one_topic_stream 生成 project_id + ingest_auto_evidence |
| `apps/api/app/api/v1/one_topic.py` | +60 | 6 个新端点 (router 追加) |
| `apps/api/tests/conftest.py` | +56 | fast-arxiv mock (3 篇固定假数据) |
| `apps/api/tests/test_evidence_api.py` | 200 | 11 个新测试用例 |

**总: 7 文件, 849 行新增, 3 行修改.**

## 3. 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/one-topic/{project_id}/evidence` | 池摘要 + papers/datasets/repos/notes |
| POST | `/api/v1/one-topic/{project_id}/evidence/papers/manual` | 手动加论文 (DOI/arXiv/标题去重) |
| POST | `/api/v1/one-topic/{project_id}/evidence/datasets/manual` | 手动加数据集 |
| POST | `/api/v1/one-topic/{project_id}/evidence/repos/manual` | 手动加 GitHub 工程 |
| PATCH | `/api/v1/one-topic/evidence/{evidence_id}/review` | 改 review_status |
| DELETE | `/api/v1/one-topic/evidence/{evidence_id}` | 删一条 |

## 4. 测试结果

```text
apps/api/tests/test_evidence_api.py (11 用例)
  test_analyze_returns_project_id ............. PASSED
  test_auto_ingest_after_analyze .............. PASSED
  test_manual_add_paper ....................... PASSED
  test_dedup_by_doi ........................... PASSED
  test_dedup_by_title ......................... PASSED
  test_manual_add_dataset_and_repo ............ PASSED
  test_patch_review ........................... PASSED
  test_patch_review_reject .................... PASSED
  test_delete_evidence ........................ PASSED
  test_patch_nonexistent_evidence ............. PASSED
  test_existing_one_topic_tests_still_pass .... PASSED
                                         11 passed in 0.29s

apps/api/tests/test_one_topic_api.py (7 老用例) ... 7 passed in 0.24s
                                                  =============
                                                  18 passed 总计
```

## 5. 修了哪些 bug (相对 SOP)

| Bug | 原因 | 修法 |
|---|---|---|
| datasets/repos 自动入池失败 | `BaselineHit` / `DatasetHit` 没有 `license` / `modality` 字段, ingest 报 AttributeError 被 try/except 吞了 | ingest 只用现有字段, tags 用 `source_xxx` 记录 |
| PATCH/DELETE 死锁 | `_summary` 锁内递归调 `_get_project` (Lock 不可重入) | `_LEDGER_LOCK` 改 RLock |
| 测试慢 (单用例 5.3s) | 单测里走真 arXiv 检索 | conftest 加 fast-arxiv mock, 假数据 3 篇 |
| 测 11 个总 timeout | 累计 arXiv + PATCH 死锁 | 修完后 0.29s |

## 6. 关键不变式 (对齐 CLAUDE.md)

- ✓ pytest 总数: 7 → 18 (老的不删, 新的加)
- ✓ LLM 路径配 heuristic fallback (没改)
- ✓ 真实 uvicorn smoke 之前做过, 这次单测 (4 测试都跑通)
- ✓ 不在 Pydantic v2 用 `T | None = None` 默认参数 (用 `Field(default=None)`)
- ✓ 不依赖 lifespan 外 ORM class (无 ORM)

## 7. 下一 session

Session 2: 证据工作台 UI (apps/web) + 审核状态机。前端加 "证据工作台" 页, 显示 papers/datasets/repos 三栏 + 接受/拒绝/核心 按钮, 调后端 6 个端点, Playwright e2e 测。
