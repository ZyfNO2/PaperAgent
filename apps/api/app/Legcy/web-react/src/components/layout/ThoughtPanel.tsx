// Session 59: ThoughtPanel — 仅开发者窗口内渲染; 普通模式完全不出现.
// ponytail: 状态来源 = localStorage + 自定义事件, 不引额外 context.
import { useEffect, useState } from "react";
import { DEV_MODE_STORAGE_KEY } from "../layout/TopBar";

const STORAGE_KEY = DEV_MODE_STORAGE_KEY;

function readDevOpen(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "1";
}

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
  { ts: "12:04:18", tag: "info", text: "loading Session 59 user-minimal + dev-mode shell" },
  { ts: "12:04:19", tag: "tool", text: "intake: read project_intake.jsonl · ok" },
  { ts: "12:04:19", tag: "info", text: "ready. dev console visible — user shell is hidden" },
];

function nowTs() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function ThoughtPanel({ testId }: ThoughtPanelProps) {
  const [open, setOpen] = useState<boolean>(() => readDevOpen());
  const [lines, setLines] = useState<Line[]>(SEED);
  const [input, setInput] = useState("");

  useEffect(() => {
    const onChange = () => setOpen(readDevOpen());
    window.addEventListener("paperagent:dev-mode", onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener("paperagent:dev-mode", onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
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
        const next: Line[] = [...prev, { ts: nowTs(), tag, text: beat.text }];
        return next.slice(-50);
      });
      i += 1;
    }, 6000);
    return () => window.clearInterval(t);
  }, [open]);

  if (!open) return null;

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
      aria-label="Agent console (developer)"
    >
      <div className="pa-thought-panel__titlebar">
        <span className="pa-thought-panel__dot pa-thought-panel__dot--r" />
        <span className="pa-thought-panel__dot pa-thought-panel__dot--y" />
        <span className="pa-thought-panel__dot pa-thought-panel__dot--g" />
        <span className="pa-thought-panel__title">
          PaperAgent | dev console
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
          placeholder="ask agent …  (dev only)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          data-testid="thought-input"
        />
      </form>
    </aside>
  );
}