// Session 57: ThoughtPanel → TUI dark console (OpenCode agent 工作区感)
// - 顶部窗口标题栏 (3 dot + PaperAgent | Topic feasibility workflow)
// - 中间流式日志 (timestamp + tag + text)
// - 底部命令行 prompt 输入框
import { useEffect, useState } from "react";

export interface ThoughtPanelProps {
  testId?: string;
}

interface Line {
  ts: string;
  tag: "info" | "tool" | "user" | "err";
  text: string;
}

const SEED: Line[] = [
  { ts: "12:04:18", tag: "info", text: "booting paperagent · topic feasibility workflow" },
  { ts: "12:04:18", tag: "info", text: "loading Session 57 OpenCode style · light theme + dark console" },
  { ts: "12:04:19", tag: "tool", text: "intake: read project_intake.jsonl · ok" },
  { ts: "12:04:19", tag: "info", text: "ready. type a topic to start or run `demo case1`" },
];

function nowTs() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function ThoughtPanel({ testId }: ThoughtPanelProps) {
  const [lines, setLines] = useState<Line[]>(SEED);
  const [input, setInput] = useState("");

  // Append a synthetic streaming line every 6s so console feels alive in demo.
  useEffect(() => {
    const beats = [
      { tag: "info" as const, text: "planner: parse topic → 3 keywords" },
      { tag: "tool" as const, text: "retriever: openalex.search(query=k1+k2)" },
      { tag: "info" as const, text: "scorer: 6-dim evidence scoring · 4 candidates" },
      { tag: "user" as const, text: "asking for confirmation …" },
    ];
    let i = 0;
    const t = window.setInterval(() => {
      const beat = beats[i % beats.length];
      const tag: Line["tag"] = beat.tag;
      setLines((prev) => {
        const next: Line[] = [
          ...prev,
          { ts: nowTs(), tag, text: beat.text },
        ];
        return next.slice(-50);
      });
      i += 1;
    }, 6000);
    return () => window.clearInterval(t);
  }, []);

  function submit() {
    if (!input.trim()) return;
    const text = input.trim();
    setLines((prev) => {
      const next: Line[] = [...prev, { ts: nowTs(), tag: "user", text }];
      return next.slice(-50);
    });
    setInput("");
  }

  return (
    <aside
      className="pa-thought-panel"
      data-testid={testId ?? "thought-panel"}
      aria-label="Agent console"
    >
      <div className="pa-thought-panel__titlebar">
        <span className="pa-thought-panel__dot pa-thought-panel__dot--r" />
        <span className="pa-thought-panel__dot pa-thought-panel__dot--y" />
        <span className="pa-thought-panel__dot pa-thought-panel__dot--g" />
        <span className="pa-thought-panel__title">
          PaperAgent | Topic feasibility workflow
        </span>
      </div>
      <div className="pa-thought-panel__body" data-testid="thought-stream">
        {lines.map((l, idx) => (
          <div className="pa-thought-panel__line" key={`${l.ts}-${idx}`}>
            <span className="pa-thought-panel__ts">{l.ts}</span>
            <span
              className={
                "pa-thought-panel__tag" +
                (l.tag === "tool"
                  ? " pa-thought-panel__tag--tool"
                  : l.tag === "user"
                    ? " pa-thought-panel__tag--user"
                    : l.tag === "err"
                      ? " pa-thought-panel__tag--err"
                      : "")
              }
            >
              {l.tag}
            </span>
            <span className="pa-thought-panel__text">{l.text}</span>
          </div>
        ))}
      </div>
      <form
        className="pa-thought-panel__prompt"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        data-testid="thought-prompt"
      >
        <span className="pa-thought-panel__sigil">›</span>
        <input
          className="pa-thought-panel__input"
          placeholder="ask agent …  (e.g. demo case1)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          data-testid="thought-input"
        />
      </form>
    </aside>
  );
}