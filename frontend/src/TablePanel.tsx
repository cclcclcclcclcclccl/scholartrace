import { useEffect, useRef, useState } from "react";
import { PageJump } from "./PageJump";
import { request, type Anchor, type Job } from "./workspaceApi";

type Cell = {
  text: string;
  bbox: number[];
  confidence: number | null;
  spans_columns: boolean;
};
export type TableContent = {
  rows: string[][];
  original_rows: string[][];
  cells: Cell[][] | null;
  source: Anchor;
  column_bounds: number[];
  revision: number;
  method: string;
  notice: string;
};

export function TableResult({
  identifier,
  content,
}: {
  identifier: string;
  content: TableContent;
}) {
  const [value, setValue] = useState(content);
  const [rows, setRows] = useState(content.rows);
  const [lines, setLines] = useState("");
  const [focus, setFocus] = useState<Cell | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  function load(next: TableContent) {
    setValue(next);
    setRows(next.rows);
    setFocus(null);
    setDirty(false);
    const [x0, , x1] = next.source.bbox;
    setLines(
      next.column_bounds
        .map((x) => (((x - x0) / (x1 - x0)) * 100).toFixed(2))
        .join(", "),
    );
  }
  useEffect(() => {
    load(content);
    setMessage("");
    setError("");
  }, [identifier]);
  function change(next: string[][]) {
    setRows(next);
    setDirty(true);
    setMessage("");
    setFocus(null);
  }
  async function save(regrid = false) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const [x0, , x1] = value.source.bbox;
      const percents = lines.trim()
        ? lines.split(/[,，]/).map((x) => Number(x.trim()))
        : [];
      if (
        regrid &&
        percents.some((p) => !Number.isFinite(p) || p <= 0 || p >= 100)
      )
        throw Error("分列位置请输入 0 到 100 之间的百分比，用逗号分隔。");
      const body = regrid
        ? { column_bounds: percents.map((p) => x0 + (p / 100) * (x1 - x0)) }
        : { rows };
      const result = await request<{ content: TableContent }>(
        `/api/tables/${identifier}`,
        { ...body, revision: value.revision },
        "PATCH",
      );
      load(result.content);
      setMessage(
        regrid
          ? "已按新分列线重新排列，之前的单元格保留在历史中。"
          : "表格修改已保存，初次提取与修改历史仍保留。",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const source = value.source;
  const [x0, y0, x1, y1] = source.bbox;
  return (
    <div className="table-result">
      <p>{value.notice}</p>
      <div className="table-proof">
        <div>
          <h4>原始表格 · PDF 第 {source.page} 页</h4>
          <div className="table-source">
            <img
              alt="表格原始裁剪区域"
              src={`/api/documents/${source.document_id}/crop?page=${source.page}&x0=${x0}&y0=${y0}&x1=${x1}&y1=${y1}`}
            />
            {focus && (
              <span
                className="table-cell-highlight"
                style={{
                  left: ((focus.bbox[0] - x0) / (x1 - x0)) * 100 + "%",
                  top: ((focus.bbox[1] - y0) / (y1 - y0)) * 100 + "%",
                  width:
                    ((focus.bbox[2] - focus.bbox[0]) / (x1 - x0)) * 100 + "%",
                  height:
                    ((focus.bbox[3] - focus.bbox[1]) / (y1 - y0)) * 100 + "%",
                }}
              />
            )}
          </div>
          {focus && (
            <p role="status">
              {focus.confidence === null
                ? "来自 PDF 原始文字"
                : `OCR 文字置信度 ${(focus.confidence * 100).toFixed(1)}%（不代表单元格正确率）`}
              {focus.spans_columns ? "；文字跨过分列线，需核对合并表头。" : ""}
            </p>
          )}
        </div>
        <div>
          <h4>
            可编辑数据 · {rows.length} 行 × {rows[0]?.length || 0} 列
          </h4>
          <p className="work-intro">
            点击单元格核对位置。原图为空的单元格请保持空白，多层表头按原来的行保留。
          </p>
          <div className="table-scroll table-editor">
            <table aria-label="表格校对数据">
              <thead>
                <tr>
                  <th>行</th>
                  {rows[0]?.map((_, c) => (
                    <th key={c}>列 {c + 1}</th>
                  ))}
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, r) => (
                  <tr key={r}>
                    <th>{r + 1}</th>
                    {row.map((cell, c) => (
                      <td
                        key={c}
                        className={
                          value.cells?.[r]?.[c]?.spans_columns
                            ? "needs-check"
                            : ""
                        }
                      >
                        <textarea
                          aria-label={`第 ${r + 1} 行第 ${c + 1} 列`}
                          rows={Math.min(
                            5,
                            Math.max(1, Math.ceil(cell.length / 20)),
                          )}
                          disabled={busy}
                          value={cell}
                          onFocus={() =>
                            !dirty && setFocus(value.cells?.[r]?.[c] || null)
                          }
                          onChange={(e) =>
                            change(
                              rows.map((rr, i) =>
                                i === r
                                  ? rr.map((cc, j) =>
                                      j === c ? e.target.value : cc,
                                    )
                                  : rr,
                              ),
                            )
                          }
                        />
                      </td>
                    ))}
                    <td>
                      <button
                        aria-label={`删除第 ${r + 1} 行`}
                        disabled={rows.length === 1 || busy}
                        onClick={() => change(rows.filter((_, i) => i !== r))}
                      >
                        删行
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="work-row">
            <button
              disabled={busy || rows.length >= 200}
              onClick={() => change([...rows, rows[0].map(() => "")])}
            >
              添加行
            </button>
            <button
              disabled={busy || rows[0].length >= 32}
              onClick={() => change(rows.map((r) => [...r, ""]))}
            >
              添加列
            </button>
            <button
              disabled={busy || rows[0].length <= 1}
              onClick={() => change(rows.map((r) => r.slice(0, -1)))}
            >
              删除末列
            </button>
            <button
              disabled={busy || !dirty}
              className="primary-button"
              onClick={() => void save()}
            >
              保存表格修改
            </button>
          </div>
        </div>
      </div>
      <details className="extended-help">
        <summary>调整分列与查看初次提取</summary>
        <p>
          错列时可修改竖向分列线的位置，以裁剪表格宽度的百分比表示，例如 40, 70
          分成三列。留空合成一列。重新分列使用原始文字框，请先保存单元格修改。
        </p>
        <label>
          分列位置（%）
          <input
            aria-label="表格分列位置"
            value={lines}
            onChange={(e) => setLines(e.target.value)}
          />
        </label>
        <button disabled={busy || dirty} onClick={() => void save(true)}>
          按分列线重新排列
        </button>
        <pre>{value.original_rows.map((r) => r.join(" | ")).join("\n")}</pre>
      </details>
      <div className="work-row">
        {!dirty && <a href={`/api/tables/${identifier}/export`}>下载 CSV</a>}
        <a href={`/api/artifacts/${identifier}/export?format=json`}>
          下载原图坐标与修改历史
        </a>
        <span>
          {dirty
            ? "有未保存的修改，请保存后下载 CSV。"
            : `已保存 · 修订 ${value.revision}`}
        </span>
      </div>
      {message && <p role="status">{message}</p>}
      {error && (
        <p className="work-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function TablePanel({
  identifier,
  pages,
}: {
  identifier: string;
  pages: number;
}) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [info, setInfo] = useState<{
    regions: Anchor[];
    width: number;
    height: number;
  } | null>(null);
  const [box, setBox] = useState<number[] | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<(TableContent & { id: string }) | null>(
    null,
  );
  const [error, setError] = useState("");
  const start = useRef<number[] | null>(null);
  useEffect(() => {
    let active = true;
    setInfo(null);
    setBox(null);
    setError("");
    if (open)
      void request<typeof info>(
        `/api/documents/${identifier}/table-regions?page=${page}`,
      )
        .then((v) => {
          if (active) setInfo(v);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [identifier, page, open]);
  useEffect(() => {
    if (!job || !["queued", "running", "interrupted"].includes(job.state))
      return;
    let active = true;
    const timer = window.setInterval(() => {
      void request<Job>(`/api/jobs/${job.id}`)
        .then((v) => {
          if (!active) return;
          setJob(v);
          if (v.state === "completed")
            setResult(v.result as unknown as TableContent & { id: string });
          if (v.state === "failed") setError(v.error || "表格提取失败");
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 1200);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.state]);
  const running =
    !!job && ["queued", "running", "interrupted"].includes(job.state);
  async function extract() {
    setError("");
    setResult(null);
    try {
      setJob(
        await request<Job>("/api/jobs", {
          kind: "table",
          payload: { document_id: identifier, page, bbox: box },
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <details
      className="work-card table-panel"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        <strong>表格提取与校对</strong>
        <span>原生 PDF / 扫描件 · CSV 导出</span>
      </summary>
      <details className="extended-help">
        <summary>功能与用法</summary>
        <p>
          选择页码，点击表格候选；未检测到的表格可在原图上拖动框选。提取后逐格对照、修改并保存，可调整分列、添加行列、下载
          CSV。合并单元格、数学符号与跨页表格需人工校对；跨页表格请分次提取。保存结果也可从“任务与成果”打开。
        </p>
      </details>
      <PageJump
        page={page}
        total={pages}
        documentId={identifier}
        onJump={setPage}
      />
      {info && (
        <>
          <div className="work-row">
            {info.regions.map((r, i) => (
              <button key={i} disabled={running} onClick={() => setBox(r.bbox)}>
                表格候选 {i + 1}
              </button>
            ))}
            {!info.regions.length && (
              <p>这一页未自动找到表格，请展开原图框选。</p>
            )}
          </div>
          <details open={!!box || !info.regions.length}>
            <summary>原图框选表格</summary>
            <div
              className="formula-select table-select"
              onPointerDown={(e) => {
                if (running) return;
                e.currentTarget.setPointerCapture(e.pointerId);
                const r = e.currentTarget.getBoundingClientRect();
                start.current = [
                  ((e.clientX - r.left) / r.width) * info.width,
                  ((e.clientY - r.top) / r.height) * info.height,
                ];
                setBox(null);
              }}
              onPointerMove={(e) => {
                if (!start.current) return;
                const r = e.currentTarget.getBoundingClientRect();
                const x = Math.max(
                  0,
                  Math.min(
                    info.width,
                    ((e.clientX - r.left) / r.width) * info.width,
                  ),
                );
                const y = Math.max(
                  0,
                  Math.min(
                    info.height,
                    ((e.clientY - r.top) / r.height) * info.height,
                  ),
                );
                setBox([
                  Math.min(x, start.current[0]),
                  Math.min(y, start.current[1]),
                  Math.max(x, start.current[0]),
                  Math.max(y, start.current[1]),
                ]);
              }}
              onPointerUp={() => {
                start.current = null;
              }}
              onPointerCancel={() => {
                start.current = null;
              }}
            >
              <img
                draggable={false}
                alt={`第 ${page} 页表格框选原图`}
                src={`/api/documents/${identifier}/crop?page=${page}`}
              />
              {box && (
                <span
                  className="formula-selection"
                  style={{
                    left: (box[0] / info.width) * 100 + "%",
                    top: (box[1] / info.height) * 100 + "%",
                    width: ((box[2] - box[0]) / info.width) * 100 + "%",
                    height: ((box[3] - box[1]) / info.height) * 100 + "%",
                  }}
                />
              )}
            </div>
          </details>
          <button
            className="primary-button"
            disabled={running || !box}
            onClick={() => void extract()}
          >
            {running ? job?.message : "提取所选表格"}
          </button>
        </>
      )}
      {error && (
        <p className="work-error" role="alert">
          {error}
        </p>
      )}
      {result && (
        <TableResult key={result.id} identifier={result.id} content={result} />
      )}
    </details>
  );
}
