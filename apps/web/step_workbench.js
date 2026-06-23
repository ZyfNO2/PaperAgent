(function (global) {
  "use strict";

  const STEPS = [
    { index: 0, key: "topic_understanding", title: "题目理解", icon: "1" },
    { index: 1, key: "keyword_breakdown", title: "关键词拆解", icon: "2" },
    { index: 2, key: "search_candidates", title: "检索计划与候选证据", icon: "3" },
    { index: 3, key: "feasibility", title: "可行性判断", icon: "4" },
    { index: 4, key: "proposal", title: "开题建议", icon: "5" },
  ];

  const STATUS = Object.freeze({
    LOCKED: "locked",
    RUNNING: "running",
    PAUSED: "paused_for_review",
    NEEDS_REVISION: "needs_revision",
    APPROVED: "approved",
    COMPLETED: "completed",
    FAILED: "failed",
    STALE: "stale",
  });

  const STATUS_LABEL = {
    locked: "未解锁",
    running: "进行中",
    paused_for_review: "等待确认",
    needs_revision: "需要修改",
    approved: "已确认",
    completed: "已完成",
    failed: "失败",
    stale: "stale",
  };

  const INTERVIEW_MODE = Object.freeze({
    LITE: "lite",
    INTERVIEW: "interview",
    FULL: "full",
  });

  const TECH_SWITCHES = [
    {
      key: "rag_chunking",
      label: "RAG Chunking",
      status: "on",
      mode: "主线默认",
      cost: "低",
      description: "按论文摘要、README 和数据集说明切块，保留可解释检索入口。",
      note: "当前主线默认开启，是可展示但不依赖重型向量库的基础能力。",
    },
    {
      key: "rag_hybrid_search",
      label: "Hybrid Search",
      status: "on",
      mode: "主线默认",
      cost: "中",
      description: "关键词召回 + 轻量规则召回，避免把 RAG 讲成单一向量库。",
      note: "当前是 lightweight 实现，重点在可解释召回链路。",
    },
    {
      key: "rag_rerank",
      label: "Rerank",
      status: "on",
      mode: "主线默认",
      cost: "中",
      description: "强调覆盖度、来源质量和可复现信号，而不是只看单分数。",
      note: "是当前面试讲解重点，建议保持开启。",
    },
    {
      key: "vector_db",
      label: "Vector DB",
      status: "off",
      mode: "扩展能力",
      cost: "高",
      description: "Milvus / Qdrant / FAISS 等真实向量库接入位。",
      note: "当前未启用，避免把小数据量 MVP 强讲成重型检索系统。",
    },
    {
      key: "langgraph_runtime",
      label: "LangGraph Runtime",
      status: "design-only",
      mode: "深挖专用",
      cost: "高",
      description: "展示状态机到 StateGraph 的映射，但不替换当前轻量实现。",
      note: "只做架构预留，不参与当前执行。",
    },
    {
      key: "human_in_loop_interrupt",
      label: "Human Gate",
      status: "on",
      mode: "主线默认",
      cost: "低",
      description: "用户确认 Gate、修改预览确认和 stale 回传。",
      note: "是当前工作台的核心边界，不建议关闭。",
    },
    {
      key: "subagent_router",
      label: "SubAgent Router",
      status: "design-only",
      mode: "深挖专用",
      cost: "高",
      description: "Supervisor + Retrieval / Review / Proposal 子代理的预留路由。",
      note: "默认关闭，避免把设计稿误说成已落地多 Agent 执行。",
    },
    {
      key: "memory_snapshot",
      label: "Memory Snapshot",
      status: "on",
      mode: "主线默认",
      cost: "中",
      description: "支持 Trace / Snapshot / Replay 的状态说明。",
      note: "当前以轻量快照和回放叙事为主。",
    },
    {
      key: "memory_compression",
      label: "Memory Compression",
      status: "design-only",
      mode: "扩展能力",
      cost: "中",
      description: "长流程时压缩普通对话，保留关键确认与证据链。",
      note: "当前工作流较短，先保留边界设计。",
    },
    {
      key: "mcp_tools",
      label: "MCP Tools",
      status: "off",
      mode: "深挖专用",
      cost: "中",
      description: "只在面试深挖时解释外部工具边界，不在主链路默认暴露写能力。",
      note: "保持 read-mostly 叙事，避免扩大权限面。",
    },
  ];

  const INTERVIEW_MODULES = [
    {
      key: "workflow",
      title: "Workflow / Step Workbench",
      status: "implemented",
      summary: "把开题流程拆成 5 个可确认阶段，保留 Gate、Trace 和 stale 回传。",
      questions: [
        "为什么不用一次性生成整份报告？",
        "用户确认点和自动步骤的边界在哪？",
      ],
      codePaths: ["apps/web/step_workbench.js", "apps/web/app.js"],
      testPaths: ["apps/web/e2e/test_one_topic_session41_step_workbench.py", "apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py"],
      docPaths: ["docs/interview/Project_OnePager.md", "docs/interview/Demo_Script_3min.md"],
      boundary: "当前是前端工作台级别的演示内核，不替代后端 8 阶段编排。",
    },
    {
      key: "rag",
      title: "RAG Pipeline",
      status: "lightweight",
      summary: "强调 Query 拆解、候选召回、融合、重排和证据晋升，而不是把卖点压成向量库。",
      questions: [
        "为什么现在不默认接真实向量库？",
        "Rerank 和 Candidate -> Evidence 的差别是什么？",
      ],
      codePaths: ["apps/api/app/services/rag_pipeline.py", "apps/api/app/services/rag_evaluator.py"],
      testPaths: ["apps/web/e2e/test_one_topic_session34_rag_eval.py", "apps/api/tests/test_session14_multi_source_retrieval.py"],
      docPaths: ["docs/interview/RAG_Design_Explainer.md", "docs/interview/Deep_Dive_QA_RAG.md"],
      boundary: "向量库、真实 embedding 和大规模评估仍是后续扩展，当前以可解释检索为主。",
    },
    {
      key: "evidence",
      title: "Evidence Governance",
      status: "implemented",
      summary: "Candidate 不等于 Evidence，写报告前必须经过可追溯确认。",
      questions: [
        "LLM 为什么不能直接把候选写进最终报告？",
        "reject / restore 为什么也要保留 Trace？",
      ],
      codePaths: ["apps/api/app/services/evidence.py", "apps/api/app/services/evidence_refs.py"],
      testPaths: ["apps/api/tests/test_session17_demo_baseline.py", "apps/web/e2e/test_one_topic_session7_evidence_refs.py"],
      docPaths: ["docs/interview/Project_DeepDive_Index.md", "docs/interview/Known_Limitations_For_Interview.md"],
      boundary: "当前工作台里的证据动作以演示边界为主，不伪装成已接通完整外部验证链路。",
    },
    {
      key: "memory",
      title: "Memory / Trace / Replay",
      status: "lightweight",
      summary: "区分 Working、Conversation、Trace、Evidence 和 Snapshot，明确哪些能压缩，哪些不能丢。",
      questions: [
        "上下文压缩后什么必须保留？",
        "刷新或恢复时应该带回哪些状态？",
      ],
      codePaths: ["apps/api/app/services/project_memory.py", "apps/api/app/services/run_event.py"],
      testPaths: ["apps/web/e2e/test_one_topic_session35_memory_replay.py", "apps/web/e2e/test_one_topic_session11_trace_persistence.py"],
      docPaths: ["docs/interview/Agent_Memory_Explainer.md", "docs/interview/Deep_Dive_QA_Memory.md"],
      boundary: "Compressed Memory 和 Vector Memory 仍是设计预留，不参与当前工作台执行。",
    },
    {
      key: "mcp",
      title: "Tool Boundary / MCP",
      status: "design-only",
      summary: "把外部工具当成可控边界，而不是默认开放的写操作能力。",
      questions: [
        "为什么默认不暴露写工具？",
        "MCP 在这里是产品能力还是架构预留？",
      ],
      codePaths: ["apps/api/app/mcp/server.py", "apps/api/app/mcp/tools.py"],
      testPaths: ["apps/web/e2e/test_one_topic_session36_mcp.py", "apps/api/tests/test_session13_skill_registry.py"],
      docPaths: ["docs/interview/MCP_FunctionCalling_Explainer.md", "docs/interview/Deep_Dive_QA_MCP.md"],
      boundary: "当前作为面试深挖材料展示，不宣称已作为默认主链路能力开放。",
    },
    {
      key: "agent",
      title: "Agent Architecture / LangGraph Mapping",
      status: "design-only",
      summary: "当前是轻量状态机 + Gate；可映射到 StateGraph、interrupt 和 supervisor，但不强接重 runtime。",
      questions: [
        "为什么现在不用 LangGraph runtime？",
        "如果以后接入，替换的是哪一层？",
      ],
      codePaths: ["apps/web/step_workbench.js", "apps/api/app/services/agent_router.py"],
      testPaths: ["apps/web/e2e/test_one_topic_session37_multi_agent.py", "apps/web/e2e/test_one_topic_session43_interview_mode.py"],
      docPaths: ["docs/interview/Deep_Dive_QA_Agent.md", "docs/interview/MultiAgent_Expansion_Design.md"],
      boundary: "Supervisor / Subgraph / Router 仅做映射与讲解，不假装已自动调度多代理执行。",
    },
    {
      key: "failure",
      title: "Failure / Limitation",
      status: "implemented",
      summary: "主动展示后端离线、导出阻塞、证据不足等失败路径，避免面试只讲 happy path。",
      questions: [
        "后端挂掉时前端怎么表现？",
        "哪些限制必须主动讲清楚？",
      ],
      codePaths: ["apps/web/app.js", "apps/web/step_workbench.js"],
      testPaths: ["apps/web/e2e/test_one_topic_session8_final_package.py", "apps/web/e2e/test_one_topic_session43_interview_mode.py"],
      docPaths: ["docs/interview/Known_Limitations_For_Interview.md", "docs/interview/Failure_Cases.md"],
      boundary: "离线提示只能诚实表达当前状态，不能伪装导出成功。",
    },
    {
      key: "tests",
      title: "Tests / Baseline",
      status: "implemented",
      summary: "把浏览器点击验收和 Playwright 基线放到同一个面试入口里，方便现场自证。",
      questions: [
        "哪些是已通过测试，哪些仍是 blocked / skipped？",
        "为什么要把 UI 演示和回归测试一起讲？",
      ],
      codePaths: ["apps/web/e2e/conftest.py", "apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py"],
      testPaths: ["apps/web/e2e/test_one_topic_session42_workbench_chat_edit.py", "apps/web/e2e/test_one_topic_session43_interview_mode.py"],
      docPaths: ["docs/interview/Project_DeepDive_Index.md", "docs/interview/Demo_Script_10min.md"],
      boundary: "当前浏览器测试主要覆盖前端工作台与演示壳；后端全链路状态要单独说明。",
    },
  ];

  const INTERVIEW_SCRIPTS = {
    "3min": [
      { label: "项目目标", seconds: 20, focus: "workflow", detail: "说明这是把选题判断做成可追溯工作台，而不是聊天框。" },
      { label: "Step Workbench", seconds: 45, focus: "middle", detail: "展示 5 步 Gate、左右栏和分页步骤卡。" },
      { label: "Trace / Memory", seconds: 35, focus: "trace", detail: "强调可回看、可审计、可保留用户修改记录。" },
      { label: "对话式修改", seconds: 40, focus: "llm", detail: "切到生成修改建议，说明先预览再确认。" },
      { label: "导出前检查", seconds: 30, focus: "report", detail: "说明 Step 6 只在准备就绪时开放，后端离线时给出明确提示。" },
    ],
    "10min": [
      { label: "加载 Demo Case", seconds: 30, focus: "workflow", detail: "加载稳定演示数据，先保证讲述节奏稳定。" },
      { label: "Workflow / Gate", seconds: 60, focus: "middle", detail: "讲为什么不用一次性生成，为什么要分步确认。" },
      { label: "RAG 深挖", seconds: 80, focus: "rag", detail: "从拆 query、召回、重排讲到 Candidate -> Evidence。" },
      { label: "Memory / Trace", seconds: 70, focus: "memory", detail: "解释哪些能压缩，哪些确认记录不能删。" },
      { label: "Agent 映射", seconds: 70, focus: "agent", detail: "说明为什么是 LangGraph friendly，而不是硬接 runtime。" },
      { label: "Tech Switches", seconds: 45, focus: "switches", detail: "展示 on / off / design-only，区分已实现和预留。" },
      { label: "Failure / Tests", seconds: 55, focus: "failure", detail: "主动讲限制，再落到通过的测试和仍待补的边界。" },
      { label: "Step 6 导出", seconds: 30, focus: "report", detail: "收束到导出 readiness 和离线提示。" },
    ],
  };

  const DEMO_CASE = {
    topic: "基于YOLO的钢材表面缺陷检测",
    disclaimer: "演示数据为固定 Demo Case，用于稳定讲解工作流，不代表实时检索结果。",
    llmIntro: "Interview Mode 已加载稳定 Demo Case。现在可以按 3 分钟或 10 分钟脚本直接演示。",
    steps: [
      {
        status: STATUS.COMPLETED,
        result: {
          direction: "工业质检 / 钢材表面缺陷检测",
          task_type: "目标检测",
          possible_object: "钢材表面缺陷",
          possible_route: "轻量化 YOLO + 多尺度缺陷增强 + 误检抑制",
          ambiguous_terms: ["缺陷粒度", "实时部署约束"],
        },
      },
      {
        status: STATUS.COMPLETED,
        result: {
          method: ["YOLOv8n", "轻量化检测"],
          task: ["钢材缺陷检测", "表面瑕疵识别"],
          object: ["钢材表面缺陷"],
          alternatives: ["NEU-DET", "热轧带钢缺陷", "实时工业质检"],
          query_combos: ["YOLO steel surface defect detection", "YOLO 钢材 表面 缺陷 检测"],
        },
      },
      {
        status: STATUS.COMPLETED,
        result: {
          summary: "检索到论文 3 条、数据集 2 条、工程 2 条；已整理成稳定演示候选。",
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
      },
      {
        status: STATUS.COMPLETED,
        result: {
          can_do: true,
          why_yes: "公开数据集、成熟 baseline 和工业检测场景都较明确。",
          dataset_risk: "NEU-DET 规模有限，正式实验需要补充 GC10-DET 或自建数据。",
          reproduce_risk: "YOLOv8n 可快速复现，主要工作量在缺陷增强和误检抑制。",
          engineering_risk: "部署侧需要明确推理速度和拍摄环境波动。",
          innovation_space: "可从多尺度缺陷增强、低样本稳定性和误检控制切入。",
        },
      },
      {
        status: STATUS.COMPLETED,
        result: {
          recommended_topic: "基于轻量化 YOLO 的钢材表面缺陷检测研究",
          background: "钢材表面缺陷检测属于高频工业质检场景，具有明确数据、模型和落地价值。",
          content: "围绕缺陷候选召回、轻量模型训练和误检抑制设计实验路线。",
          route: "YOLOv8n 基线 -> NEU-DET / GC10-DET 验证 -> 误检抑制策略对比。",
          feasibility: "具备公开数据、成熟 baseline 和可解释的证据链。",
          risk_plan: "若数据量不足，则先收缩到单一缺陷集并降低创新范围。",
          low_bar_pass: "满足面试演示和开题草稿讲解所需的最小闭环。",
        },
      },
    ],
    trace: [
      { kind: "demo_case", text: "Interview Mode 已切换到固定 Demo Case。", step: null },
      { kind: "step_start", text: "演示数据直接恢复为可讲状态，避免临场依赖实时检索。", step: 0 },
      { kind: "evidence_event", text: "候选证据按论文 / 数据集 / 工程三线整理完成。", step: 2 },
      { kind: "user_confirm", text: "演示模式默认将 Step 1-5 视为已确认，用于快速讲述。", step: 4 },
      { kind: "run_done", text: "Demo Case 已就绪，可以直接进入导出前检查。", step: 4 },
    ],
    llm: [
      { kind: "assistant_reply", text: "演示模式已切换为固定 Demo Case，便于 3 分钟和 10 分钟脚本复现。", step: null },
      { kind: "assistant_thought", text: "我会优先展示 Workflow、Trace 和修改预览，再按需打开 RAG / Memory / Agent 深挖。", step: 0 },
      { kind: "assistant_reply", text: "这里的数据是演示快照，不假装成实时联网检索结果。", step: 2 },
    ],
    tools: [
      { tool: "demo_case_loader", purpose: "恢复稳定演示状态，减少现场不确定性", source: "session43", step: null },
      { tool: "deep_dive_index", purpose: "把代码、测试、文档入口集中成一个可点开的讲解索引", source: "session43", step: null },
    ],
  };

  function buildStepState(step) {
    return {
      index: step.index,
      key: step.key,
      title: step.title,
      icon: step.icon,
      status: STATUS.LOCKED,
      result: null,
      gateQuestion: null,
      staleReason: null,
    };
  }

  function currentUrlMode() {
    try {
      const mode = new URLSearchParams(global.location.search || "").get("mode");
      return mode === "interview" ? INTERVIEW_MODE.INTERVIEW : INTERVIEW_MODE.LITE;
    } catch (err) {
      return INTERVIEW_MODE.LITE;
    }
  }

  function createState() {
    return {
      activeStepIndex: 0,
      currentRuntimeStep: -1,
      topic: "",
      steps: STEPS.map(buildStepState),
      evidenceTrace: [],
      llmTimeline: [],
      toolUseTimeline: [],
      gateState: null,
      streamTimer: null,
      seqCounter: 0,
      subTabs: {},
      chatMode: "ask",
      chatDraft: "",
      commandPreview: null,
      traceGroupOpen: { session: true },
      uiMode: currentUrlMode(),
      interviewFocus: "workflow",
      interviewScriptKey: "3min",
      interviewDrawerOpen: false,
      demoLoaded: false,
      demoDisclaimer: "",
      backendReachable: null,
      projectBound: false,
    };
  }

  const state = createState();

  function nextSeq() {
    state.seqCounter += 1;
    return state.seqCounter;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function safeLabelForAttr(value) {
    return escapeHtml(String(value || "").replace(/\s+/g, "-").toLowerCase());
  }

  function appendTrace(kind, text, step, meta) {
    state.evidenceTrace.push({
      seq: nextSeq(),
      kind: kind,
      text: text,
      step: typeof step === "number" ? step : null,
      meta: meta || {},
    });
    renderTracePanel();
  }

  function appendLlm(kind, text, step, meta) {
    state.llmTimeline.push({
      seq: nextSeq(),
      kind: kind,
      text: text,
      step: typeof step === "number" ? step : null,
      meta: meta || {},
    });
    renderLlmPanel();
  }

  function appendToolUse(tool, purpose, source, step) {
    state.toolUseTimeline.push({
      seq: nextSeq(),
      kind: "tool_use",
      tool: tool,
      purpose: purpose,
      source: source || null,
      step: typeof step === "number" ? step : null,
    });
    renderLlmPanel();
  }

  function setStepStatus(idx, status, extra) {
    if (idx < 0 || idx >= state.steps.length) return;
    const step = state.steps[idx];
    step.status = status;
    if (status !== STATUS.STALE) step.staleReason = null;
    if (extra && extra.staleReason) step.staleReason = extra.staleReason;
    if (status === STATUS.RUNNING) {
      appendTrace("step_start", "开始 Step " + (idx + 1) + ": " + step.title, idx);
      appendLlm("assistant_thought", "进入 " + step.title + "，我会先整理当前工作台上下文。", idx);
    } else if (status === STATUS.PAUSED) {
      appendTrace("step_pause", "Step " + (idx + 1) + " 已暂停，等待用户确认。", idx);
    } else if (status === STATUS.APPROVED) {
      appendTrace("user_confirm", "用户确认 Step " + (idx + 1) + "。", idx);
    } else if (status === STATUS.COMPLETED) {
      appendTrace("step_complete", "Step " + (idx + 1) + " 已完成。", idx);
    } else if (status === STATUS.NEEDS_REVISION) {
      appendTrace("step_revise", "Step " + (idx + 1) + " 需要重跑或修订。", idx);
    } else if (status === STATUS.FAILED) {
      appendTrace("step_fail", "Step " + (idx + 1) + " 失败。", idx);
    } else if (status === STATUS.STALE) {
      appendTrace("step_stale", "Step " + (idx + 1) + " 已标记为 stale。", idx, extra || {});
    }
    renderAll();
  }

  const STEP_SCRIPTS = {
    0: function () {
      return [
        ["thought", "我先把题目拆成方法、任务和研究对象。"],
        ["tool", "keyword_parser", "提取方法词、任务词和对象词", null],
        ["trace", "识别方法关键词：YOLO"],
        ["trace", "识别任务关键词：检测"],
        ["trace", "识别对象关键词：道路裂缝"],
        ["thought", "当前对象词存在领域歧义，后面可以通过对话继续改写。"],
        ["result", {
          direction: "工业质检 / 路面维护",
          task_type: "目标检测",
          possible_object: "道路表面裂缝",
          possible_route: "轻量化 YOLO + 后处理改进",
          ambiguous_terms: ["裂缝采集方式", "设备约束"],
        }],
        ["gate", "这个题目理解是否正确？确认后我再进入关键词拆解。"],
      ];
    },
    1: function () {
      return [
        ["thought", "我把方法、任务、对象扩展成可检索的关键词组合。"],
        ["tool", "keyword_expander", "生成中英关键词与替代词", null],
        ["trace", "方法词：YOLO"],
        ["trace", "任务词：检测"],
        ["trace", "对象词：道路表面裂缝"],
        ["result", {
          method: ["YOLO"],
          task: ["检测"],
          object: ["道路表面裂缝"],
          alternatives: ["缺陷检测", "路面裂缝", "实时检测"],
          query_combos: ["YOLO road crack detection", "YOLO 路面裂缝 检测"],
        }],
        ["gate", "关键词是否正确？你可以通过对话要求增删改查，确认后再进入检索。"],
      ];
    },
    2: function () {
      return [
        ["thought", "我按论文、数据集、工程三条线整理候选证据。"],
        ["tool", "search_openalex", "查询论文候选", "openalex"],
        ["tool", "search_arxiv", "补充论文候选", "arxiv"],
        ["tool", "search_github", "补充工程候选", "github"],
        ["trace", "检索到论文候选 3 条，其中 1 条待核验。"],
        ["trace", "检索到数据集候选 2 条，其中 1 条可直接使用。"],
        ["trace", "检索到工程候选 2 条，其中 1 条建议排除。"],
        ["result", {
          summary: "检索到论文 3 条、数据集 2 条、工程 2 条。",
          candidates: [
            { id: "paper-a", kind: "paper", title: "Crack Detection via Improved YOLO", status: "可用" },
            { id: "paper-b", kind: "paper", title: "Real-time Road Surface Defect Survey", status: "待核验" },
            { id: "paper-c", kind: "paper", title: "A Survey of Pavement Distress Methods", status: "不推荐" },
            { id: "dataset-a", kind: "dataset", title: "CrackTree446", status: "可用" },
            { id: "dataset-b", kind: "dataset", title: "RDD2022", status: "待核验" },
            { id: "repo-a", kind: "repo", title: "ultralytics/ultralytics", status: "可用" },
            { id: "repo-b", kind: "repo", title: "yjw0115/crack-segmentation", status: "不推荐" },
          ],
        }],
        ["gate", "检索方向是否合理？确认后进入可行性判断。"],
      ];
    },
    3: function () {
      return [
        ["thought", "我根据已有证据判断这个题能不能做。"],
        ["tool", "feasibility_evaluator", "评估数据、复现和工程风险", null],
        ["trace", "完成可行性评估，记录 3 个主要风险点。"],
        ["result", {
          can_do: true,
          why_yes: "已有公开数据集、成熟 YOLO baseline 和可复用工程。",
          dataset_risk: "CrackTree446 规模偏小，建议准备 RDD2022 作为补充。",
          reproduce_risk: "YOLO 系列复现成本较低。",
          engineering_risk: "需要明确裂缝后处理与部署方式。",
          innovation_space: "可在轻量化与裂缝拼接后处理上形成创新点。",
        }],
        ["gate", "这份可行性判断是否符合预期？确认后进入开题建议。"],
      ];
    },
    4: function () {
      return [
        ["thought", "我把前面 4 步确认的信息收束成开题建议。"],
        ["tool", "proposal_drafter", "生成推荐题目和技术路线草稿", null],
        ["trace", "开题建议草稿已生成。"],
        ["result", {
          recommended_topic: "基于轻量化 YOLO 的道路表面裂缝检测研究",
          background: "裂缝检测是基础设施运维中的高频场景，具备清晰的工程落地价值。",
          content: "围绕轻量模型、裂缝识别稳定性与后处理补强开展研究。",
          route: "YOLOv8n 微调 -> 裂缝后处理 -> CrackTree446 / RDD2022 验证。",
          feasibility: "数据、模型与复现路径均具备基础条件。",
          risk_plan: "若自建数据不足，优先扩展公开数据集并降低创新范围。",
          low_bar_pass: "满足开题前的资料、baseline 与任务闭环要求。",
        }],
        ["gate", "是否将这份内容视为可导出的开题建议草稿？确认后解锁导出区。"],
      ];
    },
  };

  function resetState() {
    if (state.streamTimer) {
      clearTimeout(state.streamTimer);
      state.streamTimer = null;
    }
    state.activeStepIndex = 0;
    state.currentRuntimeStep = -1;
    state.topic = "";
    state.steps = STEPS.map(buildStepState);
    state.evidenceTrace.length = 0;
    state.llmTimeline.length = 0;
    state.toolUseTimeline.length = 0;
    state.gateState = null;
    state.seqCounter = 0;
    state.subTabs = {};
    state.chatMode = "ask";
    state.chatDraft = "";
    state.commandPreview = null;
    state.traceGroupOpen = { session: true };
    state.demoLoaded = false;
    state.demoDisclaimer = "";
    state.projectBound = false;
  }

  function setInterviewMode(enabled) {
    state.uiMode = enabled ? INTERVIEW_MODE.INTERVIEW : INTERVIEW_MODE.LITE;
    if (!enabled) {
      state.interviewDrawerOpen = false;
      state.interviewFocus = "workflow";
      state.interviewScriptKey = "3min";
    }
    syncInterviewShell();
    renderAll();
  }

  function setInterviewFocus(key, openDrawer) {
    state.interviewFocus = key || "workflow";
    if (typeof openDrawer === "boolean") state.interviewDrawerOpen = openDrawer;
    syncInterviewShell();
    applyInterviewHighlight();
  }

  function setBackendReachable(value) {
    state.backendReachable = value;
    syncInterviewShell();
    syncReportSection();
  }

  function bindProject(projectId) {
    state.projectBound = !!projectId;
    syncReportSection();
  }

  function showInterviewModeFromUrl() {
    if (currentUrlMode() === INTERVIEW_MODE.INTERVIEW) {
      setInterviewMode(true);
    }
  }

  function startWorkbench(topic) {
    resetState();
    state.topic = topic || "";
    appendTrace("topic_received", "收到题目：" + (state.topic || "(空)"), null);
    appendLlm("assistant_reply", "工作台已启动。左侧可以随时提问，或生成修改建议预览。", null);
    startStep(0);
  }

  function loadDemoCase() {
    resetState();
    state.uiMode = INTERVIEW_MODE.INTERVIEW;
    state.demoLoaded = true;
    state.demoDisclaimer = DEMO_CASE.disclaimer;
    state.topic = DEMO_CASE.topic;
    state.activeStepIndex = 0;
    state.currentRuntimeStep = 4;
    DEMO_CASE.steps.forEach(function (demoStep, idx) {
      state.steps[idx].result = demoStep.result;
      state.steps[idx].status = demoStep.status;
      state.steps[idx].gateQuestion = idx === 4 ? "当前 Demo Case 已准备好，可继续导出或深挖讲解。" : null;
    });
    DEMO_CASE.trace.forEach(function (event) {
      appendTrace(event.kind, event.text, event.step);
    });
    DEMO_CASE.llm.forEach(function (msg) {
      appendLlm(msg.kind, msg.text, msg.step);
    });
    DEMO_CASE.tools.forEach(function (call) {
      appendToolUse(call.tool, call.purpose, call.source, call.step);
    });
    appendLlm("assistant_reply", DEMO_CASE.llmIntro, null);
    renderAll();
  }

  function startStep(idx) {
    if (idx < 0 || idx >= state.steps.length) return;
    state.currentRuntimeStep = idx;
    state.activeStepIndex = idx;
    state.traceGroupOpen["step-" + idx] = true;
    setStepStatus(idx, STATUS.RUNNING);
    streamMock(idx);
  }

  function streamMock(idx) {
    const script = (STEP_SCRIPTS[idx] || function () { return []; })();
    let pointer = 0;
    if (state.streamTimer) {
      clearTimeout(state.streamTimer);
      state.streamTimer = null;
    }

    function tick() {
      if (pointer >= script.length) {
        setStepStatus(idx, STATUS.PAUSED);
        return;
      }
      const item = script[pointer++];
      const kind = item[0];
      if (kind === "thought") {
        appendLlm("assistant_thought", item[1], idx);
      } else if (kind === "tool") {
        appendToolUse(item[1], item[2], item[3], idx);
      } else if (kind === "trace") {
        appendTrace("evidence_event", item[1], idx);
      } else if (kind === "result") {
        state.steps[idx].result = item[1];
      } else if (kind === "gate") {
        state.steps[idx].gateQuestion = item[1];
        state.gateState = { step: idx, question: item[1] };
        appendLlm("gate_question", item[1], idx);
      }
      renderAll();
      state.streamTimer = setTimeout(tick, 180);
    }

    tick();
  }

  function approveCurrent() {
    const idx = state.currentRuntimeStep;
    if (idx < 0 || idx >= state.steps.length) return;
    if (state.steps[idx].status !== STATUS.PAUSED) return;
    setStepStatus(idx, STATUS.APPROVED);
    setTimeout(function () { setStepStatus(idx, STATUS.COMPLETED); }, 40);
    const next = idx + 1;
    if (next < state.steps.length) {
      setTimeout(function () { startStep(next); }, 100);
    } else {
      state.gateState = null;
      appendTrace("run_done", "5 个步骤已完成，导出区已可用。", idx);
      appendLlm("assistant_reply", "现在可以导出开题建议，也可以继续通过对话微调工作台内容。", idx);
      renderAll();
    }
  }

  function reviseCurrent() {
    const idx = state.currentRuntimeStep;
    if (idx < 0) return;
    setStepStatus(idx, STATUS.NEEDS_REVISION);
    setTimeout(function () { startStep(idx); }, 100);
  }

  function goToPage(idx) {
    if (idx < 0 || idx >= state.steps.length) return;
    state.activeStepIndex = idx;
    renderAll();
  }

  function prevPage() {
    if (state.activeStepIndex > 0) goToPage(state.activeStepIndex - 1);
  }

  function nextPage() {
    if (state.activeStepIndex < state.steps.length - 1) goToPage(state.activeStepIndex + 1);
  }

  function defaultSubTab(stepIdx, keyList) {
    if (!state.subTabs[stepIdx] || keyList.indexOf(state.subTabs[stepIdx]) === -1) {
      state.subTabs[stepIdx] = keyList[0];
    }
    return state.subTabs[stepIdx];
  }

  function interviewEnabled() {
    return state.uiMode === INTERVIEW_MODE.INTERVIEW || state.uiMode === INTERVIEW_MODE.FULL;
  }

  function techSwitchMarkup(item) {
    return '<div class="interview-switch-card" data-switch-key="' + escapeHtml(item.key) + '">' +
      '<div class="interview-switch-card__head">' +
        '<strong>' + escapeHtml(item.label) + '</strong>' +
        '<span class="interview-badge interview-badge--' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + "</span>" +
      "</div>" +
      '<div class="interview-switch-card__meta">' + escapeHtml(item.mode) + " · 打开成本 " + escapeHtml(item.cost) + "</div>" +
      '<p class="interview-switch-card__desc">' + escapeHtml(item.description) + "</p>" +
      '<p class="interview-switch-card__note">' + escapeHtml(item.note) + "</p>" +
    "</div>";
  }

  function findInterviewModule(key) {
    return INTERVIEW_MODULES.filter(function (item) { return item.key === key; })[0] || INTERVIEW_MODULES[0];
  }

  function renderInterviewChecklist() {
    const items = INTERVIEW_SCRIPTS[state.interviewScriptKey] || INTERVIEW_SCRIPTS["3min"];
    return '<div class="interview-card interview-card--checklist">' +
      '<div class="interview-card__head">' +
        '<h4>' + escapeHtml(state.interviewScriptKey === "3min" ? "3 分钟脚本" : "10 分钟脚本") + '</h4>' +
        '<span class="interview-card__hint">每项都能在 UI 里直接找到对应位置</span>' +
      '</div>' +
      '<div class="interview-checklist">' +
        items.map(function (item, idx) {
          return '<button class="interview-checklist__item' + (state.interviewFocus === item.focus ? " is-active" : "") + '"' +
            ' data-script-focus="' + escapeHtml(item.focus) + '" type="button">' +
            '<span class="interview-checklist__index">' + (idx + 1) + '</span>' +
            '<span class="interview-checklist__main">' +
              '<strong>' + escapeHtml(item.label) + '</strong>' +
              '<small>' + escapeHtml(item.detail) + "</small>" +
            "</span>" +
            '<span class="interview-checklist__time">' + escapeHtml(String(item.seconds)) + "s</span>" +
          "</button>";
        }).join("") +
      "</div>" +
    "</div>";
  }

  function renderInterviewDrawer() {
    const moduleKey = ["middle", "llm", "trace", "report"].indexOf(state.interviewFocus) >= 0
      ? { middle: "workflow", llm: "workflow", trace: "memory", report: "failure" }[state.interviewFocus]
      : state.interviewFocus;
    const item = findInterviewModule(moduleKey);
    return '<div class="interview-card interview-card--drawer">' +
      '<div class="interview-card__head">' +
        '<h4>' + escapeHtml(item.title) + '</h4>' +
        '<span class="interview-badge interview-badge--' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + "</span>" +
      "</div>" +
      '<p class="interview-drawer__summary">' + escapeHtml(item.summary) + "</p>" +
      '<div class="interview-drawer__section"><strong>面试官可能追问</strong><ul>' +
        item.questions.map(function (question) { return "<li>" + escapeHtml(question) + "</li>"; }).join("") +
      "</ul></div>" +
      '<div class="interview-drawer__section"><strong>可展示代码</strong><ul>' +
        item.codePaths.map(function (path) { return "<li>" + escapeHtml(path) + "</li>"; }).join("") +
      "</ul></div>" +
      '<div class="interview-drawer__section"><strong>可展示测试</strong><ul>' +
        item.testPaths.map(function (path) { return "<li>" + escapeHtml(path) + "</li>"; }).join("") +
      "</ul></div>" +
      '<div class="interview-drawer__section"><strong>相关文档</strong><ul>' +
        item.docPaths.map(function (path) { return "<li>" + escapeHtml(path) + "</li>"; }).join("") +
      "</ul></div>" +
      '<div class="interview-drawer__boundary"><strong>当前边界</strong><span>' + escapeHtml(item.boundary) + "</span></div>" +
    "</div>";
  }

  function syncInterviewShell() {
    const shell = el("interview-shell");
    if (!shell) return;
    if (!interviewEnabled()) {
      shell.hidden = true;
      shell.innerHTML = "";
      applyInterviewHighlight();
      return;
    }
    shell.hidden = false;
    const modeLabel = state.uiMode === INTERVIEW_MODE.INTERVIEW ? "interview" : state.uiMode;
    const backendText = state.backendReachable === null
      ? "backend unknown"
      : state.backendReachable
        ? "backend ready"
        : "backend offline";
    shell.innerHTML =
      '<section class="interview-shell__hero">' +
        '<div class="interview-shell__title-row">' +
          '<div>' +
            '<div class="interview-shell__eyebrow">Interview Mode</div>' +
            '<h3>面试演示模式与技术深挖控制台</h3>' +
            '<p>同一套工作台，多一层稳定 Demo、脚本、深挖索引和技术边界说明。</p>' +
          '</div>' +
          '<div class="interview-shell__meta">' +
            '<span class="interview-badge interview-badge--mode">' + escapeHtml(modeLabel) + '</span>' +
            '<span class="interview-badge interview-badge--' + (state.backendReachable ? "on" : state.backendReachable === false ? "off" : "neutral") + '">' + escapeHtml(backendText) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="interview-shell__actions">' +
          '<button class="sw-btn sw-btn--primary" id="btn-interview-load-demo" type="button">加载 Demo Case</button>' +
          '<button class="sw-btn" data-script-key="3min" type="button">3min Demo</button>' +
          '<button class="sw-btn" data-script-key="10min" type="button">10min Demo</button>' +
          '<button class="sw-btn" data-open-module="workflow" type="button">Workflow</button>' +
          '<button class="sw-btn" data-open-module="rag" type="button">RAG</button>' +
          '<button class="sw-btn" data-open-module="memory" type="button">Memory</button>' +
          '<button class="sw-btn" data-open-module="mcp" type="button">MCP</button>' +
          '<button class="sw-btn" data-open-module="agent" type="button">Agent</button>' +
          '<button class="sw-btn" data-open-module="failure" type="button">Failure</button>' +
          '<button class="sw-btn" data-open-module="tests" type="button">Tests</button>' +
          '<button class="sw-btn" data-open-module="switches" type="button">Tech Switches</button>' +
          '<button class="sw-btn" id="btn-exit-interview-mode" type="button">退出面试模式</button>' +
        '</div>' +
      "</section>" +
      (state.demoDisclaimer
        ? '<div class="interview-demo-banner" id="interview-demo-banner">' + escapeHtml(state.demoDisclaimer) + "</div>"
        : "") +
      '<section class="interview-shell__grid">' +
        renderInterviewChecklist() +
        '<div class="interview-card interview-card--modules">' +
          '<div class="interview-card__head"><h4>Deep Dive 模块</h4><span class="interview-card__hint">每个模块都绑定代码 / 测试 / 文档入口</span></div>' +
          '<div class="interview-module-grid">' +
            INTERVIEW_MODULES.map(function (item) {
              return '<button class="interview-module-card' + (state.interviewFocus === item.key ? " is-active" : "") + '"' +
                ' data-open-module="' + escapeHtml(item.key) + '" type="button">' +
                '<span class="interview-module-card__title">' + escapeHtml(item.title) + "</span>" +
                '<span class="interview-badge interview-badge--' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + "</span>" +
                '<span class="interview-module-card__summary">' + escapeHtml(item.summary) + "</span>" +
              "</button>";
            }).join("") +
          "</div>" +
        "</div>" +
        '<div class="interview-card interview-card--switches">' +
          '<div class="interview-card__head"><h4>Interview Tech Switches</h4><span class="interview-card__hint">明确区分 on / off / design-only</span></div>' +
          '<div class="interview-switch-grid">' + TECH_SWITCHES.map(techSwitchMarkup).join("") + "</div>" +
        "</div>" +
      "</section>" +
      (state.interviewDrawerOpen ? '<section class="interview-shell__drawer" id="interview-deep-dive-drawer">' + renderInterviewDrawer() + "</section>" : "");
    applyInterviewHighlight();
  }

  function applyInterviewHighlight() {
    [
      { id: "sw-middle-panel", key: "middle" },
      { id: "sw-llm-panel", key: "llm" },
      { id: "sw-trace-panel", key: "trace" },
      { id: "report-workbench-section", key: "report" },
    ].forEach(function (entry) {
      const node = el(entry.id);
      if (!node) return;
      node.classList.toggle("is-interview-focus", interviewEnabled() && state.interviewFocus === entry.key);
    });
  }

  function renderHotspotButtons(panelKey, items) {
    if (!interviewEnabled()) return "";
    return '<div class="interview-hotspots" data-hotspot-panel="' + escapeHtml(panelKey) + '">' +
      items.map(function (item) {
        return '<button class="interview-hotspot' + (state.interviewFocus === item.key ? " is-active" : "") + '"' +
          ' data-open-module="' + escapeHtml(item.key) + '" type="button">' + escapeHtml(item.label) + "</button>";
      }).join("") +
    "</div>";
  }

  function renderCandidateCards(list, stepIdx) {
    if (!list || !list.length) return '<p class="sw-empty">该分组暂无候选。</p>';
    return list.map(function (candidate) {
      const cls = candidate.status === "可用" ? "is-usable" : candidate.status === "待核验" ? "is-pending" : "is-bad";
      return '<div class="sw-candidate-card ' + cls + '" data-candidate-step="' + stepIdx + '">' +
        '<span class="sw-candidate__kind">' + escapeHtml(candidate.kind) + '</span>' +
        '<span class="sw-candidate__title">' + escapeHtml(candidate.title) + '</span>' +
        '<span class="sw-candidate__status">' + escapeHtml(candidate.status) + '</span>' +
      '</div>';
    }).join("");
  }

  function renderCandidatesSubTabs(stepIdx, candidates) {
    const groups = { paper: [], dataset: [], repo: [] };
    (candidates || []).forEach(function (candidate) {
      const key = groups[candidate.kind] ? candidate.kind : "paper";
      groups[key].push(candidate);
    });
    const keys = Object.keys(groups).filter(function (key) { return groups[key].length > 0; });
    if (keys.length <= 1 && (!candidates || candidates.length <= 3)) {
      return renderCandidateCards(candidates || [], stepIdx);
    }
    const labels = { paper: "论文", dataset: "数据集", repo: "工程" };
    const active = defaultSubTab(stepIdx, keys);
    const tabs = keys.map(function (key) {
      return '<button class="sw-subtab ' + (active === key ? "is-active" : "") + '"' +
        ' data-subtab="' + key + '" data-subtab-step="' + stepIdx + '" type="button">' +
        escapeHtml(labels[key]) + " (" + groups[key].length + ")" +
      '</button>';
    }).join("");
    const panels = keys.map(function (key) {
      return '<div class="sw-subpanel ' + (active === key ? "" : "is-hidden") + '"' +
        ' data-subpanel="' + key + '" data-subpanel-step="' + stepIdx + '">' +
        renderCandidateCards(groups[key], stepIdx) +
      '</div>';
    }).join("");
    return '<div class="sw-subtabs" data-subtabs-for="' + stepIdx + '">' + tabs + '</div>' +
      '<div class="sw-subpanels" data-subpanels-for="' + stepIdx + '">' + panels + '</div>';
  }

  function renderStepBody(step) {
    const idx = step.index;
    if (step.status === STATUS.LOCKED) {
      return '<div class="sw-step__locked">先完成前一阶段确认后，这一步才会解锁。</div>';
    }
    const result = step.result;
    const staleBanner = step.status === STATUS.STALE
      ? '<div class="sw-stale-banner">该步骤已 stale。' + escapeHtml(step.staleReason || "前序内容已修改，请重新生成。") + '</div>'
      : "";
    if (step.status === STATUS.RUNNING && !result) {
      return staleBanner + '<div class="sw-streaming">正在生成当前步骤内容...</div>';
    }
    if (!result) {
      return staleBanner + '<div class="sw-empty">本步骤暂无内容。</div>';
    }
    if (idx === 0) {
      return staleBanner +
        '<dl class="sw-kv">' +
          '<dt>方向</dt><dd>' + escapeHtml(result.direction) + '</dd>' +
          '<dt>任务类型</dt><dd>' + escapeHtml(result.task_type) + '</dd>' +
          '<dt>研究对象</dt><dd>' + escapeHtml(result.possible_object) + '</dd>' +
          '<dt>技术路线</dt><dd>' + escapeHtml(result.possible_route) + '</dd>' +
          '<dt>模糊词</dt><dd>' + escapeHtml((result.ambiguous_terms || []).join("、")) + '</dd>' +
        '</dl>';
    }
    if (idx === 1) {
      function chips(items) {
        return (items || []).map(function (item) {
          return '<span class="sw-chip">' + escapeHtml(item) + '</span>';
        }).join("");
      }
      return staleBanner +
        '<div class="sw-kw-group"><label>方法</label><div class="sw-chips">' + chips(result.method) + '</div></div>' +
        '<div class="sw-kw-group"><label>任务</label><div class="sw-chips">' + chips(result.task) + '</div></div>' +
        '<div class="sw-kw-group"><label>对象</label><div class="sw-chips">' + chips(result.object) + '</div></div>' +
        '<div class="sw-kw-group"><label>替代词</label><div class="sw-chips">' + chips(result.alternatives) + '</div></div>';
    }
    if (idx === 2) {
      return staleBanner +
        '<div class="sw-summary">' + escapeHtml(result.summary) + '</div>' +
        renderCandidatesSubTabs(idx, result.candidates || []);
    }
    if (idx === 3) {
      return staleBanner +
        '<div class="sw-verdict ' + (result.can_do ? "is-yes" : "is-no") + '">' + (result.can_do ? "可做" : "需收缩") + '</div>' +
        '<dl class="sw-kv">' +
          '<dt>能做理由</dt><dd>' + escapeHtml(result.why_yes) + '</dd>' +
          '<dt>数据集风险</dt><dd>' + escapeHtml(result.dataset_risk) + '</dd>' +
          '<dt>复现风险</dt><dd>' + escapeHtml(result.reproduce_risk) + '</dd>' +
          '<dt>工程风险</dt><dd>' + escapeHtml(result.engineering_risk) + '</dd>' +
          '<dt>创新空间</dt><dd>' + escapeHtml(result.innovation_space) + '</dd>' +
        '</dl>';
    }
    return staleBanner +
      '<div class="sw-proposal-title">' + escapeHtml(result.recommended_topic) + '</div>' +
      '<dl class="sw-kv">' +
        '<dt>研究背景</dt><dd>' + escapeHtml(result.background) + '</dd>' +
        '<dt>研究内容</dt><dd>' + escapeHtml(result.content) + '</dd>' +
        '<dt>技术路线</dt><dd>' + escapeHtml(result.route) + '</dd>' +
        '<dt>可行性</dt><dd>' + escapeHtml(result.feasibility) + '</dd>' +
        '<dt>风险预案</dt><dd>' + escapeHtml(result.risk_plan) + '</dd>' +
        '<dt>低门槛审核</dt><dd>' + escapeHtml(result.low_bar_pass) + '</dd>' +
      '</dl>';
  }

  function renderMiddlePanel() {
    const wrap = el("sw-middle-panel");
    if (!wrap) return;
    const step = state.steps[state.activeStepIndex] || state.steps[0];
    let gateHtml = "";
    if (step.gateQuestion && (step.status === STATUS.PAUSED || step.status === STATUS.NEEDS_REVISION)) {
      state.gateState = { step: step.index, question: step.gateQuestion };
      gateHtml =
        '<div class="sw-gate">' +
          '<div class="sw-gate__label">等待确认</div>' +
          '<div class="sw-gate__q">' + escapeHtml(step.gateQuestion) + '</div>' +
          '<div class="sw-gate__actions">' +
            '<button class="sw-btn sw-btn--primary" id="sw-approve-btn" type="button">确认并进入下一步</button>' +
            '<button class="sw-btn" id="sw-revise-btn" type="button">重跑当前步骤</button>' +
          '</div>' +
        '</div>';
    } else if (step.status === STATUS.COMPLETED) {
      gateHtml = '<div class="sw-gate-note">这一步已经确认完成。</div>';
    } else if (step.status === STATUS.STALE) {
      gateHtml = '<div class="sw-gate-note sw-gate-note--warn">前序内容已改动，建议回到这一段重新生成。</div>';
    }

    wrap.innerHTML =
      renderHotspotButtons("middle", [
        { key: "workflow", label: "Workflow" },
        { key: "middle", label: "Step Gate" },
        { key: "rag", label: "RAG" },
      ]) +
      '<div class="sw-pager-row">' +
        '<button class="sw-nav-btn" id="sw-prev-btn" type="button"' + (state.activeStepIndex === 0 ? " disabled" : "") + '>上一页</button>' +
        '<div class="sw-step-pager" id="sw-step-pager">' +
          state.steps.map(function (item, idx) {
            const classes = [
              "sw-pager-dot",
              idx === state.activeStepIndex ? "is-current" : "",
              item.status === STATUS.LOCKED ? "is-locked" : "",
              item.status === STATUS.STALE ? "is-stale" : "",
            ].filter(Boolean).join(" ");
            return '<button class="' + classes + '" data-pager-index="' + idx + '" type="button">' + (idx + 1) + '</button>';
          }).join("") +
        '</div>' +
        '<button class="sw-nav-btn" id="sw-next-btn" type="button"' + (state.activeStepIndex === state.steps.length - 1 ? " disabled" : "") + '>下一页</button>' +
      '</div>' +
      '<header class="sw-step-head">' +
        '<span class="sw-step__icon">' + escapeHtml(step.icon) + '</span>' +
        '<h3 class="sw-step__title" id="sw-step-title">' + escapeHtml(step.title) + '</h3>' +
        '<span class="sw-step__status sw-step__status--' + step.status + '">' + STATUS_LABEL[step.status] + '</span>' +
      '</header>' +
      '<div class="sw-step__body" data-step-index="' + step.index + '">' + renderStepBody(step) + '</div>' +
      gateHtml;
  }

  function buildTraceGroups() {
    const groups = [{ key: "session", label: "Session", step: null, events: [] }];
    STEPS.forEach(function (step) {
      groups.push({
        key: "step-" + step.index,
        label: "Step " + (step.index + 1) + "：" + step.title,
        step: step.index,
        events: [],
      });
    });
    state.evidenceTrace.forEach(function (event) {
      if (typeof event.step === "number" && groups[event.step + 1]) {
        groups[event.step + 1].events.push(event);
      } else {
        groups[0].events.push(event);
      }
    });
    return groups;
  }

  function defaultTraceOpen(group) {
    if (Object.prototype.hasOwnProperty.call(state.traceGroupOpen, group.key)) {
      return state.traceGroupOpen[group.key];
    }
    if (group.step === null) return true;
    const step = state.steps[group.step];
    return step.status === STATUS.RUNNING || step.status === STATUS.PAUSED || step.status === STATUS.NEEDS_REVISION || step.status === STATUS.STALE;
  }

  function renderTracePanel() {
    const wrap = el("sw-trace-panel");
    if (!wrap) return;
    const groups = buildTraceGroups();
    const html = groups.map(function (group) {
      const step = group.step === null ? null : state.steps[group.step];
      const open = defaultTraceOpen(group);
      const evidenceCount = group.events.filter(function (event) { return event.kind === "evidence_event"; }).length;
      const statusText = step ? STATUS_LABEL[step.status] : "session";
      const headerClass = step ? " sw-trace-group__toggle--" + step.status : "";
      const bodyHtml = group.events.length
        ? group.events.map(function (event) {
            return '<div class="sw-trace__row sw-trace__row--' + event.kind + '">' +
              '<span class="sw-trace__icon">' + escapeHtml(event.kind === "evidence_event" ? "E" : event.kind === "user_edit" ? "U" : "T") + '</span>' +
              '<span class="sw-trace__text">' + escapeHtml(event.text) + '</span>' +
            '</div>';
          }).join("")
        : '<div class="sw-empty">暂无记录。</div>';
      return '<section class="sw-trace-group" data-trace-group="' + group.key + '">' +
        '<button class="sw-trace-group__toggle' + headerClass + '" data-trace-toggle="' + group.key + '" type="button">' +
          '<span class="sw-trace-group__chevron">' + (open ? "▼" : "▶") + '</span>' +
          '<span class="sw-trace-group__title">' + escapeHtml(group.label) + '</span>' +
          '<span class="sw-trace-group__meta">' + escapeHtml(statusText) + " · " + group.events.length + " events · " + evidenceCount + " evidence</span>" +
        '</button>' +
        '<div class="sw-trace-group__body' + (open ? "" : " is-hidden") + '">' + bodyHtml + '</div>' +
      '</section>';
    }).join("");
    wrap.innerHTML =
      renderHotspotButtons("trace", [
        { key: "memory", label: "Memory" },
        { key: "trace", label: "Trace" },
        { key: "evidence", label: "Evidence" },
      ]) +
      '<header class="sw-panel__head"><h3>证据 Trace</h3>' +
        '<span class="sw-panel__hint">当前运行：' + escapeHtml(state.currentRuntimeStep >= 0 ? "Step " + (state.currentRuntimeStep + 1) : "未开始") + '</span></header>' +
      '<div class="sw-trace-panel__list" id="sw-trace-list">' + html + '</div>';
  }

  function isWorkbenchReadyForExport() {
    return state.steps[4].status === STATUS.COMPLETED && !state.steps.some(function (step) {
      return step.status === STATUS.STALE;
    });
  }

  function syncReportSection() {
    const wb = el("step-workbench");
    const reportWrap = el("report-workbench-section");
    if (!wb || !reportWrap || wb.hidden) return;
    reportWrap.hidden = false;
    const hint = el("report-workbench-hint");
    const btn = el("btn-build-report");
    const stepReady = isWorkbenchReadyForExport();
    const ready = stepReady && state.projectBound;
    const statusMeta = el("report-workbench-meta");
    if (hint) {
      if (stepReady && !state.projectBound) {
        hint.textContent = "Step 1-5 已完成，但当前只是演示快照；真实导出需要先绑定后端 project。";
      } else if (ready && state.backendReachable === false) {
        hint.textContent = "Step 1-5 已完成，但后端 18181 当前不可用；可以继续演示流程，导出会给出离线提示。";
      } else if (ready) {
        hint.textContent = "Step 1-5 已完成，可以导出 Markdown。";
      } else if (state.steps.some(function (step) { return step.status === STATUS.STALE; })) {
        hint.textContent = "前序内容已修改，导出前请先重跑受影响步骤。";
      } else {
        hint.textContent = "这里只保留 Step 6 导出区；完成 Step 5 后即可启用。";
      }
    }
    if (statusMeta) {
      statusMeta.textContent = state.backendReachable === false
        ? "当前后端状态：offline"
        : state.backendReachable === true
          ? "当前后端状态：ready"
          : "当前后端状态：unknown";
    }
    if (btn) btn.disabled = !ready;
  }

  function renderPreviewCard(command) {
    if (!command) return "";
    const affected = (command.affectedSteps || []).map(function (idx) {
      return "Step " + (idx + 1);
    }).join("、") || "无";
    return '<section class="sw-preview-card" id="sw-preview-card">' +
      '<div class="sw-preview-card__title">修改预览</div>' +
      '<div class="sw-preview-card__row"><strong>操作</strong><span>' + escapeHtml(command.intent + " " + command.targetType) + '</span></div>' +
      '<div class="sw-preview-card__row"><strong>对象</strong><span>' + escapeHtml(command.targetLabel) + '</span></div>' +
      '<div class="sw-preview-card__row"><strong>修改前</strong><span>' + escapeHtml(command.beforeText) + '</span></div>' +
      '<div class="sw-preview-card__row"><strong>修改后</strong><span>' + escapeHtml(command.afterText) + '</span></div>' +
      '<div class="sw-preview-card__row"><strong>影响</strong><span>' + escapeHtml(affected) + '</span></div>' +
      '<div class="sw-preview-card__row"><strong>说明</strong><span>' + escapeHtml(command.reason || "所有写操作都要先确认。") + '</span></div>' +
      '<div class="sw-preview-card__actions">' +
        '<button class="sw-btn sw-btn--primary" id="sw-preview-confirm" type="button">确认修改</button>' +
        '<button class="sw-btn" id="sw-preview-cancel" type="button">取消</button>' +
      '</div>' +
    '</section>';
  }

  function renderChatComposer() {
    return '<div class="sw-chat-composer">' +
      '<div class="sw-chat-modes">' +
        '<button class="sw-chat-mode ' + (state.chatMode === "ask" ? "is-active" : "") + '" id="sw-chat-mode-ask" type="button">仅讨论</button>' +
        '<button class="sw-chat-mode ' + (state.chatMode === "suggest" ? "is-active" : "") + '" id="sw-chat-mode-suggest" type="button">生成修改建议</button>' +
      '</div>' +
      '<textarea class="sw-chat-input" id="sw-chat-input" rows="3" placeholder="和工作台讨论，或输入修改请求...">' + escapeHtml(state.chatDraft) + '</textarea>' +
      '<div class="sw-chat-actions">' +
        '<button class="sw-btn sw-btn--primary" id="sw-chat-send" type="button">发送</button>' +
      '</div>' +
    '</div>';
  }

  function renderLlmPanel() {
    const wrap = el("sw-llm-panel");
    if (!wrap) return;
    const runningStep = state.currentRuntimeStep >= 0 ? state.steps[state.currentRuntimeStep] : null;
    const phase = !runningStep ? "空闲" : "Step " + (runningStep.index + 1) + " · " + STATUS_LABEL[runningStep.status];
    const history = state.llmTimeline.length
      ? state.llmTimeline.slice(-40).map(function (msg) {
          const cls = "sw-llm__row sw-llm__row--" + msg.kind;
          const tag = msg.kind === "user_message" ? "你" : msg.kind === "assistant_reply" ? "AI" : msg.kind === "assistant_thought" ? "思" : msg.kind === "gate_question" ? "问" : "记";
          return '<div class="' + cls + '">' +
            '<span class="sw-llm__tag">' + escapeHtml(tag) + '</span>' +
            '<span class="sw-llm__text">' + escapeHtml(msg.text) + '</span>' +
          '</div>';
        }).join("")
      : '<div class="sw-empty">这里会持续显示 LLM 思考、对话和修改预览。</div>';
    const tools = state.toolUseTimeline.length
      ? '<div class="sw-llm__tools">' +
          '<header class="sw-llm__tools-head">页面访问 / Skill / 工具调用</header>' +
          state.toolUseTimeline.slice(-20).map(function (call) {
            return '<div class="sw-llm__row sw-llm__row--tool_use">' +
              '<span class="sw-llm__tag">工</span>' +
              '<span class="sw-llm__text"><strong>' + escapeHtml(call.tool) + '</strong>' +
                (call.source ? " · " + escapeHtml(call.source) : "") +
                " · " + escapeHtml(call.purpose) +
              '</span>' +
            '</div>';
          }).join("") +
        '</div>'
      : "";
    wrap.innerHTML =
      renderHotspotButtons("llm", [
        { key: "workflow", label: "WorkspaceCommand" },
        { key: "llm", label: "对话入口" },
        { key: "agent", label: "Agent" },
      ]) +
      '<header class="sw-panel__head"><h3>LLM 思维 / 对话</h3>' +
        '<span class="sw-panel__phase" id="sw-llm-phase">' + escapeHtml(phase) + '</span></header>' +
      '<div class="sw-llm-shell">' +
        '<div class="sw-llm__list" id="sw-llm-list">' +
          history +
          tools +
          renderPreviewCard(state.commandPreview) +
        '</div>' +
        renderChatComposer() +
      '</div>';
  }

  function renderAll() {
    renderMiddlePanel();
    renderTracePanel();
    renderLlmPanel();
    syncInterviewShell();
    syncReportSection();
  }

  function onMiddleClick(event) {
    const target = event.target;
    if (!target || !target.getAttribute) return;
    if (target.id === "sw-prev-btn") { prevPage(); return; }
    if (target.id === "sw-next-btn") { nextPage(); return; }
    if (target.id === "sw-approve-btn") { approveCurrent(); return; }
    if (target.id === "sw-revise-btn") { reviseCurrent(); return; }
    const subtab = target.getAttribute("data-subtab");
    if (subtab) {
      const stepIdx = parseInt(target.getAttribute("data-subtab-step") || "-1", 10);
      if (stepIdx >= 0) {
        state.subTabs[stepIdx] = subtab;
        renderMiddlePanel();
      }
      return;
    }
    const pagerIdx = target.getAttribute("data-pager-index");
    if (pagerIdx !== null) {
      const idx = parseInt(pagerIdx, 10);
      if (state.steps[idx] && state.steps[idx].status !== STATUS.LOCKED) goToPage(idx);
      return;
    }
    const moduleKey = target.getAttribute("data-open-module");
    if (moduleKey) {
      state.interviewDrawerOpen = true;
      setInterviewFocus(moduleKey, true);
    }
  }

  function onTraceClick(event) {
    const target = event.target && event.target.closest ? event.target.closest("[data-trace-toggle], [data-open-module]") : null;
    if (!target) return;
    const key = target.getAttribute("data-trace-toggle");
    if (key) {
      state.traceGroupOpen[key] = !defaultTraceOpen({ key: key, step: key === "session" ? null : parseInt(key.split("-")[1], 10) });
      renderTracePanel();
      return;
    }
    const moduleKey = target.getAttribute("data-open-module");
    if (moduleKey) {
      state.interviewDrawerOpen = true;
      setInterviewFocus(moduleKey, true);
    }
  }

  function buildAskReply(text) {
    const lowered = text.toLowerCase();
    const feasibility = state.steps[3].result;
    if (lowered.indexOf("为什么") >= 0 || lowered.indexOf("为啥") >= 0) {
      if (feasibility) {
        return "目前判断“能做”，因为已经有公开数据集、可复用 baseline 和可解释的工程路径；主要风险是数据规模和后处理设计。";
      }
      return "我还没完成可行性判断，但从前两步看，这个题目的方法、任务和对象已经能形成清晰检索路径。";
    }
    if (interviewEnabled() && lowered.indexOf("面试") >= 0) {
      return "如果你要面试讲解，建议先加载 Demo Case，再用上方 3 分钟脚本串 Workflow、Trace、WorkspaceCommand 和导出前检查。";
    }
    return "我会先保持工作台数据不变，只把这条消息当成讨论问题；如果你希望真正改动关键词或证据，请切到“生成修改建议”。";
  }

  function findPrimaryKeyword() {
    const step1 = state.steps[0].result;
    const step2 = state.steps[1].result;
    return {
      currentObject: step2 && step2.object && step2.object[0]
        ? step2.object[0]
        : step1 && step1.possible_object
          ? step1.possible_object
          : "对象关键词",
    };
  }

  function buildCommandPreview(text) {
    const keywordMatch = text.match(/把(.+?)改成(.+)/);
    if (keywordMatch) {
      const keywords = findPrimaryKeyword();
      const nextValue = keywordMatch[2].trim().replace(/[。！!]+$/, "");
      return {
        intent: "update",
        targetType: "keyword",
        targetLabel: "Step 2 / 对象关键词",
        beforeText: keywords.currentObject,
        afterText: nextValue,
        affectedSteps: [2, 3, 4],
        reason: "修改关键词会让后续检索、可行性和开题建议失效，需要重新生成。",
        payload: { kind: "keyword_object", value: nextValue },
      };
    }

    if (/删除|排除|不推荐/.test(text) && /证据|论文|数据集|工程|GitHub/.test(text)) {
      const step2 = state.steps[2].result;
      const candidates = step2 && step2.candidates ? step2.candidates : [];
      const candidate = candidates[0] || null;
      if (!candidate) return null;
      return {
        intent: "reject",
        targetType: "evidence",
        targetLabel: "Step 3 / " + candidate.title,
        beforeText: candidate.status,
        afterText: "rejected",
        affectedSteps: [3, 4],
        reason: "这里只做软删除，保留 Trace，不做物理删除。",
        payload: { kind: "candidate_reject", candidateId: candidate.id || candidate.title },
      };
    }
    return null;
  }

  function markAffectedStepsStale(indices, reason) {
    (indices || []).forEach(function (idx) {
      if (!state.steps[idx]) return;
      state.steps[idx].status = STATUS.STALE;
      state.steps[idx].staleReason = reason;
      state.traceGroupOpen["step-" + idx] = true;
    });
  }

  function applyCommandPreview(command) {
    if (!command) return;
    if (command.payload.kind === "keyword_object") {
      if (state.steps[0].result) state.steps[0].result.possible_object = command.afterText;
      if (state.steps[1].result && state.steps[1].result.object && state.steps[1].result.object.length) {
        state.steps[1].result.object[0] = command.afterText;
      }
      appendTrace("user_edit", "用户通过对话更新对象关键词：" + command.beforeText + " -> " + command.afterText, 1);
      markAffectedStepsStale(command.affectedSteps, "对象关键词已修改。");
      appendLlm("assistant_reply", "修改已应用：对象关键词已更新，Step 3-5 已标记为 stale。", 1);
    } else if (command.payload.kind === "candidate_reject") {
      const result = state.steps[2].result;
      if (result && result.candidates) {
        result.candidates.forEach(function (candidate) {
          if ((candidate.id || candidate.title) === command.payload.candidateId) {
            candidate.status = "不推荐";
            candidate.removal_state = "rejected";
          }
        });
      }
      appendTrace("user_edit", "用户通过对话将证据标记为 rejected：" + command.targetLabel, 2);
      markAffectedStepsStale(command.affectedSteps, "证据状态已修改。");
      appendLlm("assistant_reply", "修改已应用：证据已软删除为 rejected，并保留 Trace 记录。", 2);
    }
    state.commandPreview = null;
    renderAll();
  }

  function sendChatMessage() {
    const text = (state.chatDraft || "").trim();
    if (!text) return;
    appendLlm("user_message", text, state.activeStepIndex);
    state.chatDraft = "";

    if (state.chatMode === "ask") {
      appendLlm("assistant_reply", buildAskReply(text), state.activeStepIndex);
      renderLlmPanel();
      return;
    }

    const preview = buildCommandPreview(text);
    if (!preview) {
      appendLlm("assistant_reply", "我暂时只识别关键词改写和证据软删除两类写操作。你也可以先用“仅讨论”继续澄清。", state.activeStepIndex);
      renderLlmPanel();
      return;
    }
    preview.sourceMessage = text;
    state.commandPreview = preview;
    appendLlm("assistant_reply", "我已生成修改预览。确认前，工作台数据不会变化。", state.activeStepIndex);
    renderLlmPanel();
  }

  function onLlmInput(event) {
    const target = event.target;
    if (!target || target.id !== "sw-chat-input") return;
    state.chatDraft = target.value;
  }

  function onLlmClick(event) {
    const target = event.target && event.target.closest ? event.target.closest("button") : event.target;
    if (!target) return;
    if (target.id === "sw-chat-send") { sendChatMessage(); return; }
    if (target.id === "sw-chat-mode-ask") { state.chatMode = "ask"; renderLlmPanel(); return; }
    if (target.id === "sw-chat-mode-suggest") { state.chatMode = "suggest"; renderLlmPanel(); return; }
    if (target.id === "sw-preview-confirm") { applyCommandPreview(state.commandPreview); return; }
    if (target.id === "sw-preview-cancel") {
      state.commandPreview = null;
      appendLlm("assistant_reply", "已取消这次修改预览，工作台保持不变。", state.activeStepIndex);
      renderLlmPanel();
      return;
    }
    const moduleKey = target.getAttribute("data-open-module");
    if (moduleKey) {
      state.interviewDrawerOpen = true;
      setInterviewFocus(moduleKey, true);
    }
  }

  function onLlmKeydown(event) {
    const target = event.target;
    if (!target || target.id !== "sw-chat-input") return;
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      sendChatMessage();
    }
  }

  function onInterviewShellClick(event) {
    const target = event.target && event.target.closest ? event.target.closest("button") : event.target;
    if (!target) return;
    if (target.id === "btn-interview-load-demo") { loadDemoCase(); return; }
    if (target.id === "btn-exit-interview-mode") {
      setInterviewMode(false);
      return;
    }
    const scriptKey = target.getAttribute("data-script-key");
    if (scriptKey) {
      state.interviewScriptKey = scriptKey;
      state.interviewDrawerOpen = false;
      syncInterviewShell();
      return;
    }
    const focus = target.getAttribute("data-script-focus");
    if (focus) {
      state.interviewDrawerOpen = ["rag", "memory", "agent", "failure", "tests", "workflow"].indexOf(focus) >= 0;
      setInterviewFocus(focus, state.interviewDrawerOpen);
      return;
    }
    const moduleKey = target.getAttribute("data-open-module");
    if (moduleKey) {
      state.interviewDrawerOpen = true;
      setInterviewFocus(moduleKey, true);
    }
  }

  function onKeydown(event) {
    const wb = el("step-workbench");
    if (!wb || wb.hidden) return;
    if (document.activeElement && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName || "")) return;
    if (event.key === "ArrowLeft") prevPage();
    else if (event.key === "ArrowRight") nextPage();
    else if (event.key === "Enter" && state.gateState) approveCurrent();
  }

  let inited = false;
  function init() {
    if (inited) return;
    inited = true;
    const middle = el("sw-middle-panel");
    const trace = el("sw-trace-panel");
    const llm = el("sw-llm-panel");
    const shell = el("interview-shell");
    if (middle) middle.addEventListener("click", onMiddleClick);
    if (trace) trace.addEventListener("click", onTraceClick);
    if (llm) {
      llm.addEventListener("click", onLlmClick);
      llm.addEventListener("input", onLlmInput);
      llm.addEventListener("keydown", onLlmKeydown);
    }
    if (shell) shell.addEventListener("click", onInterviewShellClick);
    document.addEventListener("keydown", onKeydown);
    showInterviewModeFromUrl();
    renderAll();
  }

  global.StepWorkbench = {
    state: state,
    STEPS: STEPS,
    STATUS: STATUS,
    STATUS_LABEL: STATUS_LABEL,
    INTERVIEW_MODE: INTERVIEW_MODE,
    init: init,
    startWorkbench: startWorkbench,
    loadDemoCase: loadDemoCase,
    resetState: resetState,
    approveCurrent: approveCurrent,
    reviseCurrent: reviseCurrent,
    prevPage: prevPage,
    nextPage: nextPage,
    goToPage: goToPage,
    setInterviewMode: setInterviewMode,
    setInterviewFocus: setInterviewFocus,
    setBackendReachable: setBackendReachable,
    bindProject: bindProject,
    renderAll: renderAll,
    isReady: function () { return inited; },
  };
})(window);
