import { ComparisonReadiness, type Readiness } from "./ComparisonReadiness";
import { useEffect, useRef, useState } from "react";
import { request, type Anchor } from "./workspaceApi";
import "./boundaries.css";
import { ResearchTasks } from "./ResearchTasks";

type Note = { id: number; note: string; title: string };
type Source = Anchor & { note_id: number; quote: string; observation: string };
type Cell = { value: string; quote: string; note_id: number };
type Paper = {
  document_id: string;
  title: string;
  version: number | null;
  sources: Source[];
  cells: Record<string, Cell | null>;
};
type Comparison = {
  readiness?: Readiness;
  archived: number;
  id: string;
  title: string;
  revision: number;
  content: { papers: Paper[]; fields: Record<string, string>; notice: string };
};
type History = {
  items: { id: string; title: string; revision: number; archived: number }[];
  total: number;
};
type Draft = {
  document: string;
  field: string;
  revision: number;
  value: string;
  quote: string;
  note_id: number;
};

export function EvidenceBoundaries({
  notes,
  onLocate,
  initialId,
}: {
  notes: Note[];
  onLocate: (a: Anchor) => void;
  initialId?: string;
}) {
  const [open, setOpen] = useState(false),
    [chosen, setChosen] = useState<number[]>([]),
    [title, setTitle] = useState("论文证据边界对照");
  const [showArchived, setShowArchived] = useState(false);
  const [projects, setProjects] = useState<
    { id: string; title: string; archived: number }[]
  >([]);
  const [projectId, setProjectId] = useState("");
  const [taskReload, setTaskReload] = useState(0);
  const [taskEditing, setTaskEditing] = useState(false);
  const [table, setTable] = useState<Comparison | null>(null),
    [history, setHistory] = useState<History | null>(null),
    [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [conflict, setConflict] = useState<Comparison | null>(null);
  const panel = useRef<HTMLElement>(null),
    key = useRef<{ signature: string; id: string } | null>(null);
  const paper = table?.content.papers.find(
    (p) => p.document_id === draft?.document,
  );
  const source = paper?.sources.find((s) => s.note_id === draft?.note_id);
  useEffect(() => {
    if (!initialId) return;
    let live = true;
    setOpen(true);
    Promise.all([
      request<Comparison>(`/api/boundaries/${initialId}`),
      request<History>("/api/boundaries"),
      request<{ id: string; title: string; archived: number }[]>(
        "/api/projects",
      ),
    ])
      .then(([v, h, p]) => {
        if (live) {
          setTable(v);
          setHistory(h);
          setProjects(p.filter((p) => !p.archived));
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [initialId]);
  useEffect(() => {
    if (!draft?.document) return;
    const editor = panel.current?.querySelector(".boundaries-editor");
    editor?.scrollIntoView({ block: "start" });
    editor?.querySelector("textarea")?.focus({ preventScroll: true });
  }, [draft?.document, draft?.field]);
  useEffect(() => {
    if (!draft) return;
    const unload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const guard = (e: MouseEvent) => {
      if (
        e.target instanceof Element &&
        !panel.current?.contains(e.target) &&
        e.target.closest("button,a") &&
        !confirm("对照单元格正在编辑，离开可能丢失草稿。确定继续吗？")
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", guard, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", guard, true);
    };
  }, [draft]);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    const [h, p] = await Promise.all([
      request<History>(`/api/boundaries?archived=${showArchived}`),
      request<{ id: string; title: string; archived: number }[]>(
        "/api/projects",
      ),
    ]);
    setHistory(h);
    setProjects(p.filter((p) => !p.archived));
  }
  async function reloadTable() {
    if (table)
      setTable(await request<Comparison>(`/api/boundaries/${table.id}`));
    await refresh();
  }
  async function openTable(id: string) {
    setTable(await request<Comparison>(`/api/boundaries/${id}`));
    setDraft(null);
  }
  async function makeTask(p: Paper, field: string) {
    if (!table) return;
    await request("/api/research-tasks", {
      project_id: projectId,
      comparison_id: table.id,
      document_id: p.document_id,
      field,
      comparison_revision: table.revision,
    });
    setTaskReload((v) => v + 1);
    setMessage("已加入研究补查待办；同一项目同一缺口会复用已有任务。");
  }
  async function create() {
    const body = { title: title.trim(), note_ids: chosen },
      signature = JSON.stringify(body);
    if (key.current?.signature !== signature)
      key.current = { signature, id: crypto.randomUUID() };
    const result = await request<Comparison>("/api/boundaries", {
      ...body,
      request_id: key.current.id,
    });
    setTable(result);
    key.current = null;
    await refresh();
  }
  function edit(p: Paper, field: string) {
    const c = p.cells[field];
    setDraft({
      document: p.document_id,
      field,
      revision: table!.revision,
      value: c?.value || "",
      quote: c?.quote || "",
      note_id: c?.note_id || p.sources[0].note_id,
    });
    setConflict(null);
    setError("");
  }
  async function save() {
    if (!table || !draft) return;
    const next = await request<Comparison>(
      `/api/boundaries/${table.id}/cells/${draft.document}/${draft.field}`,
      draft,
      "PATCH",
    );
    setTable(next);
    setDraft(null);
    setConflict(null);
    setMessage("单元格已保存；摘录存在不等于解释一定正确，请继续核对上下文。");
    await refresh();
  }
  const filled =
    table?.content.papers.reduce(
      (n, p) => n + Object.values(p.cells).filter(Boolean).length,
      0,
    ) || 0;
  return (
    <section
      ref={panel}
      className="boundaries-panel"
      aria-label="证据边界对照表"
    >
      <div className="recall-heading">
        <div>
          <span className="eyebrow">COMPARE WITH CONTEXT</span>
          <h2>这些论文，真的能放在一起比吗？</h2>
          <p>把对象、数据、指标、条件与限制逐项摆出来，先看清比较的边界。</p>
        </div>
        <button
          className="primary-button"
          disabled={busy || !!draft}
          aria-expanded={open}
          onClick={() => {
            setOpen(!open);
            if (!open) void run(refresh);
          }}
        >
          {open ? "收起边界对照" : "开始边界对照"}
        </button>
      </div>
      {open && (
        <>
          <details className="extended-help">
            <summary>边界对照怎么用？</summary>
            <p>
              先保存来自2—3篇文献的2—6条证据笔记，同一篇可以选择多条。创建后每篇有五个维度，点击单元格填写自己的整理，再从来源复制对应摘录。系统检查摘录存在，不自动判断理解正确、条件相同或结果优劣。空格表示待补查，不表示论文没有报告。
            </p>
            <p>
              逐格保存后可刷新找回、导出Markdown/JSON或跳回PDF。将整理和摘录都清空后保存，可恢复为待补查；取消编辑会放弃本次草稿。多页面冲突时先查看最新值，再确认保存。对照表保留创建时的来源快照，更新笔记和论文不会自动改写旧表；当前历史显示最近100份。
            </p>
          </details>
          {error && (
            <p className="work-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <details className="boundaries-builder" open={!table}>
            <summary>选择证据，创建对照表</summary>
            <label>
              对照表标题
              <input
                aria-label="对照表标题"
                maxLength={120}
                value={title}
                disabled={busy || !!draft}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <div className="boundaries-notes">
              {notes.map((n) => (
                <label key={n.id}>
                  <input
                    type="checkbox"
                    aria-label={`对照证据：${n.note}`}
                    disabled={
                      busy ||
                      !!draft ||
                      (chosen.length >= 6 && !chosen.includes(n.id))
                    }
                    checked={chosen.includes(n.id)}
                    onChange={(e) =>
                      setChosen(
                        e.target.checked
                          ? [...chosen, n.id]
                          : chosen.filter((id) => id !== n.id),
                      )
                    }
                  />
                  <span>
                    {n.note}
                    <small>{n.title}</small>
                  </span>
                </label>
              ))}
            </div>
            {!notes.length && (
              <p>先在阅读台保存两篇文献的证据笔记，再回来对照。</p>
            )}
            <button
              disabled={
                busy || !!draft || chosen.length < 2 || title.trim().length < 2
              }
              onClick={() => void run(create)}
            >
              创建边界对照 · {chosen.length} 条证据
            </button>
          </details>
          <details className="boundaries-history">
            <summary>已保存的对照表（{history?.total || 0}）</summary>
            <label>
              <input
                type="checkbox"
                checked={showArchived}
                disabled={busy || !!draft || taskEditing}
                onChange={(e) => {
                  const value = e.target.checked;
                  setShowArchived(value);
                  void run(async () =>
                    setHistory(
                      await request<History>(
                        `/api/boundaries?archived=${value}`,
                      ),
                    ),
                  );
                }}
              />
              查看已归档对照表
            </label>
            <button disabled={busy} onClick={() => void run(refresh)}>
              刷新对照记录
            </button>
            {history?.items.map((i) => (
              <div className="work-row" key={i.id}>
                <span>{i.title}</span>
                <button
                  disabled={busy || !!draft}
                  aria-label={`打开对照：${i.title}`}
                  onClick={() =>
                    void run(async () => {
                      setTable(
                        await request<Comparison>(`/api/boundaries/${i.id}`),
                      );
                    })
                  }
                >
                  打开对照
                </button>
                <button
                  disabled={busy || !!draft || taskEditing}
                  aria-label={`${i.archived ? "恢复" : "归档"}对照：${i.title}`}
                  onClick={() =>
                    void run(async () => {
                      const next = await request<Comparison>(
                        `/api/boundaries/${i.id}`,
                        { revision: i.revision, archived: !i.archived },
                        "PATCH",
                      );
                      if (table?.id === i.id) {
                        setTable(next);
                        setTaskReload((v) => v + 1);
                      }
                      await refresh();
                      setMessage(
                        i.archived
                          ? "对照表已恢复，原内容与待办历史保留。"
                          : "对照表已归档，原内容与待办历史保留。",
                      );
                    })
                  }
                >
                  {i.archived ? "恢复对照表" : "归档对照表"}
                </button>
              </div>
            ))}
            {!!history && history.total > 100 && <p>仅显示最近100份。</p>}
          </details>
          {table && (
            <>
              <div className="work-row">
                <h3>{table.title}</h3>
                <span>
                  已整理 {filled}/{table.content.papers.length * 5} 格 ·
                  不代表可比性评分
                </span>
                {!draft && (
                  <>
                    <a href={`/api/boundaries/${table.id}/export?format=md`}>
                      导出边界 Markdown
                    </a>
                    <a href={`/api/boundaries/${table.id}/export?format=json`}>
                      导出边界 JSON
                    </a>
                  </>
                )}
              </div>
              <p className="boundaries-notice">{table.content.notice}</p>
              <ComparisonReadiness
                value={table.readiness}
                fields={table.content.fields}
                onFill={
                  !table.archived && !busy && !draft && !taskEditing
                    ? (document, field) => {
                        const p = table.content.papers.find(
                          (p) => p.document_id === document,
                        );
                        if (p) edit(p, field);
                      }
                    : undefined
                }
              />
              {!!table.archived && (
                <p role="status">
                  此对照表已归档，只读保留；在历史记录勾选“查看已归档对照表”后恢复。
                </p>
              )}
              {!table.archived && (
                <label>
                  补查待办归属项目
                  <select
                    aria-label="补查待办归属项目"
                    disabled={busy || !!draft || taskEditing}
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                  >
                    <option value="">选择包含目标论文的研究项目</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                  <small>
                    项目需要已加入目标文献；可在研究项目中维护。待办不会自动添加或改变项目文献范围。
                  </small>
                </label>
              )}
              <div
                className="boundaries-scroll"
                role="region"
                aria-label="可横向滚动的论文对照"
                tabIndex={0}
              >
                <table data-papers={table.content.papers.length}>
                  <thead>
                    <tr>
                      <th scope="col">核对维度</th>
                      {table.content.papers.map((p) => (
                        <th scope="col" key={p.document_id}>
                          {p.title}
                          <small>
                            v{p.version || "?"} · {p.sources.length} 条证据
                          </small>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(table.content.fields).map(
                      ([field, label]) => (
                        <tr key={field}>
                          <th scope="row">{label}</th>
                          {table.content.papers.map((p) => (
                            <td key={p.document_id}>
                              <p>{p.cells[field]?.value || "待补查"}</p>
                              {p.cells[field] && (
                                <details>
                                  <summary>查看对应摘录</summary>
                                  <small>
                                    PDF第
                                    {
                                      p.sources.find(
                                        (s) =>
                                          s.note_id === p.cells[field]!.note_id,
                                      )?.page
                                    }
                                    页 · 笔记 #{p.cells[field]!.note_id}
                                  </small>
                                  <blockquote>
                                    {p.cells[field]!.quote}
                                  </blockquote>
                                  <button
                                    disabled={!!draft || busy}
                                    onClick={() => {
                                      const s = p.sources.find(
                                        (s) =>
                                          s.note_id === p.cells[field]!.note_id,
                                      )!;
                                      onLocate({ ...s, id: s.block_id });
                                    }}
                                  >
                                    回到单元格原文
                                  </button>
                                </details>
                              )}
                              <button
                                disabled={
                                  !!draft ||
                                  busy ||
                                  !!table.archived ||
                                  taskEditing
                                }
                                aria-label={`编辑${label}：${p.title}`}
                                onClick={() => edit(p, field)}
                              >
                                整理这一格
                              </button>
                              {!p.cells[field] && !table.archived && (
                                <button
                                  disabled={
                                    !!draft || busy || taskEditing || !projectId
                                  }
                                  aria-label={`加入补查：${label}：${p.title}`}
                                  onClick={() =>
                                    void run(() => makeTask(p, field))
                                  }
                                >
                                  加入研究待办
                                </button>
                              )}
                            </td>
                          ))}
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
              <small>
                窄屏可左右滑动表格；空白只表示当前证据尚未整理充分。
              </small>
              <ResearchTasks
                key={`${table.id}-${taskReload}`}
                comparisonId={table.id}
                onOpenComparison={(id) => void run(() => openTable(id))}
                onLocate={onLocate}
                onChanged={reloadTable}
                onEditingChange={setTaskEditing}
                disabled={busy || !!draft}
              />
              {draft && paper && (
                <div
                  className="boundaries-editor"
                  role="region"
                  aria-label="对照单元格编辑"
                >
                  <h3>
                    {table.content.fields[draft.field]} · {paper.title}
                  </h3>
                  <label>
                    本篇来源
                    <select
                      aria-label="单元格来源"
                      value={draft.note_id}
                      disabled={busy}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          note_id: Number(e.target.value),
                          quote: "",
                        })
                      }
                    >
                      {paper.sources.map((s) => (
                        <option key={s.note_id} value={s.note_id}>
                          第{s.page}页 · {s.observation}
                        </option>
                      ))}
                    </select>
                  </label>
                  <details open>
                    <summary>可用原文证据</summary>
                    <blockquote>{source?.quote}</blockquote>
                  </details>
                  <label>
                    我的整理
                    <textarea
                      aria-label="单元格整理"
                      maxLength={1500}
                      disabled={busy}
                      value={draft.value}
                      onChange={(e) =>
                        setDraft({ ...draft, value: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    对应原文摘录
                    <textarea
                      aria-label="单元格摘录"
                      maxLength={12000}
                      disabled={busy}
                      value={draft.quote}
                      onChange={(e) =>
                        setDraft({ ...draft, quote: e.target.value })
                      }
                    />
                  </label>
                  <div className="work-row">
                    <button
                      disabled={busy}
                      onClick={() =>
                        setDraft({ ...draft, quote: source?.quote || "" })
                      }
                    >
                      使用这段原文
                    </button>
                    <button
                      className="primary-button"
                      disabled={busy}
                      onClick={() => void run(save)}
                    >
                      保存单元格
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => {
                        setDraft(null);
                        setConflict(null);
                        setError("");
                      }}
                    >
                      取消编辑
                    </button>
                  </div>
                  {error && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void run(async () =>
                          setConflict(
                            await request<Comparison>(
                              `/api/boundaries/${table.id}`,
                            ),
                          ),
                        )
                      }
                    >
                      载入最新对照，保留草稿
                    </button>
                  )}
                  {conflict && (
                    <div className="boundaries-conflict">
                      <strong>服务器最新单元格</strong>
                      <pre>
                        {JSON.stringify(
                          conflict.content.papers.find(
                            (p) => p.document_id === draft.document,
                          )?.cells[draft.field] || "待补查",
                          null,
                          2,
                        )}
                      </pre>
                      <button
                        disabled={busy}
                        onClick={() => {
                          setTable(conflict);
                          setDraft({ ...draft, revision: conflict.revision });
                          setConflict(null);
                          setError("");
                        }}
                      >
                        已核对，继续保存我的草稿
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
