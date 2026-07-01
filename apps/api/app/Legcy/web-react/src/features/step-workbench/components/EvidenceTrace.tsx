// Session 54: EvidenceTrace — 左侧 Trace 列表, 5 类 kind 区分
import { Badge } from "../../../components/ui/Badge";
import type { TraceEvent } from "../stepTypes";

interface Props {
  events: TraceEvent[];
  testId?: string;
}

const KIND_TONE: Record<string, "ok" | "warn" | "err" | "info" | "neutral"> = {
  step_start: "info",
  step_pause: "warn",
  step_complete: "ok",
  step_revise: "warn",
  step_fail: "err",
  step_stale: "err",
  evidence_event: "info",
  user_confirm: "ok",
  run_done: "ok",
  demo_case: "info",
};

export function EvidenceTrace({ events, testId }: Props) {
  return (
    <div className="pa-evidence-trace" data-testid={testId ?? "evidence-trace"}>
      <div className="pa-evidence-trace__title">Trace / 证据收集</div>
      {events.length === 0 ? (
        <div className="pa-muted pa-small">暂无事件, 切换步骤或加载 Demo Case 触发。</div>
      ) : (
        <ul className="pa-evidence-trace__list">
          {events.map((e) => (
            <li
              key={e.seq}
              className="pa-evidence-trace__item"
              data-testid={`trace-evt-${e.seq}`}
            >
              <Badge tone={KIND_TONE[e.kind] ?? "neutral"} testId={`trace-tone-${e.seq}`}>
                {e.kind}
              </Badge>
              <span className="pa-evidence-trace__text pa-small">{e.text}</span>
              {e.step !== null ? (
                <span className="pa-faint pa-tiny">step {e.step + 1}</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
