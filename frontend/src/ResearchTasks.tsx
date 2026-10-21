import { useEffect, useRef, useState } from "react";
import { request, type Anchor } from "./workspaceApi";
import "./researchTasks.css";
type Note = Omit<Anchor, "id"> & { id: number; note: string; quote: string };
type Evidence = {
  source: Anchor & { quote: string };
  cell: { value: string; quote: string };
  comparison_revision: number;
};
type Task = {
  id: string;
  title: string;
  project_title: string;
  project_id: string;
  comparison_id: string;
  comparison_title: string;
  document_id: string;
  field: string;
  state: string;
  revision: number;
  comparison_revision: number;
  project_archived: number;
  comparison_archived: number;
  source_in_project: number;
  outcome: string;
  evidence: Evidence | null;
  events: {
    id: number;
    state: string;
    outcome: string;
    created_at: string;
    evidence: Evidence | null;
  }[];
};
type List = { items: Task[]; total: number };
const labels: Record<string, string> = {
  todo: "待补查",
  working: "补查中",
  done: "已回填",
  dismissed: "未解决关闭",
};
type Draft = {
  task: Task;
  mode: "complete" | "dismissed";
  value: string;
  quote: string;
  note_id: number;
};
export function ResearchTasks({
  projectId,
  comparisonId,
  onOpenComparison,
  onLocate,
  onChanged,
  onEditingChange,
  disabled = false,
}: {
  projectId?: string;
  comparisonId?: string;
  onOpenComparison: (id: string) => void;
  onLocate: (a: Anchor) => void;
  onChanged?: () => Promise<void>;
  onEditingChange?: (v: boolean) => void;
  disabled?: boolean;
}) {
  const [list, setList] = useState<List>({ items: [], total: 0 }),
    [notes, setNotes] = useState<Note[]>([]),
    [draft, setDraft] = useState<Draft | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!draft) return;
    const editor = panel.current?.querySelector(".research-task-editor");
    editor?.scrollIntoView({ block: "start" });
    editor?.querySelector("textarea")?.focus({ preventScroll: true });
  }, [draft?.task.id, draft?.mode]);
  const query = new URLSearchParams({
    ...(projectId ? { project_id: projectId } : {}),
    ...(comparisonId ? { comparison_id: comparisonId } : {}),
  }).toString();
  async function refresh() {
    setList(await request<List>(`/api/research-tasks?${query}`));
  }
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/research-tasks?${query}`, { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw Error("研究待办加载失败");
        return r.json() as Promise<List>;
      })
      .then((v) => {
        if (!controller.signal.aborted) setList(v);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      });
    return () => controller.abort();
  }, [query]);
  useEffect(() => {
    onEditingChange?.(!!draft);
    return () => onEditingChange?.(false);
  }, [!!draft, onEditingChange]);
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
        !confirm("待办有未保存草稿，离开可能丢失。确定继续吗？")
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
  async function change(t: Task, state: string) {
    await request(
      `/api/research-tasks/${t.id}`,
      { revision: t.revision, state },
      "PATCH",
    );
    await refresh();
    await onChanged?.();
  }
  async function edit(t: Task, mode: Draft["mode"]) {
    const found = await request<Note[]>("/api/notes");
    setNotes(found.filter((n) => n.document_id === t.document_id));
    setDraft({ task: t, mode, value: "", quote: "", note_id: 0 });
  }
  async function save() {
    if (!draft) return;
    const t = draft.task;
    if (draft.mode === "complete") {
      await request(`/api/research-tasks/${t.id}/complete`, {
        revision: t.revision,
        comparison_revision: t.comparison_revision,
        note_id: draft.note_id,
        value: draft.value,
        quote: draft.quote,
      });
    } else {
      await request(
        `/api/research-tasks/${t.id}`,
        { revision: t.revision, state: "dismissed", outcome: draft.value },
        "PATCH",
      );
    }
    setDraft(null);
    await refresh();
    await onChanged?.();
    setMessage(
      draft.mode === "complete"
        ? "证据与单元格已一起保存，待办标记为已回填；仍需人工核对解释。"
        : "已记录未解决原因，没有把缺口标成已证实。",
    );
  }
  const latest = list.items.find((t) => t.id === draft?.task.id);
  return (
    <section className="research-tasks" ref={panel} aria-label="研究补查待办">
      <div className="work-row">
        <h3>研究补查待办 · {list.total}</h3>
        <button disabled={busy} onClick={() => void run(refresh)}>
          刷新补查待办
        </button>
      </div>
      <details className="extended-help">
        <summary>补查待办怎么用？</summary>
        <p>
          从边界对照的空格创建待办，选择包含该论文的项目。开始补查后，在阅读台保存新的证据笔记；回来选择本篇笔记、填写整理和摘录，点击“保存依据并回填”。任务与单元格一起保存，目标已有内容时不会覆盖。没找到依据可说明原因并“未解决关闭”。重新打开会保留历史和已回填内容；若要再次回填，先核对并手动清空目标格。
        </p>
        <p>
          归档项目或对照表、移出或归档文献后待办保留但暂停操作。归档恢复不会删除处理历史。刷新待办不会丢弃当前表单，冲突后需核对最新版本再确认；强制关闭仍可能丢失未保存草稿。列表最多展示最近200条，完整历史进入项目导出。
        </p>
      </details>
      {error && (
        <p role="alert" className="work-error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {!list.total && (
        <p>还没有补查待办。在证据边界对照表中，从“待补查”单元格创建。</p>
      )}
      {list.total > 200 && <p>仅显示最近200条；完整记录可在项目导出中查看。</p>}
      {list.items.map((t) => {
        const locked =
          !!t.project_archived ||
          !!t.comparison_archived ||
          !t.source_in_project;
        return (
          <article key={t.id} className="research-task">
            <div className="work-row">
              <strong>{t.title}</strong>
              <span className={`task-state ${t.state}`}>{labels[t.state]}</span>
            </div>
            <p>
              {t.project_title} · {t.comparison_title}
            </p>
            {t.outcome && <p>处理说明：{t.outcome}</p>}
            {locked && (
              <p>项目/对照表已归档或文献关联已变更，恢复后可继续处理。</p>
            )}
            <div className="work-row">
              <button
                disabled={busy || !!draft || disabled}
                onClick={() => onOpenComparison(t.comparison_id)}
              >
                返回对应对照表
              </button>
              {!locked && (
                <>
                  {t.state === "todo" && (
                    <button
                      disabled={busy || !!draft || disabled}
                      onClick={() => void run(() => change(t, "working"))}
                    >
                      开始补查
                    </button>
                  )}
                  {["todo", "working"].includes(t.state) ? (
                    <>
                      <button
                        disabled={busy || !!draft || disabled}
                        onClick={() => void run(() => edit(t, "complete"))}
                      >
                        记录依据并回填
                      </button>
                      <button
                        disabled={busy || !!draft || disabled}
                        onClick={() => void run(() => edit(t, "dismissed"))}
                      >
                        未解决关闭
                      </button>
                    </>
                  ) : (
                    <button
                      disabled={busy || !!draft || disabled}
                      onClick={() => void run(() => change(t, "todo"))}
                    >
                      重新打开待办
                    </button>
                  )}
                </>
              )}
              {t.evidence && (
                <button
                  disabled={busy || !!draft || disabled}
                  onClick={() =>
                    onLocate({
                      ...t.evidence!.source,
                      id: t.evidence!.source.block_id,
                    })
                  }
                >
                  查看完成时原文
                </button>
              )}
            </div>
            <details>
              <summary>处理历史（{t.events.length}）</summary>
              {t.events.map((e) => (
                <div className="task-event" key={e.id}>
                  <strong>
                    {labels[e.state]} ·{" "}
                    {new Date(e.created_at).toLocaleString("zh-CN")}
                  </strong>
                  <p>{e.outcome || "状态记录"}</p>
                  {e.evidence && (
                    <blockquote>{e.evidence.cell.quote}</blockquote>
                  )}
                </div>
              ))}
            </details>
          </article>
        );
      })}
      {draft && (
        <div
          className="research-task-editor"
          role="region"
          aria-label="补查待办编辑"
        >
          <h4>{draft.task.title}</h4>
          {draft.mode === "complete" && (
            <>
              <label>
                补查来源笔记
                <select
                  aria-label="补查来源笔记"
                  disabled={busy}
                  value={draft.note_id}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setDraft({
                      ...draft,
                      note_id: id,
                      quote: notes.find((n) => n.id === id)?.quote || "",
                    });
                  }}
                >
                  <option value={0}>选择本篇论文的证据笔记</option>
                  {notes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.note} · 第{n.page}页
                    </option>
                  ))}
                </select>
              </label>
              {!notes.length && (
                <p>
                  尚无可用笔记，请先取消编辑，在阅读台保存本篇证据，再回来刷新。
                </p>
              )}
              <blockquote>
                {notes.find((n) => n.id === draft.note_id)?.quote ||
                  "选择笔记后显示原文"}
              </blockquote>
            </>
          )}
          <label>
            {draft.mode === "complete" ? "补查后的整理" : "未解决原因"}
            <textarea
              aria-label="补查处理说明"
              disabled={busy}
              maxLength={1500}
              value={draft.value}
              onChange={(e) => setDraft({ ...draft, value: e.target.value })}
            />
          </label>
          {draft.mode === "complete" && (
            <label>
              对应摘录
              <textarea
                aria-label="补查对应摘录"
                disabled={busy}
                maxLength={12000}
                value={draft.quote}
                onChange={(e) => setDraft({ ...draft, quote: e.target.value })}
              />
            </label>
          )}
          <div className="work-row">
            <button
              className="primary-button"
              disabled={
                busy ||
                !draft.value.trim() ||
                (draft.mode === "complete" &&
                  (!draft.note_id || !draft.quote.trim()))
              }
              onClick={() => void run(save)}
            >
              {draft.mode === "complete" ? "保存依据并回填" : "确认未解决关闭"}
            </button>
            <button
              disabled={busy}
              onClick={() => {
                setDraft(null);
                setError("");
              }}
            >
              取消待办编辑
            </button>
          </div>
          {latest &&
            (latest.revision !== draft.task.revision ||
              latest.comparison_revision !==
                draft.task.comparison_revision) && (
              <div className="task-conflict">
                <p>
                  最新状态：{labels[latest.state]} ·{" "}
                  {latest.outcome || "尚无处理说明"}
                  。草稿仍保留，请先核对目标格是否已被填写。
                </p>
                <button
                  disabled={busy}
                  onClick={() => setDraft({ ...draft, task: latest })}
                >
                  已核对，使用最新版本继续
                </button>
              </div>
            )}
        </div>
      )}
    </section>
  );
}
