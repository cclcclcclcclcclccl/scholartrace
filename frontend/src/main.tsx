import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  GitCompareArrows,
  Layers3,
  LoaderCircle,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  StickyNote,
  X,
} from "lucide-react";
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "./styles.css";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
type Document = {
  id: string;
  name: string;
  title: string;
  pages: number;
  chars: number;
  status: string;
  arxiv_id: string | null;
  version: number | null;
};
type Block = {
  id: string;
  document_id: string;
  page: number;
  text: string;
  bbox: number[];
  width: number;
  height: number;
  title?: string;
  version?: number;
};
type Note = {
  id: number;
  block_id: string;
  document_id: string;
  page: number;
  title: string;
  version: number;
  note: string;
  quote: string;
  bbox: number[];
};
type AuditItem = {
  note: Note;
  status: "retained" | "review_required" | "unlocated";
  similarity: number;
  candidate: Block | null;
  explanation: string;
  numbers_only_in_old: string[];
  numbers_only_in_new: string[];
  semantic_review?: {
    status: string;
    decision?: "same_claim" | "claim_changed" | "unclear";
    reason: string;
    old_quote?: string;
    new_quote?: string;
  };
};
type Answer = {
  evidence: Block[];
  message: string;
  mode: string;
  model_answer: { text: string; quote: string; block_id: string }[] | null;
};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `请求失败 (${response.status})`,
    );
  }
  return response.json();
}

function Reader({
  document,
  page,
  highlight,
}: {
  document: Document;
  page: number;
  highlight: Block | null;
}) {
  const container = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [pdf, setPdf] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [width, setWidth] = useState(680);
  const [dimensions, setDimensions] = useState({ width: 680, height: 880 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const node = container.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(200, Math.min(850, entry.contentRect.width - 52))),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    setLoading(true);
    setError("");
    setPdf(null);
    const task = pdfjs.getDocument(`/api/documents/${document.id}/pdf`);
    let cancelled = false;
    task.promise
      .then((value) => {
        if (!cancelled) setPdf(value);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [document.id]);
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    let task: pdfjs.RenderTask | undefined;
    setLoading(true);
    pdf
      .getPage(page)
      .then(async (pdfPage) => {
        if (cancelled || !canvas.current) return;
        const base = pdfPage.getViewport({ scale: 1 });
        const viewport = pdfPage.getViewport({ scale: width / base.width });
        const ratio = window.devicePixelRatio || 1;
        canvas.current.width = Math.ceil(viewport.width * ratio);
        canvas.current.height = Math.ceil(viewport.height * ratio);
        setDimensions({ width: viewport.width, height: viewport.height });
        task = pdfPage.render({
          canvas: canvas.current,
          viewport,
          transform: [ratio, 0, 0, ratio, 0, 0],
        });
        await task.promise;
        if (!cancelled) setLoading(false);
      })
      .catch((e) => {
        if (!cancelled && e?.name !== "RenderingCancelledException") {
          setError(String(e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [pdf, page, width]);
  return (
    <div className="paper-stage" ref={container}>
      {loading && (
        <div className="reader-state">
          <LoaderCircle className="spin" size={17} />
          正在呈现原文
        </div>
      )}
      {error && <div className="error-message">PDF 加载失败：{error}</div>}
      <div className="paper-sheet" style={dimensions}>
        <canvas ref={canvas} style={dimensions} />
        {!loading &&
          highlight?.document_id === document.id &&
          highlight.page === page && (
            <div
              data-testid="source-highlight"
              className="source-highlight"
              style={{
                left: `${(highlight.bbox[0] / highlight.width) * 100}%`,
                top: `${(highlight.bbox[1] / highlight.height) * 100}%`,
                width: `${((highlight.bbox[2] - highlight.bbox[0]) / highlight.width) * 100}%`,
                height: `${((highlight.bbox[3] - highlight.bbox[1]) / highlight.height) * 100}%`,
              }}
            >
              <span>原文证据</span>
            </div>
          )}
      </div>
      <div className="paper-caption">原始 PDF · 保留论文版式与页码</div>
    </div>
  );
}

function App() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState<Document | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [highlight, setHighlight] = useState<Block | null>(null);
  const [view, setView] = useState<"reader" | "notes" | "audit">("reader");
  const [notes, setNotes] = useState<Note[]>([]);
  const [auditResults, setAuditResults] = useState<AuditItem[] | null>(null);
  const [targetId, setTargetId] = useState("");
  const [modelReady, setModelReady] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [noteText, setNoteText] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function refresh() {
    const [docs, noteList] = await Promise.all([
      api<Document[]>("/api/documents"),
      api<Note[]>("/api/notes"),
    ]);
    setDocuments(docs);
    setNotes(noteList);
    setSelected((old) =>
      old
        ? docs.find((d) => d.id === old.id) || old
        : docs.find((d) => d.arxiv_id === "1706.03762" && d.version === 1) ||
          docs[0] ||
          null,
    );
    setTargetId(
      (old) =>
        old ||
        docs.find((d) => d.arxiv_id === "1706.03762" && d.version === 7)?.id ||
        "",
    );
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    api<{ model_available: boolean }>("/api/health")
      .then((h) => setModelReady(h.model_available))
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 3500);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  function selectDocument(doc: Document) {
    setSelected(doc);
    setPage(1);
    setHighlight(null);
    setAnswer(null);
    setView("reader");
  }
  function locate(block: Block) {
    const doc = documents.find((d) => d.id === block.document_id);
    if (doc) {
      setSelected(doc);
      setPage(block.page);
      setHighlight(block);
      setView("reader");
    }
  }
  async function locateNote(note: Note) {
    try {
      const blocks = await api<Block[]>(
        `/api/documents/${note.document_id}/pages/${note.page}/blocks`,
      );
      const block = blocks.find((b) => b.id === note.block_id);
      if (block) locate(block);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function ask(value = question) {
    if (!selected || !value.trim() || busy) return;
    setQuestion(value);
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      const result = await api<Answer>("/api/ask", {
        question: value,
        document_ids: [selected.id],
      });
      setAnswer(result);
      if (result.evidence[0]) locate(result.evidence[0]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save(block: Block) {
    try {
      await api("/api/notes", {
        block_id: block.id,
        note: noteText.trim() || question,
      });
      setSaving(null);
      setToast("已保存笔记及对应版本的原文");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function runAudit() {
    if (!targetId || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ results: AuditItem[] }>(
        "/api/versions/audit",
        { target_document_id: targetId },
      );
      setAuditResults(result.results);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setError("");
    try {
      for (const file of files) {
        const data = new FormData();
        data.append("file", file);
        const response = await fetch("/api/documents", {
          method: "POST",
          body: data,
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "上传失败");
      }
      await refresh();
      setToast("文献已导入");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  const filtered = documents.filter((d) =>
    `${d.title} ${d.name}`.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="研证首页">
          <span className="brand-icon">
            <Layers3 size={24} />
          </span>
          <span>
            <strong>
              研证<span className="brand-dot">.</span>
            </strong>
            <small>SCHOLARTRACE</small>
          </span>
        </a>
        <div className="workspace-label">
          我的研究空间 <span>LOCAL</span>
        </div>
        <nav className="nav-list">
          <button
            className={view === "reader" ? "active" : ""}
            onClick={() => setView("reader")}
          >
            <BookOpen size={17} />
            文献阅读台<span>{documents.length}</span>
          </button>
          <button
            className={view === "notes" ? "active" : ""}
            onClick={() => setView("notes")}
          >
            <StickyNote size={17} />
            证据笔记<span>{notes.length}</span>
          </button>
          <button
            className={view === "audit" ? "active" : ""}
            onClick={() => setView("audit")}
          >
            <GitCompareArrows size={17} />
            版本复核
          </button>
        </nav>
        <div className="library-heading">
          <span>文献库</span>
          <button
            title="导入 PDF"
            className="icon-button"
            onClick={() => fileInput.current?.click()}
          >
            <Plus size={17} />
          </button>
        </div>
        <label className="library-search">
          <Search size={14} />
          <input
            aria-label="筛选文献"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="搜索标题或文件名"
          />
        </label>
        <div className="document-list">
          {filtered.map((doc) => (
            <button
              key={doc.id}
              className={`document-item ${selected?.id === doc.id ? "selected" : ""}`}
              onClick={() => selectDocument(doc)}
              title={doc.title}
            >
              <FileText size={17} />
              <span>
                <strong>{doc.title}</strong>
                <small>
                  {doc.version ? `v${doc.version} · ` : ""}
                  {doc.pages} 页
                  {doc.status === "needs_ocr"
                    ? " · 待 OCR"
                    : doc.status === "ocr_ready"
                      ? " · 扫描件"
                      : ""}
                </small>
              </span>
            </button>
          ))}
          {!filtered.length && (
            <p className="muted empty-filter">没有匹配的文献</p>
          )}
        </div>
        <div className="sidebar-footer">
          <div className="avatar">蔡</div>
          <div>
            <strong>蔡晨霖的研究空间</strong>
            <small>证据留在本机</small>
          </div>
          <ShieldCheck size={17} />
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            研究空间
            <ChevronRight size={14} />
            <strong>
              {
                { reader: "文献阅读台", notes: "证据笔记", audit: "版本复核" }[
                  view
                ]
              }
            </strong>
          </div>
          <div className="header-actions">
            <span className={`model-state ${modelReady ? "ready" : ""}`}>
              <i />
              {modelReady ? "本地模型已连接" : "原文检索模式"}
            </span>
            <button
              className="primary-button"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
            >
              {uploading ? (
                <LoaderCircle size={15} className="spin" />
              ) : (
                <Plus size={15} />
              )}
              导入文献
            </button>
          </div>
        </header>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => upload(e.target.files)}
        />
        {error && (
          <div role="alert" className="error-banner">
            {error}
            <button onClick={() => setError("")} aria-label="关闭错误">
              <X size={16} />
            </button>
          </div>
        )}
        {toast && (
          <div role="status" className="toast">
            <Check size={16} />
            {toast}
          </div>
        )}
        {view === "reader" && (
          <>
            <section className="intro">
              <div>
                <div className="eyebrow">READ. VERIFY. BUILD.</div>
                <h1>让每个结论，回到证据。</h1>
                <p>阅读论文，留下出处，在研究变化时重新核验。</p>
              </div>
              <div className="collection-summary">
                <strong>{documents.length.toString().padStart(2, "0")}</strong>
                <span>
                  篇文献
                  <small>
                    {documents
                      .reduce((sum, d) => sum + d.pages, 0)
                      .toLocaleString()}{" "}
                    页已登记
                  </small>
                </span>
              </div>
            </section>
            <label className="mobile-document-select">
              当前文献
              <select
                aria-label="选择阅读文献"
                value={selected?.id || ""}
                onChange={(e) => {
                  const doc = documents.find((d) => d.id === e.target.value);
                  if (doc) selectDocument(doc);
                }}
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title} · {doc.version ? `v${doc.version}` : doc.name}
                    {doc.status === "ocr_ready" ? " · 扫描件" : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="workbench">
              <section className="reader-panel">
                <div className="document-toolbar">
                  <div>
                    <FileText size={16} />
                    <span>{selected?.name || "选择一篇文献开始"}</span>
                    {selected?.version && (
                      <span className="version-chip">v{selected.version}</span>
                    )}
                  </div>
                  {selected && (
                    <a
                      title="打开原始 PDF"
                      href={`/api/documents/${selected.id}/pdf`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ArrowUpRight size={17} />
                    </a>
                  )}
                </div>
                {selected ? (
                  <>
                    <div className="page-toolbar">
                      <span>原文阅读</span>
                      <div>
                        <button
                          aria-label="上一页"
                          disabled={page <= 1}
                          onClick={() => {
                            setPage((p) => p - 1);
                            setHighlight(null);
                          }}
                        >
                          <ArrowLeft size={15} />
                        </button>
                        <label>
                          <input
                            aria-label="当前页码"
                            type="number"
                            min={1}
                            max={selected.pages}
                            value={page}
                            onChange={(e) => {
                              const next = Number(e.target.value);
                              if (next >= 1 && next <= selected.pages) {
                                setPage(next);
                                setHighlight(null);
                              }
                            }}
                          />
                          <span>/ {selected.pages}</span>
                        </label>
                        <button
                          aria-label="下一页"
                          disabled={page >= selected.pages}
                          onClick={() => {
                            setPage((p) => p + 1);
                            setHighlight(null);
                          }}
                        >
                          <ArrowRight size={15} />
                        </button>
                      </div>
                      <span className="page-format">PDF 原版</span>
                    </div>
                    <Reader
                      document={selected}
                      page={page}
                      highlight={highlight}
                    />
                  </>
                ) : (
                  <div className="empty-state">
                    <BookOpen size={32} />
                    <h2>从一篇论文开始</h2>
                    <p>导入 PDF，即可阅读并查找原文证据。</p>
                  </div>
                )}
              </section>
              <aside className="evidence-panel">
                <div className="evidence-heading">
                  <span className="sparkle">
                    <Sparkles size={18} />
                  </span>
                  <div>
                    <h2>与证据对话</h2>
                    <p>
                      范围：当前论文
                      {selected?.version ? ` · v${selected.version}` : ""}
                    </p>
                  </div>
                </div>
                <form
                  className="question-box"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void ask();
                  }}
                >
                  <textarea
                    aria-label="研究问题"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="例如：模型训练用了哪些 GPU？"
                    rows={3}
                  />
                  <div>
                    <span>回答有据可查</span>
                    <button
                      aria-label="查找证据"
                      type="submit"
                      disabled={busy || !selected || !question.trim()}
                    >
                      {busy ? (
                        <LoaderCircle size={17} className="spin" />
                      ) : (
                        <ArrowRight size={18} />
                      )}
                    </button>
                  </div>
                </form>
                {!answer && !busy && (
                  <>
                    <div className="suggestion-label">从这些问题开始</div>
                    <div className="suggestions">
                      {[
                        "训练用了哪些 GPU？",
                        "Adam 优化器的超参数是什么？",
                        "English-to-German BLEU",
                      ].map((q) => (
                        <button key={q} onClick={() => ask(q)}>
                          {q}
                          <ArrowUpRight size={13} />
                        </button>
                      ))}
                    </div>
                    <div className="evidence-explainer">
                      <div className="line-icon">
                        <ShieldCheck size={23} />
                      </div>
                      <h3>结论之外，保留依据</h3>
                      <p>
                        检索结果来自论文原文。点击卡片定位出处，也可以将它保存为证据笔记，在版本更新后复核。
                      </p>
                      <span>
                        <span className="tiny-dot" />
                        原文 · 页码 · 版本
                      </span>
                    </div>
                  </>
                )}
                {busy && (
                  <div className="working">
                    <LoaderCircle className="spin" size={20} />
                    <span>正在检索文献并检查本地生成服务…</span>
                  </div>
                )}
                {answer && (
                  <div className="results">
                    <div className="results-heading">
                      <strong>
                        {answer.model_answer?.length
                          ? "有出处的回答"
                          : "找到的原文证据"}
                      </strong>
                      <span>{answer.evidence.length} 条</span>
                    </div>
                    {answer.model_answer?.map((claim, i) => (
                      <div className="claim-card" key={i}>
                        <p>{claim.text}</p>
                        <button
                          onClick={() => {
                            const block = answer.evidence.find(
                              (b) => b.id === claim.block_id,
                            );
                            if (block) locate(block);
                          }}
                        >
                          核对原文 <ArrowUpRight size={13} />
                        </button>
                      </div>
                    ))}
                    <p className="result-note">{answer.message}</p>
                    {answer.evidence.map((block, i) => (
                      <article
                        className={`evidence-card ${highlight?.id === block.id ? "focused" : ""}`}
                        key={block.id}
                      >
                        <button
                          className="evidence-content"
                          onClick={() => locate(block)}
                        >
                          <div className="evidence-meta">
                            <span>来源 {String(i + 1).padStart(2, "0")}</span>
                            <span>
                              第 {block.page} 页 <ArrowUpRight size={12} />
                            </span>
                          </div>
                          <p>{block.text}</p>
                        </button>
                        <div className="evidence-card-footer">
                          <span>
                            原文摘录
                            {block.version ? ` · v${block.version}` : ""}
                          </span>
                          <button
                            onClick={() => {
                              setSaving(saving === block.id ? null : block.id);
                              setNoteText(question);
                            }}
                          >
                            <Plus size={13} />
                            存为笔记
                          </button>
                        </div>
                        {saving === block.id && (
                          <div className="note-composer">
                            <input
                              aria-label="证据笔记内容"
                              value={noteText}
                              onChange={(e) => setNoteText(e.target.value)}
                              placeholder="这段证据支持什么观察？"
                            />
                            <button
                              onClick={() => save(block)}
                              disabled={!noteText.trim()}
                            >
                              保存证据
                            </button>
                          </div>
                        )}
                      </article>
                    ))}
                    {!answer.evidence.length && (
                      <div className="empty-state small">
                        <Search size={26} />
                        <p>试试更具体的英文术语，或检查所选论文。</p>
                      </div>
                    )}
                  </div>
                )}
                <div className="evidence-footnote">
                  <ShieldCheck size={13} />
                  出处可追溯，结论仍需审慎核验
                </div>
              </aside>
            </div>
          </>
        )}
        {view === "notes" && (
          <section className="workspace-page">
            <div className="eyebrow">YOUR EVIDENCE, PRESERVED.</div>
            <h1>证据笔记</h1>
            <p className="page-description">
              保存研究观察及其原始出处。论文更新后，历史证据仍然保留。
            </p>
            <div className="notes-grid">
              {notes.map((note) => (
                <article className="saved-note" key={note.id}>
                  <div className="evidence-meta">
                    <span>证据 #{String(note.id).padStart(3, "0")}</span>
                    <span>
                      v{note.version || "?"} · 第 {note.page} 页
                    </span>
                  </div>
                  <h3>{note.note}</h3>
                  <blockquote>{note.quote}</blockquote>
                  <div className="note-source">{note.title}</div>
                  <button
                    className="text-button"
                    onClick={() => locateNote(note)}
                  >
                    回到原文 <ArrowUpRight size={15} />
                  </button>
                </article>
              ))}
            </div>
            {!notes.length && (
              <div className="empty-state">
                <StickyNote size={36} />
                <h2>为研究留下第一条证据</h2>
                <p>在文献阅读台查找证据，点击“存为笔记”。</p>
                <button
                  className="primary-button"
                  onClick={() => setView("reader")}
                >
                  前往阅读台 <ArrowRight size={16} />
                </button>
              </div>
            )}
          </section>
        )}
        {view === "audit" && (
          <section className="workspace-page">
            <div className="eyebrow">WHEN PAPERS CHANGE.</div>
            <h1>论文更新了，依据还成立吗？</h1>
            <p className="page-description">
              将已有证据笔记与另一个版本对照，找出需要重新阅读的原文。变化提示不等于结论被推翻。
            </p>
            <div className="audit-controls">
              <div>
                <label htmlFor="audit-target">对照版本</label>
                <select
                  id="audit-target"
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                >
                  <option value="">选择目标论文</option>
                  {documents
                    .filter((d) => d.status !== "needs_ocr")
                    .map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.title} · {d.version ? `v${d.version}` : d.name}
                        {d.status === "ocr_ready" ? " · 扫描件" : ""}
                      </option>
                    ))}
                </select>
              </div>
              <button
                className="primary-button"
                disabled={!targetId || busy || !notes.length}
                onClick={runAudit}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <GitCompareArrows size={16} />
                )}
                检查证据变化
              </button>
            </div>
            <div className="audit-method">
              <ShieldCheck size={17} />
              <p>
                先定位两版原文，再由本地模型比较笔记关注的论断。引用存在性会被校验，含义判断仍需结合原文复核；每次最多比较
                12 条笔记。
              </p>
            </div>
            {auditResults?.map((item) => (
              <article className="audit-card" key={item.note.id}>
                <div className="audit-title">
                  <h3>{item.note.note}</h3>
                  <span
                    className={`audit-badge ${item.semantic_review?.decision === "same_claim" ? "retained" : item.status}`}
                  >
                    {item.semantic_review?.decision === "same_claim"
                      ? "论断未见变化 · 模型初判"
                      : item.semantic_review?.decision === "claim_changed"
                        ? "论断有变化 · 模型初判"
                        : {
                            retained: "原文保留",
                            review_required: "需要复核",
                            unlocated: "尚未定位",
                          }[item.status]}
                  </span>
                </div>
                <p>{item.explanation}</p>
                {item.semantic_review?.status === "model_assessment" && (
                  <div className="semantic-review">
                    <ShieldCheck size={17} />
                    <div>
                      <strong>围绕这条笔记的比较</strong>
                      <p>{item.semantic_review.reason}</p>
                      <small>两侧引文已核验存在；此结果为模型初步判断。</small>
                    </div>
                  </div>
                )}
                <div className="comparison">
                  <div>
                    <small>保存的证据 · v{item.note.version}</small>
                    <blockquote>{item.note.quote}</blockquote>
                    <button
                      className="text-button"
                      onClick={() => locateNote(item.note)}
                    >
                      查看旧版原文 <ArrowUpRight size={13} />
                    </button>
                  </div>
                  <div>
                    <small>
                      目标版本 · 第 {item.candidate?.page ?? "—"} 页
                    </small>
                    <blockquote>
                      {item.candidate?.text || "未找到可比较的原文"}
                    </blockquote>
                    {item.candidate && (
                      <button
                        className="text-button"
                        onClick={() => locate(item.candidate!)}
                      >
                        查看目标原文 <ArrowUpRight size={13} />
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
            {auditResults?.length === 0 && (
              <div className="empty-state">
                <GitCompareArrows size={30} />
                <h2>没有可跨版本比较的笔记</h2>
                <p>先在同一论文的另一版本中保存证据，再选择此版本复核。</p>
              </div>
            )}
            {auditResults === null && (
              <div className="audit-steps">
                <div>
                  <span>01</span>
                  <strong>保存旧版证据</strong>
                  <p>在阅读台留下笔记与出处</p>
                </div>
                <ArrowRight size={18} />
                <div>
                  <span>02</span>
                  <strong>选择另一个版本</strong>
                  <p>依据正文识别同一篇论文</p>
                </div>
                <ArrowRight size={18} />
                <div>
                  <span>03</span>
                  <strong>查看变化，重新核验</strong>
                  <p>旧证据保留，变化有迹可循</p>
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
