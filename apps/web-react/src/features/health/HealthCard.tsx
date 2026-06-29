// Session 52: Health 卡片 — 展示后端探测三态
import type { HealthState } from "./useHealth";

interface Props {
  state: HealthState;
}

export function HealthCard({ state }: Props) {
  if (state.status === "loading") {
    return (
      <div className="card" data-testid="health-loading">
        <div className="card-title">后端健康</div>
        <div className="card-body muted">探测中…</div>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="card" data-testid="health-error">
        <div className="card-title">后端健康</div>
        <div className="card-body error">
          不可达{state.statusCode ? ` (HTTP ${state.statusCode})` : ""}
          <div className="muted small">{state.message}</div>
        </div>
      </div>
    );
  }
  const payload = state.payload as { status?: string; phase?: string };
  return (
    <div className="card" data-testid="health-ok">
      <div className="card-title">后端健康</div>
      <div className="card-body">
        <span className="badge ok">OK</span>{" "}
        <span className="muted">
          {payload.phase ?? "—"} · {state.latencyMs}ms
        </span>
      </div>
    </div>
  );
}
