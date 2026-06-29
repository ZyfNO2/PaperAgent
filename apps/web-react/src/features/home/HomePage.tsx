// Session 52: Home 页 — 健康/迁移阶段/旧前端入口/S50-S51 占位
import { APP_CONFIG } from "../../app/config";
import { useHealth } from "../health/useHealth";
import { HealthCard } from "../health/HealthCard";

export function HomePage() {
  const health = useHealth();

  return (
    <div className="home">
      <h2 className="page-title">{APP_CONFIG.migrationPhase}</h2>
      <p className="muted small">
        新前端 <code>apps/web-react</code> 已就位。旧{" "}
        <code>apps/web</code> 暂不删除, 保持回滚路径。
      </p>

      <div className="cards">
        <HealthCard state={health} />

        <div className="card" data-testid="phase-card">
          <div className="card-title">迁移阶段</div>
          <div className="card-body">
            <ul className="phase-list">
              <li>
                <span className="badge done">S52 ✓</span> 脚手架与迁移基线
              </li>
              <li>
                <span className="badge todo">S53</span> 设计系统 + 三栏工作台组件化
              </li>
              <li>
                <span className="badge todo">S54</span> StepWorkbench / Interview Mode 迁移
              </li>
              <li>
                <span className="badge todo">S55</span> RAG / 论文库 / ThesisEval 前端接入
              </li>
              <li>
                <span className="badge todo">S56</span> 切换 + 回归 + 旧前端收口
              </li>
            </ul>
          </div>
        </div>

        <div className="card" data-testid="legacy-card">
          <div className="card-title">旧前端入口</div>
          <div className="card-body">
            <a href={APP_CONFIG.legacyWebUrl}>→ {APP_CONFIG.legacyWebUrl}</a>
            <div className="muted small">
              旧前端继续保留, 用于回滚与对照, 直到 S56 决定收口策略。
            </div>
          </div>
        </div>

        <div className="card" data-testid="s50-card">
          <div className="card-title">S50 · RAG 评估</div>
          <div className="card-body muted small">
            recall@5 / MRR / citation_precision 等 7 指标 + 回归基线。
            S55 接入完整界面。
          </div>
        </div>

        <div className="card" data-testid="s51-card">
          <div className="card-title">S51 · ThesisEval</div>
          <div className="card-body muted small">
            100 篇工科学位论文测试集, 4 任务评估闭环。
            S55 接入完整界面。
          </div>
        </div>
      </div>
    </div>
  );
}
