# Academic RAG 双仓统一 Handoff

> 最后更新：2026-07-28  
> 适用仓库：`ZyfNO2/PaperAgent`、`ZyfNO2/PaperClaw`  
> 状态：`remote_baseline_aligned / offline evidence only / P0 GO blocked`  
> 文档修订：`2026-07-28-remote-alignment-1`

## 0. 远端基线

| 仓库 | 分支 | 对齐前远端基线 | 状态 |
|---|---|---|---|
| PaperAgent | `codex/academic-rag-p0` | `e92b7f6b3ab942526c15f8c4a58116f1413e4537` | 已推送；包含旧版统一 Handoff |
| PaperClaw | `main` | `5891d87ec2a68f434fe8f728ba9be0999932c325` | 已推送；包版本 `0.38.0` |

PaperAgent 的 Academic RAG 实现基线为
`16cf771792617164d06d0160df1266cc8bb6cd89`，该 commit 可在远端解析。

旧 Handoff 中记录的 PaperClaw `28319079210a09ac231a0da10180afd52e8f2af3`、
`0.43`、`1033 passed`、107 篇/45,281 对象等结果目前无法从远端仓库解析或复核。
这些信息保留为 **reported_local**，不得作为远端已验证能力或发布依据。
必须先将对应实现分支与测试产物推送，再恢复为 `verified`。

本文不在正文内自引用当前同步 commit SHA。获取包含本文的提交：

```powershell
git log -1 --format=%H -- docs/handoff/ACADEMIC_RAG_DUAL_REPO_HANDOFF.md
```

## 1. 文档规则

本文是 Academic RAG 后续开发、优化、验收和发布工作的统一交接入口。
两个仓库保存 byte-equivalent 副本；修改时必须在同一工作批次同步更新两份。
若本文与旧 roadmap、SOP 或 handoff 冲突，以远端代码、可复算测试证据、
当前 SOP hard Gate 和本文未完成项为准。

PaperClaw 是论文版本、解析/索引、Evidence、Artifact 和 Desktop 的预定事实源。
PaperAgent 是 Query Planning、Evidence Ledger、跨论文推理、Academic Tailoring
和科学决策的事实源。PaperAgent 不得直接读取 PaperClaw SQLite、页面缓存或模型索引。

状态词：

- `verified`：可在指定远端 commit 上复算；
- `reported_local`：有本地报告，但远端缺对应 commit 或产物；
- `proposed`：计划项；
- `blocked`：缺少代码、数据、凭据、硬件或人工验收；
- `not_verified`：当前没有足够证据。

## 2. 当前状态

### 2.1 PaperClaw 远端已验证

当前 `main@5891d87ec2a68f434fe8f728ba9be0999932c325`：

- 包版本为 `0.38.0`；
- 已有论文导入/版本化基础、REST/CLI/Desktop paper library；
- 本地 PDF smoke 记录为 5/5 导入成功，重复导入 `created=false`；
- full non-live regression 为 `1022 passed, 23 skipped, 12 deselected`；
- post-review hardening suite 为 `13 passed`。

当前远端不能验证：

- PaperClaw `academic.v1` 完整契约；
- PyMuPDF page/object canonical parser；
- page/section/figure/table-cell/equation/algorithm locator 全集；
- content-addressed 页面/对象资产；
- SentenceTransformer/ColQwen2 多通道索引；
- Evidence Bundle、Project Memory、append-only Academic Artifact Store；
- 107 篇 corpus、45,281 对象和 `1033 passed` 的 0.43 验收结果。

### 2.2 PaperAgent 远端状态

`codex/academic-rag-p0@e92b7f6b3ab942526c15f8c4a58116f1413e4537`
已包含旧版统一 Handoff，Academic RAG 实现基线
`16cf771792617164d06d0160df1266cc8bb6cd89` 可远端解析。

旧 Handoff 报告的下列能力保留为 `reported_local`，本次文档同步没有重新运行验收：

- `AcademicEvidenceSource.retrieve/resolve` 和 `AcademicArtifactSink` seam；
- identity/method/figure/table/equation/comparison/tailoring routing；
- 有界 primary/corrective/conflict 控制流；
- accepted/rejected/conflicted Evidence Ledger；
- 八类 evidence-bound deterministic drafts；
- `draft → approved/rejected → final` 状态机；
- PaperClaw optional adapter 与跨仓 tracer；
- Python 3.11/3.12 acceptance 和 coverage 记录。

### 2.3 数据和工作树约束

- PaperAgent 的 `.venv-paperagent/`、`output/` 不进入版本控制；
- PaperClaw 的 `data/` 为私人/本地 corpus，不提交原始 PDF；
- 模型、缓存、数据库、日志和 Secret 不提交；
- 当前远端分支：PaperAgent 为 `codex/academic-rag-p0`，PaperClaw 为 `main`；
- 尚未建立本轮关联 PR，也尚未记录对应 CI run ID；
- 本文同步完成后，停止在 H0 后续执行之前。

## 3. 当前不能宣称的能力

- 当前状态不是 Academic RAG P0 GO，也不是科学有效性证明；
- 不得宣称 PaperClaw 0.43 已在远端发布或可安装；
- 不得把 `reported_local` 的 107 篇 corpus、45,281 对象或 1033 tests
  写成远端已复核结果；
- PaperClaw 当前远端没有正式 Docling adapter；
- Markdown、Text、LaTeX 尚未验证进入统一 Academic parser pipeline；
- 当前远端不能宣称完整 BM25、SentenceTransformer、weighted RRF 或 ColQwen2 质量；
- 尚未形成可校准的 conflict detector；
- corrective retrieval 尚未验证能按失败原因生成新 query/channel strategy；
- deterministic draft 不是经过真实 LLM 和人工专家确认的科学分析；
- Desktop 尚未验证 optional extension 的产品级装载、恢复和审批闭环；
- 尚无远端可复算的 12 篇验收集、32 个 blinded labels、2 个跨论文人工金标；
- 没有本轮真实 LLM trace、Native Desktop 点击记录和最终 Artifact 人工审批。

## 4. P0 收口执行计划

以下阶段必须按顺序完成。本文同步结束后不自动继续执行。

### H0：发布基线与 corpus 冻结

- [x] PaperAgent `codex/academic-rag-p0` 已推送；
- [x] PaperClaw `main@5891d87...` 已推送；
- [x] 统一 Handoff 已同步到两个远端仓库；
- [ ] 推送能够支持旧 Handoff 0.43/Academic RAG 声明的 PaperClaw 实现分支，
  或明确放弃这些本地声明并按 0.38 重定计划；
- [ ] 建立关联 PR，并记录两仓 final head SHA、CI run URL/ID；
- [ ] 为 corpus 生成许可、来源、有效性状态，不提交全文；
- [ ] 对 invalid/corrupt input 执行重新获取、隔离或明确排除决策，保留 hash 和原因；
- [ ] 从有效语料冻结 12 篇验收集；
- [ ] 提交只含 metadata/hash/license/status 的 corpus manifest。

完成条件：两仓依赖关系可远端复现；tracked worktree clean；manifest digest 可复算；
原 PDF 保持 untracked；所有 `verified` 声明均绑定远端 commit 和测试证据。

### H1：canonical parser 与 locator 完整化

- [ ] 将 PaperClaw parser 组织为可替换 adapter；
- [ ] 明确 PyMuPDF、Docling、OCR/VLM/heuristic provenance；
- [ ] 增加 Markdown、Text、LaTeX ingestion；
- [ ] 加密、损坏、扫描件、渲染失败返回结构化 `partial/failed`；
- [ ] Table Cell、Equation、Caption、Algorithm、Reference/Citation locator tests 全绿；
- [ ] 重复 ingest/parse/index 幂等，旧 locator 可 replay 且 fail-closed。

完成条件：冻结 12 篇全部产生 manifest；可标注对象具有 page 和有效 bbox；
旧版本 locator resolve fail-closed。

### H2：正式多通道 Retrieval

- [ ] named retrievers：BM25、SentenceTransformer、ColQwen2、exact field；
- [ ] page、region、Figure、Table、Cell、Equation 分别入索引；
- [ ] weighted RRF Trace 保存原始分、权重、fingerprint 和降级；
- [ ] project/paper/object/section filters 与 max-char budget；
- [ ] 可测试 conflict detection；
- [ ] corrective retrieval 产生可解释 rewrite，并保留 DOI/arXiv/title identity；
- [ ] OOM、模型缺失、index corruption、fingerprint drift 有确定终态；
- [ ] 增量索引和 active generation 不破坏旧 locator。

| 指标 | Gate |
|---|---:|
| Document Recall@5 | ≥ 0.90 |
| Page Recall@5 | ≥ 0.80 |
| Object Recall@5 | ≥ 0.75 |
| Table Cell exact accuracy | ≥ 0.85 |
| Locator page accuracy | 1.00 |
| bbox IoU≥0.5 比例 | ≥ 0.80 |
| Abstention accuracy | ≥ 0.90 |

### H3：PaperAgent 科学推理与 Artifact

- [ ] PaperClaw adapter 作为正式 optional extension factory；
- [ ] Query Planner 输出 decomposition、rewrite、channel、filters、budget、reason；
- [ ] 真实 LLM 只消费 accepted Evidence Ledger；
- [ ] 每个 Claim 绑定可 resolve locator，并执行 citation/claim mismatch 检查；
- [ ] 实现多论文 Comparison、Baseline/Module、Compatibility、Experiment、Method Draft；
- [ ] 证据不足、不可复现、license/shape/semantic 冲突进入 REVISE/NO-GO；
- [ ] 八类 Artifact 写入 PaperClaw append-only store。

完成条件：两个跨论文场景生成八类 evidence-bound Artifact；critical unsupported claim、
citation mismatch、false GO 均为 0。

### H4：Desktop 与人工审批闭环

- [ ] Desktop 发现并加载 PaperAgent optional extension；
- [ ] 导入、parse/index progress、failure、channel/budget/Trace 可见；
- [ ] Claim → locator → PDF page/bbox 可点击回读；
- [ ] Evidence Ledger 展示 accepted/rejected/conflicted 和原因；
- [ ] 长任务支持 cancel、restart recovery 和 bounded failure；
- [ ] 未批准的 Methodology/Compatibility/Experiment 不得 final/export；
- [ ] Approve/Reject 只追加 revision；
- [ ] 完成 Native Windows Desktop checklist 和脱敏截图。

### H5：真实验收与 P0 GO

- [ ] 12 篇 corpus 建立 32 个 blinded questions；
- [ ] 冻结 2 个 baseline/module tailoring 场景和人工 expected decisions；
- [ ] 在目标 GPU 上运行真实 SentenceTransformer/ColQwen2 benchmark；
- [ ] 运行真实 OpenAI-compatible LLM，保存脱敏 Trace 和 Artifact revisions；
- [ ] 至少一名人工 reviewer 审批或拒绝并记录理由；
- [ ] 分开报告 synthetic、真实论文离线、GPU、真实 LLM 和人工结果；
- [ ] 两仓 full CI、wheel/package、Desktop smoke、SOP check 全绿。

只有全部 hard Gate 通过后，才允许改为 `P0 GO / release_accepted`。

## 5. P1 开发与优化计划

P1 不得在 P0 hard Gate 未闭合时改写 P0 契约。

- Relation Graph：edge 必须绑定 locator/provenance；推断 edge 标为 `inferred`；
- 质量平台：版本化 labels/splits/fingerprints/run manifests，记录 Recall、MRR、nDCG、
  bbox IoU、abstention、unsupported claim、false GO、latency、VRAM、cost；
- 性能：embedding batch、OOM retry、LRU、增量索引、streaming、p50/p95；
- 产品：Desktop accessibility、错误态、Artifact diff、privacy UI、安装和迁移。

## 6. P2 计划

- Coding Worker 只消费 approved Artifact，不自主决定科学 GO；
- workspace sandbox、命令 allowlist、资源预算、checkpoint/undo、patch review；
- 禁止自动修改论文正文或执行高成本训练；
- Connector 必须有权限、许可、provenance、rate limit 和 secret-redaction contract；
- HTTP/MCP 只能作为次级 adapter，不替代 P0 Python interface。

非目标：公开多租户、通用 IDE、自动投稿、无界 autonomous research、PixelRAG 训练、
大规模分布式服务。

## 7. 跨阶段工程规则

- 新能力先写 seam-level tracer test，再做最小实现；
- PaperClaw contract 先加 serialization fixture，再同步 PaperAgent adapter；
- 禁止双仓各自新增同名事实模型；
- 不降低 strict Mypy、coverage、abstention 或 source-hash Gate；
- 每阶段保存命令、summary、coverage、wheel SHA-256、fingerprint 和双仓 commit SHA；
- 自动化通过不等于 live/scientific/human validation；
- 缺失证据、冲突、版本漂移或无法 resolve 的 Claim 必须 fail closed。

## 8. 当前可执行验证命令

PaperAgent：

```powershell
git checkout codex/academic-rag-p0
git rev-parse HEAD
python scripts/local_acceptance.py --profile full --continue-on-error
pytest tests/academic -q
```

PaperClaw 当前远端 `0.38.0`：

```powershell
git checkout main
git rev-parse HEAD
python -m pytest -q -m "not real_llm and not process_acceptance and not distributed"
python -m build
```

旧 Handoff 中的 `academic_corpus_acceptance.py`、`artifacts/v0_43`、PaperClaw 0.43 wheel
和真实跨仓 tracer 命令，在对应实现分支推送前保持 `blocked`。

## 9. 下一执行者起点

本文同步完成后停止，不继续执行 H0。

下一批次必须从以下事项开始：

1. 决定并推送 PaperClaw Academic RAG/0.43 对应实现分支，或正式撤销本地声明；
2. 建立关联 PR；
3. 记录两仓 CI run 和 final head SHA；
4. 之后才处理 corpus 许可、invalid/corrupt 决策和 12 篇冻结集；
5. 未获得这些证据前，状态保持
   `remote_baseline_aligned / offline evidence only / P0 GO blocked`。
