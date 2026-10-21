import { useEffect, useState } from "react";
import { request, type Anchor, type Paper } from "./workspaceApi";

export function ReadingTools({
  identifier,
  page,
  onLocate,
}: {
  identifier: string;
  page: number;
  onLocate: (a: Anchor) => void;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<(Anchor & { excerpt: string })[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [label, setLabel] = useState("");
  const [bookmarks, setBookmarks] = useState<{ page: number; label: string }[]>(
    [],
  );
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    setQuery("");
    setHits([]);
    setTotal(null);
    setOffset(0);
    setNotice("");
    setBookmarks([]);
    request<typeof bookmarks>(`/api/documents/${identifier}/bookmarks`)
      .then((v) => {
        if (active) setBookmarks(v);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [identifier]);
  async function find(start = 0) {
    setBusy(true);
    setNotice("");
    try {
      const result = await request<{
        hits: typeof hits;
        total: number;
        notice: string;
      }>(
        `/api/documents/${identifier}/find?q=${encodeURIComponent(query)}&offset=${start}`,
      );
      setHits(result.hits);
      setTotal(result.total);
      setOffset(start);
      setNotice(result.notice);
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function bookmark(remove?: number) {
    try {
      setBookmarks(
        await request(
          `/api/documents/${identifier}/bookmarks${remove ? `/${remove}` : ""}`,
          remove ? {} : { page, label },
          remove ? "DELETE" : "POST",
        ),
      );
      setLabel("");
      setNotice(remove ? "书签已删除。" : "书签已保存，可在下次阅读时返回。");
    } catch (e) {
      setNotice(String(e));
    }
  }
  return (
    <details className="reading-extras">
      <summary>正文搜索与书签</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void find();
        }}
        className="work-row"
      >
        <input
          aria-label="搜索论文正文"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索术语、实验数字或原句"
        />
        <button disabled={busy || query.trim().length < 2}>搜索全文</button>
      </form>
      {total !== null && (
        <p>
          找到 {total} 处原文段落 · 已显示 {total ? offset + 1 : 0}—
          {Math.min(offset + 30, total)}
        </p>
      )}
      <div className="reading-search-results">
        {hits.map((hit, i) => (
          <button key={i} onClick={() => onLocate(hit)}>
            <strong>第 {hit.page} 页</strong>
            <span>{hit.excerpt}</span>
          </button>
        ))}
      </div>
      {!!total && total > 30 && (
        <div className="work-row">
          <button
            disabled={busy || offset === 0}
            onClick={() => void find(offset - 30)}
          >
            上一组结果
          </button>
          <button
            disabled={busy || offset + 30 >= total}
            onClick={() => void find(offset + 30)}
          >
            下一组结果
          </button>
        </div>
      )}
      <div className="work-row">
        <input
          aria-label="书签名称"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder={`第 ${page} 页书签名称（可选）`}
          maxLength={150}
        />
        <button onClick={() => void bookmark()}>收藏当前页</button>
      </div>
      <div className="bookmark-list">
        {bookmarks.map((b) => (
          <span key={b.page}>
            <button
              onClick={() =>
                onLocate({
                  document_id: identifier,
                  page: b.page,
                  bbox: [0, 0, 0, 0],
                  width: 1,
                  height: 1,
                })
              }
            >
              {b.label} · p.{b.page}
            </button>
            <button
              aria-label={`删除第 ${b.page} 页书签`}
              onClick={() => void bookmark(b.page)}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      {notice && <p role="status">{notice}</p>}
    </details>
  );
}

export function LibraryOrganizer({
  identifier,
  onSelect,
  onSaved,
}: {
  identifier: string;
  onSelect: (id: string) => void;
  onSaved?: () => void;
}) {
  const [tags, setTags] = useState("");
  const [collection, setCollection] = useState("");
  const [status, setStatus] = useState("unread");
  const [filter, setFilter] = useState("");
  const [papers, setPapers] = useState<
    (Paper & { reading_status: string; collection: string; tags: string[] })[]
  >([]);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let current = true;
    setNotice("");
    if (identifier)
      request<{
        metadata: {
          tags?: string[];
          collection?: string;
          reading_status?: string;
        };
      }>(`/api/documents/${identifier}`)
        .then((v) => {
          if (current) {
            setTags((v.metadata.tags || []).join(", "));
            setCollection(v.metadata.collection || "");
            setStatus(v.metadata.reading_status || "unread");
          }
        })
        .catch((e) => current && setNotice(String(e)));
    return () => {
      current = false;
    };
  }, [identifier]);
  async function refresh() {
    try {
      setPapers(
        await request(`/api/library/organization?reading_status=${filter}`),
      );
    } catch (e) {
      setNotice(String(e));
    }
  }
  return (
    <details className="work-card">
      <summary>文献分类与阅读清单</summary>
      <div className="chart-controls">
        <label>
          项目分类
          <input
            aria-label="文献项目分类"
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
            placeholder="例如：长上下文研究"
            maxLength={100}
          />
        </label>
        <label>
          标签
          <input
            aria-label="文献标签"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="方法, 基线, 待复现"
          />
        </label>
        <label>
          阅读状态
          <select
            aria-label="文献阅读状态"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="unread">待读</option>
            <option value="reading">阅读中</option>
            <option value="read">已读</option>
            <option value="reproduce">待复现</option>
          </select>
        </label>
      </div>
      <button
        disabled={!identifier}
        onClick={() =>
          void (async () => {
            try {
              await request(
                `/api/documents/${identifier}/organization`,
                {
                  collection,
                  tags: tags
                    .split(/[,，]/)
                    .map((s) => s.trim())
                    .filter(Boolean),
                  reading_status: status,
                },
                "PATCH",
              );
              setNotice("分类、标签与阅读状态已保存。");
              onSaved?.();
              await refresh();
            } catch (e) {
              setNotice(String(e));
            }
          })()
        }
      >
        保存分类与进度
      </button>
      <div className="work-row">
        <select
          aria-label="筛选阅读清单"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">所有阅读状态</option>
          <option value="unread">待读</option>
          <option value="reading">阅读中</option>
          <option value="read">已读</option>
          <option value="reproduce">待复现</option>
        </select>
        <button onClick={() => void refresh()}>查看阅读清单</button>
      </div>
      <div className="reading-search-results">
        {papers.map((p) => (
          <button key={p.id} onClick={() => onSelect(p.id)}>
            <strong>{p.title}</strong>
            <span>
              {p.collection || "未分类"} · {p.tags.join(" / ")}
            </span>
          </button>
        ))}
      </div>
      <p role="status">{notice}</p>
    </details>
  );
}

export function GlossaryEditor() {
  const [text, setText] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    request<{ source: string; target: string }[]>("/api/translation/glossary")
      .then((v) =>
        setText(v.map((t) => `${t.source} = ${t.target}`).join("\n")),
      )
      .catch((e) => setNotice(String(e)));
  }, []);
  return (
    <details className="work-card">
      <summary>专业术语表与翻译校对说明</summary>
      <p>
        每行一组“英文术语 =
        中文译法”。新翻译优先使用这些术语；已有译文保留，可在段落旁校正并查看历史。自动检查不代表含义一定准确。
      </p>
      <textarea
        aria-label="翻译术语表"
        rows={5}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={
          "self-attention = 自注意力\nlayer normalization = 层归一化"
        }
      />
      <button
        onClick={() =>
          void (async () => {
            try {
              const terms = text
                .split("\n")
                .filter((s) => s.trim())
                .map((line) => {
                  const split = line.indexOf("=");
                  if (split < 1)
                    throw new Error("每行需要用 = 分隔英文和中文术语");
                  return {
                    source: line.slice(0, split).trim(),
                    target: line.slice(split + 1).trim(),
                  };
                });
              await request("/api/translation/glossary", { terms }, "PUT");
              setNotice("术语表已保存，将用于新翻译。");
            } catch (e) {
              setNotice(String(e));
            }
          })()
        }
      >
        保存术语表
      </button>
      <p role="status">{notice}</p>
    </details>
  );
}

export function TranslationEditor({
  blockId,
  language,
  text,
  onSaved,
}: {
  blockId: string;
  language: string;
  text: string;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);
  const [notice, setNotice] = useState("");
  const [history, setHistory] = useState<
    { text: string; created_at: string }[]
  >([]);
  useEffect(() => {
    setDraft(text);
    setEditing(false);
    setNotice("");
    setHistory([]);
  }, [text, blockId, language]);
  return (
    <div className="translation-editor">
      <div className="work-row">
        <button onClick={() => setEditing(!editing)}>
          {editing ? "收起校正" : "校正此段译文"}
        </button>
        <button
          onClick={() =>
            void request<typeof history>(
              `/api/translations/${blockId}/history?language=${language}`,
            )
              .then(setHistory)
              .catch((e) => setNotice(String(e)))
          }
        >
          查看译文历史
        </button>
      </div>
      {editing && (
        <>
          <textarea
            aria-label="校正段落译文"
            rows={5}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            disabled={!draft.trim()}
            onClick={() =>
              void request(
                `/api/translations/${blockId}`,
                { text: draft, previous: text, language },
                "PATCH",
              )
                .then(() => {
                  setNotice("校正已保存，原译文保留在历史中。");
                  onSaved();
                })
                .catch((e) => setNotice(String(e)))
            }
          >
            保存译文校正
          </button>
        </>
      )}
      {history.map((h, i) => (
        <details key={i}>
          <summary>历史版本 · {h.created_at}</summary>
          <p>{h.text}</p>
        </details>
      ))}
      <small role="status">{notice}</small>
    </div>
  );
}

export function MatrixBuilder({
  ids,
  busy,
  submit,
}: {
  ids: string[];
  busy: boolean;
  submit: (kind: string, payload: Record<string, unknown>) => Promise<unknown>;
}) {
  const [fields, setFields] = useState(
    "本文使用哪些数据集和评估划分？\n主要评价指标和对应实验条件是什么？\n训练所需硬件、批大小和训练时长是多少？\n作者明确报告了哪些限制？",
  );
  return (
    <details className="work-card">
      <summary>逐项证据比较与复现准备</summary>
      <p>
        沿用研究意图卡片中选择的论文。每行一个具体问题，每格分别查证并保留出处；空格会进入待补清单。适合比较方法、整理实验设置和准备复现。
      </p>
      <textarea
        aria-label="证据矩阵核对问题"
        rows={5}
        value={fields}
        onChange={(e) => setFields(e.target.value)}
      />
      <button
        className="primary-button"
        disabled={busy || ids.length < 1 || ids.length > 6 || !fields.trim()}
        onClick={() =>
          void submit("matrix", {
            document_ids: ids,
            fields: fields
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean),
            topic: "文献证据与复现准备矩阵",
          })
        }
      >
        建立逐项证据矩阵
      </button>
      <p>最多 6 篇 × 6 个问题。完成后在“任务与成果”查看、定位原文和导出。</p>
    </details>
  );
}

type MatrixClaim = Anchor & {
  text: string;
  quote: string;
  block_id: string;
  source_context?: Anchor[];
};
export type MatrixRow = {
  document_id: string;
  title: string;
  cells: {
    field: string;
    status: string;
    claims: MatrixClaim[];
    evidence: Anchor[];
  }[];
};
export function MatrixResult({
  rows,
  onLocate,
}: {
  rows: MatrixRow[];
  onLocate: (a: Anchor) => void;
}) {
  if (!rows.length) return null;
  return (
    <div className="table-scroll">
      <table className="evidence-matrix">
        <thead>
          <tr>
            <th>论文</th>
            {rows[0].cells.map((c, i) => (
              <th key={i}>{c.field}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.document_id}>
              <th>{row.title}</th>
              {row.cells.map((cell, i) => (
                <td key={i}>
                  <small>{cell.status}</small>
                  {cell.claims.map((claim, j) => (
                    <div key={j}>
                      <p>{claim.text}</p>
                      <details>
                        <summary>核对引文</summary>
                        <blockquote>{claim.quote}</blockquote>
                      </details>
                      <button
                        onClick={() => {
                          const anchor = cell.evidence.find(
                            (b) => b.id === claim.block_id,
                          );
                          if (anchor) onLocate(anchor);
                        }}
                      >
                        原文第 {claim.page} 页
                      </button>
                      {claim.source_context?.map((a, k) => (
                        <button key={k} onClick={() => onLocate(a)}>
                          核对表头 · p.{a.page}
                        </button>
                      ))}
                    </div>
                  ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Draft = { text: string; revision: number; updated_at?: string };
export function WritingEditor({
  identifier,
  content,
}: {
  identifier: string;
  content: Record<string, unknown>;
}) {
  const initial = content.draft as Draft | undefined;
  const seed =
    initial?.text ||
    Object.entries((content.proposal || {}) as Record<string, string>)
      .map(([k, v]) => k + "\n" + v)
      .join("\n\n") +
      "\n\n" +
      (
        (content.sections || []) as {
          title: string;
          claims: { text: string; document_id: string; page: number }[];
        }[]
      )
        .map(
          (s) =>
            s.title +
            "\n" +
            s.claims
              .map(
                (c) => c.text + ` [${c.document_id.slice(0, 8)} p.${c.page}]`,
              )
              .join("\n"),
        )
        .join("\n\n");
  const [text, setText] = useState(seed);
  const [draft, setDraft] = useState<Draft>(
    initial || { text: "", revision: 0 },
  );
  const [history, setHistory] = useState<Draft[]>(
    (content.draft_history || []) as Draft[],
  );
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <details className="work-card writing-editor">
      <summary>编辑写作稿与版本记录</summary>
      <p>
        可以据证据修改论证、补充实验设计。保留引文标识便于回查；编辑内容尚未逐句核验，不自动继承原回答的核验状态。保存后会加入
        Markdown 导出。
      </p>
      <textarea
        aria-label="研究写作草稿"
        rows={12}
        maxLength={60000}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        disabled={busy || !text.trim()}
        onClick={() =>
          void (async () => {
            setBusy(true);
            try {
              const saved = await request<Draft>(
                `/api/artifacts/${identifier}/draft`,
                { text, revision: draft.revision },
                "PATCH",
              );
              if (draft.revision) setHistory([...history, draft]);
              setDraft(saved);
              setNotice(`已保存编辑稿第 ${saved.revision} 版。原始证据保留。`);
            } catch (e) {
              setNotice(String(e));
            } finally {
              setBusy(false);
            }
          })()
        }
      >
        保存写作稿
      </button>
      <span role="status">{notice}</span>
      {history
        .slice()
        .reverse()
        .map((h) => (
          <details key={h.revision}>
            <summary>
              第 {h.revision} 版 · {h.updated_at}
            </summary>
            <pre style={{ whiteSpace: "pre-wrap" }}>{h.text}</pre>
            <button onClick={() => setText(h.text)}>载入此版继续编辑</button>
          </details>
        ))}
    </details>
  );
}
