// Session 53: TracePanel — 左侧 Trace / 证据收集进度
// 故意不随 MainStage unmount, 保持滚动/折叠状态
import { Badge } from "../ui/Badge";
import { Collapse } from "../ui/Collapse";

export interface TraceEntry {
  id: string;
  label: string;
  state: "done" | "active" | "pending" | "err";
  hint?: string;
}

export interface TracePanelProps {
  title?: string;
  entries: TraceEntry[];
  testId?: string;
}

export function TracePanel({
  title = "Trace / 证据收集",
  entries,
  testId,
}: TracePanelProps) {
  return (
    <aside
      className="pa-trace-panel"
      data-testid={testId ?? "trace-panel"}
      aria-label="Trace 面板"
    >
      <div className="pa-trace-panel__title">{title}</div>
      <ul className="pa-trace-panel__list">
        {entries.map((e) => (
          <li
            key={e.id}
            className={`pa-trace-panel__item pa-trace-panel__item--${e.state}`}
            data-testid={`trace-item-${e.id}`}
          >
            <Badge
              tone={
                e.state === "done"
                  ? "ok"
                  : e.state === "err"
                    ? "err"
                    : e.state === "active"
                      ? "info"
                      : "neutral"
              }
              testId={`trace-badge-${e.id}`}
            >
              {e.state === "done"
                ? "✓"
                : e.state === "err"
                  ? "!"
                  : e.state === "active"
                    ? "●"
                    : "○"}
            </Badge>
            <span className="pa-trace-panel__label">{e.label}</span>
            {e.hint ? (
              <span className="pa-trace-panel__hint pa-faint pa-tiny">
                {e.hint}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      <Collapse title="高级 Trace 详情" defaultOpen={false} testId="trace-advanced">
        <div className="pa-small pa-muted">
          S53 仅占位, S54-S55 接入真实 trace (Skill 调用/HTTP 时延/token 用量)。
        </div>
      </Collapse>
    </aside>
  );
}
