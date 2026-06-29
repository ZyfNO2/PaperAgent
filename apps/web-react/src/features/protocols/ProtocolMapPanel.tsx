// Session 54: ProtocolMapPanel — MCP / A2A / ACP 协议对照 (design-only, 不接 runtime)
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";

interface Protocol {
  key: string;
  name: string;
  scope: string;
  status: "implemented" | "design-only";
  responsibility: string;
  papersAgent: string;
}

const PROTOCOLS: Protocol[] = [
  {
    key: "mcp",
    name: "MCP",
    scope: "Agent 调工具",
    status: "implemented",
    responsibility: "标准工具描述与调用, 把外部工具当成可控边界",
    papersAgent: "S36 实现, 工具注册 + 调用记录 + 显式声明",
  },
  {
    key: "a2a",
    name: "A2A",
    scope: "Agent 间任务委派",
    status: "design-only",
    responsibility: "跨 Agent 任务分发与状态共享",
    papersAgent: "当前未实现, 仅作架构预留",
  },
  {
    key: "acp",
    name: "ACP",
    scope: "Agent 间消息治理",
    status: "design-only",
    responsibility: "Agent 行为准入 + 不可抵赖审计 + Human Gate",
    papersAgent: "S44 文档化, 不参与当前主链路执行",
  },
];

const STATUS_TONE: Record<Protocol["status"], "ok" | "info"> = {
  implemented: "ok",
  "design-only": "info",
};

interface Props {
  testId?: string;
}

export function ProtocolMapPanel({ testId }: Props) {
  return (
    <Card
      title={
        <span>
          Protocol Map <Badge tone="info" testId="protocol-map-badge">design-only</Badge>
        </span>
      }
      testId={testId ?? "protocol-map"}
    >
      <table className="pa-protocol-table" data-testid="protocol-table">
        <thead>
          <tr>
            <th>协议</th>
            <th>解决</th>
            <th>状态</th>
            <th>PaperAgent 当前</th>
          </tr>
        </thead>
        <tbody>
          {PROTOCOLS.map((p) => (
            <tr key={p.key} data-testid={`protocol-row-${p.key}`}>
              <td>
                <strong>{p.name}</strong>
              </td>
              <td className="pa-small">{p.scope}</td>
              <td>
                <Badge tone={STATUS_TONE[p.status]} testId={`protocol-tone-${p.key}`}>
                  {p.status}
                </Badge>
              </td>
              <td className="pa-small pa-muted">
                <div>{p.responsibility}</div>
                <div className="pa-tiny pa-faint">{p.papersAgent}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pa-protocol-honest" data-testid="protocol-honest">
        <strong className="pa-warn">诚实边界:</strong>{" "}
        <span className="pa-small pa-muted">
          协议对照表仅用于架构讲解, 不接入真实 runtime。ACP 是设计预留, 不参与当前主链路执行。
        </span>
      </div>
    </Card>
  );
}
