// Session 60: PaperLibraryEditor — 后端接线 (RAG 库真实闭环).
// ponytail:
// - 添加文献 → POST /api/v1/projects/{project_id}/paper-library/manual
// - 列表 → GET  /api/v1/projects/{project_id}/paper-library
// - 索引 → POST /api/v1/projects/{project_id}/paper-library/index
// - 索引状态 → GET  /api/v1/projects/{project_id}/paper-library/index/status
// - 删除: 后端无端点, 标记待实现, 不假装"已删除"
// 不展示 recall@5 / MRR / NDCG 等评估指标 — 这些在开发者窗口 (RAG Eval).

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiClient } from "../../app/apiClient";

interface PaperSummary {
  paper_id: string;
  title: string;
  chunk_count: number;
  source_mode: string;
  parse_status: string;
  url?: string | null;
}

interface IndexStatusPayload {
  project_id: string;
  total_papers: number;
  total_chunks: number;
  indexed_chunks: number;
  unindexed_chunks: number;
  embedding_provider: string;
  papers: Array<{
    paper_id: string;
    title: string;
    chunk_count: number;
    indexed_chunk_count: number;
    is_indexed: boolean;
  }>;
}

interface ManualIngestResp {
  paper_id: string;
  status: string;
  parse_status: string;
  chunk_count: number;
  is_duplicate: boolean;
  message: string;
}

export type LibraryTag = "方法参考" | "数据集来源" | "复现实验" | "写作引用";

const TAG_OPTIONS: LibraryTag[] = [
  "方法参考",
  "数据集来源",
  "复现实验",
  "写作引用",
];

export interface PaperLibraryEditorProps {
  testId?: string;
  projectId?: string;
  apiPrefix?: string;
}

const DEFAULT_PROJECT = "demo-local-rag";

export function PaperLibraryEditor({
  testId,
  projectId = DEFAULT_PROJECT,
  apiPrefix = "/api/v1",
}: PaperLibraryEditorProps) {
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [indexStatus, setIndexStatus] = useState<IndexStatusPayload | null>(null);

  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");

  const [busy, setBusy] = useState<"add" | "index" | "reload" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [tagMap, setTagMap] = useState<Record<string, LibraryTag[]>>({});

  const canSubmit =
    title.trim().length > 0 && text.trim().length >= 10 && !busy;

  const loadPapers = useCallback(async () => {
    setBusy("reload");
    setError(null);
    try {
      const resp = await apiClient.get<{
        papers: PaperSummary[];
        total_papers: number;
      }>(`${apiPrefix}/projects/${projectId}/paper-library`);
      setPapers(resp.papers || []);
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
      setError(`加载文献失败: ${msg}`);
    } finally {
      setBusy(null);
    }
  }, [apiPrefix, projectId]);

  const loadIndexStatus = useCallback(async () => {
    try {
      const resp = await apiClient.get<IndexStatusPayload>(
        `${apiPrefix}/projects/${projectId}/paper-library/index/status`,
      );
      setIndexStatus(resp);
    } catch {
      // 索引未建过 → 静默, 不显示错误卡
      setIndexStatus(null);
    }
  }, [apiPrefix, projectId]);

  useEffect(() => {
    void loadPapers();
    void loadIndexStatus();
  }, [loadPapers, loadIndexStatus]);

  async function submit() {
    if (!canSubmit) return;
    setBusy("add");
    setError(null);
    setFlash(null);
    try {
      const resp = await apiClient.post<ManualIngestResp>(
        `${apiPrefix}/projects/${projectId}/paper-library/manual`,
        {
          title: title.trim(),
          text: text.trim(),
          url: url.trim() || null,
          tags: [],
        },
      );
      if (resp.status === "duplicate") {
        setFlash(`重复文献: ${resp.paper_id} (${resp.message})`);
      } else if (resp.status === "ingested") {
        setFlash(`已入库: ${resp.paper_id} (${resp.chunk_count} chunks)`);
      } else {
        setFlash(`入库结果: ${resp.status} — ${resp.message}`);
      }
      setTitle("");
      setUrl("");
      setText("");
      await loadPapers();
      await loadIndexStatus();
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
      setError(`入库失败: ${msg}`);
    } finally {
      setBusy(null);
    }
  }

  async function buildIndex() {
    setBusy("index");
    setError(null);
    setFlash(null);
    try {
      const resp = await apiClient.post<{
        chunk_count: number;
        indexed: number;
        skipped: number;
        duration_ms: number;
        paper_count: number;
        message: string;
      }>(`${apiPrefix}/projects/${projectId}/paper-library/index`, {
        force: false,
      });
      setFlash(
        `索引完成: ${resp.indexed}/${resp.chunk_count} chunks (${resp.duration_ms}ms)`,
      );
      await loadIndexStatus();
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
      setError(`索引失败: ${msg}`);
    } finally {
      setBusy(null);
    }
  }

  const indexedPaperIds = useMemo(() => {
    const set = new Set<string>();
    (indexStatus?.papers || []).forEach((p) => {
      if (p.is_indexed) set.add(p.paper_id);
    });
    return set;
  }, [indexStatus]);

  function toggleTag(paperId: string, tag: LibraryTag) {
    setTagMap((prev) => {
      const cur = prev[paperId] || [];
      const on = cur.includes(tag);
      return {
        ...prev,
        [paperId]: on ? cur.filter((t) => t !== tag) : [...cur, tag],
      };
    });
  }

  return (
    <section className="pa-uw-zone" data-testid={testId ?? "library-panel"}>
      <header className="pa-uw-zone__head">
        <span className="pa-uw-zone__cap">D</span>
        <h2 className="pa-uw-zone__title">文献 RAG 库</h2>
        <div className="pa-uw-zone__meta" data-testid="library-meta">
          {indexStatus ? (
            <>
              <span data-testid="library-meta-papers">
                {indexStatus.total_papers} 篇
              </span>
              <span data-testid="library-meta-chunks">
                {indexStatus.indexed_chunks}/{indexStatus.total_chunks} chunks 已索引
              </span>
              <span data-testid="library-meta-provider">
                provider: {indexStatus.embedding_provider}
              </span>
            </>
          ) : (
            <span>索引未建立</span>
          )}
        </div>
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
            <span className="pa-uw-form__label">链接 / DOI (可选)</span>
            <input
              type="text"
              className="pa-uw-form__input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://arxiv.org/abs/... 或 DOI"
              data-testid="library-link"
            />
          </label>
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">正文 / 摘要 (≥ 10 字)</span>
            <textarea
              className="pa-uw-form__textarea"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              placeholder="粘贴摘要、笔记或整段文字..."
              data-testid="library-text"
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
              {busy === "add" ? "入库中..." : "入库"}
            </button>
            <button
              type="button"
              className="pa-btn pa-btn--ghost pa-btn--md"
              onClick={buildIndex}
              disabled={busy !== null || papers.length === 0}
              data-testid="library-reindex-all"
            >
              {busy === "index" ? "索引中..." : "重建索引"}
            </button>
          </div>
          {error && (
            <div className="pa-uw-form__error" data-testid="library-error">
              {error}
            </div>
          )}
          {flash && (
            <div className="pa-uw-form__flash" data-testid="library-flash">
              {flash}
            </div>
          )}
        </div>
        <ul className="pa-uw-library-list" data-testid="library-list">
          {papers.length === 0 ? (
            <li className="pa-uw-library-list__empty" data-testid="library-empty">
              {busy === "reload"
                ? "加载中..."
                : "文献库为空. 上方表单提交后会在此显示真实后端返回的 paper_id 与 chunk_count."}
            </li>
          ) : (
            papers.map((p) => {
              const isIdx = indexedPaperIds.has(p.paper_id);
              const tags = tagMap[p.paper_id] || [];
              return (
                <li
                  key={p.paper_id}
                  className="pa-uw-library-item"
                  data-testid={`library-item-${p.paper_id}`}
                >
                  <div className="pa-uw-library-item__head">
                    <span className="pa-uw-library-item__title">{p.title}</span>
                    <span
                      className={
                        "pa-uw-library-item__status pa-uw-library-item__status--" +
                        (isIdx ? "indexed" : "pending")
                      }
                      data-testid={`library-index-status-${p.paper_id}`}
                    >
                      {isIdx ? "已索引" : "待索引"}
                    </span>
                  </div>
                  <div
                    className="pa-uw-library-item__meta"
                    data-testid={`library-meta-${p.paper_id}`}
                  >
                    <code>{p.paper_id}</code> · {p.chunk_count} chunks ·{" "}
                    {p.parse_status}
                    {p.url ? (
                      <>
                        {" · "}
                        <a href={p.url} target="_blank" rel="noreferrer">
                          链接
                        </a>
                      </>
                    ) : null}
                  </div>
                  <div className="pa-uw-library-item__tags">
                    {TAG_OPTIONS.map((t) => {
                      const on = tags.includes(t);
                      return (
                        <button
                          key={t}
                          type="button"
                          className={"pa-uw-tag" + (on ? " pa-uw-tag--on" : "")}
                          onClick={() => toggleTag(p.paper_id, t)}
                          data-testid={`library-tag-${p.paper_id}-${t}`}
                        >
                          {t}
                        </button>
                      );
                    })}
                  </div>
                </li>
              );
            })
          )}
        </ul>
        <div className="pa-uw-form__hint" data-testid="library-delete-hint">
          删除文献: 后端端点暂未实现, 当前版本仅支持入库 / 重建索引. (后续 Session 接入.)
        </div>
      </div>
    </section>
  );
}