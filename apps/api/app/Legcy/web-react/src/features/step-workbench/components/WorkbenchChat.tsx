// Session 54: WorkbenchChat — 右侧对话入口, 支持 add/remove/modify/query 意图预览
import { type FormEvent } from "react";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import type { ChatMessage } from "../stepTypes";

interface Props {
  draft: string;
  preview: { intent: string; description: string } | null;
  messages: ChatMessage[];
  onDraftChange: (v: string) => void;
  onSubmit: (text: string) => void;
  onAcceptPreview: () => void;
  testId?: string;
}

export function WorkbenchChat({
  draft,
  preview,
  messages,
  onDraftChange,
  onSubmit,
  onAcceptPreview,
  testId,
}: Props) {
  const handle = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    onSubmit(draft);
  };
  return (
    <Card title="对话式编辑" testId={testId ?? "workbench-chat"}>
      <form onSubmit={handle} className="pa-workbench-chat__form" data-testid="chat-form">
        <input
          type="text"
          className="pa-workbench-chat__input"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          placeholder="例: 修改第 3 步的工程证据"
          data-testid="chat-input"
        />
        <Button
          variant="primary"
          size="sm"
          type="submit"
          disabled={!draft.trim()}
          data-testid="chat-submit"
        >
          预览
        </Button>
      </form>
      {preview ? (
        <div className="pa-workbench-chat__preview" data-testid="chat-preview">
          <div className="pa-small pa-muted">{preview.intent}: {preview.description}</div>
          <Button
            variant="secondary"
            size="sm"
            onClick={onAcceptPreview}
            data-testid="chat-accept"
          >
            接受并应用
          </Button>
        </div>
      ) : null}
      {messages.length > 0 ? (
        <ul className="pa-workbench-chat__list" data-testid="chat-messages">
          {messages.map((m) => (
            <li
              key={m.id}
              className={`pa-workbench-chat__msg pa-workbench-chat__msg--${m.role}`}
              data-testid={`chat-msg-${m.id}`}
            >
              <span className="pa-faint pa-tiny">{m.role}</span>
              <span className="pa-small">{m.text}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
