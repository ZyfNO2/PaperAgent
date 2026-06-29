// Session 59: PaperLibraryEditor — 普通用户管理文献 RAG 库 (本地状态闭环).
// ponytail: 不引 store; useState 局部; 操作 = add / delete / replace / tag / mark-stale.
// 不展示 recall@5 / MRR / NDCG 等评估指标 — 这些在开发者窗口 (RAG Eval).
import { useState } from "react";

export type LibraryTag = "方法参考" | "数据集来源" | "复现实验" | "写作引用";
export type LibraryStatus = "待处理" | "已切分" | "已入库" | "待重新索引";

const TAG_OPTIONS: LibraryTag[] = [
  "方法参考",
  "数据集来源",
  "复现实验",
  "写作引用",
];
const STATUS_OPTIONS: LibraryStatus[] = [
  "待处理",
  "已切分",
  "已入库",
  "待重新索引",
];

interface LibraryEntry {
  id: string;
  title: string;
  link: string;
  tags: LibraryTag[];
  status: LibraryStatus;
}

function nextId() {
  return `lib-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export interface PaperLibraryEditorProps {
  testId?: string;
}

export function PaperLibraryEditor({ testId }: PaperLibraryEditorProps) {
  const [items, setItems] = useState<LibraryEntry[]>([]);
  const [title, setTitle] = useState("");
  const [link, setLink] = useState("");

  const canSubmit = title.trim().length > 0 && link.trim().length > 0;

  function submit() {
    if (!canSubmit) return;
    setItems((prev) => [
      {
        id: nextId(),
        title: title.trim(),
        link: link.trim(),
        tags: [],
        status: "待处理",
      },
      ...prev,
    ]);
    setTitle("");
    setLink("");
  }

  function remove(id: string) {
    setItems((prev) => prev.filter((it) => it.id !== id));
  }

  function replace(id: string) {
    const it = items.find((x) => x.id === id);
    if (!it) return;
    const next = window.prompt("替换链接:", it.link);
    if (next && next.trim()) {
      setItems((prev) =>
        prev.map((x) => (x.id === id ? { ...x, link: next.trim() } : x))
      );
    }
  }

  function toggleTag(id: string, tag: LibraryTag) {
    setItems((prev) =>
      prev.map((it) => {
        if (it.id !== id) return it;
        const has = it.tags.includes(tag);
        return {
          ...it,
          tags: has ? it.tags.filter((t) => t !== tag) : [...it.tags, tag],
        };
      }),
    );
  }

  function setStatus(id: string, status: LibraryStatus) {
    setItems((prev) =>
      prev.map((it) => (it.id === id ? { ...it, status } : it))
    );
  }

  function markReindex(id: string) {
    setStatus(id, "待重新索引");
  }

  return (
    <section className="pa-uw-zone" data-testid={testId ?? "library-panel"}>
      <header className="pa-uw-zone__head">
        <span className="pa-uw-zone__cap">D</span>
        <h2 className="pa-uw-zone__title">文献 RAG 库</h2>
      </header>
      <div className="pa-uw-zone__body">
        <div className="pa-uw-form">
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">标题</span>
            <input
              type="text"
              className="pa-uw-form__input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例: YOLOv5 钢材表面缺陷检测"
              data-testid="library-title"
            />
          </label>
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">链接 / DOI / arXiv</span>
            <input
              type="text"
              className="pa-uw-form__input"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://arxiv.org/abs/... 或 DOI"
              data-testid="library-link"
            />
          </label>
          <div className="pa-uw-form__actions">
            <button
              type="button"
              className="pa-btn pa-btn--primary pa-btn--md"
              onClick={submit}
              disabled={!canSubmit}
              data-testid="library-submit"
            >
              添加文献
            </button>
          </div>
        </div>
        <ul className="pa-uw-library-list" data-testid="library-list">
          {items.length === 0 ? (
            <li className="pa-uw-library-list__empty">
              文献库为空。添加文献后会在此显示; 用途标签和入库状态可手动维护。
            </li>
          ) : (
            items.map((it) => (
              <li
                key={it.id}
                className="pa-uw-library-item"
                data-testid={`library-item-${it.id}`}
              >
                <div className="pa-uw-library-item__head">
                  <span className="pa-uw-library-item__title">{it.title}</span>
                  <select
                    className="pa-uw-library-item__status"
                    value={it.status}
                    onChange={(e) =>
                      setStatus(it.id, e.target.value as LibraryStatus)
                    }
                    data-testid={`library-status-${it.id}`}
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="pa-uw-library-item__link">{it.link}</div>
                <div className="pa-uw-library-item__tags">
                  {TAG_OPTIONS.map((t) => {
                    const on = it.tags.includes(t);
                    return (
                      <button
                        key={t}
                        type="button"
                        className={
                          "pa-uw-tag" + (on ? " pa-uw-tag--on" : "")
                        }
                        onClick={() => toggleTag(it.id, t)}
                        data-testid={`library-tag-${it.id}-${t}`}
                      >
                        {t}
                      </button>
                    );
                  })}
                </div>
                <div className="pa-uw-library-item__actions">
                  <button
                    type="button"
                    className="pa-btn pa-btn--ghost pa-btn--sm"
                    onClick={() => replace(it.id)}
                    data-testid={`library-replace-${it.id}`}
                  >
                    替换链接
                  </button>
                  <button
                    type="button"
                    className="pa-btn pa-btn--ghost pa-btn--sm"
                    onClick={() => markReindex(it.id)}
                    data-testid={`library-reindex-${it.id}`}
                  >
                    标记重新索引
                  </button>
                  <button
                    type="button"
                    className="pa-btn pa-btn--ghost pa-btn--sm"
                    onClick={() => remove(it.id)}
                    data-testid={`library-remove-${it.id}`}
                  >
                    删除
                  </button>
                </div>
              </li>
            ))
          )}
        </ul>
      </div>
    </section>
  );
}