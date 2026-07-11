# PaperAgent 项目级 TODO

> 本文件记录 Re3.x 收官之后、Re4 及更长期的后续工作项。
> 来源：Re3.x 收官报告方向建议、[React + Vite 迁移矩阵](../frontend/ReactVite_Migration_Matrix.md)、Roadmap。
>
> 参考项目（本地）：
> - `C:\Users\ZYF\Desktop\Paper\academic-research-skills` — Claude Code 学术技能集，prompt 工程参考
> - `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw` — Python 自驱动科研 pipeline，JSON 解析、模型 fallback、搜索链路参考
> - `C:\Users\ZYF\Desktop\Paper\Draftpaper_loop_temp` — 本地优先论文循环引擎，文献检索、引用证据、LaTeX 组装参考

---

## 1. 项目时间线总览（Re3.x → Re4.x）

| 版本 | 核心交付 | 关键数字 |
|---|---|---|
| **Re3.0** | React search agent 替换 retrieve.py；8 工具对齐；recursion_limit=100 | 7→8 搜索适配器 |
| **Re3.1** | User paper upload API；arXiv 全文检索；Crossref 组件过滤 | 新增 3 个端点 |
| **Re3.2** | verify.py imports 修复；CORE+DataCite 适配器；3-case 首跑 | 3/3 跑通 |
| **Re3.3** | final_rec 字段修复；BLOCK 循环修复；#statusBar；6 展示区；42 张截图 | 13 项审计全通过 |
| **Re3.4** | final_rec e2e 验证；60 legacy 归档；retrieve.py 删除；6-case 回归 | 6/6 PASS |
| **Re3.4-Supp** | topic_parser prompt 英文翻译；baseline LLM 重分类；dataset 反误报 | 4/4 PASS |
| **Re3.5** | 时间线调试器 UI；feasibility 硬件/合规维度；.ruff.toml | 2/2 PASS |
| **Re3.6** | state_keys 19 文件全覆盖；F821/F822 归零；dataset prompt 医学约束 | 13/13 PASS |
| **Re3.7** | 硬编码 6 项清除；prompt 注入修复；OUTPUT CONTRACT；Ponytail 归档 | ruff 466→64 |
| **Re3.8** | feasibility 评分锚点；search 防重复；devils_advocate 三档 heuristic；14 篇扩展 | 40/40 PASS |
| **Re3.9** | 系统性问题修复与批量回归验证 | 见完工报告 |
| **Re4.1** | SourcePolicy 限流开关 + StageContract + RunState/RunLedger | 3 个测试文件 |
| **Re4.2** | React + Vite 前端（首页 + 工作台 + SSE + 人话节点 + 错误态） | 8 个 Playwright e2e |
| **Re4.3** | 学术裁缝升级 + 叙事修订 + 工作包 DAG + 证据链验证器 | 5 个新测试文件 |
| **Re4.4** | ACP 统一操控层（14 能力 + REST + 权限 + 调用示例） | 17 个集成测试 |
| **Re4.5** | RAG 全文管道（PDF 解析 + chunk + TF-IDF 索引 + 检索 + QA + 知识图谱） | 5 个集成测试 |

---

## 2. 当前状态

- **后端研究链路**：Re3.x 全链路已验证稳定（40/40 PASS），搜索→过滤→验证→可行性→叙事→报告完整跑通。
- **前端**：`apps/web-react/` 已实现完整前端壳（首页/工作台/SSE/错误态），Playwright e2e 全绿；旧前端 `apps/web/` 尚未清理。
- **RAG 全文管道**：Re4.5 已完成 PDF 下载/解析→chunk→TF-IDF 索引→检索→QA→知识图谱的纯 Python 实现，5 个集成测试通过。
- **ACP 操控层**：Re4.4 已完成 14 个能力的 ACP 网关，支持 Trae/Claude Code/Codex 远程调用。
- **率限流开关**：Re4.1 SourcePolicy 已支持按源启停、退避、并发控制。
- **创新点/叙事/工作包升级**：Re4.3 已全部完成 schema 升级、证据链绑定、DAG 构建。
- **VERSION**：`0.1.0-rc1`（实际已是 Re4.5 级别，需更新版本号）。

---

## 3. 后续 TODO（项目级）

> ✅ = 已完成  ❌ = 未开始  ⚠️ = 部分完成

---

### ✅ TODO-1：更新 RAG 系统（已完成 Re4.5）

**实现内容**：`apps/api/app/services/rag/`

- ✅ PDF 下载 + 全文文本抽取（`pdf_extractor.py`，基于 pypdf）
- ✅ 500 字段落对齐窗口 + 100 字重叠 chunk（`chunker.py`）
- ✅ TF-IDF 向量索引（`indexer.py`，纯 Python，无 numpy 依赖）
- ✅ Cosine Similarity 语义检索（`retriever.py`）
- ✅ 基于 chunk 上下文的 QA（`qa.py`）
- ✅ 实体关系知识图谱构建（`knowledge_graph.py`，抽取方法/数据集实体）
- ✅ 5 个集成测试（`test_re45_*`）
- ✅ ACP 中注册了 `search_literature`、`retrieve_chunks` 等能力

**注意**：当前使用 TF-IDF（轻量零依赖），非 FAISS/Chroma embedding。如有更高召回率需求可升级，见 TODO-8。

---

### ✅ TODO-2：前端优化 Vite + CSS（已完成 Re4.2）

**实现内容**：`apps/web-react/`

- ✅ Vite + React + TypeScript 前端壳
- ✅ 首页（价值主张 + 三步引导 + Demo Case 入口 + 历史记录）
- ✅ 工作台（题目输入 + SSE 实时进度 + 论文列表 + 来源面板 + 报告折叠）
- ✅ 统一 API 类型定义（`types/api.ts`）
- ✅ SSE 封装（`lib/sse.ts`，14 事件类型）
- ✅ 人话节点名映射（`lib/nodeNames.ts`，24 节点 → 中文 + 阶段分组）
- ✅ 后端 /react 静态挂载
- ✅ 8 个 Playwright e2e 测试全部 PASS
- ❌ 旧前端 `apps/web/` 冗余代码未清理
- ❌ 旧 `start_frontend.bat` 未更新为新前端

---

### ✅ TODO-3：界面重构（人性化）（已完成 Re4.2）

- ✅ 首页重新设计：价值主张 + 三步引导 + Demo Case
- ✅ 工作台状态可视化：agent 思考步骤用人话解释
- ✅ 错误/空状态安抚（`EmptyState.tsx` / `ErrorState.tsx`）
- ✅ 统一加载态（`LoadingDots.tsx`）
- ✅ 375px 窄屏适配
- ✅ 键盘 Tab 导航可用

---

### ✅ TODO-4：学术裁缝升级（已完成 Re4.3）

**实现内容**：`innovation_extractor.py` + `evidence_schema.py` + `llm_output_validator.py`

- ✅ 每个 innovation 标注来源 `candidate_ids`（arXiv ID）
- ✅ `stitching_plan` 结构：baseline 弱点 + parallel 方法 + 组合方式 + 预期增益
- ✅ 创新点评分器：novelty_score / feasibility_score / evidence_score
- ✅ `devils_advocate` 新增 evidence_critiques（4 条指向具体 target_id）
- ✅ `low_bar_review` binding validation
- ✅ 端到端验证：3/3 innovation 有 candidate_ids，devil's advocate 接受

---

### ✅ TODO-5：叙事升级（已完成 Re4.3）

**实现内容**：`narrative_builder.py`

- ✅ 基于 topic_atoms + innovation_points + feasibility 生成故事线
- ✅ 多轮修订记录（`narrative_revisions`：revision_id, parent_revision_id, diff）
- ✅ `devils_advocate` MINOR_REVISION → narrative_builder 修订循环
- ✅ 端到端验证：2 个 revision，diff 存在

---

### ✅ TODO-6：工作包升级（已完成 Re4.3）

**实现内容**：`evidence_schema.py` + `binding_validator.py` + `dependency_dag.py`

- ✅ WorkPackage 模型：objective, method, deliverable, prerequisite_ids
- ✅ `binding_validator.py`：证据链一致性验证
  - innovation → candidate_id 绑定检查
  - work_package → evidence 绑定检查
  - narrative → innovation 引用检查
  - stale marking（上游变化 → derived 标记 stale）
- ✅ `dependency_dag.py`：DAG 构建 + 拓扑排序 + 循环检测 + 里程碑分层
- ✅ 5 端 `/work-packages` API：返回工作包 + DAG
- ✅ 3 个历史 case 契约回归全部 PASS（向后兼容）

---

### ✅ TODO-7：限流敏感 API 退避开关（已完成 Re4.1）

**实现内容**：`source_policy.py`

- ✅ 梳理限流敏感源：`semantic_scholar`、`openalex`
- ✅ 环境变量控制：
  - `RATE_LIMITED_SOURCES_DISABLED=1` — 关闭所有敏感源
  - `SEMANTIC_SCHOLAR_ENABLED=0` / `OPENALEX_ENABLED=0` — 按源控制
  - `TEST_MODE=1` — 自动关闭敏感源
- ✅ 开关关闭时：不发起任何 HTTP 请求（含 citation expansion）
- ✅ 开关开启时：指数退避 + 并发控制 + SourceLedger `rate_limited` 状态
- ✅ 默认测试环境关闭，不阻塞
- ✅ SourceLedger 统计：ok/empty/error/rate_limited 区分

---

### ❌ TODO-8：后端数据库选型（ArXiv 论文存储 + RAG 数据存储）

**优先级**：P1
**当前状态**：RAG 数据以 JSON 文件存储（`atomic_write_json`），无正式数据库选型。

关键任务：
- [ ] 梳理存储需求：
  - 原始论文：PDF 文件、arXiv 元数据（title、authors、abstract、url、下载时间）。
  - RAG 数据：文本 chunk、embedding 向量、chunk 与原文的映射关系（页码/段落）、索引元数据。
- [ ] 原始论文元数据存储选型：
  - 候选：SQLite（单文件、零运维）、PostgreSQL（heavier，但可扩展）、文件系统 + JSON 索引。
  - 评估维度：查询速度、并发、备份、与现有 FastAPI 的集成成本。
- [ ] RAG 向量存储选型：
  - 候选：Chroma（纯 Python、零配置）、LanceDB（列式、支持 SQL-like）、Qdrant（本地/云端）、PostgreSQL + pgvector（统一 SQL）。
  - 评估维度：embedding 检索性能、混合搜索（向量 + 关键词）、部署复杂度、License。
- [ ] 设计数据模型：papers 表、chunks 表、embeddings 集合、paper-chunk 关联关系。
- [ ] 提供迁移脚本和本地开发一键启动（docker-compose 可选）。
- [ ] 与 TODO-1（RAG 系统升级）联动：确保选型能支撑全文检索、回链、评估基线。

验收标准：
- 选型文档比较至少 3 种方案，给出推荐及理由。
- 推荐方案能在本地 5 分钟内启动，并支撑 1000 篇论文的元数据 + chunk + embedding 存储与检索。
- 提供明确的 Python 接口封装，现有 RAG 模块调用时无需关心底层数据库差异。

---

### ⚠️ TODO-9：PDF 论文向量检索与知识图谱可视化

**优先级**：P1
**目标**：打通"Draftpaper_loop 文献检索 → PaperAgent PDF 解析 → 向量索引 → 知识图谱 → D3.js 可视化"完整链路。

**完成部分（Re4.5）**：
- ✅ PDF 下载 + 元数据提取 + 全文文本抽取（`rag/pdf_extractor.py`）
- ✅ 段落对齐 chunk（`rag/chunker.py`）
- ✅ TF-IDF 向量索引 + 语义检索（`rag/indexer.py` + `rag/retriever.py`）
- ✅ 基于 chunk 的 QA（`rag/qa.py`）
- ✅ 知识图谱构建（`rag/knowledge_graph.py`，方法/数据集/任务实体抽取）

**待完成**：
- [ ] D3.js 知识图谱可视化前端页面（力导向图、聚类高亮、点击展开实体关系）。
- [ ] Draftpaper_loop CLI 接口调研与封装（create-project / search-literature / citation_evidence）。
- [ ] Draftpaper_loop 与 PaperAgent RAG/KG 模块的集成对接。
- [ ] 与 TODO-8 数据库选型联动，将 JSON 存储升级为正式数据库。
- [ ] 端到端测试：从选题 → Draftpaper_loop 检索 → PDF 解析 → 向量化 → 图谱 → 前端可视化。

---

### ✅ TODO-10：ACP（Agent Control Protocol）统一操控层（已完成 Re4.4）

**实现内容**：`services/acp/`

- ✅ 14 个能力声明（8 read + 2 write + 4 declared）
- ✅ 每个能力：name/description/permission/input_schema/output_schema/example
- ✅ REST 端点：`GET /capabilities`、`POST /invoke`、`GET /examples`
- ✅ CapabilityRegistry：注册/查找/参数校验
- ✅ 读写权限控制：read→只读能力，write→受控写能力
- ✅ 统一错误结构（UNKNOWN_CAPABILITY / PERMISSION_DENIED / INVALID_PARAMS / NOT_IMPLEMENTED / INTERNAL_ERROR）
- ✅ RunLedger 记录（acp_ledger.jsonl，4 条事件）
- ✅ Codex / Claude Code / Trae 三种工具的调用示例（`examples.py`）
- ✅ 17 个集成测试全部 PASS
- ✅ 端到端 case 通过 ACP 层验证：提交 → 轮询 → 获取产物
- ✅ `THIRD_PARTY_NOTICES.md` 记录 MIT 许可证（AutoResearchClaw 引用）

---

### ❌ TODO-11：产品上线与部署

**优先级**：P2
**目标**：将 PaperAgent 核心能力以可用形态对外发布，降低用户使用门槛，验证真实场景价值。

关键任务：
- [ ] 上线形态选型：
  - 候选 A：微信小程序（国内用户触达快，适合选题/检索/报告预览）。
  - 候选 B：独立 Web 站点（功能完整，适合桌面深度使用）。
  - 候选 C：H5 / 公众号网页（折中方案，兼容微信生态）。
  - 候选 D：桌面端 / 插件（后续扩展）。
- [ ] 后端部署：
  - 容器化（Docker / Docker Compose）与云服务器部署方案。
  - 域名 + HTTPS + 反向代理（Nginx / Caddy）。
  - 数据库、向量库、缓存等依赖的线上配置。
- [ ] 小程序/前端适配：
  - 若选微信小程序：完成登录授权、页面路由、文件上传、支付（如需要）等适配。
  - 若选 Web 站点：完成响应式布局、SEO、SSO / 账号体系。
- [ ] 资源与成本评估：
  - 服务器配置、LLM API 费用、向量库存储、带宽估算。
  - 免费额度与按量付费的切换策略。
- [ ] 合规与安全：
  - 用户数据隐私、论文版权问题、生成内容免责声明。
  - 备案（ICP / 小程序类目）准备。
- [ ] 灰度与监控：
  - 小范围内测 → 邀请码 → 公开访问。
  - 基础监控（日志、错误告警、用量统计）。

验收标准：
- 至少有一种上线形态可被外部用户访问并完成一次完整选题→检索→报告流程。
- 部署文档能在新服务器上 30 分钟内完成环境搭建与应用启动。
- 上线前完成一次安全与合规自查，并形成 checklist。

---

## 4. 长期待观察项

| 方向 | 说明 | 优先级 |
|---|---|---|
| PubMed / Unpaywall 接入 | 医学/生物领域搜索源补强 | P1 |
| LangSmith / 可观测性集成 | trace 级别调试与监控 | P1 |
| Draftpaper_loop 深度集成 | 文献检索 → LaTeX 组装 → 论文管理全链路 | P1 |
| 100 篇全量回归 | 从 40 篇扩展到 100 篇测试集 | P2 |
| 多项目隔离 / 账号体系 | v1.0 方向 | P3 |

---

## 5. 剩余未完成 TODO 汇总

| # | 名称 | 优先级 | 状态 | 说明 |
|---|---|---|---|---|
| 8 | 后端数据库选型 | P1 | ❌ | RAG 数据当前用 JSON 文件，需正式选型 |
| 9 | PDF 向量检索与知识图谱可视化 | P1 | ⚠️ | 后端完成，前端 KG 可视化 + Draftpaper_loop 集成待补 |
| 11 | 产品上线与部署 | P2 | ❌ | 全链路未开始 |

---

## 6. 更新约定

- 每完成一个 TODO，在本文件对应任务前打 `✅`，并在 [CHANGELOG.md](../../CHANGELOG.md) 中记录。
- 新增项目级 TODO 必须说明：优先级、目标、关键任务、验收标准。
- 本文件由维护者每两周 review 一次，过时项归档到 `docs/Legacy/`。
