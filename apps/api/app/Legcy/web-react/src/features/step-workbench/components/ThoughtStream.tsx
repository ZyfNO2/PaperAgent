// Session 54: ThoughtStream — 右侧 LLM 思维/对话流
import { Badge } from "../../../components/ui/Badge";
import { Spinner } from "../../../components/ui/Spinner";
import type { LlmEvent } from "../stepTypes";

interface Props {
  events: LlmEvent[];
  streaming: boolean;
  testId?: string;
}

export function ThoughtStream({ events, streaming, testId }: Props) {
  return (
    <div className="pa-thought-stream" data-testid={testId ?? "thought-stream"}>
      <div className="pa-thought-stream__title">
        LLM 思维 / 对话
        {streaming ? <Spinner size={12} testId="thought-streaming" /> : null}
      </div>
      {events.length === 0 ? (
        <div className="pa-muted pa-small">暂无 LLM 输出, 切换步骤或加载 Demo Case 触发。</div>
      ) : (
        <ul className="pa-thought-stream__list">
          {events.map((e) => (
            <li
              key={e.seq}
              className={`pa-thought-stream__item pa-thought-stream__item--${e.kind}`}
              data-testid={`llm-evt-${e.seq}`}
            >
              <Badge
                tone={
                  e.kind === "assistant_thought"
                    ? "info"
                    : e.kind === "user_input"
                      ? "ok"
                      : e.kind === "command_preview"
                        ? "warn"
                        : "neutral"
                }
                testId={`llm-tone-${e.seq}`}
              >
                {e.kind}
              </Badge>
              <span className="pa-small">{e.text}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
