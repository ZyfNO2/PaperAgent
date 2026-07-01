// Session 54: TechSwitchPanel — 8 个 tech switch, 3 状态色区分
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Collapse } from "../../components/ui/Collapse";
import { TECH_SWITCHES, type TechStatus } from "./interviewData";

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
  testId?: string;
}

export function TechSwitchPanel({ testId }: Props) {
  return (
    <Card title="Tech Switches" testId={testId ?? "tech-switches"}>
      <ul className="pa-tech-switches" data-testid="tech-switch-list">
        {TECH_SWITCHES.map((t) => (
          <li
            key={t.key}
            className="pa-tech-switches__item"
            data-testid={`tech-switch-${t.key}`}
            data-status={t.status}
          >
            <div className="pa-tech-switches__row">
              <span className="pa-tech-switches__label">{t.label}</span>
              <Badge tone={STATUS_TONE[t.status]} testId={`tech-tone-${t.key}`}>
                {STATUS_LABEL[t.status]}
              </Badge>
            </div>
            <div className="pa-tech-switches__meta pa-muted pa-tiny">
              {t.mode} · 成本 {t.cost}
            </div>
            <Collapse title={t.description} testId={`tech-desc-${t.key}`}>
              <div className="pa-small">{t.note}</div>
            </Collapse>
          </li>
        ))}
      </ul>
    </Card>
  );
}
