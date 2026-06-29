// Session 53: Tabs 组件 — 受控
import { useState, type ReactNode } from "react";

export interface TabItem {
  key: string;
  label: ReactNode;
  content: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  defaultKey?: string;
  onChange?: (key: string) => void;
  testId?: string;
}

export function Tabs({ items, defaultKey, onChange, testId }: TabsProps) {
  const [active, setActive] = useState<string>(
    defaultKey ?? items[0]?.key ?? "",
  );
  const current = items.find((it) => it.key === active) ?? items[0];

  const select = (key: string) => {
    setActive(key);
    onChange?.(key);
  };

  return (
    <div className="pa-tabs" data-testid={testId ?? "tabs"}>
      <div className="pa-tabs__bar" role="tablist">
        {items.map((it) => (
          <button
            key={it.key}
            type="button"
            role="tab"
            aria-selected={it.key === active}
            className={
              "pa-tabs__tab" + (it.key === active ? " pa-tabs__tab--active" : "")
            }
            data-testid={`tab-${it.key}`}
            onClick={() => select(it.key)}
          >
            {it.label}
          </button>
        ))}
      </div>
      <div className="pa-tabs__panel" role="tabpanel">
        {current?.content}
      </div>
    </div>
  );
}
