import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, FileText, Search, X } from "lucide-react";
import type { WorkView } from "./Workbench";
import "./quickSearch.css";

type View = "reader" | "notes" | "audit" | "projects" | WorkView;
type Paper = {
  id: string;
  title: string;
  name: string;
  arxiv_id: string | null;
  version: number | null;
};
const actions: { id: View; title: string; detail: string; keywords: string }[] =
  [
    {
      id: "discover",
      title: "查找论文与相关文章",
      detail: "按标题、主题、DOI 或 arXiv 编号发现文献",
      keywords: "论文发现 搜索 推荐 查文献 search doi arxiv",
    },
    {
      id: "reader",
      title: "阅读原文与证据问答",
      detail: "原版 PDF、页码定位、引用和限定原文追问",
      keywords: "文献阅读台 问问题 提问 阅读 pdf chat ask",
    },
    {
      id: "audit",
      title: "复核论文版本变化",
      detail: "对照两版原文，检查旧笔记的依据是否变化",
      keywords: "版本复核 更新 比较 旧结论 version diff",
    },
    {
      id: "notes",
      title: "整理证据与比较条件",
      detail: "证据笔记、条件对照、比较前检查和补查待办",
      keywords: "笔记 比较 表格 矩阵 边界 补查 note compare",
    },
    {
      id: "projects",
      title: "组织一个研究项目",
      detail: "集中管理目标、文献、笔记、任务与成果",
      keywords: "课题 研究项目 project",
    },
    {
      id: "library",
      title: "管理文献与解析质量",
      detail: "筛选标签、阅读状态、OCR 和逐页覆盖检查",
      keywords: "文献管理 导入 扫描 解析 ocr library",
    },
    {
      id: "translate",
      title: "双语阅读与引用导出",
      detail: "段落翻译、双语联动与参考文献",
      keywords: "双语与引文 翻译 术语 bibtex ris translate",
    },
    {
      id: "studio",
      title: "写作、研究方案与绘图",
      detail: "有来源草稿、研究方案、流程图和 CSV 图表",
      keywords: "科研工作室 绘图 画图 作图 实验 综述 mermaid csv writing",
    },
    {
      id: "graph",
      title: "查看引用图谱",
      detail: "查看已获得的文献关系与关键节点",
      keywords: "引用 网络 图谱 graph citation",
    },
    {
      id: "tasks",
      title: "找回任务与研究成果",
      detail: "后台进度、生成历史和成果导出",
      keywords: "任务与成果 历史 下载 导出 进度 task export",
    },
    {
      id: "account",
      title: "登录与管理研究空间",
      detail: "切换账号并查看空间信息",
      keywords: "研究空间与账号 登录 注册 account login",
    },
  ];
const normalized = (text: string) =>
  text.normalize("NFKC").toLocaleLowerCase().trim();

export function QuickSearch({
  documents,
  onDocument,
  onNavigate,
  onClose,
}: {
  documents: Paper[];
  onDocument: (id: string) => void;
  onNavigate: (view: View) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const words = normalized(query).split(/\s+/).filter(Boolean);
  const matches = (text: string) =>
    words.every((word) => normalized(text).includes(word));
  const tasks = actions.filter((item) =>
    matches(`${item.title} ${item.detail} ${item.keywords}`),
  );
  const papers = words.length
    ? documents.filter((p) =>
        matches(`${p.title} ${p.name} ${p.arxiv_id || ""}`),
      )
    : [];
  const results = [
    ...tasks.map((item) => ({
      key: item.id,
      title: item.title,
      detail: item.detail,
      paper: false,
      run: () => onNavigate(item.id),
    })),
    ...papers
      .slice(0, 12)
      .map((p) => ({
        key: p.id,
        title: p.title || p.name,
        detail: `${p.version ? `v${p.version} · ` : ""}${p.name}`,
        paper: true,
        run: () => onDocument(p.id),
      })),
  ];
  const selected = Math.min(active, Math.max(0, results.length - 1));
  useEffect(() => {
    const node = dialog.current!;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    node.showModal();
    document.body.style.overflow = "hidden";
    input.current?.focus();
    return () => {
      node.close();
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    document
      .getElementById(`quick-result-${selected}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selected]);
  function choose(index: number) {
    const result = results[index];
    if (!result) return;
    onClose();
    result.run();
  }
  return (
    <dialog
      ref={dialog}
      className="quick-dialog"
      aria-labelledby="quick-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header>
        <div>
          <h2 id="quick-title">你想做什么？</h2>
          <p>搜索功能或库内论文，快速继续研究。</p>
        </div>
        <button aria-label="关闭快捷查找" onClick={onClose}>
          <X size={20} />
        </button>
      </header>
      <div className="quick-input">
        <Search size={20} />
        <input
          ref={input}
          aria-label="搜索功能或库内论文"
          role="combobox"
          aria-expanded="true"
          aria-controls="quick-results"
          aria-autocomplete="list"
          aria-activedescendant={
            results.length ? `quick-result-${selected}` : undefined
          }
          value={query}
          placeholder="试试：版本、画图、翻译，或论文标题"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing || e.keyCode === 229) return;
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              if (results.length)
                setActive(
                  (selected +
                    (e.key === "ArrowDown" ? 1 : -1) +
                    results.length) %
                    results.length,
                );
            } else if (e.key === "Enter") {
              e.preventDefault();
              choose(selected);
            }
          }}
        />
      </div>
      <p className="quick-count" role="status">
        {tasks.length} 个功能入口
        {words.length
          ? ` · ${papers.length} 篇库内论文${papers.length > 12 ? "（显示前 12 篇，请补充关键词）" : ""}`
          : " · 输入标题可查找已导入论文"}
      </p>
      <ul id="quick-results" role="listbox" aria-label="快捷查找结果">
        {results.map((r, i) => (
          <li
            id={`quick-result-${i}`}
            key={`${r.paper ? "paper" : "task"}-${r.key}`}
            role="option"
            aria-selected={selected === i}
            onClick={() => choose(i)}
            onMouseMove={() => setActive(i)}
          >
            {r.paper ? <FileText size={19} /> : <ArrowUpRight size={19} />}
            <span>
              <strong>{r.title}</strong>
              <small>
                {r.paper ? "库内论文 · " : "功能 · "}
                {r.detail}
              </small>
            </span>
          </li>
        ))}
      </ul>
      {!results.length && (
        <div className="quick-empty">
          <strong>没有匹配的功能或库内论文</strong>
          <p>试试更短的关键词；寻找尚未导入的文章，请进入“论文发现”。</p>
          <button
            onClick={() => {
              onClose();
              onNavigate("discover");
            }}
          >
            前往论文发现 <ArrowUpRight size={16} />
          </button>
        </div>
      )}
      <footer>
        ↑ ↓ 选择 · Enter 打开 · Esc 关闭
        <span>仅匹配当前已加载的文献，不联网发送查询</span>
      </footer>
    </dialog>
  );
}
