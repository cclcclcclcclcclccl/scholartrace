import { useEffect, useRef, useState } from "react";
import { List, LoaderCircle, Minus, Plus, RotateCcw } from "lucide-react";
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "./text-layer.css";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
type Source = {
  document_id: string;
  page: number;
  bbox: number[];
  width: number;
  height: number;
};
type Outline = [number, string, number][];
export function Reader({
  document,
  page,
  highlight,
  onPage,
  reloadKey,
}: {
  document: { id: string; pages: number; status: string };
  page: number;
  highlight: Source | null;
  onPage: (page: number) => void;
  reloadKey: number;
}) {
  const container = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const textLayer = useRef<HTMLDivElement>(null);
  const marker = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [width, setWidth] = useState(680);
  const [zoom, setZoom] = useState(1);
  const [dimensions, setDimensions] = useState({ width: 680, height: 880 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [outline, setOutline] = useState<Outline>([]);
  const [outlineOpen, setOutlineOpen] = useState(false);
  const [outlineError, setOutlineError] = useState(false);
  const [outlineReady, setOutlineReady] = useState(false);
  const [outlineFilter, setOutlineFilter] = useState("");

  useEffect(() => {
    const node = container.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(200, Math.min(900, entry.contentRect.width - 44))),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    setZoom(1);
    setOutlineOpen(false);
    setOutlineFilter("");
  }, [document.id]);
  useEffect(() => {
    const controller = new AbortController();
    setOutline([]);
    setOutlineError(false);
    setOutlineReady(false);
    fetch(`/api/documents/${document.id}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw Error("目录暂时无法加载");
        return response.json();
      })
      .then((data) => {
        if (!controller.signal.aborted) {
          setOutline(data.metadata?.outline || []);
          setOutlineReady(true);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setOutlineError(true);
          setOutlineReady(true);
        }
      });
    return () => controller.abort();
  }, [document.id, reloadKey, retry]);
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
      .catch(() => {
        if (!cancelled) {
          setError("原文暂时无法加载，请检查本地服务后重试。");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [document.id, retry, reloadKey]);
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    let task: pdfjs.RenderTask | undefined;
    let textTask: pdfjs.TextLayer | undefined;
    setLoading(true);
    setError("");
    textLayer.current?.replaceChildren();
    pdf
      .getPage(page)
      .then(async (pdfPage) => {
        if (cancelled || !canvas.current || !textLayer.current) return;
        const base = pdfPage.getViewport({ scale: 1 });
        const viewport = pdfPage.getViewport({
          scale: (width * zoom) / base.width,
        });
        const ratio = window.devicePixelRatio || 1;
        canvas.current.width = Math.ceil(viewport.width * ratio);
        canvas.current.height = Math.ceil(viewport.height * ratio);
        setDimensions({ width: viewport.width, height: viewport.height });
        textLayer.current.style.setProperty(
          "--scale-factor",
          String(viewport.scale),
        );
        textLayer.current.style.setProperty(
          "--total-scale-factor",
          String(viewport.scale),
        );
        task = pdfPage.render({
          canvas: canvas.current,
          viewport,
          transform: [ratio, 0, 0, ratio, 0, 0],
        });
        // Cancellation may arrive before getTextContent resolves.
        void task.promise.catch(() => {});
        const text = await pdfPage.getTextContent();
        if (cancelled) return;
        textTask = new pdfjs.TextLayer({
          textContentSource: text,
          container: textLayer.current,
          viewport,
        });
        await Promise.all([task.promise, textTask.render()]);
        if (!cancelled) setLoading(false);
      })
      .catch((e) => {
        if (!cancelled && e?.name !== "RenderingCancelledException") {
          setError("这一页加载失败，请重试。");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      task?.cancel();
      textTask?.cancel();
    };
  }, [pdf, page, width, zoom]);
  useEffect(() => {
    if (loading) return;
    const frame = requestAnimationFrame(() => {
      const stage = container.current;
      if (!stage) return;
      if (marker.current) {
        const target = marker.current.getBoundingClientRect();
        const bounds = stage.getBoundingClientRect();
        stage.scrollTo({
          top:
            stage.scrollTop +
            target.top -
            bounds.top -
            Math.max(35, (stage.clientHeight - target.height) / 2),
          left:
            stage.scrollLeft +
            target.left -
            bounds.left -
            Math.max(20, (stage.clientWidth - target.width) / 2),
          behavior: "instant",
        });
      } else stage.scrollTo({ top: 0, left: 0 });
    });
    return () => cancelAnimationFrame(frame);
  }, [loading, page, highlight, dimensions]);
  const entries = outline.filter(([, title]) =>
    title.toLowerCase().includes(outlineFilter.toLowerCase()),
  );
  return (
    <>
      <div className="reading-tools">
        <button
          className={outlineOpen ? "active" : ""}
          aria-expanded={outlineOpen}
          onClick={() => setOutlineOpen((v) => !v)}
        >
          <List size={15} />
          论文目录
        </button>
        <span className="reading-hint">
          {document.status === "ocr_ready"
            ? "扫描原文 · 证据支持定位"
            : "原文文字可选择、复制"}
        </span>
        <div className="zoom-tools">
          <button
            aria-label="缩小原文"
            disabled={zoom <= 0.75}
            onClick={() => setZoom((v) => Math.max(0.75, v - 0.25))}
          >
            <Minus size={14} />
          </button>
          <button
            title="恢复适合宽度"
            aria-label="适合宽度"
            onClick={() => setZoom(1)}
          >
            {Math.round(zoom * 100)}%<RotateCcw size={12} />
          </button>
          <button
            aria-label="放大原文"
            disabled={zoom >= 2}
            onClick={() => setZoom((v) => Math.min(2, v + 0.25))}
          >
            <Plus size={14} />
          </button>
        </div>
      </div>
      {outlineOpen && (
        <nav className="paper-outline" aria-label="论文目录">
          {!!outline.length && (
            <input
              aria-label="搜索论文章节"
              placeholder="搜索章节标题"
              value={outlineFilter}
              onChange={(e) => setOutlineFilter(e.target.value)}
            />
          )}
          {!outlineReady ? (
            <p>正在读取目录…</p>
          ) : outlineError ? (
            <p>
              目录加载失败。
              <button onClick={() => setRetry((v) => v + 1)}>重试</button>
            </p>
          ) : !outline.length ? (
            <p>这份 PDF 没有内嵌目录，可使用页码跳转。</p>
          ) : !entries.length ? (
            <p>没有匹配的章节。</p>
          ) : (
            entries.map(([level, title, target], index) => (
              <button
                key={index}
                disabled={target < 1 || target > document.pages}
                style={{ paddingLeft: 12 + Math.min(level - 1, 4) * 14 }}
                className={target === page ? "current" : ""}
                onClick={() => {
                  onPage(target);
                  setOutlineOpen(false);
                }}
              >
                <span>{title}</span>
                <small>{target > 0 ? target : "—"}</small>
              </button>
            ))
          )}
        </nav>
      )}
      <div className="paper-stage" ref={container} aria-busy={loading}>
        {loading && (
          <div className="reader-state">
            <LoaderCircle className="spin" size={17} />
            正在呈现原文
          </div>
        )}
        {error && (
          <div className="error-message" role="alert">
            {error}
            <button
              className="text-button"
              onClick={() => setRetry((v) => v + 1)}
            >
              重新加载
            </button>
          </div>
        )}
        <div className="paper-sheet" style={dimensions}>
          <canvas ref={canvas} style={dimensions} />
          <div className="textLayer" ref={textLayer} />
          {!loading &&
            highlight?.document_id === document.id &&
            highlight.page === page && (
              <div
                ref={marker}
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
    </>
  );
}
