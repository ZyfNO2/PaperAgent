// Session 59: EvidenceSubmitPanel — 普通用户提交证据 (本地状态闭环)
// ponytail: 不引 store; useState 局部; 提交后追加到列表, 状态默认 待核验.
import { useState } from "react";

export type EvidenceKind = "paper" | "dataset" | "github" | "web" | "file";
export type EvidenceStatus = "待核验" | "可用" | "不适合" | "需人工确认";

interface Evidence {
  id: string;
  kind: EvidenceKind;
  link: string;
  note: string;
  status: EvidenceStatus;
}

const KIND_LABEL: Record<EvidenceKind, string> = {
  paper: "论文 (DOI / arXiv)",
  dataset: "数据集",
  github: "GitHub 项目",
  web: "网页说明",
  file: "本地文件 (占位)",
};

const STATUS_OPTIONS: EvidenceStatus[] = [
  "待核验",
  "可用",
  "不适合",
  "需人工确认",
];

function nextId() {
  return `ev-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export interface EvidenceSubmitPanelProps {
  testId?: string;
}

export function EvidenceSubmitPanel({ testId }: EvidenceSubmitPanelProps) {
  const [items, setItems] = useState<Evidence[]>([]);
  const [kind, setKind] = useState<EvidenceKind>("paper");
  const [link, setLink] = useState("");
  const [note, setNote] = useState("");

  const canSubmit = link.trim().length > 0;

  function submit() {
    if (!canSubmit) return;
    const item: Evidence = {
      id: nextId(),
      kind,
      link: link.trim(),
      note: note.trim(),
      status: "待核验",
    };
    setItems((prev) => [item, ...prev]);
    setLink("");
    setNote("");
  }

  function remove(id: string) {
    setItems((prev) => prev.filter((it) => it.id !== id));
  }

  function setStatus(id: string, status: EvidenceStatus) {
    setItems((prev) =>
      prev.map((it) => (it.id === id ? { ...it, status } : it))
    );
  }

  return (
    <section className="pa-uw-zone" data-testid={testId ?? "evidence-panel"}>
      <header className="pa-uw-zone__head">
        <span className="pa-uw-zone__cap">C</span>
        <h2 className="pa-uw-zone__title">证据提交</h2>
      </header>
      <div className="pa-uw-zone__body">
        <div className="pa-uw-form">
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">类型</span>
            <select
              className="pa-uw-form__select"
              value={kind}
              onChange={(e) => setKind(e.target.value as EvidenceKind)}
              data-testid="evidence-kind"
            >
              {(Object.keys(KIND_LABEL) as EvidenceKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">链接 / 文本</span>
            <input
              type="text"
              className="pa-uw-form__input"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://arxiv.org/abs/... 或 DOI / GitHub URL"
              data-testid="evidence-link"
            />
          </label>
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">备注</span>
            <input
              type="text"
              className="pa-uw-form__input"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="可选, 例如: 用于方法对比"
              data-testid="evidence-note"
            />
          </label>
          <div className="pa-uw-form__actions">
            <button
              type="button"
              className="pa-btn pa-btn--primary pa-btn--md"
              onClick={submit}
              disabled={!canSubmit}
              data-testid="evidence-submit"
            >
              提交证据
            </button>
          </div>
        </div>
        <ul className="pa-uw-evidence-list" data-testid="evidence-list">
          {items.length === 0 ? (
            <li className="pa-uw-evidence-list__empty">
              暂无证据。提交论文 / 数据集 / GitHub / 网页链接后会出现在此。
            </li>
          ) : (
            items.map((it) => (
              <li
                key={it.id}
                className="pa-uw-evidence-item"
                data-testid={`evidence-item-${it.id}`}
              >
                <div className="pa-uw-evidence-item__head">
                  <span className="pa-uw-evidence-item__kind">
                    {KIND_LABEL[it.kind]}
                  </span>
                  <select
                    className="pa-uw-evidence-item__status"
                    value={it.status}
                    onChange={(e) =>
                      setStatus(it.id, e.target.value as EvidenceStatus)
                    }
                    data-testid={`evidence-status-${it.id}`}
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="pa-uw-evidence-item__remove"
                    onClick={() => remove(it.id)}
                    data-testid={`evidence-remove-${it.id}`}
                  >
                    删除
                  </button>
                </div>
                <div className="pa-uw-evidence-item__link">{it.link}</div>
                {it.note ? (
                  <div className="pa-uw-evidence-item__note">{it.note}</div>
                ) : null}
              </li>
            ))
          )}
        </ul>
      </div>
    </section>
  );
}