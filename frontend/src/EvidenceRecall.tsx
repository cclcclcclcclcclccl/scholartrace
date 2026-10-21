import { useEffect, useState } from "react";
import { request, type Anchor } from "./workspaceApi";
import "./recall.css";

type Note = { id: number; note: string; title: string };
type Card = Anchor & {
  id: string;
  note_id: number;
  prompt: string;
  observation: string;
  quote: string;
  title: string;
  version: number | null;
  revision: number;
  reviews: number;
  due: boolean;
  due_at: string;
  archived: number;
};
type Deck = {
  cards: Card[];
  due_count: number;
  review_count: number;
  hidden_count: number;
  notice: string;
  archived_cards: Card[];
};

export function EvidenceRecall({
  notes,
  onLocate,
}: {
  notes: Note[];
  onLocate: (a: Anchor) => void;
}) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");
  const [prompt, setPrompt] = useState(
    "这条证据支持什么结论？有哪些关键数字或适用条件？",
  );
  const [active, setActive] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [draft, setDraft] = useState("");
  const [all, setAll] = useState(false);
  const [message, setMessage] = useState("");
  const [sessionCount, setSessionCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<{
    id: string;
    revision: number;
    prompt: string;
  } | null>(null);
  async function refresh() {
    setDeck(await request<Deck>("/api/recall"));
  }
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void fetch("/api/recall", { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error("复习卡加载失败，请刷新重试");
        return r.json() as Promise<Deck>;
      })
      .then((value) => {
        if (!controller.signal.aborted) setDeck(value);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError((e as Error).message);
      });
    return () => controller.abort();
  }, [open, notes]);
  const candidates = deck?.cards.filter((c) => all || c.due) || [];
  const card = candidates.find((c) => c.id === active) || candidates[0];
  useEffect(() => {
    setRevealed(false);
    setDraft("");
  }, [card?.id, card?.revision]);
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
  async function create() {
    const result = await request<{ card: Card; already_exists: boolean }>(
      "/api/recall",
      { note_id: Number(selected || notes[0]?.id), prompt },
    );
    await refresh();
    setActive(result.card.id);
    setAll(true);
    setRevealed(false);
    setDraft("");
    setMessage(
      result.card.archived
        ? "这条笔记的卡片已归档。请在下方“已归档的卡片”中恢复，原题目与进度仍保留。"
        : result.already_exists
          ? "这条笔记已有复习卡，已为你打开；题目和进度未覆盖。"
          : "复习卡已保存。先回忆，再展开原文核对。",
    );
  }
  async function rate(rating: string) {
    if (!card) return;
    const result = await request<{ due_at: string }>(
      `/api/recall/${card.id}/review`,
      { rating, revision: card.revision },
    );
    setSessionCount((n) => n + 1);
    setActive("");
    setAll(false);
    setRevealed(false);
    setDraft("");
    setMessage(
      `已记录本次自评，下次复习：${new Date(result.due_at).toLocaleString("zh-CN")}。`,
    );
    await refresh();
  }
  return (
    <section className="recall-panel" aria-label="证据复习卡">
      <div className="recall-heading">
        <div>
          <span className="eyebrow">READ · RECALL · VERIFY</span>
          <h2>把读过的论文，变成记得住的证据</h2>
          <p>用自己的问题挑战记忆，再翻开原文验证。每张卡都能回到论文出处。</p>
        </div>
        <button
          className="primary-button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "收起复习卡" : "开始证据复习"}
        </button>
      </div>
      {open && (
        <>
          <details className="extended-help">
            <summary>复习卡怎么玩？</summary>
            <p>
              从一条证据笔记建卡，并写一个具体问题，例如“训练用了多少张图片？这个数量属于哪个模型？”。先回忆或写下草稿，再揭示笔记观察和完整原文。自评“再想一遍”安排10分钟后复习，“有些模糊”安排1天后，“记得清楚”从3天开始递增，最长60天。这里不会用AI给你打分。
            </p>
            <p>
              每条笔记只创建一张卡，重复创建会打开旧卡。卡片保存创建时的观察与引文，修改笔记不会悄悄改变卡片。归档笔记或文献会暂时隐藏对应卡，恢复后可继续。导出的TSV可在Anki中选择制表符、允许HTML，并将三列对应正面、背面、标签；本机PDF不会随卡片导出。
            </p>
            <p>
              可独立编辑卡片题目、归档或恢复卡片，引用快照、笔记和复习进度不会随之覆盖。发生多页面冲突时保留题目草稿，刷新核对后再确认继续保存。
            </p>
          </details>
          {error && (
            <p className="work-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <div className="recall-stats">
            <span>
              <strong>{deck?.cards.length || 0}</strong> 张有据卡片
            </span>
            <span>
              <strong>{deck?.due_count || 0}</strong> 张待复习
            </span>
            <span>
              <strong>{sessionCount}</strong> 张本次完成
            </span>
            <span>累计自评 {deck?.review_count || 0} 次</span>
          </div>
          <details className="recall-builder" open={!deck?.cards.length}>
            <summary>从证据笔记创建卡片</summary>
            {!notes.length ? (
              <p>先在阅读台把一段原文存为证据笔记，再回来创建复习卡。</p>
            ) : (
              <div>
                <label>
                  选择证据笔记
                  <select
                    aria-label="复习卡来源笔记"
                    value={selected || notes[0].id}
                    onChange={(e) => setSelected(e.target.value)}
                  >
                    {notes.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.note} · {n.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  你想考自己什么？
                  <textarea
                    aria-label="复习卡问题"
                    value={prompt}
                    maxLength={500}
                    onChange={(e) => setPrompt(e.target.value)}
                  />
                </label>
                <button
                  disabled={busy || prompt.trim().length < 3}
                  onClick={() => void run(create)}
                >
                  创建并开始回忆
                </button>
              </div>
            )}
          </details>
          <div className="work-row recall-controls">
            <label>
              <input
                type="checkbox"
                checked={all}
                onChange={(e) => {
                  setAll(e.target.checked);
                  setActive("");
                }}
              />
              也练习未到期的卡片
            </label>
            <button disabled={busy} onClick={() => void run(refresh)}>
              刷新复习进度
            </button>
            <a href="/api/recall/export?format=tsv">导出 Anki TSV</a>
            <a href="/api/recall/export?format=md">导出 Markdown</a>
            <a href="/api/recall/export?format=json">备份 JSON</a>
          </div>
          {editing && (
            <div className="recall-builder" aria-label="编辑卡片题目面板">
              <label>
                修改问题
                <textarea
                  aria-label="修改复习卡题目"
                  value={editing.prompt}
                  maxLength={500}
                  onChange={(e) =>
                    setEditing({ ...editing, prompt: e.target.value })
                  }
                />
              </label>
              <button
                disabled={busy || editing.prompt.trim().length < 3}
                onClick={() =>
                  void run(async () => {
                    await request(
                      `/api/recall/${editing.id}`,
                      { revision: editing.revision, prompt: editing.prompt },
                      "PATCH",
                    );
                    setEditing(null);
                    await refresh();
                    setMessage("题目已更新，原文快照与复习进度保留。");
                  })
                }
              >
                保存卡片题目
              </button>
              <button disabled={busy} onClick={() => setEditing(null)}>
                取消编辑
              </button>
              <button disabled={busy} onClick={() => void run(refresh)}>
                载入最新卡片，保留题目草稿
              </button>
              {(() => {
                const latest = [
                  ...(deck?.cards || []),
                  ...(deck?.archived_cards || []),
                ].find((c) => c.id === editing.id);
                return latest && latest.revision !== editing.revision ? (
                  <div>
                    <p>最新题目：{latest.prompt}</p>
                    <button
                      disabled={busy}
                      onClick={() =>
                        setEditing({ ...editing, revision: latest.revision })
                      }
                    >
                      已核对，保留草稿继续保存
                    </button>
                  </div>
                ) : null;
              })()}
            </div>
          )}
          {card ? (
            <article
              className={`recall-card ${revealed ? "revealed" : ""}`}
              key={card.id}
            >
              <div className="evidence-meta">
                <span>
                  {card.due
                    ? "现在可以复习"
                    : `下次 ${new Date(card.due_at).toLocaleDateString("zh-CN")}`}
                </span>
                <span>已复习 {card.reviews} 次</span>
              </div>
              <h3>{card.prompt}</h3>
              <div className="work-row">
                <button
                  disabled={busy || !!editing}
                  onClick={() =>
                    setEditing({
                      id: card.id,
                      revision: card.revision,
                      prompt: card.prompt,
                    })
                  }
                >
                  编辑卡片题目
                </button>
                <button
                  disabled={busy || !!editing}
                  onClick={() =>
                    void run(async () => {
                      await request(
                        `/api/recall/${card.id}`,
                        { revision: card.revision, archived: true },
                        "PATCH",
                      );
                      await refresh();
                      setMessage(
                        "仅归档了卡片，原笔记与引用仍保留。可在下方恢复。",
                      );
                    })
                  }
                >
                  归档这张卡
                </button>
              </div>
              <p className="muted">
                {card.title} · v{card.version || "?"} · 第 {card.page} 页
              </p>
              {!revealed ? (
                <>
                  <textarea
                    aria-label="我的回忆草稿"
                    placeholder="可选：先写下你的回忆与不确定之处。草稿仅留在当前页面，不会上传。"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    maxLength={4000}
                  />
                  <button
                    className="primary-button"
                    onClick={() => setRevealed(true)}
                  >
                    揭示证据，核对回忆
                  </button>
                </>
              ) : (
                <>
                  {draft && (
                    <div className="recall-draft">
                      <strong>我的回忆</strong>
                      <p>{draft}</p>
                    </div>
                  )}
                  <strong>创建卡片时的笔记观察（非标准答案）</strong>
                  <p>{card.observation}</p>
                  <strong>完整原文依据</strong>
                  <blockquote>{card.quote}</blockquote>
                  <button
                    className="text-button"
                    onClick={() => onLocate({ ...card, id: card.block_id })}
                  >
                    回到论文原文
                  </button>
                  <p>结合原文中的数字、对象和适用条件，自评这次回忆：</p>
                  <div className="recall-ratings">
                    <button
                      disabled={busy}
                      onClick={() => void run(() => rate("again"))}
                    >
                      再想一遍 · 10分钟
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void run(() => rate("hard"))}
                    >
                      有些模糊 · 1天
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void run(() => rate("good"))}
                    >
                      记得清楚 · 延后复习
                    </button>
                  </div>
                </>
              )}
              {candidates.length > 1 && (
                <button
                  disabled={busy}
                  className="text-button"
                  onClick={() => {
                    const i = candidates.findIndex((c) => c.id === card.id);
                    setActive(candidates[(i + 1) % candidates.length].id);
                  }}
                >
                  换一张，不记入自评
                </button>
              )}
            </article>
          ) : (
            <div className="recall-empty">
              {deck?.cards.length
                ? "到期卡片已完成。可以休息一下，或勾选上方选项提前练习。"
                : "从你真正关心的一条证据开始，建立第一张复习卡。"}
            </div>
          )}
          {!!deck?.hidden_count && (
            <p>
              有 {deck.hidden_count}{" "}
              张卡因卡片或来源归档而隐藏。恢复卡片后，来源也需处于未归档状态。
            </p>
          )}
          {!!deck?.archived_cards.length && (
            <details className="recall-builder">
              <summary>已归档的卡片（{deck.archived_cards.length}）</summary>
              {deck.archived_cards.map((c) => (
                <div className="work-row" key={c.id}>
                  <span>{c.prompt}</span>
                  <button
                    disabled={busy}
                    aria-label={`恢复卡片：${c.prompt}`}
                    onClick={() =>
                      void run(async () => {
                        await request(
                          `/api/recall/${c.id}`,
                          { revision: c.revision, archived: false },
                          "PATCH",
                        );
                        await refresh();
                        setAll(true);
                        setActive(c.id);
                        setMessage(
                          "卡片已恢复；如果来源已归档，请再恢复笔记或文献。",
                        );
                      })
                    }
                  >
                    恢复卡片
                  </button>
                </div>
              ))}
            </details>
          )}
          <p className="muted">{deck?.notice}</p>
        </>
      )}
    </section>
  );
}
