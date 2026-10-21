import { useEffect, useRef, useState } from "react";
import { request, type Anchor } from "./workspaceApi";
import "./rehearsal.css";

type Note = { id: number; note: string; title: string };
type Source = Anchor & {
  quote: string;
  observation: string;
  title: string;
  version: number | null;
};
type Round = {
  id: number;
  label: string;
  question: string;
  source: Source;
  answer: string;
  checks: string[];
  saved_at: string | null;
};
type Session = {
  id: string;
  title: string;
  revision: number;
  content: { rounds: Round[]; notice: string };
};
type History = {
  sessions: { id: string; title: string; updated_at: string }[];
  total: number;
  limit: number;
};
const CHECKS = {
  source: "核对了原文依据",
  conditions: "核对了数字对象与适用条件",
  unknowns: "标出了未确认或待补查内容",
};

export function Rehearsal({
  notes,
  onLocate,
}: {
  notes: Note[];
  onLocate: (a: Anchor) => void;
}) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<number[]>([]);
  const [title, setTitle] = useState("我的论文组会演练");
  const [session, setSession] = useState<Session | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [step, setStep] = useState(0);
  const [answer, setAnswer] = useState("");
  const [checks, setChecks] = useState<string[]>([]);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [conflict, setConflict] = useState<Session | null>(null);
  const requestKey = useRef<{ signature: string; id: string } | null>(null);
  const panelRef = useRef<HTMLElement>(null);
  const [remaining, setRemaining] = useState(180);
  const [deadline, setDeadline] = useState<number | null>(null);
  const round = session?.content.rounds[step];
  const dirty =
    !!round &&
    (answer !== round.answer ||
      JSON.stringify(checks) !== JSON.stringify(round.checks));
  useEffect(() => {
    if (!deadline) return;
    const tick = () => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setRemaining(left);
      if (!left) setDeadline(null);
    };
    tick();
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  }, [deadline]);
  useEffect(() => {
    if (!dirty) return;
    const protect = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (event: MouseEvent) => {
      const target = event.target;
      if (
        !(target instanceof Element) ||
        panelRef.current?.contains(target) ||
        !target.closest("button,a")
      )
        return;
      if (
        !window.confirm(
          "本轮演练有未保存的回答。离开可能丢失草稿，确定继续吗？",
        )
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    document.addEventListener("click", guard, true);
    return () => document.removeEventListener("click", guard, true);
  }, [dirty]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void fetch("/api/rehearsal", { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error("演练历史加载失败，请刷新重试");
        return r.json() as Promise<History>;
      })
      .then((v) => {
        if (!controller.signal.aborted) setHistory(v);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError((e as Error).message);
      });
    return () => controller.abort();
  }, [open]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function refreshHistory() {
    setHistory(await request<History>("/api/rehearsal"));
  }
  function load(value: Session, index = 0) {
    setSession(value);
    setStep(index);
    setAnswer(value.content.rounds[index].answer);
    setChecks(value.content.rounds[index].checks);
    setRevealed(false);
    setConflict(null);
    setDeadline(null);
    setRemaining(180);
    setMessage("");
  }
  async function create() {
    const spec = { title: title.trim(), note_ids: chosen };
    const signature = JSON.stringify(spec);
    if (requestKey.current?.signature !== signature)
      requestKey.current = { signature, id: crypto.randomUUID() };
    const next = await request<Session>("/api/rehearsal", {
      ...spec,
      request_id: requestKey.current.id,
    });
    load(next);
    requestKey.current = null;
    await refreshHistory();
  }
  async function save() {
    if (!session || !round) return;
    const next = await request<Session>(
      `/api/rehearsal/${session.id}/rounds/${step}`,
      { revision: session.revision, answer, checks },
      "PATCH",
    );
    setSession(next);
    setMessage("这一轮的回答和自检已保存，可以继续或导出。");
    setConflict(null);
    await refreshHistory();
  }
  const saved =
    session?.content.rounds.filter((r) => r.answer.trim()).length || 0;
  return (
    <section ref={panelRef} className="rehearsal-panel" aria-label="组会演练">
      <div className="recall-heading">
        <div>
          <span className="eyebrow">EXPLAIN · DEFEND · VERIFY</span>
          <h2>组会前，先把自己问住</h2>
          <p>
            三分钟讲清主张，再练习证据追问与适用边界。每轮带着真实出处练习。
          </p>
        </div>
        <button
          className="primary-button"
          aria-expanded={open}
          disabled={dirty || busy}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "收起组会演练" : "开始组会演练"}
        </button>
      </div>
      {open && (
        <>
          <details className="extended-help">
            <summary>组会演练怎么用？</summary>
            <p>
              选择1—3条证据笔记，每条安排“讲清主张、回应证据追问、说明适用边界”三轮。问题是通用练习模板，不是AI对论文的事实判断。可以先口述或记录要点，再展开原文，标出条件和不确定内容。计时仅辅助口述，不录音、不上传音频、不自动评分。
            </p>
            <p>
              点击“保存本轮回答”持久保存回答和自检。换轮、打开其他演练或跳原文前请保存；未保存草稿离开当前页面可能丢失。浏览器刷新时会提示未保存内容。所有回答填过也只代表练习覆盖，不能证明内容正确。历史记录最多展示最近100场，可导出Markdown或JSON保存。
            </p>
          </details>
          {error && (
            <p className="work-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <details className="rehearsal-builder" open={!session}>
            <summary>选择证据，创建新演练</summary>
            <label>
              演练标题
              <input
                aria-label="演练标题"
                value={title}
                maxLength={120}
                disabled={busy || dirty}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <div className="rehearsal-notes">
              {notes.map((n) => (
                <label key={n.id}>
                  <input
                    type="checkbox"
                    aria-label={`演练证据：${n.note}`}
                    checked={chosen.includes(n.id)}
                    disabled={
                      busy ||
                      dirty ||
                      (chosen.length >= 3 && !chosen.includes(n.id))
                    }
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
            {!notes.length && <p>先在阅读台保存证据笔记，再回来练习。</p>}
            <button
              disabled={
                busy || dirty || !chosen.length || title.trim().length < 2
              }
              onClick={() => void run(create)}
            >
              创建演练 · {chosen.length * 3} 轮
            </button>
          </details>
          <details className="rehearsal-history">
            <summary>我的演练记录（{history?.total || 0}）</summary>
            <button disabled={busy} onClick={() => void run(refreshHistory)}>
              刷新演练记录
            </button>
            {history?.sessions.map((s) => (
              <div className="work-row" key={s.id}>
                <span>
                  {s.title} · {new Date(s.updated_at).toLocaleString("zh-CN")}
                </span>
                <button
                  disabled={busy || dirty}
                  aria-label={`打开演练：${s.title}`}
                  onClick={() =>
                    void run(async () =>
                      load(await request<Session>(`/api/rehearsal/${s.id}`)),
                    )
                  }
                >
                  继续演练
                </button>
              </div>
            ))}
            {!!history && history.total > history.limit && (
              <p>仅展示最近 {history.limit} 场。</p>
            )}
          </details>
          {session && round && (
            <div className="rehearsal-session">
              <div className="work-row">
                <h3>{session.title}</h3>
                <span>
                  已填写 {saved}/{session.content.rounds.length} 轮
                </span>
                {!dirty ? (
                  <>
                    <a href={`/api/rehearsal/${session.id}/export?format=md`}>
                      导出演练 Markdown
                    </a>
                    <a href={`/api/rehearsal/${session.id}/export?format=json`}>
                      导出演练 JSON
                    </a>
                  </>
                ) : (
                  <span>保存后可导出最新记录</span>
                )}
              </div>
              <nav aria-label="演练轮次" className="rehearsal-steps">
                {session.content.rounds.map((r, i) => (
                  <button
                    key={r.id}
                    disabled={busy || dirty}
                    aria-current={step === i ? "step" : undefined}
                    onClick={() => load(session, i)}
                  >
                    {i + 1}. {r.label}
                    {r.answer.trim() ? " ✓" : ""}
                  </button>
                ))}
              </nav>
              <article className="rehearsal-round">
                <span className="eyebrow">
                  第 {step + 1} 轮 · {round.label}
                </span>
                <h3>{round.question}</h3>
                <p>
                  {round.source.title} · v{round.source.version || "?"} · 第{" "}
                  {round.source.page} 页
                </p>
                <div className="rehearsal-timer">
                  <strong aria-label="口述剩余时间">
                    {Math.floor(remaining / 60)}:
                    {String(remaining % 60).padStart(2, "0")}
                  </strong>
                  <button
                    onClick={() => {
                      if (deadline) {
                        setRemaining(
                          Math.max(
                            0,
                            Math.ceil((deadline - Date.now()) / 1000),
                          ),
                        );
                        setDeadline(null);
                      } else
                        setDeadline(
                          Date.now() +
                            Math.max(
                              remaining,
                              180 * (remaining === 0 ? 1 : 0),
                            ) *
                              1000,
                        );
                    }}
                  >
                    {deadline ? "暂停计时" : "开始口述计时"}
                  </button>
                  <button
                    onClick={() => {
                      setDeadline(null);
                      setRemaining(180);
                    }}
                  >
                    重置为3分钟
                  </button>
                  <small>
                    {remaining === 0
                      ? "计时结束，仍可继续整理回答。"
                      : "计时不录音，不作为评分。"}
                  </small>
                </div>
                <label>
                  我的回答与待补查问题
                  <textarea
                    aria-label="本轮演练回答"
                    value={answer}
                    maxLength={6000}
                    disabled={busy}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder="先用自己的话讲清，再写下原文不足以支持的部分。"
                  />
                </label>
                <button onClick={() => setRevealed((v) => !v)}>
                  {revealed ? "收起本轮证据" : "展开本轮证据"}
                </button>
                {revealed && (
                  <div className="rehearsal-source">
                    <strong>创建时的笔记观察（非标准答案）</strong>
                    <p>{round.source.observation}</p>
                    <blockquote>{round.source.quote}</blockquote>
                    <button
                      disabled={dirty || busy}
                      onClick={() => {
                        setDeadline(null);
                        onLocate({
                          ...round.source,
                          id: round.source.block_id,
                        });
                      }}
                    >
                      回到本轮原文
                    </button>
                  </div>
                )}
                <fieldset>
                  <legend>我的自检（由你确认，不是自动评分）</legend>
                  {Object.entries(CHECKS).map(([key, label]) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={checks.includes(key)}
                        disabled={busy}
                        onChange={(e) =>
                          setChecks(
                            e.target.checked
                              ? [...checks, key]
                              : checks.filter((c) => c !== key),
                          )
                        }
                      />
                      {label}
                    </label>
                  ))}
                </fieldset>
                <div className="work-row">
                  <button
                    className="primary-button"
                    disabled={busy}
                    onClick={() => void run(save)}
                  >
                    保存本轮回答
                  </button>
                  <span role="status">
                    {dirty
                      ? "有未保存修改，保存后再换轮或跳原文。"
                      : round.saved_at
                        ? "当前回答已保存"
                        : "本轮尚未保存"}
                  </span>
                </div>
                {error && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        setConflict(
                          await request<Session>(
                            `/api/rehearsal/${session.id}`,
                          ),
                        );
                      })
                    }
                  >
                    载入最新演练，保留当前草稿
                  </button>
                )}
                {conflict && (
                  <div className="rehearsal-conflict">
                    <p>服务器最新回答：</p>
                    <pre>
                      {conflict.content.rounds[step].answer || "尚未填写"}
                    </pre>
                    <button
                      disabled={busy}
                      onClick={() => {
                        setSession(conflict);
                        setConflict(null);
                        setError("");
                        setMessage(
                          "已载入最新版本，当前草稿仍保留；核对后点击保存。",
                        );
                      }}
                    >
                      已核对，保留草稿继续保存
                    </button>
                  </div>
                )}
              </article>
              {saved === session.content.rounds.length && (
                <p className="rehearsal-complete">
                  各轮均已填写。建议再检查一次引用条件和待补查问题，然后导出作为组会准备稿。
                </p>
              )}
              <p className="muted">{session.content.notice}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
