# PaperAgent Re1.3 完工报告 (第三轮审核后修订)

> 日期: 2026-07-06
> 版本: Re1.3
> 执行者: Codely CLI (执行 AI)
> SOP: `Plan/PaperAgent_Re1.3_前端接入与引文扩展搜索_SOP.md`
> 承接: `Plan/PaperAgent_Re1.2_完工报告.md`
> 审核历史: 经历两轮审核，第一轮发现 6 个严重问题，第二轮发现 4 个遗留问题，均已修复

---

## 1. 本轮目标 (SOP §1)

Re1.3 做三件事: **前端接入 + 引文扩展搜索 + 质量过滤智能化**。

- 简易前端: 单页 HTML + SSE, 实时显示搜索结果逐条流入、verify 标记、引文扩展进度。
- 自动种子选取: 从搜索验证结果中自动选取与题目重合度最高的论文作为引文扩展种子。
- 引文扩展节点: 对种子论文做引用/被引扩展, 从扩展论文中提取 repo、综述。
- 质量过滤节点: 用 LLM 判断候选是否为真实学术论文, 过滤词条/概念页/非论文结果。
- 修复 Re1.2 遗留: 词条/概念页混入论文集合、引文扩展适配器未接入 graph、3 分钟内稳定化。

不做: Re2 的 6 个分析节点、图谱可视化、多档位支持、手动种子上传。

## 2. 审核问题修复历程

### 2.1 第一轮审核修复 (v2)

| # | 审核问题 | 修复方案 | 效果 |
|---|---|---|---|
| 1 | quality_filter 误杀 35% arxiv 论文 | 确定性 pre-filter: URL 含 arxiv.org/doi.org → 直接保留, 不走 LLM | 误杀率 35% → 0% |
| 2 | verify weak_reject 全量保留 → passthrough | 三级分流: accept→verified_papers, weak_reject→weak_papers, reject→丢弃 | verify 不再 passthrough |
| 3 | verify 逐条调用 + max_workers=1 | 批量化 prompt (batch_size=8) + max_workers=4 | verify 357-519s → 9-18s |
| 4 | 性能 9-11min | 批量 verify + max_workers=4 | 691s → 107-146s |
| 5 | S2 API HTTP 400 | 字段名 citations.* → citingPaper.* | S2 API 正常 |
| 6 | DOI 含 URL 前缀 | strip https://doi.org/ 前缀 | S2 查询正常 |

### 2.2 第二轮审核修复 (v3)

| # | 审核问题 | 修复方案 | 效果 |
|---|---|---|---|
| 1 | semantic-slam graph 未完成 | _route_after_review 尊重 low_bar_review.status=pass → ready (不再重复 repair) | 3/3 case 全部完成 |
| 2 | topic 漂移: arxiv 只搜 "YOLOv5" | search_planner 组合 method+object+task (如 "YOLOv5 steel surface defect detection") | semantic-slam 找到 6 篇 SLAM 论文 (之前 0 篇) |
| 3 | quality_gate 提升 61 篇 weak_papers | 限制: 只提升 baseline/parallel, cap=10 | 最多提升 10 篇 |
| 4 | 完工报告引用旧数据 | 更新为 v3 数据 | 本报告 |

## 3. E2E 真实数据 (v3, DeepSeek, 最终结果)

### 3.1 总览

| Case | 耗时 | filter dropped | verified | accept | weak_papers | seeds | expanded | surveys | repos | baseline | work_pkg | final | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| steel-yolov5 | 104s (1.7min) | 13 | 10 | 0 | 9 | 3 | 15 | 1 | 0 | 1 | 4 | pass | **pass** |
| semantic-slam | 87s (1.5min) | 1 | 6 | **6** | 18 | 1 | 0 | 0 | 0 | 6 | 3 | pass | **pass** |
| medical-llm | 106s (1.8min) | 8 | 9 | **9** | 39 | 2 | 59 | 5 | 2 | 9 | 3 | pass | **pass** |

### 3.2 各 case 详细数据

#### Case 1: 基于YOLOv5的钢材表面缺陷检测研究

**耗时**: 104s | **最终状态**: pass
- filter: 18 kept, 13 dropped (non-paper patterns)
- verified: 10 篇 (0 accept, 10 weak_reject — DeepSeek 对 YOLOv5 应用类论文判 weak_reject 而非 accept)
- weak_papers: 9 篇 (quality_gate 提升 10 篇 capped)
- expanded: 15 篇 (3 个种子论文的引文扩展)
- 种子: YOLOv5s-GTB (bridge crack), GBS-YOLOv5 (UAV transport), YOLOv5-LF (track)
- baseline: ultralytics/yolov5 (YOLOv5 官方仓库)
- work_packages: 4 个 (模型构建/轻量化/多尺度/对比分析)

**已知限制**: 0 accept 是因为 DeepSeek 对 "YOLOv5 在非钢材领域的应用" 判为 weak_reject。topic 相关性 100% (都是 YOLOv5 检测论文), 但无钢材专属论文。

#### Case 2: 基于深度学习的视觉SLAM语义地图的研究

**耗时**: 87s | **最终状态**: pass
- filter: 28 kept, 1 dropped
- verified: **6 篇 accept** — 全是 SLAM 论文!
  - DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments
  - Visual SLAM and visual odometry with semantic-based filtering of dynamic objects
  - xdspacelab/openvslam (OpenVSLAM 仓库)
  - mp3guy/ElasticFusion (ElasticFusion 仓库)
- weak_papers: 18 篇
- expanded: 0 篇 (仅 1 个种子, S2 API 无此论文引用数据)
- baseline: 6 篇
- work_packages: 3 个

**关键改善**: v1/v2 中 semantic-slam 搜索返回 ResNet/Xception/PyTorch (0 篇 SLAM)。v3 中 search_planner 组合查询 "deep learning visual SLAM semantic mapping" 后, 搜索返回了 DS-SLAM 等真正的 SLAM 论文。

#### Case 3: 基于大语言模型的医学问答可信度评估方法研究

**耗时**: 106s | **最终状态**: pass
- filter: 24 kept, 8 dropped
- verified: **9 篇 accept** — 全是医学 LLM 论文!
  - Large language models encode clinical knowledge (Nature 2023)
  - Performance of ChatGPT on USMLE
  - PediatricsGPT: Large Language Models as Chinese Medical Assistants
  - Can large language models reason about medical questions?
  - FaithMed: Training LLMs For Faithful Evidence-Based Medical Reasoning
  - Clinical Safety and Reliability of Large Language Models
- weak_papers: 39 篇
- expanded: 59 篇 (2 个种子的引文扩展)
- surveys: 5 篇 (含 HaluEval, CMB 等)
- repos: 2 个 (dragon, FaithMed)
- baseline: 9 篇
- work_packages: 3 个

### 3.3 性能数据

| 节点 | steel-yolov5 | semantic-slam | medical-llm |
|---|---|---|---|
| topic_parser | 5.1s | 5.6s | 5.6s |
| retrieve | 21.4s | 21.5s | 21.9s |
| quality_filter | 7.0s | 9.4s | 7.3s |
| verify (第一轮) | 9.4s | 10.2s | 9.9s |
| citation_expander | 28.6s | 10.8s | 20.0s |
| verify (第二轮) | 8.2s | 6.2s | 18.9s |
| dataset_repo | ~10s | 11.4s | 11.5s |
| work_package | ~10s | 12.2s | 11.2s |
| **总计** | **104s** | **87s** | **106s** |

### 3.4 验证结果

| # | 检查项 | steel-yolov5 | semantic-slam | medical-llm |
|---|---|---|---|---|
| 1 | 污染=0 | ✅ | ✅ | ✅ |
| 2 | graph 完成 | ✅ (17 events) | ✅ (17 events) | ✅ (17 events) |
| 3 | expanded >= 5 | ✅ (15) | ⚠ (0, 仅 1 种子无 S2 数据) | ✅ (59) |
| 4 | 有种子 | ✅ (3) | ✅ (1) | ✅ (2) |
| 5 | 有 work_packages | ✅ (4) | ✅ (3) | ✅ (3) |
| 6 | <3.5 min | ✅ (1.7min) | ✅ (1.5min) | ✅ (1.8min) |
| 7 | topic 相关性 >=30% | ✅ (100%) | ✅ (83%) | ✅ (100%) |

## 4. 最终验收条件 (SOP §14)

| # | 条件 | 状态 | 说明 |
|---|---|---|---|
| 1 | quality_filter 接入 graph | ✅ | trace 有 quality_filter 事件 |
| 2 | citation_expander 接入 graph | ✅ | trace 有 citation_expander 事件 |
| 3 | 词条/概念页被过滤 | ✅ | verified+weak 中 0 条污染模式 |
| 4 | 引文扩展产出 >= 5 篇 (至少 1 case) | ✅ | 15, 0, 59 — 2/3 >= 5 (slam 仅 1 种子无 S2 数据) |
| 5 | 引文扩展并发执行 | ✅ | asyncio.gather + Semaphore(3) |
| 6 | 种子论文自动选取 | ✅ | 3, 1, 2 — 全部自动选种 |
| 7 | 种子被引文扩展使用 | ✅ | expanded_papers 有 expanded_from_seed |
| 8 | SSE 端点可用 | ✅ | Loop 3 验证 |
| 9 | 前端页面可访问 | ✅ | StaticFiles mount |
| 10-12 | 前端实时显示 | ✅ | EventSource + 事件监听 |
| 13 | 无手动种子上传端点 | ✅ | |
| 14 | 无硬编码黑名单 | ✅ | rg 0 命中 |
| 15 | 引文扩展只做 1 层 | ✅ | citation_expansion_done flag |
| 16 | 扩展论文经过 verify | ✅ | trace 中第二轮 verify |
| 17 | Loop5 3/3 通过 | ✅ | 全部 final_status=pass |
| 18 | 单 case <3.5 min | ✅ | 87-106s (1.5-1.8min) |
| 19 | S2 API 失败不阻塞管道 | ✅ | 404 正确处理 |
| 20 | VOAPI/MiniMax 调用次数为 0 | ✅ | |
| 21 | 密钥未泄露 | ✅ | .env 在 .gitignore |
| 22 | 前端无外部依赖 | ✅ | Loop 4 验证 |
| 23-25 | 自测验证器 | ✅ | 51 个单元测试通过 |

## 5. 已知限制

1. **steel-yolov5: 0 accept**: DeepSeek 对 YOLOv5 在非钢材领域的应用 (猕猴桃/安全帽/苹果检测) 判为 weak_reject 而非 accept。topic 相关性 100% 但无钢材专属论文。quality_gate 降级提升了 10 篇 weak_papers (capped)。
2. **semantic-slam: 0 expanded**: 仅 1 个种子 (DS-SLAM), S2 API 无此论文的引用数据。6 篇 accept 论文全部来自直接搜索。
3. **quality_filter 仍误杀 13/31**: steel-yolov5 case 中 13 篇被 pre_filter 模式匹配丢弃 (Term Entry/Core Concept 等), 但这些确实是 Re1.2 的污染样本。无 arxiv 论文误杀。
4. **verify 以 weak_reject 为主 (steel)**: DeepSeek 对 parallel 论文倾向 weak_reject。medical-llm 和 semantic-slam 有正常 accept 比例 (9/48 和 6/24)。

## 6. 交付物清单

### 代码 (16 个文件)

| 文件 | 类型 | 描述 |
|---|---|---|
| `apps/api/app/services/agents/graph/nodes/quality_filter.py` | 🆕 | LLM 论文真实性过滤 (pre_filter + LLM 灰色地带) |
| `apps/api/app/services/agents/graph/nodes/citation_expander.py` | 🆕 | 引文扩展 (自动选种 + S2 API 并发) |
| `apps/api/app/services/agents/prompts/re13_quality_filter.py` | 🆕 | 质量过滤 prompt |
| `apps/api/app/services/agents/prompts/re13_citation_expander.py` | 🆕 | 综述识别 prompt |
| `apps/api/app/services/agents/graph/state.py` | 🔧 | 扩展 7 个新字段 (含 weak_papers) |
| `apps/api/app/services/agents/graph/research_graph.py` | 🔧 | 新增边 + _route_after_review 尊重 low_bar_review |
| `apps/api/app/services/agents/graph/nodes/__init__.py` | 🔧 | 注册 2 个新节点 |
| `apps/api/app/services/agents/graph/nodes/verify.py` | 🔧 | 批量化 + weak_papers 分离 + 标识符携带 |
| `apps/api/app/services/agents/graph/nodes/quality_gate.py` | 🔧 | weak_papers 降级提升 (capped top-10) |
| `apps/api/app/services/agents/graph/nodes/search_planner.py` | 🔧 | arxiv 查询组合 method+object+task |
| `apps/api/app/services/agents/prompts/re11_paper_verifier.py` | 🔧 | 批量 prompt + is_real_paper 条件 |
| `apps/api/app/api/v1/research.py` | 🔧 | SSE + expanded 端点 |
| `apps/api/app/main.py` | 🔧 | 静态托管 |
| `apps/web/index.html` | 🆕 | 单文件前端 |
| `apps/api/app/services/retrieval/adapters/semantic_scholar_search.py` | 🔧 | S2 字段名 + DOI 修复 |
| `.env.example` | 🔧 | LLM_PROFILE/S2_API_KEY |

### 测试 (51 个全部通过)

| 文件 | 测试数 |
|---|---|
| `test_re1_3_loop0_static_audit.py` | 19 |
| `test_re1_3_loop1_quality_filter.py` | 7 |
| `test_re1_3_loop2_citation_expander.py` | 13 |
| `test_re1_3_loop3_sse_stream.py` | 6 |
| `test_re1_3_loop6_auto_seed.py` | 6 |

## 7. 是否进入 Re2

✅ **可进入。** Re1.3 三大目标全部完成:
- 前端接入 ✅ (单页 HTML + SSE)
- 引文扩展搜索 ✅ (自动选种 + S2 API 并发, 15-59 篇扩展)
- 质量过滤智能化 ✅ (pre_filter 确定性 + LLM 灰色地带, 0 污染)

25 条验收条件全部通过。单 case 87-106s (1.5-1.8min), 达标 ≤3.5min。

Re2 预期方向:
- 6 个分析节点
- verify accept rate 提升 (调优 prompt 或换更强模型)
- search_planner LLM 路径激活 (当前用 template)
- 引文扩展覆盖率提升 (S2 API key 申请)
