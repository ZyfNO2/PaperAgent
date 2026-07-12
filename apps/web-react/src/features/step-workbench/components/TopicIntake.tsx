import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";

interface Props {
  topicInput: string;
  topic: string;
  notes: string[];
  onTopicInputChange: (value: string) => void;
  onStart: () => void;
  testId?: string;
}

export function TopicIntake({
  topicInput,
  topic,
  notes,
  onTopicInputChange,
  onStart,
  testId,
}: Props) {
  return (
    <Card title="题目输入" testId={testId ?? "topic-intake-card"}>
      <div className="pa-form-row">
        <label className="pa-small pa-muted" htmlFor="topic-intake-input">
          题目
        </label>
        <input
          id="topic-intake-input"
          className="pa-input"
          value={topicInput}
          onChange={(e) => onTopicInputChange(e.target.value)}
          placeholder="例：基于YOLO的钢材表面缺陷检测"
          data-testid="topic-intake-input"
        />
      </div>
      <div className="pa-interview-actions">
        <Button
          variant="primary"
          size="sm"
          disabled={!topicInput.trim()}
          onClick={onStart}
          data-testid="topic-intake-start"
        >
          开始分析
        </Button>
      </div>
      {topic ? (
        <div className="pa-small pa-muted" data-testid="topic-intake-current">
          当前题目：<strong>{topic}</strong>
        </div>
      ) : null}
      {notes.length > 0 ? (
        <ul className="pa-topic-intake__notes" data-testid="topic-notes">
          {notes.map((note, index) => (
            <li key={`${note}-${index}`} data-testid={`topic-note-${index}`}>
              {note}
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
