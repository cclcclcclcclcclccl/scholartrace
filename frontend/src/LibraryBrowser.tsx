import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Download, Search, Settings2, RotateCcw } from "lucide-react";
import { downloadText, request, type Paper } from "./workspaceApi";
import "./library.css";

type Organization = {
  tags: string[];
  collection: string;
  reading_status: string;
};
type OrganizedPaper = Paper & Organization;
type Change = { id: string; previous: Organization; value: Organization };
const statuses: Record<string, string> = {
  unread: "待读",
  reading: "在读",
  read: "已读",
  reproduce: "待复现",
};
const organization = (p: OrganizedPaper): Organization => ({
  tags: [...p.tags],
  collection: p.collection,
  reading_status: p.reading_status,
});

export function LibraryBrowser({
  papers,
  onRead,
  onManage,
  onCompare,
  onChanged,
  revision,
}: {
  papers: Paper[];
  onRead: (id: string) => void;
  onManage: (id: string) => void;
  onCompare: (ids: string[]) => void;
  onChanged: () => void;
  revision: number;
}) {
  const [rows, setRows] = useState<OrganizedPaper[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [collection, setCollection] = useState("");
  const [tag, setTag] = useState("");
  const [sort, setSort] = useState("title");
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [batchStatus, setBatchStatus] = useState("");
  const [changeCollection, setChangeCollection] = useState(false);
  const [batchCollection, setBatchCollection] = useState("");
  const [batchTags, setBatchTags] = useState("");
  const [undo, setUndo] = useState<Change[]>([]);
  const [reload, setReload] = useState(0);
  const allCheckbox = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let current = true;
    setLoading(true);
    setError("");
    request<OrganizedPaper[]>("/api/library/organization")
      .then((value) => {
        if (!current) return;
        setRows(value);
        setSelected((ids) =>
          ids.filter((id) => value.some((p) => p.id === id)),
        );
      })
      .catch((e) => {
        if (current) setError(String(e));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [papers, revision, reload]);
  const collections = [
    ...new Set(rows.map((p) => p.collection).filter(Boolean)),
  ].sort();
  const tags = [...new Set(rows.flatMap((p) => p.tags))].sort();
  const visible = useMemo(
    () =>
      rows
        .filter(
          (p) =>
            (!query.trim() ||
              `${p.title} ${p.name} ${p.arxiv_id || ""} ${(p.aliases || []).join(" ")} ${p.collection} ${p.tags.join(" ")}`
                .toLocaleLowerCase()
                .includes(query.trim().toLocaleLowerCase())) &&
            (!status || p.reading_status === status) &&
            (!collection ||
              (collection === "__none__"
                ? !p.collection
                : p.collection === collection)) &&
            (!tag || p.tags.includes(tag)),
        )
        .sort((a, b) =>
          sort === "pages"
            ? b.pages - a.pages || a.title.localeCompare(b.title)
            : sort === "version"
              ? (b.version || 0) - (a.version || 0) ||
                a.title.localeCompare(b.title)
              : a.title.localeCompare(b.title),
        ),
    [rows, query, status, collection, tag, sort],
  );
  const visibleIds = visible.map((p) => p.id);
  const selectedVisible = visibleIds.filter((id) =>
    selected.includes(id),
  ).length;
  useEffect(() => {
    if (allCheckbox.current)
      allCheckbox.current.indeterminate =
        selectedVisible > 0 && selectedVisible < visible.length;
  }, [selectedVisible, visible.length]);
  const hiddenCount = selected.filter((id) => !visibleIds.includes(id)).length;

  async function save(revert = false) {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const additions = batchTags
        .split(/[,，;；\n]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const items = revert
        ? undo.map((c) => ({ id: c.id, expected: c.value, value: c.previous }))
        : rows
            .filter((p) => selected.includes(p.id))
            .map((p) => ({
              id: p.id,
              expected: organization(p),
              value: {
                tags: [...new Set([...p.tags, ...additions])],
                collection: changeCollection
                  ? batchCollection.trim()
                  : p.collection,
                reading_status: batchStatus || p.reading_status,
              },
            }));
      const response = await request<{ updated: number; changes: Change[] }>(
        "/api/library/organization/batch",
        { items },
        "PATCH",
      );
      setRows((old) =>
        old.map((p) => {
          const change = response.changes.find((c) => c.id === p.id);
          return change ? { ...p, ...change.value } : p;
        }),
      );
      setUndo(revert ? [] : response.changes);
      setNotice(
        revert
          ? `已撤销 ${response.updated} 篇文献的上次批量修改。`
          : `已更新 ${response.updated} 篇文献。可撤销本次修改。`,
      );
      setBatchStatus("");
      setChangeCollection(false);
      setBatchCollection("");
      setBatchTags("");
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }
  function exportSelection() {
    const exported = rows
      .filter((p) => selected.includes(p.id))
      .map((p) => ({
        id: p.id,
        title: p.title,
        filename: p.name,
        arxiv_id: p.arxiv_id,
        version: p.version,
        pages: p.pages,
        ...organization(p),
      }));
    downloadText(
      "墨衡-文献清单.json",
      JSON.stringify(
        { exported_at: new Date().toISOString(), papers: exported },
        null,
        2,
      ),
      "application/json",
    );
    setNotice(
      `已导出 ${exported.length} 篇文献的信息清单（不含 PDF 和笔记）。`,
    );
  }
  return (
    <section
      className="library-browser"
      aria-label="文献库列表"
      aria-busy={loading || saving}
    >
      <div className="library-overview">
        <div>
          <strong>{rows.length}</strong>
          <span>篇文献</span>
        </div>
        {Object.entries(statuses).map(([key, label]) => (
          <button
            key={key}
            aria-pressed={status === key}
            onClick={() => setStatus(status === key ? "" : key)}
          >
            {label}
            <strong>
              {rows.filter((p) => p.reading_status === key).length}
            </strong>
          </button>
        ))}
      </div>
      <div className="library-filters">
        <label className="library-query">
          <span>
            <Search size={15} /> 搜索文献
          </span>
          <input
            aria-label="搜索文献库"
            placeholder="标题、文件名、arXiv 编号、别名或标签"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          分类
          <select
            aria-label="筛选文献分类"
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
          >
            <option value="">所有分类</option>
            <option value="__none__">未分类</option>
            {collections.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          标签
          <select
            aria-label="筛选文献标签"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
          >
            <option value="">所有标签</option>
            {tags.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          排序
          <select
            aria-label="文献排序"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="title">标题 A—Z</option>
            <option value="pages">页数从多到少</option>
            <option value="version">版本号从高到低</option>
          </select>
        </label>
      </div>
      <div className="library-list-status">
        <p aria-live="polite">
          {loading
            ? "正在加载文献…"
            : `显示 ${visible.length} / ${rows.length} 篇`}
          {status && ` · ${statuses[status]}`}
        </p>
        <div>
          {(query || status || collection || tag) && (
            <button
              onClick={() => {
                setQuery("");
                setStatus("");
                setCollection("");
                setTag("");
              }}
            >
              清除筛选
            </button>
          )}
          <button
            disabled={saving || loading}
            onClick={() => setReload((n) => n + 1)}
          >
            刷新列表
          </button>
        </div>
      </div>
      {error && (
        <div className="work-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p className="library-feedback" role="status">
          {notice}
        </p>
      )}
      {!!undo.length && (
        <button
          className="library-undo"
          disabled={saving || loading}
          onClick={() => void save(true)}
        >
          <RotateCcw size={14} />
          撤销上次批量修改（{undo.length} 篇）
        </button>
      )}
      {!!selected.length && (
        <div className="library-batch">
          <div className="library-batch-title">
            <strong>已选 {selected.length} 篇</strong>
            {hiddenCount > 0 && (
              <span role="status">含 {hiddenCount} 篇不在当前筛选结果中</span>
            )}
            <button disabled={saving} onClick={() => setSelected([])}>
              取消选择
            </button>
            <button disabled={saving || loading} onClick={exportSelection}>
              <Download size={14} />
              导出所选清单
            </button>
          </div>
          <button
            disabled={
              saving || loading || selected.length < 2 || selected.length > 40
            }
            onClick={() => onCompare(selected)}
          >
            对所选文献提问（2—40 篇）
          </button>
          <fieldset
            disabled={saving || loading}
            className="library-batch-fields"
          >
            <legend>批量整理所选文献</legend>
            <label>
              阅读状态
              <select
                aria-label="批量阅读状态"
                value={batchStatus}
                onChange={(e) => setBatchStatus(e.target.value)}
              >
                <option value="">保持原状态</option>
                {Object.entries(statuses).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <label className="library-check">
                <input
                  type="checkbox"
                  checked={changeCollection}
                  onChange={(e) => setChangeCollection(e.target.checked)}
                />
                修改分类
              </label>
              <input
                aria-label="批量文献分类"
                disabled={!changeCollection}
                value={batchCollection}
                maxLength={100}
                onChange={(e) => setBatchCollection(e.target.value)}
                placeholder="留空则移至未分类"
                list="library-collections"
              />
              <datalist id="library-collections">
                {collections.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>
            <label>
              追加标签
              <input
                aria-label="批量追加标签"
                value={batchTags}
                onChange={(e) => setBatchTags(e.target.value)}
                placeholder="用逗号分隔，保留已有标签"
              />
            </label>
            <button
              className="primary-button"
              disabled={!batchStatus && !changeCollection && !batchTags.trim()}
              onClick={() => void save()}
            >
              应用到 {selected.length} 篇
            </button>
          </fieldset>
        </div>
      )}
      <div
        className="library-table-scroll"
        tabIndex={0}
        aria-label="文献表格，可横向滚动"
      >
        <table className="library-table">
          <thead>
            <tr>
              <th>
                <input
                  ref={allCheckbox}
                  type="checkbox"
                  aria-label="选择当前筛选结果"
                  checked={
                    visible.length > 0 && selectedVisible === visible.length
                  }
                  disabled={loading || saving || !visible.length}
                  onChange={(e) =>
                    setSelected((old) =>
                      e.target.checked
                        ? [...new Set([...old, ...visibleIds])]
                        : old.filter((id) => !visibleIds.includes(id)),
                    )
                  }
                />
              </th>
              <th>文献 · 版本与来源</th>
              <th>阅读状态</th>
              <th>分类与标签</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((p) => (
              <tr
                key={p.id}
                data-document-id={p.id}
                className={selected.includes(p.id) ? "is-selected" : ""}
              >
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择 ${p.title} ${p.name}`}
                    checked={selected.includes(p.id)}
                    disabled={loading || saving}
                    onChange={(e) =>
                      setSelected((old) =>
                        e.target.checked
                          ? [...old, p.id]
                          : old.filter((id) => id !== p.id),
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    className="library-paper-title"
                    onClick={() => onRead(p.id)}
                  >
                    {p.title}
                  </button>
                  <div className="library-paper-meta">
                    <span>
                      {p.version ? `v${p.version} · ` : ""}
                      {p.pages} 页
                    </span>
                    <span>{p.arxiv_id ? `arXiv:${p.arxiv_id}` : p.name}</span>
                    {p.status === "needs_ocr" && (
                      <span className="library-warning">待 OCR</span>
                    )}
                    {p.status === "ocr_ready" && <span>扫描件</span>}
                    {p.status === "partial_ocr" && <span>部分页需核对</span>}
                  </div>
                </td>
                <td>
                  <span className={`reading-badge status-${p.reading_status}`}>
                    {statuses[p.reading_status] || p.reading_status}
                  </span>
                </td>
                <td>
                  <span>{p.collection || "未分类"}</span>
                  <div className="library-tags">
                    {p.tags.map((t) => (
                      <span key={t}>{t}</span>
                    ))}
                  </div>
                </td>
                <td>
                  <div className="library-row-actions">
                    <button
                      onClick={() => onRead(p.id)}
                      aria-label={`阅读 ${p.title} ${p.name}`}
                    >
                      <BookOpen size={14} />
                      阅读
                    </button>
                    <button
                      onClick={() => onManage(p.id)}
                      aria-label={`管理 ${p.title} ${p.name}`}
                    >
                      <Settings2 size={14} />
                      详情
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!loading && !visible.length && (
        <div className="work-empty">
          {rows.length
            ? "没有符合条件的文献，试试清除筛选。"
            : "还没有文献。点击顶部「导入文献」，可以一次选择多份 PDF。"}
        </div>
      )}
    </section>
  );
}
