import { useEffect, useRef, useState } from "react";
import {
  FolderOpen,
  Plus,
  Search,
  BookOpen,
  MessageSquare,
  FlaskConical,
  Link,
  RefreshCw,
  Archive,
} from "lucide-react";
import { request, type Anchor, type Paper } from "./workspaceApi";
import { Artifact, type Result } from "./Workbench";
import {
  openProjectLink,
  projectFromHash,
  type ProjectContext,
  type ProjectDetail,
  type ProjectSummary,
} from "./projectApi";
import "./projects.css";
import { ResearchTasks } from "./ResearchTasks";

type Props = {
  papers: Paper[];
  onRead: (id: string) => void;
  onLocate: (anchor: Anchor) => void;
  onUse: (project: ProjectContext, mode: "reader" | "studio") => void;
  onTasks: () => void;
  onOpenComparison: (id: string) => void;
};
const kindLabel: Record<string, string> = {
  answer: "论文问答",
  review: "文献综述",
  writing: "研究方案",
  matrix: "证据矩阵",
  diagram: "流程图",
  chart: "统计图表",
  protocol: "实验设计",
  measurements: "实验统计",
  preflight: "执行预检",
  impact: "影响复核",
};
const jobLabel: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "等待恢复",
};

export function Projects({
  papers,
  onRead,
  onLocate,
  onUse,
  onTasks,
  onOpenComparison,
}: Props) {
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [chosen, setChosen] = useState(projectFromHash);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [draft, setDraft] = useState<{
    title: string;
    goal: string;
    document_ids: string[];
  } | null>(null);
  const [paperQuery, setPaperQuery] = useState("");
  const [catalog, setCatalog] = useState<ProjectDetail["artifacts"]>([]);
  const [artifactQuery, setArtifactQuery] = useState("");
  const [artifactChoice, setArtifactChoice] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [tab, setTab] = useState("documents");
  const [reload, setReload] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);
  const pending = useRef(0);
  useEffect(() => {
    const change = () => {
      pending.current++;
      setChosen(projectFromHash());
      setDraft(null);
      setResult(null);
      setNotice("");
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    let live = true;
    pending.current++;
    setLoading(true);
    setError("");
    setProject(null);
    setDraft(null);
    setResult(null);
    setArtifactChoice("");
    Promise.allSettled([
      request<ProjectSummary[]>("/api/projects"),
      chosen
        ? request<ProjectDetail>(`/api/projects/${chosen}`)
        : Promise.resolve(null),
      request<ProjectDetail["artifacts"]>("/api/artifacts"),
    ])
      .then(([list, detail, outputs]) => {
        if (live) {
          if (list.status === "fulfilled") setItems(list.value);
          if (detail.status === "fulfilled") {
            setProject(detail.value);
            if (detail.value) setArchived(!!detail.value.archived);
          }
          if (outputs.status === "fulfilled") setCatalog(outputs.value);
          setError(
            [list, detail, outputs]
              .filter((r) => r.status === "rejected")
              .map((r) => String(r.reason))
              .join("；"),
          );
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [chosen, reload]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  function select(id: string) {
    openProjectLink(id);
    setChosen(id);
    setTab("documents");
    setCreating(false);
    setPaperQuery("");
  }
  async function saveProject(
    changes: Partial<{
      title: string;
      goal: string;
      document_ids: string[];
      artifact_ids: string[];
      archived: boolean;
    }>,
  ) {
    if (!project) return;
    const updated = await request<ProjectDetail>(
      `/api/projects/${project.id}`,
      {
        title: project.title,
        goal: project.goal,
        document_ids: project.document_ids,
        artifact_ids: project.artifacts.map((a) => a.id),
        archived: !!project.archived,
        expected_revision: project.revision,
        ...changes,
      },
      "PATCH",
    );
    setProject(updated);
    setDraft(null);
    setItems(await request("/api/projects"));
    setArtifactChoice("");
    setNotice("项目已保存。");
  }
  async function openArtifact(id: string) {
    const ticket = ++pending.current;
    const output = await request<Result>(`/api/artifacts/${id}`);
    if (ticket !== pending.current) return;
    setResult(output);
    requestAnimationFrame(() =>
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }
  const activePapers = project?.documents.filter((p) => !p.archived) || [];
  const papersReady = activePapers.every((p) =>
    papers.some((available) => available.id === p.id),
  );
  const available = papers.filter((p) =>
    `${p.title} ${p.name}`
      .toLowerCase()
      .includes(paperQuery.trim().toLowerCase()),
  );
  const projectChoices = items.filter(
    (p) =>
      !!p.archived === archived &&
      `${p.title} ${p.goal}`.toLowerCase().includes(search.toLowerCase()),
  );
  const outputs = catalog.filter(
    (a) =>
      !project?.artifacts.some((p) => p.id === a.id) &&
      `${a.title} ${kindLabel[a.kind] || a.kind}`
        .toLowerCase()
        .includes(artifactQuery.toLowerCase()),
  );
  return (
    <section className="research-workspace project-workspace">
      <div className="work-title">
        <h1>研究项目</h1>
        <button
          className="primary-button"
          disabled={busy || !!draft}
          onClick={() => setCreating((v) => !v)}
        >
          <Plus size={15} />
          新建项目
        </button>
      </div>
      <p className="work-intro">
        围绕一个研究问题，整理文献、核对证据、积累成果。同一篇论文可以属于多个项目。
      </p>
      <details className="extended-help">
        <summary>功能与用法</summary>
        <div>
          <p>
            新建项目并写下研究目标，在“编辑目标与文献”勾选论文并保存。项目文献中的非归档笔记会显示在“关联笔记”，同一论文的笔记可在多个项目中看到。
          </p>
          <p>
            使用项目文献提问，或从项目进入工作室后，问答、综述、方案、证据矩阵及工作室图表会自动收纳。其他既有成果可以手动加入；加入和移出只改变关联，不删除原成果。项目归档不会删除论文、笔记或成果。
          </p>
          <p>
            阅读台的“后台问答”支持 1—8
            篇，完成后会收纳到发起时的项目；停止时已完成论文的部分结果可在阅读台“查看后台问答”中找回。
          </p>
          <p>
            “下载完整成果包”包含全部关联成果正文和修订历史、证据笔记、项目任务记录及文件校验清单，不包含
            PDF
            原文件、外部附件和未保存草稿，也不是整站备份。复制项目链接可在同一台电脑、同一研究账号中定位；它不自动变成公网分享。项目摘要导出包含目标、文献清单、关联笔记、成果索引和最近任务，不含
            PDF 与成果全文。详情需要刷新才能获取其他页面或后台任务的新结果。
          </p>
        </div>
        <p>
          “研究补查待办”用于人工补查证据，与后台运行任务分开。可开始、记录依据并回填对照表、未解决关闭或重新打开。项目导出包含处理历史与证据，完整成果包同时包含关联对照表；归档项目后待办保留为只读。
        </p>
      </details>
      {error && (
        <div className="work-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="project-notice" role="status">
          {notice}
        </div>
      )}
      {creating && (
        <form
          className="work-card project-create"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              const p = await request<ProjectDetail>("/api/projects", {
                title: name,
                goal,
              });
              setName("");
              setGoal("");
              select(p.id);
              setProject(p);
              setItems(await request("/api/projects"));
            });
          }}
        >
          <h3>创建一个研究课题</h3>
          <label>
            项目名称
            <input
              required
              maxLength={120}
              aria-label="新项目名称"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：注意力机制的效率与复现"
            />
          </label>
          <label>
            研究目标
            <textarea
              maxLength={1800}
              aria-label="新项目研究目标"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="要回答什么问题？准备比较哪些方法、条件与指标？"
              rows={3}
            />
          </label>
          <button className="primary-button" disabled={busy || !name.trim()}>
            创建项目
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setCreating(false)}
          >
            取消
          </button>
        </form>
      )}
      <div className="project-layout">
        <aside className="project-list">
          <label>
            <Search size={14} />
            查找项目
            <input
              aria-label="搜索研究项目"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="项目名称或研究目标"
            />
          </label>
          <div className="project-list-tabs">
            <button aria-pressed={!archived} onClick={() => setArchived(false)}>
              进行中
            </button>
            <button aria-pressed={archived} onClick={() => setArchived(true)}>
              已归档
            </button>
          </div>
          {projectChoices.map((p) => (
            <button
              className={`project-card ${chosen === p.id ? "selected" : ""}`}
              key={p.id}
              disabled={busy || !!draft}
              onClick={() => select(p.id)}
            >
              <strong>
                <FolderOpen size={16} />
                {p.title}
              </strong>
              <span>{p.goal || "尚未填写研究目标"}</span>
              <small>
                {p.document_count} 篇文献 · {p.artifact_count} 份成果
              </small>
            </button>
          ))}
          {!loading && !projectChoices.length && (
            <p className="project-empty">
              {search
                ? "没有匹配的项目。"
                : archived
                  ? "暂无归档项目。"
                  : "还没有项目。先创建一个具体的研究课题。"}
            </p>
          )}
        </aside>
        <div className="project-main">
          {loading ? (
            <p role="status">正在加载项目…</p>
          ) : !project ? (
            <div className="work-empty">
              <FolderOpen size={32} />
              <h2>从一个研究问题开始</h2>
              <p>创建或选择项目，把分散的资料与成果放在一起。</p>
            </div>
          ) : (
            <>
              <div className="project-heading">
                <div>
                  <span className="project-kicker">
                    {project.archived ? "已归档项目" : "进行中的研究"}
                  </span>
                  <h2>{project.title}</h2>
                </div>
                <button
                  disabled={busy}
                  onClick={() => {
                    setDraft(null);
                    setReload((n) => n + 1);
                  }}
                >
                  <RefreshCw size={14} />
                  {draft ? "放弃草稿并刷新" : "刷新项目"}
                </button>
              </div>
              <p className="project-goal">
                {project.goal || "点击“编辑目标与文献”，补充要解决的研究问题。"}
              </p>
              <div className="project-actions">
                <button
                  disabled={busy || !!project.archived || !!draft}
                  onClick={() => {
                    setDraft({
                      title: project.title,
                      goal: project.goal,
                      document_ids: [...project.document_ids],
                    });
                    setTab("documents");
                  }}
                >
                  编辑目标与文献
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await navigator.clipboard.writeText(
                        `${location.origin}${location.pathname}#${new URLSearchParams({ project: project.id })}`,
                      );
                      setNotice(
                        "项目链接已复制，仅在可访问本机服务且属于同一账号时有效。",
                      );
                    })
                  }
                >
                  <Link size={14} />
                  复制项目链接
                </button>
                <a href={`/api/projects/${project.id}/export`}>导出项目摘要</a>
                <a href={`/api/projects/${project.id}/bundle`}>
                  下载完整成果包
                </a>
                <button
                  disabled={busy || !!draft}
                  onClick={() =>
                    void run(async () => {
                      await saveProject({ archived: !project.archived });
                      setArchived(!project.archived);
                    })
                  }
                >
                  <Archive size={14} />
                  {project.archived ? "恢复项目" : "归档项目"}
                </button>
              </div>
              {draft && (
                <form
                  className="project-editor"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run(() => saveProject(draft));
                  }}
                >
                  <h3>编辑目标与项目文献</h3>
                  <label>
                    项目名称
                    <input
                      required
                      maxLength={120}
                      aria-label="编辑项目名称"
                      value={draft.title}
                      onChange={(e) =>
                        setDraft({ ...draft, title: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    研究目标
                    <textarea
                      aria-label="编辑项目目标"
                      maxLength={1800}
                      rows={3}
                      value={draft.goal}
                      onChange={(e) =>
                        setDraft({ ...draft, goal: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    筛选可加入的论文
                    <input
                      aria-label="筛选项目候选文献"
                      value={paperQuery}
                      onChange={(e) => setPaperQuery(e.target.value)}
                    />
                  </label>
                  <p>
                    已选 {draft.document_ids.length} 篇 ·
                    选择论文不会改变文献库中的分类
                  </p>
                  <div className="project-paper-picker">
                    {available.map((p) => (
                      <label key={p.id}>
                        <input
                          type="checkbox"
                          aria-label={`加入项目 ${p.name}`}
                          checked={draft.document_ids.includes(p.id)}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              document_ids: e.target.checked
                                ? [...draft.document_ids, p.id]
                                : draft.document_ids.filter(
                                    (id) => id !== p.id,
                                  ),
                            })
                          }
                        />
                        <span>
                          {p.title}
                          <small>
                            {p.version ? `v${p.version} · ` : ""}
                            {p.name}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                  {project.documents
                    .filter(
                      (p) => p.archived && draft.document_ids.includes(p.id),
                    )
                    .map((p) => (
                      <p key={p.id}>
                        已归档文献：{p.title}
                        <button
                          type="button"
                          onClick={() =>
                            setDraft({
                              ...draft,
                              document_ids: draft.document_ids.filter(
                                (id) => id !== p.id,
                              ),
                            })
                          }
                        >
                          移出项目
                        </button>
                      </p>
                    ))}
                  <div className="work-row">
                    <button
                      className="primary-button"
                      disabled={busy || !draft.title.trim()}
                    >
                      保存项目设置
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setDraft(null)}
                    >
                      取消编辑
                    </button>
                  </div>
                </form>
              )}
              <div className="project-launch">
                <div>
                  <strong>{activePapers.length} 篇可用文献</strong>
                  <p>
                    问答、综述、方案、矩阵与图稿自动收纳；实验记录可手动关联。
                  </p>
                </div>
                <button
                  disabled={
                    busy ||
                    !!draft ||
                    !!project.archived ||
                    !activePapers.length ||
                    !papersReady ||
                    activePapers.length > 40
                  }
                  onClick={() =>
                    onUse(
                      {
                        ...project,
                        document_ids: activePapers.map((p) => p.id),
                      },
                      "reader",
                    )
                  }
                >
                  <MessageSquare size={15} />
                  使用项目文献提问
                </button>
                <button
                  disabled={
                    busy ||
                    !!draft ||
                    !!project.archived ||
                    !activePapers.length ||
                    !papersReady ||
                    activePapers.length > 40
                  }
                  onClick={() =>
                    onUse(
                      {
                        ...project,
                        document_ids: activePapers.map((p) => p.id),
                      },
                      "studio",
                    )
                  }
                >
                  <FlaskConical size={15} />
                  进入项目工作室
                </button>
              </div>
              {activePapers.length > 40 && (
                <p>
                  当前问答和工作室一次最多处理 40
                  篇，请先在项目中精简本次研究文献。
                </p>
              )}
              <div className="project-tabs">
                {[
                  ["documents", `项目文献 ${project.documents.length}`],
                  ["notes", `关联笔记 ${project.notes.length}`],
                  ["artifacts", `研究成果 ${project.artifacts.length}`],
                  ["jobs", `最近任务 ${project.jobs.length}`],
                  ["research_tasks", "研究补查待办"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    aria-pressed={tab === id}
                    onClick={() => setTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === "research_tasks" && (
                <ResearchTasks
                  key={project.id}
                  projectId={project.id}
                  onOpenComparison={onOpenComparison}
                  onLocate={onLocate}
                />
              )}
              {tab === "documents" && (
                <div className="project-document-list">
                  {project.documents.map((p) => (
                    <article key={p.id}>
                      <div>
                        <strong>{p.title}</strong>
                        <small>
                          {p.version ? `v${p.version} · ` : ""}
                          {p.pages} 页 ·{" "}
                          {p.archived ? "文献已归档，仅保留项目关联" : p.name}
                        </small>
                      </div>
                      <button
                        disabled={!!p.archived}
                        onClick={() => onRead(p.id)}
                      >
                        <BookOpen size={14} />
                        阅读
                      </button>
                    </article>
                  ))}
                  {!project.documents.length && (
                    <p className="project-empty">
                      项目还没有文献。点击“编辑目标与文献”，从文献库选择。
                    </p>
                  )}
                </div>
              )}
              {tab === "notes" && (
                <div>
                  <p className="project-explanation">
                    这些笔记来自本项目关联文献，可能也用于其他项目。移出文献会改变这里的显示，不会删除笔记。
                  </p>
                  {project.notes.map((n) => (
                    <article className="project-note" key={n.id}>
                      <strong>{n.note}</strong>
                      <blockquote>{n.quote}</blockquote>
                      <small>
                        {n.title} · {n.version ? `v${n.version}` : "版本未标注"}{" "}
                        · 第 {n.page} 页
                      </small>
                      <button
                        onClick={() => onLocate({ ...n, id: n.block_id })}
                      >
                        核对原文
                      </button>
                    </article>
                  ))}
                  {!project.notes.length && (
                    <p className="project-empty">
                      还没有关联笔记。阅读项目论文、核对回答后，可以将出处存为证据笔记。
                    </p>
                  )}
                </div>
              )}
              {tab === "artifacts" && (
                <div>
                  {!project.archived && (
                    <details className="project-attach">
                      <summary>收纳已有成果</summary>
                      <p>
                        可以把全库已有成果关联到本项目；关联不会复制或修改原文。
                      </p>
                      <input
                        aria-label="搜索待收纳成果"
                        value={artifactQuery}
                        onChange={(e) => setArtifactQuery(e.target.value)}
                        placeholder="搜索成果标题或类型"
                      />
                      <select
                        aria-label="选择待收纳成果"
                        value={artifactChoice}
                        onChange={(e) => setArtifactChoice(e.target.value)}
                      >
                        <option value="">选择已有成果</option>
                        {outputs.map((a) => (
                          <option key={a.id} value={a.id}>
                            {kindLabel[a.kind] || a.kind} · {a.title}
                          </option>
                        ))}
                      </select>
                      <button
                        disabled={busy || !artifactChoice || !!draft}
                        onClick={() =>
                          void run(() =>
                            saveProject({
                              artifact_ids: [
                                ...project.artifacts.map((a) => a.id),
                                artifactChoice,
                              ],
                            }),
                          )
                        }
                      >
                        加入项目成果
                      </button>
                    </details>
                  )}
                  {project.artifacts.map((a) => (
                    <article className="project-output" key={a.id}>
                      <div>
                        <small>
                          {kindLabel[a.kind] || a.kind} · {a.created_at}
                        </small>
                        <h3>{a.title}</h3>
                      </div>
                      <button
                        disabled={busy}
                        onClick={() => void run(() => openArtifact(a.id))}
                      >
                        打开成果
                      </button>
                      <button
                        disabled={busy || !!project.archived || !!draft}
                        onClick={() =>
                          void run(() =>
                            saveProject({
                              artifact_ids: project.artifacts
                                .filter((x) => x.id !== a.id)
                                .map((x) => x.id),
                            }),
                          )
                        }
                      >
                        移出项目
                      </button>
                    </article>
                  ))}
                  {!project.artifacts.length && (
                    <p className="project-empty">
                      还没有研究成果。从本项目开始问答或研究任务，或收纳已有成果。
                    </p>
                  )}
                  <div ref={resultRef}>
                    {result && <Artifact result={result} onLocate={onLocate} />}
                  </div>
                </div>
              )}
              {tab === "jobs" && (
                <div>
                  <p className="project-explanation">
                    仅显示从项目工作室提交的最近 25
                    个后台任务；直接问答保存在研究成果中。
                  </p>
                  {project.jobs.map((j) => (
                    <article className="project-output" key={j.id}>
                      <div>
                        <strong>
                          {kindLabel[j.kind] || j.kind} ·{" "}
                          {jobLabel[j.state] || j.state}
                        </strong>
                        <p>{j.error || j.message}</p>
                      </div>
                      <span>{Math.round(j.progress * 100)}%</span>
                    </article>
                  ))}
                  {!project.jobs.length && (
                    <p className="project-empty">还没有后台任务。</p>
                  )}
                  <button onClick={onTasks}>
                    打开任务与成果，查看详情或重试
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
