import { useEffect, useRef, useState } from "react";
import { PageJump } from "./PageJump";
import { request, downloadText, type Anchor, type Job } from "./workspaceApi";
import "katex/dist/katex.min.css";

export function FormulaResult({
  identifier,
  content,
}: {
  identifier: string;
  content: Record<string, unknown>;
}) {
  const [latex, setLatex] = useState(String(content.latex || ""));
  const [html, setHtml] = useState("");
  const [message, setMessage] = useState("");
  const [warnings, setWarnings] = useState(
    (content.warnings as string[]) || [],
  );
  const source = content.source as Anchor;
  useEffect(() => {
    setLatex(String(content.latex || ""));
    setMessage("");
    setWarnings((content.warnings as string[]) || []);
  }, [identifier]);
  useEffect(() => {
    let active = true;
    import("katex").then((k) => {
      try {
        const output = k.default.renderToString(latex, {
          displayMode: true,
          throwOnError: true,
          trust: false,
          maxExpand: 500,
        });
        if (active) setHtml(output);
      } catch {
        if (active) setHtml("");
      }
    });
    return () => {
      active = false;
    };
  }, [latex]);
  return (
    <div className="formula-result">
      <p>{String(content.notice || "请逐项对照原图核对识别结果。")}</p>
      {source && (
        <img
          className="source-crop"
          alt="公式原始裁剪区域"
          src={`/api/documents/${source.document_id}/crop?page=${source.page}&x0=${source.bbox[0]}&y0=${source.bbox[1]}&x1=${source.bbox[2]}&y1=${source.bbox[3]}`}
        />
      )}
      {warnings.map((w, i) => (
        <p className="work-error" key={i}>
          {w}
        </p>
      ))}
      <label>
        LaTeX 候选（可修改）
        <textarea
          aria-label="公式 LaTeX"
          className="code-input"
          rows={4}
          value={latex}
          onChange={(e) => setLatex(e.target.value)}
        />
      </label>
      {html ? (
        <div
          className="formula-render"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <p>暂不能渲染，请检查 LaTeX 语法。</p>
      )}
      <p className="work-intro">
        能渲染不代表识别正确；尤其要检查括号、正负号、分子分母与上下标。
      </p>
      <div className="work-row">
        <button
          onClick={() => {
            void request<{ content: { warnings: string[] } }>(
              `/api/formulas/${identifier}`,
              { latex },
              "PATCH",
            )
              .then((result) => {
                setWarnings(result.content.warnings);
                setMessage("修改已保存，原始识别结果仍保留。");
              })
              .catch((e) => setMessage(e.message));
          }}
        >
          保存公式修改
        </button>
        <button onClick={() => downloadText("formula.tex", latex)}>
          下载 LaTeX
        </button>
      </div>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

export function FormulaPanel({
  identifier,
  pages,
}: {
  identifier: string;
  pages: number;
}) {
  const [page, setPage] = useState(1);
  const [info, setInfo] = useState<{
    regions: Anchor[];
    width: number;
    height: number;
    available: boolean;
  } | null>(null);
  const [box, setBox] = useState<number[] | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const start = useRef<number[] | null>(null);
  useEffect(() => {
    setPage(1);
    setInfo(null);
    setBox(null);
    setResult(null);
    setJob(null);
  }, [identifier]);
  useEffect(() => {
    let current = true;
    setInfo(null);
    setBox(null);
    setError("");
    if (identifier)
      request<typeof info>(
        `/api/documents/${identifier}/formula-regions?page=${page}`,
      )
        .then((r) => {
          if (current) setInfo(r);
        })
        .catch((e) => {
          if (current) setError(e.message);
        });
    return () => {
      current = false;
    };
  }, [identifier, page]);
  useEffect(() => {
    if (!job || !["queued", "running", "interrupted"].includes(job.state))
      return;
    let active = true;
    const timer = window.setInterval(() => {
      void request<Job>(`/api/jobs/${job.id}`)
        .then((r) => {
          if (active) {
            setJob(r);
            if (r.state === "completed") setResult(r.result || null);
            if (r.state === "failed") setError(r.error || "识别失败");
          }
        })
        .catch(() => {});
    }, 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.state]);
  async function recognize() {
    if (!box) return;
    setError("");
    setResult(null);
    try {
      setJob(
        await request<Job>("/api/jobs", {
          kind: "formula",
          payload: { document_id: identifier, page, bbox: box },
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const running =
    !!job && ["queued", "running", "interrupted"].includes(job.state);
  return (
    <div className="work-card">
      <h3>公式识别与校对</h3>
      <details className="extended-help">
        <summary>功能与用法</summary>
        <p>
          选页后可以点击自动检测到的候选，或在原图上拖动框选一条公式。扫描件也支持框选。离线识别生成
          LaTeX 候选；对照原图检查并修改后保存或下载。不要把整段文字一并框入。
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
          {!info.available && <p>本地公式组件尚未安装，当前可以查看原图。</p>}
          <div className="work-row">
            {info.regions.map((r, i) => (
              <button key={i} onClick={() => setBox(r.bbox)}>
                公式候选 {i + 1}
              </button>
            ))}
          </div>
          <details open={!!box || !info.regions.length}>
            <summary>原图框选（单条公式）</summary>
            <div
              className="formula-select"
              onPointerDown={(e) => {
                if (e.button !== 0) return;
                const r = e.currentTarget.getBoundingClientRect();
                start.current = [
                  Math.max(0, ((e.clientX - r.left) / r.width) * info.width),
                  Math.max(0, ((e.clientY - r.top) / r.height) * info.height),
                ];
                e.currentTarget.setPointerCapture(e.pointerId);
                setBox(null);
              }}
              onPointerMove={(e) => {
                if (!start.current) return;
                const r = e.currentTarget.getBoundingClientRect();
                const x = Math.min(
                  info.width,
                  Math.max(0, ((e.clientX - r.left) / r.width) * info.width),
                );
                const y = Math.min(
                  info.height,
                  Math.max(0, ((e.clientY - r.top) / r.height) * info.height),
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
                alt={`第 ${page} 页公式框选原图`}
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
            disabled={!box || !info.available || running}
            onClick={() => void recognize()}
          >
            {running ? job?.message : "识别所选公式"}
          </button>
        </>
      )}
      {error && (
        <p className="work-error" role="alert">
          {error}
        </p>
      )}
      {result && (
        <FormulaResult identifier={String(result.id)} content={result} />
      )}
    </div>
  );
}
