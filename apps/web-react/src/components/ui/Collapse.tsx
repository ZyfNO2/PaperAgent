// Session 53: Collapse 组件 — 默认折叠 / 受控展开
import { useState, type ReactNode } from "react";

export interface CollapseProps {
  title: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onToggle?: (open: boolean) => void;
  children?: ReactNode;
  testId?: string;
}

export function Collapse({
  title,
  defaultOpen = false,
  open,
  onToggle,
  children,
  testId,
}: CollapseProps) {
  const isControlled = open !== undefined;
  const [internal, setInternal] = useState(defaultOpen);
  const isOpen = isControlled ? (open as boolean) : internal;

  const toggle = () => {
    const next = !isOpen;
    if (!isControlled) setInternal(next);
    onToggle?.(next);
  };

  return (
    <div
      className={"pa-collapse" + (isOpen ? " pa-collapse--open" : "")}
      data-testid={testId ?? "collapse"}
    >
      <button
        type="button"
        className="pa-collapse__header"
        aria-expanded={isOpen}
        onClick={toggle}
        data-testid={isOpen ? "collapse-toggle-open" : "collapse-toggle-closed"}
      >
        <span className="pa-collapse__caret" aria-hidden="true">
          {isOpen ? "▾" : "▸"}
        </span>
        <span className="pa-collapse__title">{title}</span>
      </button>
      {isOpen ? (
        <div className="pa-collapse__body" data-testid="collapse-body">
          {children}
        </div>
      ) : null}
    </div>
  );
}
