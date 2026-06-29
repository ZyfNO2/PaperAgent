// Session 54: DeepDiveDrawer — 9 个 Interview Module 抽屉式讲解
import { useState } from "react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Collapse } from "../../components/ui/Collapse";
import { INTERVIEW_MODULES, type TechStatus } from "./interviewData";

const STATUS_TONE: Record<TechStatus, "ok" | "warn" | "info"> = {
  implemented: "ok",
  lightweight: "warn",
  "design-only": "info",
};

const STATUS_LABEL: Record<TechStatus, string> = {
  implemented: "已实现",
  lightweight: "轻量",
  "design-only": "架构预留",
};

interface Props {
  open: boolean;
  onClose: () => void;
  testId?: string;
}

export function DeepDiveDrawer({ open, onClose, testId }: Props) {
  const [filter, setFilter] = useState<TechStatus | "all">("all");
  const items =
    filter === "all"
      ? INTERVIEW_MODULES
      : INTERVIEW_MODULES.filter((m) => m.status === filter);
  if (!open) return null;
  return (
    <div
      className="pa-deep-dive"
      role="dialog"
      aria-label="Deep Dive"
      data-testid={testId ?? "deep-dive"}
    >
      <Card
        title={
          <span>
            Deep Dive — 模块讲解索引
            <Button
              size="sm"
              variant="ghost"
              onClick={onClose}
              data-testid="deep-dive-close"
            >
              关闭
            </Button>
          </span>
        }
        testId="deep-dive-card"
        footer={
          <div className="pa-deep-dive__filter" data-testid="deep-dive-filter">
            <Button
              size="sm"
              variant={filter === "all" ? "primary" : "secondary"}
              onClick={() => setFilter("all")}
              data-testid="filter-all"
            >
              全部
            </Button>
            <Button
              size="sm"
              variant={filter === "implemented" ? "primary" : "secondary"}
              onClick={() => setFilter("implemented")}
              data-testid="filter-implemented"
            >
              已实现
            </Button>
            <Button
              size="sm"
              variant={filter === "lightweight" ? "primary" : "secondary"}
              onClick={() => setFilter("lightweight")}
              data-testid="filter-lightweight"
            >
              轻量
            </Button>
            <Button
              size="sm"
              variant={filter === "design-only" ? "primary" : "secondary"}
              onClick={() => setFilter("design-only")}
              data-testid="filter-design"
            >
              架构预留
            </Button>
          </div>
        }
      >
        <ul className="pa-deep-dive__list" data-testid="deep-dive-list">
          {items.map((m) => (
            <li
              key={m.key}
              className="pa-deep-dive__item"
              data-testid={`deep-dive-${m.key}`}
            >
              <div className="pa-deep-dive__head">
                <strong>{m.title}</strong>
                <Badge tone={STATUS_TONE[m.status]} testId={`deep-dive-tone-${m.key}`}>
                  {STATUS_LABEL[m.status]}
                </Badge>
              </div>
              <div className="pa-small pa-muted">{m.summary}</div>
              <Collapse title={`${m.questions.length} 个常见问题`} testId={`deep-dive-q-${m.key}`}>
                <ul className="pa-deep-dive__q">
                  {m.questions.map((q, i) => (
                    <li key={i} className="pa-small">· {q}</li>
                  ))}
                </ul>
              </Collapse>
              <Collapse title="代码 / 测试 / 文档 / 边界" testId={`deep-dive-p-${m.key}`}>
                <div className="pa-small">
                  <div>
                    <strong>code:</strong>{" "}
                    {m.codePaths.map((p, i) => (
                      <code key={i} className="pa-tiny">
                        {p}{i < m.codePaths.length - 1 ? ", " : ""}
                      </code>
                    ))}
                  </div>
                  <div>
                    <strong>test:</strong>{" "}
                    {m.testPaths.map((p, i) => (
                      <code key={i} className="pa-tiny">
                        {p}{i < m.testPaths.length - 1 ? ", " : ""}
                      </code>
                    ))}
                  </div>
                  <div>
                    <strong>doc:</strong>{" "}
                    {m.docPaths.map((p, i) => (
                      <code key={i} className="pa-tiny">
                        {p}{i < m.docPaths.length - 1 ? ", " : ""}
                      </code>
                    ))}
                  </div>
                  <div className="pa-warn pa-tiny">boundary: {m.boundary}</div>
                </div>
              </Collapse>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
