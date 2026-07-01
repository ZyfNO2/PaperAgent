// Session 57: HomePage → OpenCode 化首页
// - 大留白 hero + 单句主张
// - 黑色主按钮「进入工作台」 + 次按钮「加载面试 Demo」
// - 三组能力数据区 (使用项目真实数据, 不编造 Star / 月活)
// - 隐私 / 本地 / 证据可追踪说明
import { useHealth } from "../health/useHealth";
import { HealthCard } from "../health/HealthCard";
import { TracePanel, type TraceEntry } from "../../components/layout/TracePanel";

const TRACE_ENTRIES: TraceEntry[] = [
  { id: "intake", label: "ProjectIntake", state: "done", hint: "S18" },
  { id: "topic", label: "TopicSpec", state: "done", hint: "S19" },
  { id: "plan", label: "SearchQueryPlan", state: "done", hint: "S20" },
  { id: "rag", label: "PaperRAG 检索", state: "done", hint: "S47" },
  { id: "ground", label: "Claim Grounding", state: "done", hint: "S48" },
  { id: "thesis", label: "ThesisEval", state: "done", hint: "S51" },
];

export function HomePage() {
  const health = useHealth();
  return (
    <>
      <TracePanel entries={TRACE_ENTRIES} testId="trace-panel" />
      <div className="pa-main-stage" data-testid="home-main">
        <section className="pa-hero" data-testid="home-hero">
          <span className="pa-hero__eyebrow">PaperAgent · v0.1 · Session 57</span>
          <h1 className="pa-hero__title">
            面向毕业选题与论文复现的 AI 证据工作台
          </h1>
          <p className="pa-hero__sub">
            输入一个题目，系统会拆关键词、检索证据、判断资源可行性、生成开题建议。
            每一步的来源都可回溯到论文 / 数据集 / 仓库的真实条目，不允许编造。
          </p>
          <div className="pa-hero__cta">
            <a
              href="#/"
              className="pa-hero__cta-primary"
              data-testid="home-cta-workbench"
            >
              进入工作台 →
            </a>
            <a
              href="#/?mode=interview&demo=case1"
              className="pa-hero__cta-secondary"
              data-testid="home-cta-demo"
            >
              加载面试 Demo
            </a>
            <a
              href="http://127.0.0.1:18183/health"
              className="pa-hero__cta-secondary"
              target="_blank"
              rel="noreferrer"
              data-testid="home-cta-health"
            >
              /health
            </a>
          </div>
        </section>

        <section
          className="pa-zone-grid"
          data-testid="home-zones"
          aria-label="capabilities"
        >
          <article className="pa-zone" data-testid="zone-rag">
            <span className="pa-zone__cap">图 1 · RAG 评估基线 (S50)</span>
            <h3 className="pa-zone__title">11 项检索 / 引用指标</h3>
            <p className="pa-zone__body">
              Recall@5 / MRR / NDCG / citation_precision /
              evidence_coverage / unsupported_claim_rate / faithfulness …
              每条都有基线文件和回归门, 数据来自 Session 50
              的 5 篇论文 / 12 道题 fixture。
            </p>
          </article>
          <article className="pa-zone" data-testid="zone-thesis">
            <span className="pa-zone__cap">图 2 · ThesisEval 数据集 (S51)</span>
            <h3 className="pa-zone__title">100 篇工科学位论文</h3>
            <p className="pa-zone__body">
              按章节拆为 4 个子集 (摘要 / 章节 / 引用 / 附录),
              配 verified / partial / failed 三态评级; 离线评估,
              不依赖真实 LLM 网络。
            </p>
          </article>
          <article className="pa-zone" data-testid="zone-interview">
            <span className="pa-zone__cap">图 3 · Interview Mode (S54)</span>
            <h3 className="pa-zone__title">8 项技术开关 + 9 个深挖问题</h3>
            <p className="pa-zone__body">
              Tech Switches 显式标注 implemented / lightweight /
              design-only, Deep Dive 用问答对展示真实能答的题与不能答的题;
              ACP 协议仍为设计稿状态, 保持诚实边界。
            </p>
          </article>
        </section>

        <section
          className="pa-doc-section"
          data-testid="home-system-status"
          aria-label="system status"
        >
          <h2 className="pa-doc-section__title">系统状态</h2>
          <div className="pa-doc-section__body">
            <div data-testid="card-health">
              <HealthCard state={health} />
            </div>
          </div>
        </section>

        <section className="pa-privacy" data-testid="home-privacy">
          <h3 className="pa-privacy__title">隐私 / 本地 / 可追踪</h3>
          <div className="pa-privacy__items">
            <div className="pa-privacy__item">
              <span className="pa-privacy__cap">本地优先</span>
              <span className="pa-privacy__text">
                所有评估 (RAG / ThesisEval) 默认离线; LLM 路径只在显式启用
                <code> MINIMAX_API_KEY </code> 时调用, 且配 heuristic 兜底。
              </span>
            </div>
            <div className="pa-privacy__item">
              <span className="pa-privacy__cap">证据可回溯</span>
              <span className="pa-privacy__text">
                每个结论必须挂 evidence_ref; 引用不全直接 409,
                不会被前端渲染。
              </span>
            </div>
            <div className="pa-privacy__item">
              <span className="pa-privacy__cap">诚实边界</span>
              <span className="pa-privacy__text">
                设计稿 / 未接入能力会明确标 design-only,
                不会伪装成 production ready。
              </span>
            </div>
          </div>
        </section>
      </div>
      <></>
    </>
  );
}