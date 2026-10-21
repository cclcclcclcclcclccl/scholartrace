import { AnswerChecklist, type Checklist } from "./AnswerChecklist";
import { useJobHistory } from "./useJobHistory";
import { useEffect, useRef, useState } from "react";
import { request, type Anchor, type Job } from "./workspaceApi";
import { Artifact, type Result } from "./Workbench";
import { AnswerCoverage, type Subquestion } from "./AnswerCoverage";

type Part = {
  answer_checklist?: Checklist;
  document_id: string;
  title: string;
  claims: { text: string; block_id: string; quote: string }[];
  evidence: (Anchor & { id: string })[];
  subquestions?: Subquestion[];
};
const states: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败，可恢复",
  cancelled: "已停止，可恢复",
  interrupted: "等待服务恢复",
};
export function BackgroundAnswers({
  question,
  ids,
  projectId,
  disabled,
  onLocate,
}: {
  question: string;
  ids: string[];
  projectId?: string;
  disabled: boolean;
  onLocate: (a: Anchor) => void;
}) {
  const [chosen, setChosen] = useState("");
  const [parts, setParts] = useState<Part[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const history = useJobHistory("ask", open);
  const items = history.items;
  const [pollError, setPollError] = useState("");
  const ticket = useRef(0);
  useEffect(() => {
    if (!open) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const current = chosen
          ? await request<Job>(`/api/jobs/${chosen}`, undefined, "GET", 15000)
          : null;
        const saved = chosen
          ? await request<Part[]>(
              `/api/jobs/${chosen}/answer-parts`,
              undefined,
              "GET",
              15000,
            )
          : [];
        if (live) {
          setJob(current);
          setParts(saved);
          setPollError("");
        }
      } catch (e) {
        if (live)
          setPollError(`刷新失败，已有结果保留；稍后自动重试。${String(e)}`);
      } finally {
        if (live) timer = setTimeout(() => void tick(), 2000);
      }
    };
    void tick();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [open, chosen]);
  function choose(id: string) {
    ticket.current++;
    setChosen(id);
    setJob(null);
    setParts([]);
    setResult(null);
    setError("");
  }
  async function submit() {
    setBusy(true);
    setError("");
    try {
      const created = await request<Job>("/api/jobs", {
        kind: "ask",
        payload: { question, document_ids: ids, project_id: projectId },
      });
      choose(created.id);
      setJob(created);
      setOpen(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function action(kind: "cancel" | "retry") {
    if (!job) return;
    setBusy(true);
    try {
      setJob(await request<Job>(`/api/jobs/${job.id}/${kind}`, {}));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="background-answers">
      <div className="background-answer-actions">
        <button
          className="text-button"
          disabled={
            disabled ||
            busy ||
            !question.trim() ||
            ids.length < 1 ||
            ids.length > 8
          }
          onClick={() => void submit()}
        >
          后台问答（可恢复）
        </button>
        <button
          className="text-button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "收起后台问答" : "查看后台问答"}
        </button>
      </div>
      <p className="result-note">
        长问题可选择 1—8 篇后后台处理；每篇完成即保存，离开页面不停止。Enter
        仍为直接问答。
      </p>
      {(pollError || history.error) && (
        <p className="work-error" role="alert">
          {pollError || history.error}
        </p>
      )}
      {error && (
        <p className="work-error" role="alert">
          {error}
        </p>
      )}
      {open && (
        <>
          <label>
            恢复已有问答
            <select
              aria-label="选择后台问答"
              value={chosen}
              onChange={(e) => choose(e.target.value)}
              disabled={busy}
            >
              <option value="">选择任务（当前账号的后台问答）</option>
              {items.map((t) => (
                <option key={t.id} value={t.id}>
                  {states[t.state]} · {String(t.payload.question)} ·{" "}
                  {t.created_at}
                </option>
              ))}
            </select>
          </label>
          {history.cursor !== null && (
            <button
              disabled={history.loading}
              onClick={() => void history.loadOlder()}
            >
              加载更早问答
            </button>
          )}
          {!items.length && !job && (
            <p className="result-note">
              还没有后台问答。填写问题、选择论文后可提交。
            </p>
          )}
          {job && (
            <div className="background-answer-status" role="status">
              <strong>
                {states[job.state]} · 已保存 {parts.length}/
                {(job.payload.document_ids as string[]).length} 篇
              </strong>
              <p>{String(job.payload.question)}</p>
              <progress value={job.progress} max={1} />
              <p>{job.message}</p>
              <small>
                进度按完成篇数估算，不代表回答正确率。中断的当前篇需重新处理。
              </small>
              {job.error && <p className="work-error">{job.error}</p>}
              <div className="background-answer-actions">
                {["queued", "running"].includes(job.state) && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => void action("cancel")}
                  >
                    停止后台任务
                  </button>
                )}
                {["failed", "cancelled", "interrupted"].includes(job.state) && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => void action("retry")}
                  >
                    恢复未完成论文
                  </button>
                )}
                {job.state === "completed" &&
                  typeof job.result?.id === "string" && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={async () => {
                        const stamp = ++ticket.current;
                        setBusy(true);
                        try {
                          const value = await request<Result>(
                            `/api/artifacts/${job.result!.id}`,
                          );
                          if (stamp === ticket.current) setResult(value);
                        } catch (e) {
                          if (stamp === ticket.current) setError(String(e));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      打开完整回答与导出
                    </button>
                  )}
              </div>
            </div>
          )}
          {parts.length > 0 && !result && (
            <div>
              <h3>已完成论文的结果</h3>
              {parts.map((p) => (
                <details className="background-answer-part" key={p.document_id}>
                  <summary>
                    {p.title} · {p.claims.length} 条通过初筛
                  </summary>
                  <p className="result-note">
                    仅展示本篇已保存结果，不代表其他论文或所有问题已完成。
                  </p>
                  {p.claims.map((c, i) => (
                    <div key={i}>
                      <p>{c.text}</p>
                      <details>
                        <summary>原始引用</summary>
                        <blockquote>{c.quote}</blockquote>
                      </details>
                      <button
                        className="text-button"
                        onClick={() => {
                          const b = p.evidence.find((b) => b.id === c.block_id);
                          if (b) onLocate(b);
                        }}
                      >
                        核对原文
                      </button>
                    </div>
                  ))}
                  <AnswerChecklist
                    value={p.answer_checklist}
                    onLocate={(id) => {
                      const b = p.evidence.find((b) => b.id === id);
                      if (b) onLocate(b);
                    }}
                  />
                  <AnswerCoverage
                    items={p.subquestions}
                    sources={p.evidence}
                    onLocateEvidence={(id) => {
                      const b = p.evidence.find((b) => b.id === id);
                      if (b) onLocate(b);
                    }}
                  />
                  {!p.claims.length && (
                    <p>本篇未形成通过核验的回答，请查看未解决项和候选原文。</p>
                  )}
                </details>
              ))}
            </div>
          )}
          {result && <Artifact result={result} onLocate={onLocate} />}
        </>
      )}
    </section>
  );
}
