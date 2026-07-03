# PaperAgent Agent 架构图

## 整体架构

```mermaid
graph TB
    subgraph Entry["入口层"]
        API["main.py<br/>FastAPI"]
        RE04["re04_entry.py<br/>Re04主入口"]
    end

    subgraph Core["Agent核心"]
        RA["research_agent.py<br/>S66v LLM-first"]
        RO["retrieval_orchestrator.py<br/>5轮检索编排"]
    end

    subgraph Query["查询构建"]
        QM["query_matrix.py<br/>8个query families"]
        SEED["seed_relevance.py<br/>种子相关性过滤"]
    end

    subgraph Adapters["检索适配器"]
        ARX["arxiv"]
        OA["openalex"]
        CR["crossref"]
        GH["github"]
        HF["huggingface"]
        CORE["core.ac.uk"]
        SS["semantic_scholar"]
    end

    subgraph Candidates["候选池"]
        CP["candidate_pool.py<br/>去重候选池"]
        ER["evidence_review.py<br/>LLM批量审核"]
    end

    subgraph Expand["引用扩展"]
        CE["citation_expand.py<br/>OpenAlex引用链"]
    end

    subgraph Quality["质量控制"]
        LBR["low_bar_reviewer.py<br/>5项轻量检查"]
    end

    subgraph Infra["基础设施"]
        LLM["llm.py<br/>MiniMax M3"]
        SL["source_ledger.py<br/>来源账本"]
    end

    subgraph Output["输出"]
        B1["baseline_papers"]
        B2["parallel_papers"]
        B3["module_papers"]
        B4["reference_papers"]
        B5["dataset_candidates"]
        B6["repo_candidates"]
        B7["evidence_gaps"]
    end

    API --> RA
    RE04 --> RO

    RA --> QM
    RA --> CE
    RA --> ER
    RA --> LBR

    RO --> QM
    RO --> SEED
    RO --> CP

    QM --> RO
    SEED --> CE

    RO --> ARX
    RO --> OA
    RO --> CR
    RO --> GH
    RO --> HF
    RO --> CORE
    RO --> SS

    ARX --> CP
    OA --> CP
    CR --> CP
    GH --> CP
    HF --> CP
    CORE --> CP
    SS --> CP

    CP --> ER
    CP --> CE
    CE --> CP

    ER --> LBR
    LBR --> RA

    LLM -.-> RA
    LLM -.-> ER
    LLM -.-> LBR

    RO --> SL
    RA --> SL

    RA --> Output
```

## Pipeline 流程

```
用户输入题目
    ↓
┌─ Round 0: query_matrix (无网络/无LLM) ─────────────┐
│  → 8个query families (core/method_task/object_task/...) │
└──────────────────────────────────────────────────────┘
    ↓
┌─ Round 1-2: retrieval_orchestrator ─────────────────┐
│  → dispatch to 7 adapters (arxiv/openalex/crossref/...) │
│  → results → candidate_pool (dedup by stable_id)      │
│  → result_expander (LLM refinement)                   │
└──────────────────────────────────────────────────────┘
    ↓
┌─ Round 2.5: citation_expand ────────────────────────┐
│  → seed_relevance filter → OpenAlex referenced_works  │
│  → expanded refs → candidate_pool                     │
└──────────────────────────────────────────────────────┘
    ↓
┌─ Round 3: evidence_review (1 LLM batch call) ──────┐
│  → Every candidate → status (core/candidate/rejected) │
└──────────────────────────────────────────────────────┘
    ↓
┌─ Round 4: low_bar_reviewer (1 LLM call) ───────────┐
│  → pass / needs_revision / stop                       │
└──────────────────────────────────────────────────────┘
    ↓
输出 7 buckets + fabrication_alerts + source_ledger
```

## 数据流图 (Data Flow)

```mermaid
flowchart TD
    INPUT["用户输入: 基于患者虚拟定位的三维人体重建关键技术研究"]

    subgraph R0["Round 0: QueryMatrix (无网络/无LLM)"]
        PARSE["parse_topic()"]
        QM["query_matrix.build_query_matrix()"]
    end

    subgraph R1["Round 1: Family Dispatch"]
        ADAPTERS["7个适配器并行"]
        ARX["arxiv_search"]
        OA["openalex_search"]
        CR["crossref_search"]
        GH["github_search"]
        HF["huggingface_search"]
        CORE["core_search"]
        SS["semantic_scholar_search"]
    end

    subgraph R2["Round 2: Dynamic Expansion"]
        EXPAND["result_expander.expand_from_round1()"]
    end

    subgraph R25["Round 2.5: Citation Expand"]
        SEED["seed_relevance.filter_seeds()"]
        CITATION["citation_expand()"]
    end

    subgraph R3["Round 3: Evidence Review"]
        ER["evidence_review.audit_candidates()"]
    end

    subgraph R4["Round 4: Low Bar Review"]
        LBR["low_bar_reviewer.run_low_bar_review()"]
    end

    OUTPUT["输出: 7 buckets + synthesis"]

    INPUT --> PARSE
    PARSE --> QM
    QM --> ADAPTERS

    ADAPTERS --> ARX
    ADAPTERS --> OA
    ADAPTERS --> CR
    ADAPTERS --> GH
    ADAPTERS --> HF
    ADAPTERS --> CORE
    ADAPTERS --> SS

    ARX -->|"empty"| EXPAND
    OA -->|"empty"| EXPAND
    CR -->|"20 results"| EXPAND
    GH -->|"empty"| EXPAND
    HF -->|"empty"| EXPAND
    CORE -->|"empty"| EXPAND
    SS -->|"empty"| EXPAND

    EXPAND --> SEED
    SEED -->|"5 seeds, 0 eligible"| CITATION
    CITATION -->|"0 refs added"| ER

    ER -->|"18 candidates reviewed"| LBR
    LBR -->|"needs_revision"| OUTPUT

    style INPUT fill:#4CAF50,color:white
    style OUTPUT fill:#2196F3,color:white
    style R0 fill:#E8F5E9
    style R1 fill:#E3F2FD
    style R2 fill:#FFF3E0
    style R25 fill:#F3E5F5
    style R3 fill:#FFEBEE
    style R4 fill:#E0F2F1
```

## 真实案例: ENG-THESIS-015

### 输入

**题目**: 基于患者虚拟定位的三维人体重建关键技术研究

### Round 0: QueryMatrix (无网络/无LLM)

```mermaid
flowchart LR
    TOPIC["原始题目"] --> PARSE["parse_topic()"]

    PARSE --> METHOD["method_terms:<br/>3D human body reconstruction<br/>multi-view stereo<br/>NeRF<br/>SMPL/SMPL-X<br/>RGB-D fusion<br/>point cloud registration"]
    PARSE --> TASK["task_terms:<br/>patient virtual localization<br/>3D human shape reconstruction<br/>pose estimation<br/>avatar generation"]
    PARSE --> OBJECT["object_terms:<br/>patient<br/>human body mesh<br/>depth image<br/>RGB-D scan"]

    METHOD --> QM["query_matrix.build_query_matrix()"]
    TASK --> QM
    OBJECT --> QM

    QM --> FAMILIES["8个query families:<br/>core: 2 queries<br/>method_task: 4 queries<br/>object_task: 4 queries<br/>dataset: 2 queries<br/>repo: 3 queries<br/>survey: 2 queries<br/>benchmark: 1 query<br/>baseline: 2 queries"]
```

**产出**: 20个query分布在8个family

### Round 1: Family Dispatch (检索)

```mermaid
flowchart TD
    QUERIES["20个queries"]

    subgraph ADAPTERS["适配器分派"]
        ARX["arxiv<br/>4 queries"]
        OA["openalex<br/>6 queries"]
        CR["crossref<br/>6 queries"]
        GH["github<br/>3 queries"]
        OTHER["其他适配器"]
    end

    ARX -->|"结果: 0"| LEDGER1["SourceLedger"]
    OA -->|"结果: 0"| LEDGER1
    CR -->|"结果: 20"| LEDGER1
    GH -->|"结果: 0"| LEDGER1
    OTHER -->|"结果: 0"| LEDGER1

    LEDGER1 --> POOL["candidate_pool<br/>18个candidates"]

    style ARX fill:#ffcdd2
    style OA fill:#ffcdd2
    style CR fill:#c8e6c9
    style GH fill:#ffcdd2
```

**SourceLedger 记录**:
| adapter | query | status | result_count |
|---------|-------|--------|--------------|
| crossref | 3D human body reconstruction classic | ok | 8 |
| crossref | patient patient virtual localization | ok | 8 |
| crossref | 3D human body reconstruction patient | ok | 7 |
| arxiv | 所有queries | empty | 0 |
| openalex | 所有queries | empty | 0 |
| github | 所有queries | empty | 0 |

### Round 2.5: Citation Expand (种子过滤)

```mermaid
flowchart TD
    POOL["candidate_pool<br/>18个candidates"] --> SEED_CHECK["seed_relevance.filter_seeds()"]

    SEED_CHECK --> REJECT1["rejected: Non-rigid 3D reconstruction..."]
    SEED_CHECK --> REJECT2["rejected: 3D Human Body Model..."]
    SEED_CHECK --> REJECT3["rejected: Figure 1: 3D body scanner..."]
    SEED_CHECK --> REJECT4["rejected: 3D Human Body Reconstruction from Head-Mounted..."]
    SEED_CHECK --> REJECT5["rejected: A Survey of 3d Human Body Reconstruction..."]

    REJECT1 --> RESULT["seeds_total: 5<br/>seeds_eligible: 0<br/>refs_added: 0"]

    style REJECT1 fill:#ffcdd2
    style REJECT2 fill:#ffcdd2
    style REJECT3 fill:#ffcdd2
    style REJECT4 fill:#ffcdd2
    style REJECT5 fill:#ffcdd2
```

**种子过滤原因**: 所有候选论文都没有openalex_id或DOI作为引用扩展的种子

### Round 3: Evidence Review (LLM批量审核)

```mermaid
flowchart TD
    POOL["18个candidates"] --> LLM["LLM batch audit<br/>(1次调用)"]

    LLM --> CORE["core (1)"]
    LLM --> CANDIDATE["candidate (7)"]
    LLM --> NEEDS_MANUAL["needs_manual (1)"]
    LLM --> REJECTED["rejected (7)"]

    CORE --> |"c-a6120f4a"| SURVEY["A Survey of 3d Human Body Reconstruction<br/>confidence: high<br/>relation: survey"]

    CANDIDATE --> C1["c-9cdb1e1a: 3D Human Body Model...<br/>confidence: high"]
    CANDIDATE --> C2["c-f2fbe7c1: Towards Accurate 3D...<br/>confidence: high"]
    CANDIDATE --> C3["c-acd759b2: 3D Reconstruction...Kinect<br/>confidence: high"]
    CANDIDATE --> C4["c-e7af122e: A High Precision 3d...<br/>confidence: high"]
    CANDIDATE --> C5["c-7c030080: PeeledHuman...<br/>confidence: high"]
    CANDIDATE --> C6["c-b7e4392d: Non-rigid 3D...<br/>confidence: medium"]
    CANDIDATE --> C7["c-c48bc24e: 3D Human Body...<br/>confidence: medium"]

    NEEDS_MANUAL --> NM1["c-db16a094: Figure 1: 3D body scanner...<br/>reason: metadata_mismatch"]

    REJECTED --> R1["c-f86b584a: Neurologic Examination...<br/>reason: unrelated"]
    REJECTED --> R2["c-a0ee1cc7: Replicate Engineered...<br/>reason: unrelated"]
    REJECTED --> R3["c-54bfd053: Shifting from the...<br/>reason: unrelated"]
    REJECTED --> R4["c-ca23e8b5: Supplemental Information 5...<br/>reason: metadata_mismatch"]
    REJECTED --> R5["c-740cc3bf: Virtual Patient Encounter<br/>reason: unrelated"]
    REJECTED --> R6["c-8f49efef: Patient-to-Patient Communication...<br/>reason: unrelated"]
    REJECTED --> R7["c-2a9c7658: The Data-Driven Cyber Patient<br/>reason: unrelated"]

    style CORE fill:#4CAF50,color:white
    style CANDIDATE fill:#2196F3,color:white
    style NEEDS_MANUAL fill:#FF9800,color:white
    style REJECTED fill:#f44336,color:white
```

### Round 4: Low Bar Review (质量控制)

```mermaid
flowchart TD
    REVIEW["evidence_review结果"] --> LBR["low_bar_reviewer"]

    LBR --> VERDICT["verdict: needs_revision"]

    VERDICT --> Q1["blocking_questions:<br/>1. 'patient virtual localization'含义?<br/>2. 输出是SMPL mesh还是NeRF?<br/>3. 感知模态: multi-view RGB or RGB-D?<br/>4. 是否需要临床背景?<br/>5. 是否需要真实患者数据?"]

    VERDICT --> Q2["weak_points:<br/>1. 题目边界模糊<br/>2. baseline缺乏patient-specific工作<br/>3. evidence_gaps为空<br/>4. reference组薄弱<br/>5. work_suggestions缺少明确区分"]

    VERDICT --> STOP["can_continue_to_opening_report: false"]

    style VERDICT fill:#FF9800,color:white
    style STOP fill:#f44336,color:white
```

### 最终输出: 7 Buckets

```mermaid
flowchart TD
    subgraph BUCKETS["输出: 7 Buckets"]
        B1["baseline_papers<br/>(3篇)"]
        B2["parallel_papers<br/>(4篇)"]
        B3["module_papers<br/>(0篇)"]
        B4["reference_papers<br/>(2篇)"]
        B5["dataset_candidates<br/>(0篇)"]
        B6["repo_candidates<br/>(0篇)"]
        B7["evidence_gaps<br/>(5个问题)"]
    end

    B1 --> D1["c-acd759b2: 3D Reconstruction...Kinect (2022)"]
    B1 --> D2["c-e7af122e: A High Precision 3d... (2022)"]
    B1 --> D3["c-9cdb1e1a: 3D Human Body Model... (2024)"]

    B2 --> P1["c-7c030080: PeeledHuman... (2020)"]
    B2 --> P2["c-f2fbe7c1: Towards Accurate 3D... (2019)"]
    B2 --> P3["c-c48bc24e: 3D Human Body... (2023)"]
    B2 --> P4["c-310ee0fe: Image-based 3D..."]

    B4 --> S1["c-a6120f4a: A Survey of 3d... (2023)"]
    B4 --> S2["c-25fa513a: Remarks on 3d... (2007)"]

    B7 --> G1["1. 'patient virtual localization'含义?"]
    B7 --> G2["2. 输出格式?"]
    B7 --> G3["3. 感知模态?"]
    B7 --> G4["4. 临床背景需求?"]
    B7 --> G5["5. 数据需求?"]
```

### 处理统计

| 指标 | 值 |
|------|-----|
| 总耗时 | 169秒 |
| LLM调用次数 | 3-4次 |
| 适配器调用次数 | 22次 |
| 候选池大小 | 18篇 |
| Core论文 | 1篇 |
| Candidate论文 | 7篇 |
| Rejected论文 | 7篇 |
| 需人工审核 | 1篇 |
| 种子过滤 | 5个种子全部被拒绝 |
| 引用扩展 | 0篇 |

### 关键发现

1. **crossref是唯一有效适配器**: arxiv、openalex、github全部返回空结果
2. **"virtual localization"语义歧义**: 导致检索到大量无关的"virtual patient"临床文献
3. **种子相关性过滤有效**: 阻止了不相关论文的引用扩展
4. **质量控制触发修订**: low_bar_reviewer正确识别了题目边界模糊问题

---

## 关键设计决策

- **LLM-first**: 仅 3-4 次 LLM 调用（parse_topic → plan_tools → synthesize → devils_advocate）
- **无评分字段**: 无 `*_score` 字段，纯 tier enums
- **来源追踪**: SourceLedger 记录每次适配器调用的 provenance
- **多适配器路由**: 7 个检索适配器按 query family 路由，非单一 `multi_round_fetch`
