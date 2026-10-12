import {
  ProposalRevision,
  ProtocolEditor,
  MeasurementLab,
  MeasurementResult,
  type MeasurementContent,
  type ProtocolContent,
} from "./ExperimentLab";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  BookOpen,
  Search,
  Network,
  Languages,
  FlaskConical,
  ListChecks,
  CircleHelp,
  ArrowUpRight,
  LoaderCircle,
  Download,
  Play,
  Pause,
  RotateCcw,
  Check,
  Archive,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import {
  WritingEditor,
  LibraryOrganizer,
  GlossaryEditor,
  TranslationEditor,
  MatrixBuilder,
  MatrixResult,
  type MatrixRow,
} from "./ResearchTools";
import { PageJump } from "./PageJump";
import { FormulaPanel, FormulaResult } from "./FormulaPanel";
import { TablePanel, TableResult, type TableContent } from "./TablePanel";
import {
  request,
  downloadText,
  type Paper,
  type Job,
  type Anchor,
} from "./workspaceApi";
import "./workbench.css";

export type WorkView =
  | "library"
  | "translate"
  | "discover"
  | "graph"
  | "studio"
  | "tasks"
  | "account";
export const workViews: {
  id: WorkView;
  label: string;
  icon: typeof BookOpen;
}[] = [
  { id: "tasks", label: "任务与成果", icon: ListChecks },
  { id: "library", label: "文献管理", icon: BookOpen },
  { id: "translate", label: "双语与引文", icon: Languages },
  { id: "discover", label: "论文发现", icon: Search },
  { id: "graph", label: "引用图谱", icon: Network },
  { id: "studio", label: "科研工作室", icon: FlaskConical },
  { id: "account", label: "账号与空间", icon: BookOpen },
];
type Props = {
  view: WorkView;
  papers: Paper[];
  selected: Paper | null;
  onRefresh: () => Promise<void>;
  onLocate: (a: Anchor) => void;
  onTasks: () => void;
};
type Result = {
  id: string;
  kind: string;
  title: string;
  content: Record<string, unknown>;
};
function Help({ children }: { children: ReactNode }) {
  return (
    <details className="extended-help">
      <summary>
        <CircleHelp size={15} /> 功能与用法
      </summary>
      <div>{children}</div>
    </details>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return <div className="work-empty">{children}</div>;
}

function SavedDiagram({ code }: { code: string }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "neutral",
          maxTextSize: 12000,
        });
        await mermaid.parse(code);
        const result = await mermaid.render(
          "saved-" + crypto.randomUUID(),
          code,
        );
        if (current) setSvg(result.svg);
      } catch {
        if (current) setError("图稿渲染失败，请下载脚本并在科研工作室修改。");
      }
    })();
    return () => {
      current = false;
    };
  }, [code]);
  return (
    <>
      {error && <p role="alert">{error}</p>}
      {svg && (
        <>
          <div
            className="diagram-preview"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
          <button
            onClick={() =>
              downloadText("architecture.svg", svg, "image/svg+xml")
            }
          >
            下载图稿 SVG
          </button>
        </>
      )}
      <details>
        <summary>查看可编辑脚本</summary>
        <pre>{code}</pre>
      </details>
    </>
  );
}
function PaperSelect({
  papers,
  value,
  onChange,
}: {
  papers: Paper[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      aria-label="工作文献"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">选择文献</option>
      {papers.map((p) => (
        <option key={p.id} value={p.id}>
          {p.title} · {p.version ? `v${p.version}` : p.name}
        </option>
      ))}
    </select>
  );
}
function SourceButton({
  anchor,
  onLocate,
  children,
}: {
  anchor: Anchor;
  onLocate: Props["onLocate"];
  children?: ReactNode;
}) {
  return (
    <button className="text-button" onClick={() => onLocate(anchor)}>
      {children || `第 ${anchor.page} 页原文`}
      <ArrowUpRight size={13} />
    </button>
  );
}

export function Workbench(props: Props) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    setError("");
    setNotice("");
  }, [props.view]);
  async function run(action: () => Promise<unknown>) {
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
  async function submit(kind: string, payload: Record<string, unknown>) {
    const job = await request<Job>("/api/jobs", { kind, payload });
    setNotice(
      `任务已${job.state === "running" ? "开始" : "加入队列"}，可在“任务与成果”查看进度、停止或重试。`,
    );
    return job;
  }
  const tools = { ...props, run, submit, busy, setNotice };
  return (
    <section className="research-workspace">
      <div className="eyebrow">RESEARCH, WITH EVIDENCE.</div>
      <div className="work-title">
        <h1>
          {props.view === "account"
            ? "研究空间与账号"
            : workViews.find((v) => v.id === props.view)?.label}
        </h1>
        <span>本地模型 · 免费数据源</span>
      </div>
      {error && (
        <div className="work-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="work-notice" role="status">
          {notice}
          <button onClick={props.onTasks}>查看任务 →</button>
        </div>
      )}
      {props.view === "library" && <Library {...tools} />}
      {props.view === "translate" && <Translation {...tools} />}
      {props.view === "discover" && <Discover {...tools} />}
      {props.view === "graph" && <Graph {...tools} />}
      {props.view === "studio" && <Studio {...tools} />}
      {props.view === "tasks" && <Tasks {...tools} />}
      {props.view === "account" && <Account {...tools} />}
    </section>
  );
}
type Tools = Props & {
  run: (action: () => Promise<unknown>) => Promise<void>;
  submit: (kind: string, payload: Record<string, unknown>) => Promise<Job>;
  busy: boolean;
  setNotice: (text: string) => void;
};

type Structure = {
  complete: boolean;
  title?: string;
  abstract?: string;
  author_affiliation_source?: string;
  headings?: (Anchor & { text: string })[];
  pages: {
    page: number;
    tables: { rows: string[][] }[];
    figures: (Anchor & { caption: string })[];
    equations: (Anchor & { text: string })[];
  }[];
};
function Library({
  papers,
  selected,
  run,
  submit,
  busy,
  onRefresh,
  onLocate,
}: Tools) {
  const [identifier, setId] = useState(selected?.id || papers[0]?.id || "");
  const [title, setTitle] = useState("");
  const [aliases, setAliases] = useState("");
  const [archived, setArchived] = useState<Paper[]>([]);
  const [duplicates, setDuplicates] = useState<
    (Paper & {
      content_cosine: number;
      semantic_title_similarity: number;
      match_status: string;
      recommended_version_id?: string;
    })[]
  >([]);
  const [structure, setStructure] = useState<Structure | null>(null);
  const [diff, setDiff] = useState<{
    first: string;
    second: string;
    notice: string;
    changes: { kind: string; before: Anchor[]; after: Anchor[] }[];
  } | null>(null);
  const [index, setIndex] = useState<{
    indexed_blocks: number;
    total_blocks: number;
  } | null>(null);
  function reload() {
    return Promise.all([
      request<Paper[]>("/api/library/archived").then(setArchived),
      request<typeof index>("/api/retrieval/status").then(setIndex),
    ]);
  }
  useEffect(() => {
    void run(reload);
  }, []);
  useEffect(() => {
    setTitle(papers.find((p) => p.id === identifier)?.title || "");
    setAliases(
      (papers.find((p) => p.id === identifier)?.aliases || []).join(", "),
    );
    setStructure(null);
    setDuplicates([]);
    setDiff(null);
  }, [identifier, papers]);
  return (
    <>
      <p className="work-intro">
        管理原始
        PDF、文献信息与处理状态。移入归档后可恢复，已保存的证据继续保留。
      </p>
      <Help>
        <p>
          顶部“导入文献”支持批量
          PDF。选择文献后可以修改标题和常用别名、解析章节与图表、识别扫描文字、检查同文版本。解析后点击“查看结构”核对原文。别名帮助问答识别论文中的模型名称，例如
          GPT-1；它不作为回答的证据。
        </p>
        <p>
          归档会将文献移出检索范围；旧笔记仍可回到原文。语义索引可重复提交，已处理的段落会跳过。结构解析和
          OCR 失败时在任务页重试。
        </p>
      </Help>
      <div className="work-card">
        <div className="work-row">
          <PaperSelect papers={papers} value={identifier} onChange={setId} />
          <button
            disabled={busy || !identifier}
            onClick={() =>
              void run(async () => {
                setStructure(
                  await request(`/api/documents/${identifier}/structure`),
                );
                setDuplicates(
                  await request(`/api/documents/${identifier}/duplicates`),
                );
              })
            }
          >
            查看结构与版本
          </button>
        </div>
        <label>
          显示标题
          <input
            aria-label="文献标题"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          文献别名（用逗号分隔）
          <input
            aria-label="文献别名"
            value={aliases}
            placeholder="例如 GPT-1，用于识别问题中的文献简称"
            onChange={(e) => setAliases(e.target.value)}
          />
        </label>
        <div className="work-row">
          <button
            className="primary-button"
            disabled={busy || !identifier || title.trim().length < 2}
            onClick={() =>
              void run(async () => {
                await request(
                  `/api/documents/${identifier}`,
                  {
                    title,
                    aliases: aliases
                      .split(/[,，;；\n]/)
                      .map((s) => s.trim())
                      .filter(Boolean),
                  },
                  "PATCH",
                );
                await onRefresh();
              })
            }
          >
            保存文献信息
          </button>
          {(["parse", "ocr"] as const).map((kind, i) => (
            <button
              key={kind}
              disabled={busy || !identifier}
              onClick={() =>
                void run(() => submit(kind, { document_id: identifier }))
              }
            >
              {i ? "识别扫描文字" : "解析章节、图表与引用"}
            </button>
          ))}
          <button
            disabled={busy || !identifier}
            onClick={() =>
              void run(async () => {
                await request(
                  `/api/documents/${identifier}`,
                  { archived: true },
                  "PATCH",
                );
                setId("");
                await onRefresh();
                await reload();
              })
            }
          >
            <Archive size={15} />
            移入归档
          </button>
        </div>
        {duplicates.length > 0 && (
          <div className="version-candidates">
            <h3>检测到同文版本或语义相近文献</h3>
            {duplicates.map((p) => (
              <div key={p.id}>
                <strong>{p.name}</strong>
                <span>
                  {" "}
                  {p.match_status} · 标题语义{" "}
                  {(p.semantic_title_similarity * 100).toFixed(1)}% · 内容词频{" "}
                  {(p.content_cosine * 100).toFixed(1)}%{" "}
                  {p.recommended_version_id === p.id ? "· 版本号较新" : ""}
                </span>
                <button
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      setDiff(
                        await request("/api/versions/diff", {
                          first: identifier,
                          second: p.id,
                        }),
                      );
                    })
                  }
                >
                  对照全文变化
                </button>
                <button
                  onClick={() =>
                    void run(async () => {
                      await request(
                        `/api/documents/${p.id}`,
                        { archived: true },
                        "PATCH",
                      );
                      await onRefresh();
                      setDuplicates(duplicates.filter((v) => v.id !== p.id));
                      await reload();
                    })
                  }
                >
                  保留当前，归档此版本
                </button>
              </div>
            ))}
            <p>
              保留两份无需额外操作。版本建议来自 PDF
              中的编号；不会自动覆盖原文。
            </p>
          </div>
        )}
      </div>
      {diff && (
        <div className="work-card version-diff">
          <h3>全文对照 · {diff.changes.length} 处差异</h3>
          <p>{diff.notice}</p>
          <p>
            左侧：{papers.find((p) => p.id === diff.first)?.name}；右侧：
            {papers.find((p) => p.id === diff.second)?.name}
          </p>
          <button
            onClick={() =>
              downloadText(
                "version-diff.json",
                JSON.stringify(diff, null, 2),
                "application/json",
              )
            }
          >
            导出差异与出处
          </button>
          {diff.changes.map((change, i) => (
            <details key={i}>
              <summary>
                变化 {i + 1} ·{" "}
                {{
                  replace: "内容变化",
                  insert: "右侧新增",
                  delete: "右侧未出现",
                }[change.kind] || change.kind}{" "}
                · {change.before.length} / {change.after.length} 段
              </summary>
              <div className="diff-columns">
                {[change.before, change.after].map((blocks, side) => (
                  <div key={side}>
                    <h4>{side ? "对照版本" : "当前版本"}</h4>
                    {!blocks.length && <p>此侧无对应段落</p>}
                    {blocks.map((b, j) => (
                      <div key={j}>
                        <SourceButton anchor={b} onLocate={onLocate} />
                        <p>{b.text}</p>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}
      <div className="work-card">
        <div className="work-row">
          <h3>全库语义索引</h3>
          <span>
            {index
              ? `${index.indexed_blocks.toLocaleString()} / ${index.total_blocks.toLocaleString()} 段`
              : "读取中"}
          </span>
          <button
            disabled={busy}
            onClick={() => void run(() => submit("index", {}))}
          >
            补建索引
          </button>
          <button onClick={() => void run(reload)}>刷新状态</button>
        </div>
        <p>
          关键词与多语言语义联合检索。新文献自动索引，索引期间仍可查关键词。
        </p>
      </div>
      <LibraryOrganizer
        key={`organize-${identifier}`}
        identifier={identifier}
        onSelect={setId}
      />
      {identifier && (
        <TablePanel
          key={`table-${identifier}`}
          identifier={identifier}
          pages={papers.find((p) => p.id === identifier)?.pages || 1}
        />
      )}
      {identifier && (
        <FormulaPanel
          key={identifier}
          identifier={identifier}
          pages={papers.find((p) => p.id === identifier)?.pages || 1}
        />
      )}
      {structure && (
        <div className="work-card">
          <h3>文献结构 · {structure.complete ? "解析完成" : "尚未完成"}</h3>
          <p>{structure.abstract}</p>
          {structure.author_affiliation_source && (
            <details>
              <summary>作者与机构原文</summary>
              <pre>{structure.author_affiliation_source}</pre>
            </details>
          )}
          <div className="structure-list">
            {structure.headings?.map((h, i) => (
              <SourceButton key={i} anchor={h} onLocate={onLocate}>
                {h.text}
              </SourceButton>
            ))}
          </div>
          {structure.pages
            .filter(
              (p) => p.figures.length || p.equations.length || p.tables.length,
            )
            .map((p) => (
              <details key={p.page}>
                <summary>
                  第 {p.page} 页 · {p.figures.length} 个图表标题 ·{" "}
                  {p.equations.length} 个公式片段 · {p.tables.length} 张表格
                </summary>
                {[...p.figures, ...p.equations].map((a, i) => (
                  <div key={i}>
                    <SourceButton anchor={a} onLocate={onLocate}>
                      {"caption" in a ? a.caption : a.text}
                    </SourceButton>
                    <img
                      className="source-crop"
                      loading="lazy"
                      alt="原文区域"
                      src={`/api/documents/${identifier}/crop?page=${a.page}&x0=${Math.max(0, a.bbox[0] - 5)}&y0=${Math.max(0, a.bbox[1] - 10)}&x1=${a.bbox[2] + 5}&y1=${a.bbox[3] + 10}`}
                    />
                  </div>
                ))}
                {p.tables.map((t, i) => (
                  <div className="table-scroll" key={i}>
                    <table>
                      <tbody>
                        {t.rows.map((r, j) => (
                          <tr key={j}>
                            {r.map((c, k) => (
                              <td key={k}>{c}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <small>几何提取候选；请与 PDF 对照。</small>
                  </div>
                ))}
              </details>
            ))}
        </div>
      )}
      <div className="work-card">
        <h3>归档文献 · {archived.length}</h3>
        {archived.map((p) => (
          <div className="work-row" key={p.id}>
            <span>{p.title}</span>
            <button
              onClick={() =>
                void run(async () => {
                  await request(
                    `/api/documents/${p.id}`,
                    { archived: false },
                    "PATCH",
                  );
                  await onRefresh();
                  await reload();
                })
              }
            >
              <RotateCcw size={14} />
              恢复
            </button>
          </div>
        ))}
        {!archived.length && <p>暂无归档文献。</p>}
      </div>
    </>
  );
}

type Aligned = Anchor & {
  id: string;
  text: string;
  translation: string | null;
  quality?: { warnings: string[] };
  translation_model?: string;
};
type Reference = Anchor & {
  number: number;
  text: string;
  cited_by: (Anchor & { context: string })[];
};
function Translation({ papers, selected, run, submit, busy, onLocate }: Tools) {
  const [identifier, setId] = useState(selected?.id || papers[0]?.id || "");
  const [page, setPage] = useState(1);
  const [language, setLanguage] = useState("zh");
  const [blocks, setBlocks] = useState<Aligned[]>([]);
  const [references, setReferences] = useState<Reference[]>([]);
  const [text, setText] = useState("");
  const [translated, setTranslated] = useState("");
  const left = useRef<HTMLDivElement>(null);
  const right = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);
  const doc = papers.find((p) => p.id === identifier);
  async function refresh() {
    if (!identifier) return;
    setBlocks(
      await request(
        `/api/documents/${identifier}/translation?page=${page}&language=${language}`,
      ),
    );
  }
  useEffect(() => {
    let current = true;
    setBlocks([]);
    if (identifier)
      request<Aligned[]>(
        `/api/documents/${identifier}/translation?page=${page}&language=${language}`,
      )
        .then((v) => {
          if (current) setBlocks(v);
        })
        .catch(() => {});
    return () => {
      current = false;
    };
  }, [identifier, page, language]);
  function sync(from: HTMLDivElement, to: HTMLDivElement | null) {
    if (!to || syncing.current) return;
    syncing.current = true;
    const elements = [...from.querySelectorAll<HTMLElement>("[data-block]")];
    const top = from.getBoundingClientRect().top;
    const active = elements.find(
      (el) => el.getBoundingClientRect().bottom > top + 5,
    );
    if (active) {
      const target = to.querySelector<HTMLElement>(
        `[data-block="${active.dataset.block}"]`,
      );
      if (target) {
        const progress = Math.max(
          0,
          (top - active.getBoundingClientRect().top) / active.offsetHeight,
        );
        to.scrollTop +=
          target.getBoundingClientRect().top -
          to.getBoundingClientRect().top +
          progress * target.offsetHeight;
      }
    }
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  }
  return (
    <>
      <p className="work-intro">
        按原文段落对齐翻译，保留出处；也可以从参考文献返回正文中的每次引用。
      </p>
      <Help>
        <p>
          选择论文、页码和目标语言，点击“翻译本页”。全文翻译在后台逐段处理，可停止后重试，已有译文不会重复生成。完成后点“刷新译文”。两侧滚动按段落同步；点击原文定位可返回
          PDF。
        </p>
        <p>
          在 PDF
          阅读台选中文本后使用“翻译选中文本”，或粘贴到下方输入框。中译英选择
          English。参考文献中的“出现位置”返回正文，“参考条目”跳到文末。
        </p>
      </Help>
      <div className="work-card">
        <div className="work-row">
          <PaperSelect
            papers={papers}
            value={identifier}
            onChange={(v) => {
              setId(v);
              setPage(1);
              setReferences([]);
            }}
          />
          <select
            aria-label="翻译目标语言"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
          {doc && (
            <PageJump
              page={page}
              total={doc.pages}
              documentId={doc.id}
              onJump={setPage}
            />
          )}
        </div>
        <div className="work-row">
          <button
            className="primary-button"
            disabled={busy || !identifier}
            onClick={() =>
              void run(() =>
                submit("translate", {
                  document_id: identifier,
                  language,
                  page,
                }),
              )
            }
          >
            翻译本页
          </button>
          <button
            disabled={busy || !identifier}
            onClick={() =>
              void run(() =>
                submit("translate", { document_id: identifier, language }),
              )
            }
          >
            全文翻译
          </button>
          <button
            disabled={busy || !identifier}
            onClick={() => void run(refresh)}
          >
            刷新译文
          </button>
          {identifier && (
            <>
              <a
                href={`/api/documents/${identifier}/translation/export?language=${language}&format=md`}
              >
                导出 Markdown
              </a>
              <a
                href={`/api/documents/${identifier}/translation/export?language=${language}&format=html`}
              >
                导出双语 HTML
              </a>
            </>
          )}
        </div>
      </div>
      <GlossaryEditor />
      <div className="bilingual-grid">
        <div>
          <h3>原文 · 第 {page} 页</h3>
          <div
            ref={left}
            className="bilingual-scroll"
            onScroll={(e) => sync(e.currentTarget, right.current)}
          >
            {blocks.map((b) => (
              <article data-block={b.id} key={b.id}>
                <p>{b.text}</p>
                <SourceButton anchor={b} onLocate={onLocate} />
                <button onClick={() => setText(b.text)}>选段翻译</button>
              </article>
            ))}
          </div>
        </div>
        <div>
          <h3>{language === "zh" ? "中文译文" : "English translation"}</h3>
          <div
            ref={right}
            className="bilingual-scroll"
            onScroll={(e) => sync(e.currentTarget, left.current)}
          >
            {blocks.map((b) => (
              <article data-block={b.id} key={b.id}>
                <p>
                  {b.translation || "此段尚未翻译。可提交本页或全文翻译任务。"}
                </p>
                <small>
                  对应原文段落 {blocks.indexOf(b) + 1}
                  {b.translation_model === "human-corrected"
                    ? " · 已人工校正"
                    : ""}
                </small>
                {b.quality?.warnings.map((w, i) => (
                  <p className="work-notice" key={i}>
                    {w}
                  </p>
                ))}
                {b.translation && (
                  <TranslationEditor
                    blockId={b.id}
                    language={language}
                    text={b.translation}
                    onSaved={() => void refresh()}
                  />
                )}
              </article>
            ))}
          </div>
        </div>
      </div>
      <div className="work-card">
        <h3>选段翻译 / 学术中译英</h3>
        <textarea
          aria-label="待翻译文本"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="粘贴原文、中文摘要或正文（最多 7000 字符）"
          maxLength={7000}
        />
        <button
          className="primary-button"
          disabled={busy || !text.trim()}
          onClick={() =>
            void run(async () =>
              setTranslated(
                (
                  await request<{ translation: string }>(
                    "/api/translate/text",
                    { text, language },
                  )
                ).translation,
              ),
            )
          }
        >
          {busy ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <Languages size={15} />
          )}
          翻译文本
        </button>
        {translated && (
          <div className="translation-result">
            <p>{translated}</p>
            <button onClick={() => downloadText("translation.txt", translated)}>
              下载译文
            </button>
          </div>
        )}
      </div>
      <div className="work-card">
        <div className="work-row">
          <h3>引文 ↔ 参考文献</h3>
          <button
            disabled={busy || !identifier}
            onClick={() =>
              void run(async () =>
                setReferences(
                  (
                    await request<{ references: Reference[] }>(
                      `/api/documents/${identifier}/references`,
                    )
                  ).references,
                ),
              )
            }
          >
            读取引用关系
          </button>
        </div>
        {references.map((r) => (
          <details key={r.number}>
            <summary>
              [{r.number}] {r.text.slice(0, 200)}
            </summary>
            <p>{r.text}</p>
            <SourceButton anchor={r} onLocate={onLocate}>
              参考条目 · 第 {r.page} 页
            </SourceButton>
            {r.cited_by.map((c, i) => (
              <div className="reference-context" key={i}>
                <p>{c.context}</p>
                <SourceButton anchor={c} onLocate={onLocate}>
                  出现位置 {i + 1} · 第 {c.page} 页
                </SourceButton>
              </div>
            ))}
          </details>
        ))}
      </div>
    </>
  );
}

type RemotePaper = {
  id: string;
  title: string;
  authors: string[];
  abstract: string;
  published: string;
  url: string;
  pdf_url?: string;
  github: string[];
  code_checks?: {
    url: string;
    status: string;
    checked_at: string;
    license?: string;
    reproduction: string;
  }[];
  vote?: number;
  retrieval_status?: string;
  retrieved_at?: string;
};
type Tracker = {
  id: string;
  query: string;
  enabled: number;
  last_checked: string | null;
  error?: string;
  papers: RemotePaper[];
};
function Discover({ run, submit, busy, setNotice }: Tools) {
  const [query, setQuery] = useState("retrieval augmented generation evidence");
  const [source, setSource] = useState("arxiv");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [latest, setLatest] = useState(false);
  const [searchStart, setSearchStart] = useState(0);
  const [searchSpec, setSearchSpec] = useState<Record<string, unknown> | null>(
    null,
  );
  async function searchPapers(start = 0, force = false, previous = false) {
    const spec =
      previous && searchSpec
        ? searchSpec
        : {
            query,
            source,
            latest,
            year_from: yearFrom ? Number(yearFrom) : null,
            year_to: yearTo ? Number(yearTo) : null,
          };
    const result = await request<RemotePaper[]>("/api/discover/search", {
      ...spec,
      start,
      force,
    });
    setPapers(result);
    setSearchStart(start);
    setSearchSpec(spec);
    setNotice(
      result.length
        ? `第 ${start + 1}—${start + result.length} 条；可逐页继续发现。`
        : "此查询页未返回结果，可调整条件或切换数据源。外部接口错误会单独提示。",
    );
  }
  const [papers, setPapers] = useState<RemotePaper[]>([]);
  const [trackers, setTrackers] = useState<Tracker[]>([]);
  const refresh = async () => setTrackers(await request("/api/trackers"));
  useEffect(() => {
    void run(refresh);
  }, []);
  async function vote(p: RemotePaper, value: number) {
    await request("/api/discover/feedback", { paper_id: p.id, vote: value });
    setPapers(papers.map((a) => (a.id === p.id ? { ...a, vote: value } : a)));
    setNotice("偏好已保存；下次检索会优先排列喜欢的结果。");
  }
  function card(p: RemotePaper) {
    return (
      <article className="remote-paper" key={p.id}>
        <div className="eyebrow">
          {p.published?.slice(0, 10)} · {p.id}
        </div>
        {p.retrieval_status && p.retrieval_status !== "live" && (
          <small className="work-notice">
            {p.retrieval_status === "stale_after_error"
              ? "在线请求失败，展示历史缓存；并非最新结果"
              : "10 分钟内的查询缓存"}{" "}
            · {p.retrieved_at}
          </small>
        )}
        <h3>
          <a href={p.url} target="_blank" rel="noreferrer">
            {p.title} <ArrowUpRight size={14} />
          </a>
        </h3>
        <small>{p.authors.slice(0, 7).join(" · ")}</small>
        <p>{p.abstract || "此数据源未提供摘要，可打开来源页查看。"}</p>
        <div className="work-row">
          <button
            disabled={busy || !p.pdf_url}
            onClick={() =>
              void run(() => submit("download", { paper_id: p.id }))
            }
          >
            <Download size={14} />
            {p.pdf_url ? "下载全文并入库" : "暂无可自动下载的全文"}
          </button>
          <button
            aria-label={`喜欢 ${p.title}`}
            aria-pressed={p.vote === 1}
            onClick={() => void run(() => vote(p, p.vote === 1 ? 0 : 1))}
          >
            <ThumbsUp size={15} />
            喜欢
          </button>
          <button
            aria-label={`减少推荐 ${p.title}`}
            aria-pressed={p.vote === -1}
            onClick={() => void run(() => vote(p, p.vote === -1 ? 0 : -1))}
          >
            <ThumbsDown size={15} />
            减少推荐
          </button>
          {p.github.map((link) => (
            <a key={link} target="_blank" rel="noreferrer" href={link}>
              GitHub 线索 ↗
            </a>
          ))}
        </div>
        {p.github.length > 0 && (
          <div>
            <small>
              链接来自论文摘要。可核验公开仓库访问状态、许可；实验复现需要另外运行代码。
            </small>
            <button
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  const checked = await request<RemotePaper>(
                    "/api/discover/repositories",
                    { paper_id: p.id },
                  );
                  setPapers(papers.map((a) => (a.id === p.id ? checked : a)));
                  setTrackers(
                    trackers.map((t) => ({
                      ...t,
                      papers: t.papers.map((a) =>
                        a.id === p.id ? checked : a,
                      ),
                    })),
                  );
                })
              }
            >
              核验代码链接
            </button>
            {p.code_checks?.map((c) => (
              <p key={c.url}>
                {c.status}
                {c.license ? ` · 许可 ${c.license}` : ""} · {c.reproduction}
                <small>
                  核验时间：{new Date(c.checked_at).toLocaleString()}
                </small>
              </p>
            ))}
          </div>
        )}
      </article>
    );
  }
  return (
    <>
      <p className="work-intro">
        从真实学术数据源发现论文，保存检索主题，追踪后续更新。
      </p>
      <Help>
        <p>
          输入英文主题、论文标题或参考文献。arXiv 支持开放全文下载和
          ti:/au:/cat: 查询；Crossref 补充 DOI 元数据，未提供全文时会明确提示。
        </p>
        <p>
          点击“每 24
          小时追踪”保存主题；服务运行期间定期检查，关闭期间暂停，重启补查。首次收集最新
          30
          条，后续按更新时间逐页补查，历史命中按论文版本去重。喜欢/减少推荐会影响相同结果的排序。
        </p>
      </Help>
      <form
        className="work-card"
        onSubmit={(e) => {
          e.preventDefault();
          void run(() => searchPapers());
        }}
      >
        <div className="work-row">
          <input
            aria-label="论文检索词"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入论文标题、英文主题或引用条目"
            maxLength={500}
          />
          <select
            aria-label="论文数据源"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="arxiv">arXiv</option>
            <option value="crossref">Crossref</option>
          </select>
          <button className="primary-button" disabled={busy || !query.trim()}>
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Search size={16} />
            )}
            搜索论文
          </button>
          <input
            aria-label="发表起始年份"
            type="number"
            min={1900}
            max={2100}
            value={yearFrom}
            onChange={(e) => setYearFrom(e.target.value)}
            placeholder="起始年份"
          />
          <input
            aria-label="发表结束年份"
            type="number"
            min={1900}
            max={2100}
            value={yearTo}
            onChange={(e) => setYearTo(e.target.value)}
            placeholder="结束年份"
          />
          <label>
            <input
              type="checkbox"
              checked={latest}
              onChange={(e) => setLatest(e.target.checked)}
            />
            按最新排序
          </label>
          <button
            type="button"
            disabled={busy || !query.trim()}
            onClick={() =>
              void run(async () => {
                await request("/api/trackers", { query, interval_hours: 24 });
                await refresh();
                setNotice("追踪主题已保存，首次检索已加入后台任务。");
              })
            }
          >
            每 24 小时追踪
          </button>
        </div>
      </form>
      {searchSpec && (
        <div className="work-row">
          <button
            disabled={busy || searchStart === 0}
            onClick={() =>
              void run(() =>
                searchPapers(Math.max(0, searchStart - 12), false, true),
              )
            }
          >
            上一页论文
          </button>
          <span>查询页 {Math.floor(searchStart / 12) + 1}</span>
          <button
            disabled={busy || papers.length < 12 || searchStart >= 9888}
            onClick={() =>
              void run(() => searchPapers(searchStart + 12, false, true))
            }
          >
            下一页论文
          </button>
          <button
            disabled={busy}
            onClick={() =>
              void run(() => searchPapers(searchStart, true, true))
            }
          >
            重新请求在线结果
          </button>
        </div>
      )}
      <p>
        年份按发表时间筛选；arXiv
        使用首次提交时间，最新排序按更新日期。主题追踪仍按主题在 arXiv
        持续检查，不受本次分页和年份筛选限制。
      </p>
      {papers.map(card)}
      {!papers.length && (
        <Empty>输入研究问题，从检索结果开始建立文献库。</Empty>
      )}
      <div className="work-card">
        <div className="work-row">
          <h3>我的追踪主题</h3>
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const r = await request<{
                  papers: RemotePaper[];
                  reason: string;
                }>("/api/discover/recommendations");
                setPapers(r.papers);
                setSearchSpec(null);
                setNotice(r.reason);
              })
            }
          >
            根据文献与偏好推荐
          </button>
          <button onClick={() => void run(refresh)}>刷新追踪结果</button>
        </div>
        {trackers.map((t) => (
          <details key={t.id}>
            <summary>
              {t.query} · {t.enabled ? "追踪中" : "已暂停"} · {t.papers.length}{" "}
              条
            </summary>
            <p>上次检查：{t.last_checked || "等待首次检查"}</p>
            {t.error && <p role="alert">{t.error}</p>}
            <div className="work-row">
              <button
                onClick={() =>
                  void run(() => submit("track", { tracker_id: t.id }))
                }
              >
                立即检查
              </button>
              <button
                onClick={() =>
                  void run(async () => {
                    await request(
                      `/api/trackers/${t.id}`,
                      { enabled: !t.enabled },
                      "PATCH",
                    );
                    await refresh();
                  })
                }
              >
                {t.enabled ? "暂停追踪" : "恢复追踪"}
              </button>
            </div>
            {t.papers.map(card)}
          </details>
        ))}
      </div>
    </>
  );
}

type GraphData = {
  nodes: (Paper & {
    pagerank: number;
    in_degree: number;
    out_degree: number;
    centrality: number;
    versions: string[];
  })[];
  edges: {
    source: string;
    target: string;
    purpose: string;
    hidden: boolean;
    reference: Reference;
    contexts: (Anchor & { context: string })[];
  }[];
  method: string;
  scope: string;
};
function Graph({ run, busy, onLocate }: Tools) {
  const [data, setData] = useState<GraphData | null>(null);
  const [chosen, setChosen] = useState("");
  const [purpose, setPurpose] = useState("全部");
  const refresh = async () => setData(await request("/api/graph"));
  useEffect(() => {
    void run(refresh);
  }, []);
  const positions = new Map(
    data?.nodes.map((n, i, a) => [
      n.id,
      {
        x: 360 + 270 * Math.cos((i / a.length) * Math.PI * 2),
        y: 305 + 245 * Math.sin((i / a.length) * Math.PI * 2),
      },
    ]),
  );
  const edges =
    data?.edges.filter(
      (e) =>
        (!chosen || e.source === chosen || e.target === chosen) &&
        (purpose === "全部" || e.purpose === purpose),
    ) || [];
  return (
    <>
      <p className="work-intro">
        由参考文献构建可核验的局域图谱。点击节点查看其引用关系，点击引用边的出处回到
        PDF。
      </p>
      <Help>
        <p>
          箭头由引用方指向被引方。同一论文版本折叠为一个节点，默认最新版本。右侧按当前图的
          PageRank 排序，显示入度和介数中心性。
        </p>
        <p>
          用途标签依据引用上下文关键词辅助归类，不等于人工学术评定。隐藏边只影响当前图的计算，可在下方恢复。没有连线可能是引用未识别，不能认定论文不重要。
        </p>
      </Help>
      <div className="work-row">
        <button disabled={busy} onClick={() => void run(refresh)}>
          重新计算图谱
        </button>
        <select
          aria-label="引用用途筛选"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
        >
          {["全部", "方法继承", "比较", "局限", "背景或未判定"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <button onClick={() => setChosen("")}>显示全部节点</button>
        {data && (
          <button
            onClick={() =>
              downloadText(
                "citation-graph.json",
                JSON.stringify(data, null, 2),
                "application/json",
              )
            }
          >
            导出图谱与出处
          </button>
        )}
      </div>
      {data && (
        <>
          <div className="graph-layout">
            <div className="work-card graph-canvas">
              <svg
                viewBox="0 0 720 610"
                role="img"
                aria-label={`${data.nodes.length} 篇文献的引用图谱`}
              >
                <defs>
                  <marker
                    id="citation-arrow"
                    viewBox="0 0 10 10"
                    refX="18"
                    refY="5"
                    markerWidth="5"
                    markerHeight="5"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#79928a" />
                  </marker>
                </defs>
                {edges
                  .filter((e) => !e.hidden)
                  .map((e, i) => {
                    const a = positions.get(e.source)!;
                    const b = positions.get(e.target)!;
                    return (
                      <line
                        key={i}
                        x1={a.x}
                        y1={a.y}
                        x2={b.x}
                        y2={b.y}
                        stroke="#a8bbb3"
                        strokeWidth="1.4"
                        markerEnd="url(#citation-arrow)"
                      />
                    );
                  })}
                {data.nodes.map((n, i) => {
                  const p = positions.get(n.id)!;
                  return (
                    <g
                      key={n.id}
                      role="button"
                      tabIndex={0}
                      aria-label={n.title}
                      onClick={() => setChosen(n.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setChosen(n.id);
                        }
                      }}
                    >
                      <title>{n.title}</title>
                      <circle
                        cx={p.x}
                        cy={p.y}
                        r={9 + Math.min(18, n.pagerank * 160)}
                        fill={chosen === n.id ? "#d38c42" : "#2b6454"}
                      />
                      <text
                        x={p.x}
                        y={p.y + 4}
                        textAnchor="middle"
                        fill="white"
                        fontSize="10"
                      >
                        {i + 1}
                      </text>
                    </g>
                  );
                })}
              </svg>
              <p>
                {data.nodes.length} 篇独立文献 ·{" "}
                {data.edges.filter((e) => !e.hidden).length} 条引用匹配
              </p>
            </div>
            <div className="graph-ranking">
              {data.nodes.map((n, i) => (
                <button
                  className={chosen === n.id ? "selected" : ""}
                  key={n.id}
                  onClick={() => setChosen(n.id)}
                >
                  <span>{i + 1}</span>
                  <div>
                    <strong>{n.title}</strong>
                    <small>
                      PageRank {n.pagerank.toFixed(4)} · 入度 {n.in_degree} ·
                      介数 {n.centrality.toFixed(3)}
                    </small>
                  </div>
                </button>
              ))}
            </div>
          </div>
          <p className="work-intro">
            {data.method} {data.scope}
          </p>
          <div className="work-card">
            <h3>引用边的原文依据 · {edges.length}</h3>
            {edges.map((e, i) => (
              <details key={i}>
                <summary>
                  {data.nodes.find((n) => n.id === e.source)?.title} →{" "}
                  {data.nodes.find((n) => n.id === e.target)?.title} ·{" "}
                  {e.purpose}
                  {e.hidden ? " · 已隐藏" : ""}
                </summary>
                <p>{e.reference.text}</p>
                <SourceButton anchor={e.reference} onLocate={onLocate}>
                  查看参考条目
                </SourceButton>
                {e.contexts.map((c, j) => (
                  <div key={j}>
                    <p>{c.context}</p>
                    <SourceButton anchor={c} onLocate={onLocate} />
                  </div>
                ))}
                <button
                  onClick={() =>
                    void run(async () => {
                      await request("/api/graph/edge", {
                        source: e.source,
                        target: e.target,
                        hidden: !e.hidden,
                      });
                      await refresh();
                    })
                  }
                >
                  {e.hidden ? "恢复此边" : "从计算中隐藏此边"}
                </button>
              </details>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function Studio({ papers, selected, run, submit, busy, setNotice }: Tools) {
  const [topic, setTopic] = useState(
    "分析 Transformer 的注意力架构及计算效率，并提出可验证的改进研究方案",
  );
  const [ids, setIds] = useState<string[]>(selected ? [selected.id] : []);
  const [mode, setMode] = useState("review");
  const [code, setCode] = useState(
    "flowchart LR\n  A[导入文献] --> B[段落解析]\n  B --> C[混合检索]\n  C --> D[引用核验]\n  D --> E[科研结论]",
  );
  const [svg, setSvg] = useState("");
  const [diagramJob, setDiagramJob] = useState<string | null>(null);
  useEffect(() => {
    if (!diagramJob) return;
    let active = true;
    const tick = async () => {
      try {
        const job = await request<Job>(`/api/jobs/${diagramJob}`);
        if (!active) return;
        if (job.state === "completed") {
          setDiagramJob(null);
          const source = String(job.result?.code || "");
          setCode(source);
          setSvg("");
          await run(() => renderDiagram(source, false));
          setNotice("图稿已生成并保存，可以修改下方脚本或下载 SVG。");
        } else if (["failed", "cancelled"].includes(job.state)) {
          setDiagramJob(null);
          setNotice(job.error || "图稿生成已停止，可在任务页查看。");
        }
      } catch {
        /* Task remains available after transient connection failures. */
      }
    };
    const timer = window.setInterval(() => void tick(), 1500);
    void tick();
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [diagramJob]);
  const preview = useRef<HTMLDivElement>(null);
  const [csv, setCsv] = useState(
    "方法,准确率,召回率,F1\n基线,72,68,70\n改进一,78,74,76\n改进二,81,79,80",
  );
  const [x, setX] = useState("方法");
  const [ys, setYs] = useState("准确率,召回率,F1");
  const [kind, setKind] = useState("bar");
  const [chart, setChart] = useState<{ id: string; caption: string } | null>(
    null,
  );
  const [chartTitle, setChartTitle] =
    useState("示例数据比较（非论文实验结果）");
  const [unit, setUnit] = useState("百分比 (%)");
  const [xscale, setXscale] = useState("linear");
  const [yscale, setYscale] = useState("linear");
  const [chartIntent, setChartIntent] = useState("");
  const [planNotice, setPlanNotice] = useState("");
  async function renderDiagram(source = code, save = true) {
    const mermaid = (await import("mermaid")).default;
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "neutral",
      maxTextSize: 12000,
    });
    await mermaid.parse(source);
    const value = await mermaid.render("diagram-" + Date.now(), source);
    setSvg(value.svg);
    if (save)
      await request("/api/diagrams", { title: "研究流程图", code: source });
  }
  return (
    <>
      <p className="work-intro">
        把研究问题转成有出处的综述、待验证的方案和可复用图表。
      </p>
      <Help>
        <p>
          选择文献范围后生成综述、写作框架或未来工作时间线；不选文献表示查全库。Agent
          模式先生成工具计划，校验参数，再执行并记录结果。任务完成后在“任务与成果”查看和导出。
        </p>
        <p>
          写作框架中的实验是待开展方案。Mermaid 脚本可编辑、渲染并下载；CSV
          图表使用你提供的数字，保留原数据与重跑脚本。下方初始 CSV
          仅为演示数据，请先替换。
        </p>
      </Help>
      <MatrixBuilder
        ids={ids}
        busy={busy}
        submit={(kind, payload) => run(() => submit(kind, payload))}
      />
      <div className="work-card">
        <h3>从研究意图出发</h3>
        <textarea
          aria-label="研究目标"
          rows={4}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          maxLength={1800}
        />
        <div className="work-row">
          <select
            aria-label="生成任务类型"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="review">证据综述</option>
            <option value="writing">论文方案与写作框架</option>
            <option value="future">未来工作与后续相关论文</option>
            <option value="agent">Agent 自动规划与执行</option>
          </select>
          <button
            className="primary-button"
            disabled={
              busy || !topic.trim() || (mode === "future" && ids.length !== 1)
            }
            onClick={() =>
              void run(() =>
                submit(mode, {
                  topic,
                  goal: topic,
                  document_ids: ids,
                  ...(mode === "future" ? { document_id: ids[0] } : {}),
                }),
              )
            }
          >
            <Play size={15} />
            开始研究任务
          </button>
          <button
            disabled={!ids.length || busy}
            onClick={() =>
              void run(async () => {
                const r = await request<{ bibtex: string }>(
                  "/api/bibliography",
                  { document_ids: ids },
                );
                downloadText("references.bib", r.bibtex);
              })
            }
          >
            导出所选 BibTeX
          </button>
        </div>
        <details>
          <summary>
            文献范围：{ids.length ? `已选 ${ids.length} 篇` : "全库"}
            （未来工作须选一篇）
          </summary>
          <div className="paper-checklist">
            {papers.map((p) => (
              <label key={p.id}>
                <input
                  type="checkbox"
                  checked={ids.includes(p.id)}
                  onChange={(e) =>
                    setIds(
                      e.target.checked
                        ? [...ids, p.id]
                        : ids.filter((i) => i !== p.id),
                    )
                  }
                />
                {p.title} · {p.version ? `v${p.version}` : p.name}
              </label>
            ))}
          </div>
        </details>
      </div>
      <ProtocolEditor documents={ids} />
      <MeasurementLab />
      <div className="work-card">
        <h3>架构与流程图</h3>
        <p>使用上方研究目标生成模块和连线，生成后可继续编辑脚本。</p>
        <button
          disabled={busy || !!diagramJob || !topic.trim()}
          onClick={() =>
            void run(async () => {
              const job = await submit("diagram", { topic });
              setDiagramJob(job.id);
            })
          }
        >
          {diagramJob ? "正在生成图稿…" : "按研究目标生成图稿"}
        </button>
        <textarea
          className="code-input"
          aria-label="Mermaid 图脚本"
          rows={7}
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <div className="work-row">
          <button
            disabled={busy || !code.trim()}
            onClick={() => void run(() => renderDiagram())}
          >
            渲染并保存图稿
          </button>
          <button onClick={() => downloadText("architecture.mmd", code)}>
            下载脚本
          </button>
          {svg && (
            <button
              onClick={() =>
                downloadText("architecture.svg", svg, "image/svg+xml")
              }
            >
              下载 SVG
            </button>
          )}
        </div>
        {svg && (
          <div
            className="diagram-preview"
            ref={preview}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        )}
      </div>
      <div className="work-card">
        <h3>CSV 数据分析与绘图</h3>
        <p className="work-intro">
          初始内容是演示数据。上传或粘贴你的 CSV
          后，选择横轴和数值列；指标单位写在列名或纵轴单位中。
        </p>
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="导入 CSV"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f)
              void run(async () => {
                if (f.size > 2_000_000) throw new Error("CSV 上限 2 MB");
                setCsv(await f.text());
                setNotice("CSV 已载入，请检查列名与单位。");
                setChart(null);
              });
          }}
        />
        <textarea
          aria-label="CSV 数据"
          rows={6}
          className="code-input"
          value={csv}
          onChange={(e) => {
            setCsv(e.target.value);
            setChart(null);
          }}
        />
        <label>
          用一句话描述想画什么
          <textarea
            aria-label="绘图意图"
            value={chartIntent}
            onChange={(e) => setChartIntent(e.target.value)}
            maxLength={1500}
            placeholder="例如：横轴用训练步数，纵轴用损失，画对数纵轴折线图"
          />
        </label>
        <button
          disabled={busy || chartIntent.trim().length < 3}
          onClick={() =>
            void run(async () => {
              const plan = await request<{
                x: string;
                ys: string[];
                kind: string;
                title: string;
                unit: string;
                xscale: string;
                yscale: string;
                limitations: string;
                notice: string;
              }>("/api/charts/plan", { csv, intent: chartIntent });
              setX(plan.x);
              setYs(plan.ys.join(","));
              setKind(plan.kind);
              setChartTitle(plan.title);
              setUnit(plan.unit);
              setXscale(plan.xscale);
              setYscale(plan.yscale);
              setChart(null);
              setPlanNotice(plan.notice + " " + plan.limitations);
            })
          }
        >
          解析绘图意图
        </button>
        {planNotice && <p role="status">{planNotice}</p>}
        <div className="chart-controls">
          <label>
            横轴刻度
            <select
              aria-label="横轴刻度"
              value={xscale}
              onChange={(e) => setXscale(e.target.value)}
            >
              <option value="linear">线性</option>
              <option value="log">对数（正数）</option>
            </select>
          </label>
          <label>
            纵轴刻度
            <select
              aria-label="纵轴刻度"
              value={yscale}
              onChange={(e) => setYscale(e.target.value)}
            >
              <option value="linear">线性</option>
              <option value="log">对数（正数）</option>
            </select>
          </label>
          <label>
            图标题
            <input
              aria-label="图标题"
              value={chartTitle}
              onChange={(e) => setChartTitle(e.target.value)}
            />
          </label>
          <label>
            横轴 / 标识列
            <input
              aria-label="横轴列"
              value={x}
              onChange={(e) => setX(e.target.value)}
            />
          </label>
          <label>
            数值列（逗号分隔）
            <input
              aria-label="数值列"
              value={ys}
              onChange={(e) => setYs(e.target.value)}
            />
          </label>
          <label>
            纵轴单位
            <input
              aria-label="纵轴单位"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            />
          </label>
          <label>
            图表类型
            <select
              aria-label="图表类型"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="line">折线图</option>
              <option value="bar">柱状图</option>
              <option value="scatter">散点图</option>
              <option value="table">数据表格</option>
              <option value="radar3d">三维雷达图</option>
            </select>
          </label>
        </div>
        <button
          className="primary-button"
          disabled={busy}
          onClick={() =>
            void run(async () =>
              setChart(
                await request("/api/charts", {
                  csv,
                  x,
                  ys: ys
                    .split(/[,，]/)
                    .map((v) => v.trim())
                    .filter(Boolean),
                  kind,
                  title: chartTitle,
                  unit,
                  xscale,
                  yscale,
                }),
              ),
            )
          }
        >
          生成图表与图注
        </button>
        {chart && (
          <div className="chart-result">
            <img
              src={`/api/charts/${chart.id}/chart.png`}
              alt={chart.caption}
            />
            <p>{chart.caption}</p>
            <div className="work-row">
              {["png", "svg", "pdf"].map((ext) => (
                <a key={ext} href={`/api/charts/${chart.id}/chart.${ext}`}>
                  下载 {ext.toUpperCase()}
                </a>
              ))}
              <a href={`/api/charts/${chart.id}/bundle.zip`}>
                数据与重跑脚本 ZIP
              </a>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

const stateLabels: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已停止",
  interrupted: "等待恢复",
};
function Tasks({ run, busy, onLocate, onRefresh }: Tools) {
  const [tasks, setTasks] = useState<Job[]>([]);
  const [artifacts, setArtifacts] = useState<
    { id: string; kind: string; title: string }[]
  >([]);
  const [chosen, setChosen] = useState("");
  const [events, setEvents] = useState<
    { id: number; kind: string; message: string; data?: string }[]
  >([]);
  const [result, setResult] = useState<Result | null>(null);
  const refresh = async () => {
    setTasks(await request("/api/jobs"));
    setArtifacts(await request("/api/artifacts"));
  };
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const [j, a] = await Promise.all([
          request<Job[]>("/api/jobs"),
          request<typeof artifacts>("/api/artifacts"),
        ]);
        if (alive) {
          setTasks(j);
          setArtifacts(a);
        }
      } catch {
        /* Keep last visible state during reconnection. */
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 2500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  useEffect(() => {
    setEvents([]);
    if (!chosen) return;
    const source = new EventSource(`/api/jobs/${chosen}/events`);
    source.onmessage = (e) => {
      const item = JSON.parse(e.data);
      setEvents((previous) =>
        previous.some((v) => v.id === item.id)
          ? previous
          : [...previous.slice(-299), item],
      );
    };
    source.addEventListener("end", () => {
      source.close();
      void onRefresh();
    });
    return () => source.close();
  }, [chosen]);
  return (
    <>
      <p className="work-intro">
        长任务在后台排队。离开页面不会中断，进度和成果保存在当前研究空间。
      </p>
      <Help>
        <p>
          点击任务查看真实执行事件。停止会在当前原子操作完成后生效，翻译和索引已有成果保留；失败或停止后可重试。网页重连后从已保存事件恢复。
        </p>
        <p>
          下方“已保存成果”打开综述、写作、时间线和图稿，提供 Markdown / JSON
          导出。引文可点击返回原文。生成结论需要核对语义，不能只凭引文存在就认定正确。
        </p>
      </Help>
      <div className="work-row">
        <button
          onClick={() =>
            void run(async () => {
              await refresh();
              await onRefresh();
            })
          }
        >
          刷新任务和文献库
        </button>
      </div>
      <div className="tasks-layout">
        <div>
          {tasks.map((t) => (
            <article
              className={`task-card ${chosen === t.id ? "selected" : ""}`}
              key={t.id}
            >
              <button className="task-open" onClick={() => setChosen(t.id)}>
                <strong>
                  {(
                    {
                      parse: "结构解析",
                      ocr: "扫描识别",
                      index: "语义索引",
                      translate: "双语翻译",
                      download: "全文下载",
                      track: "主题追踪",
                      review: "证据综述",
                      writing: "写作方案",
                      refine_plan: "方案复核修订",
                      matrix: "证据比较矩阵",
                      future: "未来工作",
                      agent: "Agent 研究",
                      impact: "成果版本复核",
                      table: "表格提取",
                    } as Record<string, string>
                  )[t.kind] || t.kind}
                </strong>
                <span>{stateLabels[t.state]}</span>
              </button>
              <progress value={t.progress} max={1} />
              <p>{t.message}</p>
              {t.error && <p className="work-error">{t.error}</p>}
              <div className="work-row">
                {["queued", "running"].includes(t.state) && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await request(`/api/jobs/${t.id}/cancel`, {});
                        await refresh();
                      })
                    }
                  >
                    <Pause size={13} />
                    停止
                  </button>
                )}
                {["failed", "cancelled", "interrupted"].includes(t.state) && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await request(`/api/jobs/${t.id}/retry`, {});
                        await refresh();
                      })
                    }
                  >
                    <RotateCcw size={13} />
                    重试
                  </button>
                )}
                {typeof t.result?.id === "string" && (
                  <button
                    onClick={() =>
                      void run(async () =>
                        setResult(
                          await request(`/api/artifacts/${t.result!.id}`),
                        ),
                      )
                    }
                  >
                    <Check size={13} />
                    打开成果
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
        <div className="task-log work-card">
          <h3>执行记录</h3>
          {!chosen && <p>选择左侧任务查看事件。</p>}
          {events.map((e) => (
            <div key={e.id}>
              <small>
                {e.kind} · #{e.id}
              </small>
              <p>{e.message}</p>
              {e.data && e.kind === "tool" && (
                <details>
                  <summary>工具参数 / 返回</summary>
                  <pre>{JSON.stringify(JSON.parse(e.data), null, 2)}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="work-card">
        <h3>已保存成果 · {artifacts.length}</h3>
        <div className="artifact-list">
          {artifacts.map((a) => (
            <button
              key={a.id}
              onClick={() =>
                void run(async () =>
                  setResult(await request(`/api/artifacts/${a.id}`)),
                )
              }
            >
              <span>
                {{
                  protocol: "实验设计",
                  measurements: "实验统计",
                  matrix: "证据矩阵",
                }[a.kind] || a.kind}
              </span>
              {a.title}
            </button>
          ))}
        </div>
      </div>
      {result && <Artifact result={result} onLocate={onLocate} />}
    </>
  );
}

type Section = {
  title: string;
  claims: {
    text: string;
    quote: string;
    block_id: string;
    document_id: string;
    page: number;
    source_context?: Anchor[];
  }[];
  evidence: (Anchor & { id: string; text: string })[];
  limitations: string;
  validation?: string;
};
type ImpactItem = {
  artifact_id: string;
  artifact_title: string;
  note: {
    text: string;
    quote: string;
    document_id: string;
    page: number;
    block_id: string;
    dependency_role?: string;
  };
  candidate:
    | (Anchor & {
        text: string;
        segments?: Anchor[];
        skipped_context?: Anchor[];
      })
    | null;
  explanation: string;
  semantic_review?: { decision?: string; reason: string; method?: string };
};
type ProgressAssessment = {
  question: { text: string; quote: string };
  status: string;
  reason: string;
  assessment?: string;
  claims?: Section["claims"];
  evidence: Section["evidence"];
};
function Artifact({
  result,
  onLocate,
}: {
  result: Result;
  onLocate: Props["onLocate"];
}) {
  const c = result.content;
  const sections = (c.sections || []) as Section[];
  const proposal = c.proposal as Record<string, string> | undefined;
  const timeline = c.timeline as RemotePaper[] | undefined;
  return (
    <article className="work-card artifact-result">
      <h2>{result.title}</h2>
      <div className="work-row">
        <a href={`/api/artifacts/${result.id}/export?format=md`}>
          下载 Markdown
        </a>
        <a href={`/api/artifacts/${result.id}/export?format=json`}>
          下载完整 JSON 与来源
        </a>
      </div>
      {typeof c.notice === "string" && (
        <p className="work-notice">{c.notice}</p>
      )}
      {["writing", "review", "matrix"].includes(result.kind) && (
        <WritingEditor key={result.id} identifier={result.id} content={c} />
      )}
      {Array.isArray(c.plan_checks) && c.plan_checks.length > 0 && (
        <section className="work-notice">
          <h3>执行实验前必须补齐</h3>
          <p>
            方案仍是草稿。以下检查发现未定条件或可能不匹配的设计，请编辑后核对。
          </p>
          {(c.plan_checks as string[]).map((check, i) => (
            <p key={i}>• {check}</p>
          ))}
        </section>
      )}
      {proposal && (
        <ProposalRevision
          key={`revision-${result.id}`}
          identifier={result.id}
          audit={
            c.revision_audit as Parameters<typeof ProposalRevision>[0]["audit"]
          }
        />
      )}
      {proposal && (
        <ProtocolEditor key={`protocol-from-${result.id}`} source={result.id} />
      )}
      {result.kind === "protocol" && (
        <ProtocolEditor
          key={`${result.id}-${c.revision}`}
          identifier={result.id}
          content={c as ProtocolContent}
        />
      )}
      {result.kind === "measurements" && (
        <MeasurementResult
          identifier={result.id}
          content={c as MeasurementContent}
        />
      )}
      {proposal &&
        Object.entries(proposal).map(([k, v]) => (
          <section key={k}>
            <h3>
              {
                (
                  {
                    abstract: "研究设想摘要",
                    introduction: "引言框架",
                    method_plan: "拟议方法",
                    evaluation_plan: "待开展的评估",
                  } as Record<string, string>
                )[k]
              }
            </h3>
            <p style={{ whiteSpace: "pre-line" }}>{v}</p>
          </section>
        ))}
      {result.kind === "matrix" && (
        <MatrixResult
          rows={(c.matrix || []) as MatrixRow[]}
          onLocate={onLocate}
        />
      )}
      {Array.isArray(c.missing_items) && c.missing_items.length > 0 && (
        <section>
          <h3>复现前待补清单</h3>
          {(
            c.missing_items as {
              title: string;
              field: string;
              action: string;
            }[]
          ).map((m, i) => (
            <p key={i}>
              <strong>
                {m.title} · {m.field}
              </strong>
              <br />
              {m.action}
            </p>
          ))}
        </section>
      )}
      {(result.kind === "matrix" ? [] : sections).map((s, i) => (
        <section key={i}>
          <h3>{s.title}</h3>
          {s.claims.map((claim, j) => {
            const b = s.evidence.find((e) => e.id === claim.block_id);
            return (
              <div key={j} className="grounded-claim">
                <p>{claim.text}</p>
                <blockquote>{claim.quote}</blockquote>
                {b && <SourceButton anchor={b} onLocate={onLocate} />}
                {claim.source_context?.map((context, i) => (
                  <SourceButton key={i} anchor={context} onLocate={onLocate}>
                    核对表头
                  </SourceButton>
                ))}
              </div>
            );
          })}
          <p>{s.limitations}</p>
          <small>{s.validation}</small>
          {!s.claims.length && <p>未生成通过引用校验的论断。</p>}
        </section>
      ))}
      {timeline?.map((p) => (
        <div className="timeline-item" key={p.id}>
          <small>{p.published.slice(0, 10)}</small>
          <a href={p.url} target="_blank" rel="noreferrer">
            {p.title} ↗
          </a>
          <p>相关进展候选；解决状态待全文核验。</p>
        </div>
      ))}
      {typeof c.external_error === "string" && (
        <p className="work-error">
          {c.external_error} 可稍后重新提交此任务，已完成的本地分析仍可使用。
        </p>
      )}
      {Array.isArray(c.progress_assessments) &&
        (c.progress_assessments as ProgressAssessment[]).map((p, i) => (
          <section className="grounded-claim" key={i}>
            <h3>{p.question.text}</h3>
            <blockquote>{p.question.quote}</blockquote>
            <strong>{p.status} · 模型初判</strong>
            <p>{p.reason}</p>
            {p.claims?.map((claim, j) => {
              const b = p.evidence.find((b) => b.id === claim.block_id);
              return (
                <div key={j}>
                  <p>{claim.text}</p>
                  <blockquote>{claim.quote}</blockquote>
                  {b && (
                    <SourceButton anchor={b} onLocate={onLocate}>
                      核对后续全文证据
                    </SourceButton>
                  )}
                </div>
              );
            })}
            <small>{p.assessment}</small>
          </section>
        ))}
      {result.kind === "chart" && (
        <>
          <img
            className="artifact-chart"
            src={`/api/charts/${result.id}/chart.png`}
            alt="已保存的 CSV 图表"
          />
          <p>{String(c.caption)}</p>
          <a href={`/api/charts/${result.id}/bundle.zip`}>
            下载数据、图表和脚本
          </a>
        </>
      )}
      {result.kind === "diagram" && (
        <>
          <SavedDiagram code={String(c.code)} />
          <button
            onClick={() => downloadText("architecture.mmd", String(c.code))}
          >
            下载 Mermaid 脚本
          </button>
        </>
      )}
      {result.kind === "formula" && (
        <FormulaResult identifier={result.id} content={c} />
      )}
      {result.kind === "table" && (
        <TableResult
          identifier={result.id}
          content={c as unknown as TableContent}
        />
      )}
      {result.kind === "agent" && (
        <>
          <h3>已经执行的研究步骤</h3>
          {(
            (c.results || []) as {
              tool: string;
              result: Record<string, unknown> | RemotePaper[];
            }[]
          ).map((step, i) => {
            if (Array.isArray(step.result))
              return (
                <section key={i}>
                  <h3>{i + 1}. 外部论文检索</h3>
                  {step.result.map((p) => (
                    <p key={p.id}>
                      <a href={p.url} target="_blank" rel="noreferrer">
                        {p.title} ↗
                      </a>
                    </p>
                  ))}
                </section>
              );
            const value = step.result;
            if (value.kind && value.id)
              return (
                <Artifact
                  key={i}
                  result={{
                    id: String(value.id),
                    kind: String(value.kind),
                    title: String(value.title || `步骤 ${i + 1}`),
                    content: value,
                  }}
                  onLocate={onLocate}
                />
              );
            if (Array.isArray(value.claims))
              return (
                <Artifact
                  key={i}
                  result={{
                    id: result.id,
                    kind: "evidence",
                    title: `步骤 ${i + 1} · 查证原文`,
                    content: {
                      sections: [{ title: "检索到的论断与出处", ...value }],
                    },
                  }}
                  onLocate={onLocate}
                />
              );
            return (
              <section key={i}>
                <h3>
                  步骤 {i + 1} · {step.tool}
                </h3>
                <pre>{JSON.stringify(value, null, 2)}</pre>
              </section>
            );
          })}
          <h3>下一步核验建议</h3>
          <p>{String(c.next_steps || "")}</p>
          <details>
            <summary>查看完整工具参数与执行记录</summary>
            <pre>{JSON.stringify(c, null, 2)}</pre>
          </details>
        </>
      )}
      {result.kind === "impact" && (
        <>
          <p>
            找到 {Number(c.total_dependencies)} 条成果引用依赖，本次检查{" "}
            {Number(c.checked)} 条。
          </p>
          {(c.impact as ImpactItem[]).map((item, i) => (
            <section className="grounded-claim" key={i}>
              <h3>{item.artifact_title}</h3>
              <p>{item.note.text}</p>
              {item.note.dependency_role === "table_header" && (
                <small>
                  此项核对的是该论断依赖的表头；列含义变化也会影响数字解释。
                </small>
              )}
              <strong>
                {item.semantic_review?.decision === "claim_changed"
                  ? "论断可能受影响"
                  : item.semantic_review?.decision === "same_claim"
                    ? item.semantic_review.method
                      ? "原文规则核对未见变化"
                      : "模型初判论断未变"
                    : item.explanation}
              </strong>
              <p>{item.semantic_review?.reason}</p>
              <blockquote>原引用：{item.note.quote}</blockquote>
              {item.candidate && (
                <>
                  <blockquote>新版本候选：{item.candidate.text}</blockquote>
                  {!!item.candidate.skipped_context?.length && (
                    <details>
                      <summary>跨页衔接时略过的图表与页脚（可核对）</summary>
                      {item.candidate.skipped_context.map((segment, index) => (
                        <div key={index}>
                          <blockquote>{segment.text}</blockquote>
                          <SourceButton anchor={segment} onLocate={onLocate}>
                            查看第 {segment.page} 页上下文
                          </SourceButton>
                        </div>
                      ))}
                    </details>
                  )}
                  {(item.candidate.segments || [item.candidate]).map(
                    (segment, index, segments) => (
                      <SourceButton
                        key={index}
                        anchor={segment}
                        onLocate={onLocate}
                      >
                        核对新版本出处
                        {segments.length > 1
                          ? ` ${index + 1}/${segments.length}`
                          : ""}
                      </SourceButton>
                    ),
                  )}
                </>
              )}
              <a href={`/api/artifacts/${item.artifact_id}/export?format=md`}>
                下载原始成果
              </a>
            </section>
          ))}
        </>
      )}
    </article>
  );
}

function Account({ run, busy }: Tools) {
  const [status, setStatus] = useState<{
    account: { name: string } | null;
    public_mode: boolean;
  } | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  useEffect(() => {
    void run(async () => setStatus(await request("/api/account/status")));
  }, []);
  return (
    <>
      <p className="work-intro">
        每个账号拥有独立的文献、笔记、偏好和任务。当前本机空间的数据不会自动复制到新账号。
      </p>
      <Help>
        <p>
          本地模式允许直接使用默认研究空间。建立账号后进入独立空间；退出登录可回到本机默认空间。公开部署要求登录，注册默认关闭。密码至少
          10 个字符，使用加盐哈希保存。
        </p>
      </Help>
      <div className="work-card">
        <h3>
          {status?.account
            ? `当前账号：${status.account.name}`
            : "当前为本机默认空间"}
        </h3>
        {status?.account ? (
          <button
            onClick={() =>
              void run(async () => {
                await request("/api/account/logout", {});
                location.reload();
              })
            }
          >
            退出账号
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                await request("/api/account/login", { name, password });
                location.reload();
              });
            }}
          >
            <label>
              用户名
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="username"
                minLength={2}
                maxLength={40}
                required
              />
            </label>
            <label>
              密码
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                minLength={10}
                maxLength={200}
                required
              />
            </label>
            <div className="work-row">
              <button className="primary-button" disabled={busy}>
                登录
              </button>
              {!status?.public_mode && (
                <button
                  type="button"
                  disabled={busy || name.length < 2 || password.length < 10}
                  onClick={() =>
                    void run(async () => {
                      await request("/api/account/register", {
                        name,
                        password,
                      });
                      location.reload();
                    })
                  }
                >
                  创建独立账号
                </button>
              )}
            </div>
          </form>
        )}
      </div>
    </>
  );
}
