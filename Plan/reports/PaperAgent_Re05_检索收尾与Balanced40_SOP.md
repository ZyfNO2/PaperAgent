# PaperAgent Re05 检索收尾与 Balanced 40 SOP

> 起草日：2026-07-02
> 前置：Re04 + Re04-fix 已完工（Smoke 5 达 3p+2w+0f，SOP §6.2 合格线达标）
> 本 SOP 范围：方案 A —— 纯检索收尾。把 Re04-fix 后剩余 5 个检索硬伤全部修掉，跑通 balanced 40 ≥ 80% pass+weak，为 Re06+ 后续功能（verify/novelty/知识图）立稳地基。
> 参考实现（已核实路径真实存在，禁止闭门造车）：
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\agents\benchmark_agent\surveyor.py`（HF Hub dataset 发现 + 本地 benchmark_knowledge.yaml）
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\data\benchmark_knowledge.yaml`（domain→标准数据集/baseline 注册表范式）
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\search.py`（多源联合 + cache）
> - `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-paper\agents\literature_strategist_agent.md`（4 层检索策略 / 中英分检）

---

## 0. 目标与不做的事

**目标**：Re04-fix 后 Smoke 5 是 3p+2w+0f，但 5 个检索硬伤仍在。本 SOP 把这 5 个硬伤全修，跑 balanced 40 达 SOP §6.3 ≥80% pass+weak，**检索正式收尾**。

**不做**（方案 A 边界，用户已审批）：
- ❌ 不做候选核验（verify.py）/ 新颖性（novelty.py）/ 知识图 —— 留 Re06+
- ❌ 不做 Forward Tracking / Semantic 语义检索 —— 留 Re06+
- ❌ 不引入 `*_score` 字段、不新增绕过检索的假白名单（S66v）
- ❌ 不改 ER / synthesize 的 prompt 文本
- ❌ 不跑 balanced 40 之外的 100 全量

---

## 1. 诊断：5 个剩余硬伤 + 已有资产核实（避免闭门造车）

> **关键发现**：H1 不是"缺能力"，是"接线 bug + 资产未用"。PaperAgent 已有 HuggingFace adapter + 域白名单 + collect_mentioned_datasets，但 Re04 主路径没用它们。本 SOP 优先接线和扩资产，而非从零造。

| # | 硬伤 | 已有资产（核实位置） | 缺陷 | 影响 case |
|---|---|---|---|---|
| H1 | dataset 0/5 | `huggingface_search.py`（HF dataset API，已存在）；`collect_mentioned_datasets()`（candidate_pool.py:295）；`_DATASET_WHITELIST_BY_DOMAIN`（research_agent.py:954，已含 DOTA/DIOR/DTU/KITTI/ScanNet 等 8 域） | (a) `re04_entry.py:224` 调 `collect_mentioned_datasets(raw, pool)` **没传 whitelist**→默认空→啥也不扫；(b) `FAMILY_TO_ADAPTER["dataset"]=["crossref","openalex"]`，**huggingface 没接线**；(c) 白名单缺点云补全专属（ModelNet40/PCN/ShapeNet/Completion3D）+ TJU-DHD | 015/018/027 |
| H2 | 018/024 weak（点云召回稀疏） | 无 canonical method-name 注册表 | query_matrix baseline query 是宽词（"point cloud completion"），搜不到 PCN/SnowflakeNet/PoinTr 等专属方法 | 018/024 |
| H3 | 027 parallel=1（RS 数据集没升桶） | 同 H1（remote_sensing 白名单已含 DOTA/DIOR） | 同 H1 接线 bug + 缺 TJU-DHD/AIR-SAR | 027 |
| H4 | OpenAlex 28/28 empty + S2 5/5 429 | `semantic_scholar_search.py`（已有 circuit breaker）；AutoResearchClaw `literature/cache.py`（持久缓存范式） | 无备用源；无持久缓存（每次重跑重打 429）；OpenAlex 无备用 endpoint | 全部 |
| H5 | balanced 40 未跑 | `re04_balanced_40_ids.txt`（已就绪）；`run_re04_smoke.py`（已就绪） | H1-H4 没修前跑 40 只会多 weak | SOP §6.3 验收 |

---

## 2. 任务 1（H1）：dataset 接线 + 白名单扩展

### 2.1 缺陷 (a)：collect_mentioned_datasets 没传 whitelist

**位置**：`apps/api/app/services/agents/re04_entry.py:224`

**现状**：
```python
collect_mentioned_datasets(raw, pool)   # whitelist 默认 {} → 扫 0 个
```

**改**：
```python
from .research_agent import _DATASET_WHITELIST_BY_DOMAIN
# 按 qm.domain_route 选域子集；unknown 时用全量（保守）
domain_route = qm.get("domain_route") or "unknown"
wl = _DATASET_WHITELIST_BY_DOMAIN if domain_route == "unknown" else {
    domain_route: _DATASET_WHITELIST_BY_DOMAIN.get(domain_route, ())
}
collect_mentioned_datasets(raw, pool, whitelist=wl)
```

**机制说明（S66v 合规）**：`collect_mentioned_datasets` 不是"注册表直接塞 pool"——它扫描**已检索论文的 title/abstract**，看其中是否**提到了**白名单里的已知数据集名。来源信号是真实检索结果，不是凭空捏造。原代码注释（research_agent.py:951-953）已明确辩护此点。本 SOP 沿用此机制，不改变其合规性质。

### 2.2 缺陷 (b)：HuggingFace adapter 接线

**位置**：`apps/api/app/services/agents/retrieval_orchestrator.py:44-53, 88-94`

**现状**：`FAMILY_TO_ADAPTER["dataset"] = ["crossref", "openalex"]`，`adapter_calls` 字典无 `"huggingface"` 键，HF adapter 是死代码。

**改**：
- `FAMILY_TO_ADAPTER["dataset"] = ["crossref", "openalex", "huggingface"]`
- `_dispatch_family_to_adapters` 签名新增 `fetch_huggingface` 参数
- `adapter_calls["huggingface"] = fetch_huggingface`
- `re04_entry._dispatch_to_adapters` 把 `huggingface_search` 传入

**HF adapter 适配**：现有 `huggingface_search.py` 只取 `queries[:1]`，返回 `id/likes/downloads/tags`。需小改：
- 取 `queries[:2]`（不只 1 个）
- 返回字段加 `title=id`、`evidence_type="dataset"`、`source="huggingface"`，使其能被 `collect_papers_from_raw` 识别为 dataset 候选
- HF 返回的 dataset 卡（cardData）若含 `task_categories`，写入 `tags` 供 ER 判定

### 2.3 缺陷 (c)：白名单扩展

**位置**：`apps/api/app/services/agents/research_agent.py:954-988` `_DATASET_WHITELIST_BY_DOMAIN`

**新增条目**：
```python
"vision_3d": (
    # 现有 DTU/ETH3D/T&T/BlendedMVS/TUM/ScanNet/Matterport/KITTI/ApolloScape/Waymo/NeRF/LLFF 保留
    # 新增点云补全/配准专属：
    "ModelNet40", "ModelNet10", "ShapeNet", "ShapeNetCore",
    "PCN", "Completion3D", "MVPG", "KITTI-360",
),
"remote_sensing": (
    # 现有 DOTA/DIOR/LEVIR-CD/AID/NWPU-RESISC45 保留
    # 新增：
    "TJU-DHD", "AIR-SAR", "RSOD", "UCAS-AOD", "DOTA-v2",
),
```

**禁止**：不新增"未在论文里被提及过"的冷门数据集（避免凭空塞 pool 的 S66v 风险）。只加"任何该领域学生都认识"的公开 benchmark。

### 2.4 参考依据
AutoResearchClaw `benchmark_agent/surveyor.py:48-63` 用本地 `benchmark_knowledge.yaml` + HuggingFace Hub API 双路发现 dataset。本任务的 HF 接线 + 白名单扩展与其思路一致：本地已知名录（白名单）兜底 + HF API 在线发现。

### 2.5 验证
| case | H1 修复前 dataset | 修复后预期 |
|---|---|---|
| 015 | 0 | ≥1（TUM RGBD / KITTI 应在已检索论文 title 里被扫到） |
| 018 | 0 | ≥1（ModelNet40 / ShapeNet / PCN 若被点云论文提及） |
| 027 | 0 | ≥1（DOTA / DIOR / TJU-DHD） |

---

## 3. 任务 2（H2）：canonical method-name 注册表 → 只喂 query

### 3.1 S66v 边界（用户已审批：只喂 query）

**本任务的注册表与任务 1 的白名单机制不同**：
- 任务 1 白名单 → `collect_mentioned_datasets` 扫描已检索文本提取（来源是检索信号，喂 pool，合规）
- 任务 2 注册表 → **只生成 baseline query 喂给 adapter 检索**，**不喂 pool**。注册表条目本身不进 pool，只作为 query 种子

### 3.2 新增资产

**文件**：`apps/api/app/services/agents/data/canonical_baselines.yaml`（新建）

**结构**（借鉴 AutoResearchClaw `benchmark_knowledge.yaml`）：
```yaml
# canonical method-name registry — ONLY feeds retrieval queries, never pool.
# S66v compliant: entries do not bypass any round; they only seed queries.
domains:
  point_cloud_completion:
    canonical_baselines:
      - PCN
      - SnowflakeNet
      - PoinTr
      - GRNet
      - TopNet
      - FoldingNet
    keywords: [point cloud completion, shape completion, 3d completion]
  point_cloud_registration:
    canonical_baselines:
      - PointNetLK
      - DCP
      - OMNet
      - PREDATOR
      - RIP-Net
      - PointerNet
    keywords: [point cloud registration, point cloud alignment, 3d registration]
  remote_sensing_detection:
    canonical_baselines:
      - YOLOv5
      - YOLOv7
      - YOLOv8
      - Faster R-CNN
      - RetinaNet
    keywords: [remote sensing, aerial detection, object detection]
  # 其余 domain 按需补，本 SOP 只硬性要求上述 3 个（Smoke 5 的 weak case 覆盖）
```

### 3.3 接线

**位置**：`apps/api/app/services/agents/query_matrix.py:147-168`（baseline_family 四层退路后）

**改**：在四层退路**之前**插入注册表优先级——
```python
# Re05: canonical baseline registry feeds queries (NOT pool). S66v: only seeds queries.
from .data.canonical_baselines import load_canonical_baselines
canonical = load_canonical_baselines(domain)
baseline_family = [f"{b} {task_first}" for b in canonical[:4]] if canonical else []
# 若 canonical 非空 → fallback_reason = null（精确 query，无降级）
# 若 canonical 空 → 走原 Re04-fix 四层退路（不变）
```

**data/canonical_baselines.py**（新建，loader）：读 yaml → 按 domain 返回 list。文件不存在时返空（不崩）。

### 3.4 参考依据
AutoResearchClaw `benchmark_knowledge.yaml` 的 `common_baselines` + `required_baselines` 字段就是此范式。其 `selector.py:30-54` 用这些名录做筛选——本任务只用其"名录"部分做 query 种子，不做 selector 的硬件筛选（那是后续功能）。

### 3.5 验证
| case | H2 修复前 baseline query | 修复后 |
|---|---|---|
| 018 | ["point cloud completion ..."]（宽词） | ["PCN point cloud completion", "SnowflakeNet ...", "PoinTr ..."] |
| 024 | ["unsupervised point cloud registration ..."] | ["PointNetLK ...", "DCP ...", "PREDATOR ..."] |
| 027 | ["YOLOv5 object detection"] | ["YOLOv5 remote sensing", "YOLOv7 ..."] |

---

## 4. 任务 3（H3）：027 RS 数据集升桶

### 4.1 位置
任务 1 的白名单扩展已覆盖 H3（remote_sensing 加 TJU-DHD/AIR-SAR/RSOD）。H3 无独立代码改动，依赖任务 1。

### 4.2 额外：ER dataset 桶升桶规则（仅 prompt 注释，不改文本）

**问题**：即使 dataset 进了 pool，LLM ER 仍可能把它判成 reference 而非 dataset 桶（027 的 TJU-DHD 落 parallel）。

**改（最小）**：`evidence_review.py` 的 candidate 投递给 LLM 时，`pool_block` 里给 `evidence_type=="dataset"` 的候选加一个显式标记字段 `"is_dataset_candidate": True`（不改 prompt，只让 LLM 看到这个字段）。LLM 自然倾向把它判 dataset 桶。

**禁止**：不在 prompt 里写 `if is_dataset_candidate: status=core` 这种硬规则（违反 S66v 不泄题）。只暴露字段，LLM 自判。

### 4.3 验证
027 重跑后 dataset ≥1，且该候选 `relation_to_topic == "dataset"`。

---

## 5. 任务 4（H4）：备用源 + 持久缓存

### 5.1 CORE adapter（新源）

**文件**：`apps/api/app/services/retrieval/adapters/core_search.py`（新建）

**接口**：`async def core_search(queries, top_k=8, *, client=None) -> list[dict]`
- API：`https://api.core.ac.uk/v3/search/works?q=<query>&limit=<top_k>`
- 无 key（CORE 的 v3 需 key，免费注册；无 key 时走 v3 公共端点降级 top_k=3）
- 返回字段归一化：`title/abstract/year/doi/source="core"/evidence_type="paper"`
- 429/5xx 返空，不抛

**接线**：`FAMILY_TO_ADAPTER["core"].append("core")`？**否**——CORE 是论文源不是 baseline/dataset 专属。改：加到 `core` 和 `dataset` 族的备用位：
```python
"core": ["arxiv", "openalex", "crossref", "core"],
"dataset": ["crossref", "openalex", "huggingface", "core"],
```

### 5.2 OpenAlex 备用 endpoint

**位置**：`apps/api/app/services/retrieval/adapters/openalex_search.py`

**改**：503/空 body 时，切到 `https://api.openalex.org/works?search=<query>`（当前若用 `filter=` 走法，改 `search=` 走法），重试 1 次。仍空则记 ledger `status=openalex_backup_empty`。

### 5.3 持久缓存

**文件**：`apps/api/app/services/retrieval/adapters/_cache.py`（新建，借鉴 AutoResearchClaw `literature/cache.py`）

**机制**：
- key = `hash(adapter + query)`
- 存 `tmp_re04_eval/adapter_cache/<key>.json`（24h TTL）
- 命中 → 直接返，不打网络（避免重跑重打 429）
- 未命中 → 打网络，成功则写缓存
- 429/5xx → 不写缓存（避免缓存空结果）

**接线**：每个 adapter 的 search 函数包一层 `_cached(adapter_name, query, fn)`。环境变量 `PAPERAGENT_ADAPTER_CACHE=1` 开启，默认关（不污染离线测试）。

### 5.4 参考依据
AutoResearchClaw `literature/cache.py` + `search.py:143-161` 的 `cache_get/cache_put` 双回调缓存范式。`semantic_scholar.py:46-48` 三态 circuit breaker（PaperAgent 已有）。

### 5.5 验证
- balanced 40 重跑时，OpenAlex ok 率从 0/28 提升到 ≥14/28（备用 endpoint 救一半）
- 第二次重跑同 case，adapter 调用数减少（缓存命中），429 数下降

---

## 6. 任务 5（H5）：Balanced 40 跑通

### 6.1 前置条件
H1-H4 全部落地 + 离线测试全绿 + Smoke 5 重跑仍 ≥4/5 pass+weak（不退化）。

### 6.2 命令
```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe apps/api/scripts/run_re04_smoke.py \
  --jsonl apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl \
  --ids apps/api/tests/fixtures/re04_balanced_40_ids.txt \
  --max 40 \
  --out-dir tmp_re04_eval/balanced40
```

### 6.3 SOP §6.3 合格线
- `pass+weak_rate ≥ 0.80`
- 每个 fail case 必须附 `degradation_chain` 失败链路（Re04-fix 已落地）
- 强噪声入 core/baseline/parallel ≤ 1 case
- `machine learning` fallback 出现 = 0 case

### 6.4 预期
40 case × ~225s ≈ 150 min。H1-H4 修后预期 pass+weak ≥ 32/40。

---

## 7. 执行边界

### 7.1 范围内
- ✅ 任务 1-4 的代码改动（接线 + 白名单扩展 + 注册表 + CORE adapter + OpenAlex 备用 + 缓存）
- ✅ 任务 5 balanced 40 跑通
- ✅ 每任务独立 commit，可回滚
- ✅ 新增测试覆盖：HF 接线 / whitelist 传递 / canonical query 生成 / CORE adapter mock / 缓存命中

### 7.2 范围外（禁止）
- ❌ 不做 verify / novelty / 知识图（Re06+）
- ❌ 不做 Forward Tracking / Semantic 语义检索（Re06+）
- ❌ 不改 ER / synthesize 的 prompt 文本（只加 `is_dataset_candidate` 字段暴露）
- ❌ 不引入 `*_score`
- ❌ canonical 注册表条目直接进 pool（违反"只喂 query"决议）
- ❌ 在 prompt 里写 `if is_dataset_candidate: force dataset` 硬规则
- ❌ 跑 100 全量

### 7.3 禁止偷懒清单

| 禁止 | 为什么 |
|---|---|
| canonical 注册表条目直接塞 pool | 违反用户"只喂 query"决议 + S66v |
| collect_mentioned_datasets 传全量白名单不按 domain 过滤 | 引入跨域噪声 dataset |
| HF adapter 接线后不做字段归一化 | collect_papers_from_raw 不识别 → 等于没接 |
| CORE adapter 无 key 时硬抛 | 返空即可，adapter 不应崩主链路 |
| 缓存 429 空结果 | 重跑永远空 |
| OpenAlex 备用 endpoint 改成无限重试 | 会拖垮 elapsed；重试 1 次封顶 |
| balanced 40 跑前不重验 Smoke 5 | 可能 H1-H4 引入退化却没发现 |
| `is_dataset_candidate` 在 prompt 里加硬规则 | 违反 S66v 不泄题 |
| 白名单加冷门/自造数据集名 | 凭空塞 pool 的 S66v 风险 |
| 任务 2 注册表只写点云不写 RS | 027 是 weak case，必须覆盖 |

---

## 8. 验收方案

### 8.1 离线测试（必须全绿）
```bash
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_re04_eval_dataset_loader.py \
  apps/api/tests/test_re04_resource_deduper.py \
  apps/api/tests/test_re04_resource_eval_offline.py \
  apps/api/tests/test_re04_main_entry.py \
  apps/api/tests/test_re04_work_package_binding.py \
  apps/api/tests/test_re04_semantic_scholar_adapter.py -q
```
预期 93 passed（不退化）。

### 8.2 新增测试
| 测试 | 验收 |
|---|---|
| `test_collect_mentioned_datasets_uses_whitelist` | re04_entry 传 whitelist 后，pool 含 dataset 候选 |
| `test_huggingface_adapter_wired_to_dataset_family` | FAMILY_TO_ADAPTER["dataset"] 含 "huggingface" |
| `test_canonical_baselines_feed_query` | point_cloud_completion domain → baseline query 含 "PCN" 等 |
| `test_canonical_baselines_not_in_pool` | 注册表条目不直接进 pool（S66v 断言） |
| `test_core_adapter_mock` | CORE adapter mock 返字段归一化 |
| `test_adapter_cache_hit` | 同 query 二次调走缓存 |

### 8.3 Online Smoke 5 重跑（不退化）
```bash
... --out-dir tmp_re04_eval/smoke5_re05
```
预期 ≥ 3p+2w（H1-H4 修后应升：018/027 升 pass 或维持 weak 但 dataset≥1）。

### 8.4 Balanced 40
SOP §6.3：`pass+weak_rate ≥ 0.80` + fail case 附 degradation_chain + 强噪声 ≤1 + `machine learning` fallback = 0。

### 8.5 degradation_chain 验收
balanced 40 每个 fail case 的 raw dump 必须含非空 `degradation_chain`（Re04-fix 已落地，本 SOP 不动此机制，只验证仍在）。

---

## 9. 参考资料引用（已核实存在）

### 9.1 AutoResearchClaw
- `agents/benchmark_agent/surveyor.py:48-63` — 本地 benchmark_knowledge.yaml + HF Hub 双路 dataset 发现
- `data/benchmark_knowledge.yaml` — domain→标准数据集/baseline 注册表范式（任务 1/2 借鉴结构）
- `agents/code_searcher/query_gen.py:16-38` — LLM 生成 GitHub 查询的 prompt 范式（任务 2 注册表 query 生成的参考）
- `literature/cache.py` — 持久缓存范式（任务 4 借鉴）
- `literature/search.py:143-161` — cache_get/cache_put 双回调
- `literature/semantic_scholar.py:46-48` — 三态 circuit breaker（PaperAgent 已有，不重造）

### 9.2 academic-research-skills
- `agents/literature_strategist_agent.md` §Search Strategy Design — 2-4 核心概念 + 同义词 + 布尔组合（任务 2 canonical 名录 = 同义词扩展）
- `agents/literature_strategist_agent.md` 第 516-530 行 — 中英分检（本 SOP 不改中英逻辑，Re04-fix 已处理）

---

## 10. 提交规范

5 个任务 → 5 个独立 commit，前缀 `re05(n/5):`：
1. `re05(1/5): wire huggingface adapter + pass whitelist to collect_mentioned_datasets`
2. `re05(2/5): canonical baselines registry feeds baseline queries only`
3. `re05(3/5): expose is_dataset_candidate field for ER (no prompt rule)`
4. `re05(4/5): CORE adapter + openalex backup endpoint + persistent cache`
5. `re05(5/5): balanced 40 run + report`

---

## 11. 下一阶段（Re06+，本 SOP 不做）

- Re06：候选核验（borrow `literature/verify.py` 三层 arXiv ID→DOI→title）+ Forward Tracking（被引追踪）
- Re07：新颖性检查（borrow `literature/novelty.py`）+ 知识图（borrow `knowledge/graph/`）
- Re08：Semantic 语义检索（需 embedding 模型）
- 不在可见范围：difficulty/cycle/repeatability 真值评估（需 labels 对齐）、HumanGate、面试项目化

---

> 本 SOP 不引入 `*_score`、不绕过检索造假、不改 prompt 文本。
> canonical 注册表只喂 query 不喂 pool（用户决议）。
> dataset 白名单走 collect_mentioned_datasets 的"扫已检索文本"机制（S66v 合规，非凭空塞 pool）。
> 检索正式收尾于 balanced 40 达标。
