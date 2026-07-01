// Session 54: Interview Mode 数据 - Tech Switches + Deep Dive Modules + Scripts
// ponytail: 从旧 step_workbench.js §TECH_SWITCHES (40-175), §INTERVIEW_MODULES (178-306), §INTERVIEW_SCRIPTS (308-326) 抽

export type TechStatus = "implemented" | "lightweight" | "design-only";

export interface TechSwitch {
  key: string;
  label: string;
  status: TechStatus;
  mode: string;
  cost: string;
  description: string;
  note: string;
}

export interface InterviewModule {
  key: string;
  title: string;
  status: TechStatus;
  summary: string;
  questions: string[];
  codePaths: string[];
  testPaths: string[];
  docPaths: string[];
  boundary: string;
}

export interface ScriptBeat {
  label: string;
  seconds: number;
  focus: string;
  detail: string;
}

export const TECH_SWITCHES: TechSwitch[] = [
  {
    key: "paper_rag",
    label: "Paper RAG",
    status: "implemented",
    mode: "主链路",
    cost: "中",
    description: "S46-S48 论文库 RAG 检索 + 答案生成 + claim grounding。",
    note: "面试可点开 /ask 与 /ground-claims 验证。",
  },
  {
    key: "reality_check",
    label: "Reality Check 资源四层",
    status: "implemented",
    mode: "主链路",
    cost: "低",
    description: "S45 feasibility_card 资源判断, existing_env/rent_compute/self_collect/hardware。",
    note: "可在 Step 4 中调用, 输出 grad feasibility。",
  },
  {
    key: "claim_grounding",
    label: "Claim Grounding",
    status: "implemented",
    mode: "主链路",
    cost: "中",
    description: "S48 强制 evidence_refs, reject/pending/failed 引用规则。",
    note: "答报告前必须跑 claim_grounding。",
  },
  {
    key: "track_b_extractor",
    label: "Track B 小论文扩展",
    status: "implemented",
    mode: "扩展",
    cost: "中",
    description: "S49 已有小论文 → 贡献抽取 → 章节映射 → gap → 扩展计划。",
    note: "前端菜单『冲高水平 / 已有小论文』入口。",
  },
  {
    key: "thesis_eval",
    label: "ThesisEval 评估闭环",
    status: "lightweight",
    mode: "评估",
    cost: "中",
    description: "S51 100 篇工科学位论文测试集, 4 任务评估。",
    note: "可用于面试官问『你怎么验证可行性判断靠谱』。",
  },
  {
    key: "rag_evaluator",
    label: "RAG 评估",
    status: "implemented",
    mode: "评估",
    cost: "中",
    description: "S50 7 指标 + 回归基线。recall@5=0.68, MRR=0.76, citation_precision=1.0。",
    note: "可对比 baseline_diff, 退化时发警告。",
  },
  {
    key: "mcp",
    label: "MCP / Tool Boundary",
    status: "design-only",
    mode: "架构",
    cost: "高",
    description: "S36 MCP server 框架, 当前只读工具 + 显式声明。",
    note: "面试演示边界, 不假装已默认开放写工具。",
  },
  {
    key: "acp_admission_control",
    label: "ACP Admission Control",
    status: "design-only",
    mode: "深挖专用",
    cost: "高",
    description: "Agent 行为准入检查、能力授权、不可抵赖审计 (S44)。",
    note: "仅作为架构预留, 不参与当前执行。",
  },
];

export const INTERVIEW_MODULES: InterviewModule[] = [
  {
    key: "workflow",
    title: "Workflow / Step Workbench",
    status: "implemented",
    summary: "把开题流程拆成 5 个可确认阶段, 保留 Gate、Trace 和 stale 回传。",
    questions: [
      "为什么不用一次性生成整份报告？",
      "用户确认点和自动步骤的边界在哪？",
    ],
    codePaths: ["apps/web-react/src/features/step-workbench"],
    testPaths: ["e2e/test_session54_step_workbench.py"],
    docPaths: ["docs/interview/Project_OnePager.md", "docs/interview/Demo_Script_3min.md"],
    boundary: "当前是前端工作台级别的演示内核, 不替代后端 8 阶段编排。",
  },
  {
    key: "rag",
    title: "RAG Pipeline",
    status: "lightweight",
    summary: "强调 Query 拆解、候选召回、融合、重排和证据晋升, 而不是把卖点压成向量库。",
    questions: [
      "为什么现在不默认接真实向量库？",
      "Rerank 和 Candidate -> Evidence 的差别是什么？",
    ],
    codePaths: ["apps/api/app/services/paper_library"],
    testPaths: ["e2e/test_session54_*.py", "apps/api/tests/test_session47_paper_rag.py"],
    docPaths: ["docs/interview/RAG_Design_Explainer.md", "docs/interview/RAG_Data_Flow.md"],
    boundary: "向量库、真实 embedding 和大规模评估仍是后续扩展, 当前以可解释检索为主。",
  },
  {
    key: "evidence",
    title: "Evidence Governance",
    status: "implemented",
    summary: "Candidate 不等于 Evidence, 写报告前必须经过可追溯确认。",
    questions: [
      "LLM 为什么不能直接把候选写进最终报告？",
      "reject / restore 为什么也要保留 Trace?",
    ],
    codePaths: ["apps/api/app/services/evidence.py", "apps/api/app/services/evidence_refs.py"],
    testPaths: ["apps/api/tests/test_session48_claim_grounding.py"],
    docPaths: ["docs/interview/Project_DeepDive_Index.md", "docs/interview/Known_Limitations_For_Interview.md"],
    boundary: "claim_grounding 强制 evidence_refs, 防止候选直接晋升。",
  },
  {
    key: "memory",
    title: "Memory / Trace / Replay",
    status: "lightweight",
    summary: "区分 Working、Conversation、Trace、Evidence 和 Snapshot。",
    questions: [
      "上下文压缩后什么必须保留？",
      "刷新或恢复时应该带回哪些状态？",
    ],
    codePaths: ["apps/api/app/services/project_memory.py", "apps/api/app/services/run_event.py"],
    testPaths: ["apps/api/tests/test_session35_memory_replay.py"],
    docPaths: ["docs/interview/Agent_Memory_Explainer.md", "docs/interview/Deep_Dive_QA_Memory.md"],
    boundary: "Compressed Memory 和 Vector Memory 仍是设计预留, 不参与当前工作台执行。",
  },
  {
    key: "mcp",
    title: "Tool Boundary / MCP",
    status: "design-only",
    summary: "把外部工具当成可控边界, 而不是默认开放的写操作能力。",
    questions: [
      "为什么默认不暴露写工具？",
      "MCP 在这里是产品能力还是架构预留？",
    ],
    codePaths: ["apps/api/app/mcp/server.py", "apps/api/app/mcp/tools.py"],
    testPaths: ["apps/api/tests/test_session36_mcp.py"],
    docPaths: ["docs/interview/MCP_FunctionCalling_Explainer.md", "docs/interview/Deep_Dive_QA_MCP.md"],
    boundary: "当前作为面试深挖材料展示, 不宣称已作为默认主链路能力开放。",
  },
  {
    key: "agent",
    title: "Agent Architecture / LangGraph Mapping",
    status: "design-only",
    summary: "当前是轻量状态机 + Gate; 可映射到 StateGraph、interrupt 和 supervisor, 但不强接重 runtime。",
    questions: [
      "为什么现在不用 LangGraph runtime?",
      "如果以后接入, 替换的是哪一层?",
    ],
    codePaths: ["apps/api/app/services/agent_router.py"],
    testPaths: ["apps/api/tests/test_session37_multi_agent.py"],
    docPaths: ["docs/interview/Deep_Dive_QA_Agent.md", "docs/interview/MultiAgent_Expansion_Design.md"],
    boundary: "Supervisor / Subgraph / Router 仅做映射与讲解, 不假装已自动调度多代理执行。",
  },
  {
    key: "failure",
    title: "Failure / Limitation",
    status: "implemented",
    summary: "主动展示后端离线、导出阻塞、证据不足等失败路径, 避免面试只讲 happy path。",
    questions: [
      "后端挂掉时前端怎么表现?",
      "哪些限制必须主动讲清楚?",
    ],
    codePaths: ["apps/web-react/src/components/ui/ErrorState.tsx"],
    testPaths: ["e2e/test_session54_step_workbench.py"],
    docPaths: ["docs/interview/Known_Limitations_For_Interview.md", "docs/interview/Failure_Cases.md"],
    boundary: "离线提示只能诚实表达当前状态, 不能伪装导出成功。",
  },
  {
    key: "tests",
    title: "Tests / Baseline",
    status: "implemented",
    summary: "把浏览器点击验收和 Playwright 基线放到同一个面试入口里, 方便现场自证。",
    questions: [
      "哪些是已通过测试, 哪些仍是 blocked / skipped?",
      "为什么要把 UI 演示和回归测试一起讲?",
    ],
    codePaths: ["e2e/test_session54_*.py", "apps/api/tests"],
    testPaths: ["e2e/test_session54_*.py", "apps/api/tests/test_session50_rag_eval.py"],
    docPaths: ["docs/interview/Project_DeepDive_Index.md", "docs/interview/Demo_Script_10min.md"],
    boundary: "当前浏览器测试主要覆盖前端工作台与演示壳; 后端全链路状态要单独说明。",
  },
  {
    key: "protocols",
    title: "Protocols / MCP / A2A / ACP",
    status: "design-only",
    summary: "MCP 解决 Agent 调工具; A2A 解决 Agent 间任务委派; ACP 解决 Agent 间消息治理。",
    questions: [
      "MCP / A2A / ACP 有什么区别?",
      "PaperAgent 为什么当前只做 MCP, 不接 ACP?",
      "ACP 怎么保证不绕过 Human Gate?",
    ],
    codePaths: ["Plan/design/ACP_Interop_And_Agent_Communication.md"],
    testPaths: ["e2e/test_session54_*.py"],
    docPaths: ["docs/interview/Deep_Dive_QA_MCP.md", "docs/interview/MCP_FunctionCalling_Explainer.md"],
    boundary: "ACP 是 design-only 通信治理层, 不接入真实 runtime, 不参与当前主链路执行。",
  },
];

export const INTERVIEW_SCRIPTS: Record<string, ScriptBeat[]> = {
  "3min": [
    { label: "项目目标", seconds: 20, focus: "workflow", detail: "说明这是把选题判断做成可追溯工作台, 而不是聊天框。" },
    { label: "Step Workbench", seconds: 45, focus: "middle", detail: "展示 5 步 Gate、左右栏和分页步骤卡。" },
    { label: "Trace / Memory", seconds: 35, focus: "trace", detail: "强调可回看、可审计、可保留用户修改记录。" },
    { label: "对话式修改", seconds: 40, focus: "llm", detail: "切到生成修改建议, 说明先预览再确认。" },
    { label: "导出前检查", seconds: 30, focus: "report", detail: "说明 Step 6 只在准备就绪时开放, 后端离线时给出明确提示。" },
  ],
  "10min": [
    { label: "加载 Demo Case", seconds: 30, focus: "workflow", detail: "加载稳定演示数据, 先保证讲述节奏稳定。" },
    { label: "Workflow / Gate", seconds: 60, focus: "middle", detail: "讲为什么不用一次性生成, 为什么要分步确认。" },
    { label: "RAG 深挖", seconds: 80, focus: "rag", detail: "从拆 query、召回、重排讲到 Candidate -> Evidence。" },
    { label: "Memory / Trace", seconds: 70, focus: "memory", detail: "解释哪些能压缩, 哪些确认记录不能删。" },
    { label: "Agent 映射", seconds: 70, focus: "agent", detail: "说明为什么是 LangGraph friendly, 而不是硬接 runtime。" },
    { label: "Tech Switches", seconds: 45, focus: "switches", detail: "展示 on / off / design-only, 区分已实现和预留。" },
    { label: "Failure / Tests", seconds: 55, focus: "failure", detail: "主动讲限制, 再落到通过的测试和仍待补的边界。" },
    { label: "Step 6 导出", seconds: 30, focus: "report", detail: "收束到导出 readiness 和离线提示。" },
  ],
};

export const DEMO_CASE_TOPIC = "基于YOLO的钢材表面缺陷检测";
export const DEMO_CASE_DISCLAIMER =
  "演示数据为固定 Demo Case, 用于稳定讲解工作流, 不代表实时检索结果。";
export const DEMO_CASE_INTRO =
  "Interview Mode 已加载稳定 Demo Case。现在可以按 3 分钟或 10 分钟脚本直接演示。";

// ponytail: demo case 5 步结果只抽关键字段, 用于 Step 1-5 默认 completed
export const DEMO_CASE_STEP_RESULTS: Record<string, unknown>[] = [
  {
    direction: "工业质检 / 钢材表面缺陷检测",
    task_type: "目标检测",
    possible_object: "钢材表面缺陷",
    possible_route: "轻量化 YOLO + 多尺度缺陷增强 + 误检抑制",
    ambiguous_terms: ["缺陷粒度", "实时部署约束"],
  },
  {
    method: ["YOLOv8n", "轻量化检测"],
    task: ["钢材缺陷检测", "表面瑕疵识别"],
    object: ["钢材表面缺陷"],
    alternatives: ["NEU-DET", "热轧带钢缺陷", "实时工业质检"],
    query_combos: ["YOLO steel surface defect detection", "YOLO 钢材 表面 缺陷 检测"],
  },
  {
    summary: "检索到论文 3 条、数据集 2 条、工程 2 条; 已整理成稳定演示候选。",
    candidates: [
      { id: "paper-steel-a", kind: "paper", title: "Steel Surface Defect Detection With Improved YOLO", status: "可用" },
      { id: "paper-steel-b", kind: "paper", title: "NEU-DET Benchmark Revisit", status: "待核验" },
      { id: "paper-steel-c", kind: "paper", title: "Survey on Industrial Surface Defects", status: "可用" },
      { id: "dataset-neu-det", kind: "dataset", title: "NEU-DET", status: "可用" },
      { id: "dataset-gc10", kind: "dataset", title: "GC10-DET", status: "待核验" },
      { id: "repo-ultralytics", kind: "repo", title: "ultralytics/ultralytics", status: "可用" },
      { id: "repo-steel-demo", kind: "repo", title: "steel-defect-yolo-demo", status: "不推荐" },
    ],
  },
  {
    can_do: true,
    why_yes: "公开数据集、成熟 baseline 和工业检测场景都较明确。",
    dataset_risk: "NEU-DET 规模有限, 正式实验需要补充 GC10-DET 或自建数据。",
    reproduce_risk: "YOLOv8n 可快速复现, 主要工作量在缺陷增强和误检抑制。",
    engineering_risk: "部署侧需要明确推理速度和拍摄环境波动。",
    innovation_space: "可从多尺度缺陷增强、低样本稳定性和误检控制切入。",
  },
  {
    recommended_topic: "基于轻量化 YOLO 的钢材表面缺陷检测研究",
    background: "钢材表面缺陷检测属于高频工业质检场景, 具有明确数据、模型和落地价值。",
    content: "围绕缺陷候选召回、轻量模型训练和误检抑制设计实验路线。",
    route: "YOLOv8n 基线 -> NEU-DET / GC10-DET 验证 -> 误检抑制策略对比。",
    feasibility: "具备公开数据、成熟 baseline 和可解释的证据链。",
    risk_plan: "若数据量不足, 则先收缩到单一缺陷集并降低创新范围。",
    low_bar_pass: "满足面试演示和开题草稿讲解所需的最小闭环。",
  },
];
