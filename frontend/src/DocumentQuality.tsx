import { useEffect, useRef, useState } from "react";
import { downloadText, type Anchor, type Job } from "./workspaceApi";

export type Quality = {
  document_id: string;
  text_pages: number;
  attention_pages: number[];
  retry_pages: number[];
  notice: string;
  pages: {
    page: number;
    state: "native" | "ocr" | "mixed" | "review" | "pending" | "unrecognized";
    native_chars: number;
    ocr_chars: number;
    confidence: number | null;
    ocr_warning?: string | null;
    duplicates_skipped?: number;
    width: number;
    height: number;
  }[];
};
const labels = {
  native: "原生文字",
  ocr: "OCR 文字",
  mixed: "原生 + OCR 补充",
  review: "文字需核对",
  pending: "待识别 / 文字稀少",
  unrecognized: "未识别到文字",
};

export function DocumentQuality({
  identifier,
  onLocate,
  onOcr,
  onRefresh,
}: {
  identifier: string;
  onLocate: (anchor: Anchor) => void;
  onOcr: (page: number) => Promise<Job>;
  onRefresh: () => Promise<void>;
}) {
  const [report, setReport] = useState<Quality | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  async function recognize(page: number) {
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const next = await onOcr(page);
      if (mounted.current) setJob(next);
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  }
  useEffect(() => {
    if (!job) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const response = await fetch(`/api/jobs/${job!.id}`, {
          signal: AbortSignal.any([
            controller.signal,
            AbortSignal.timeout(15000),
          ]),
        });
        if (!response.ok)
          throw new Error(
            "进度读取失败；任务可能仍在执行，请到任务与成果查看。",
          );
        const current = (await response.json()) as Job;
        if (controller.signal.aborted) return;
        if (
          ["completed", "failed", "cancelled", "interrupted"].includes(
            current.state,
          )
        ) {
          setJob(null);
          setRevision((n) => n + 1);
          if (current.state === "completed") {
            const pages = (current.result?.pages || []) as {
              preserved?: boolean;
              added_lines?: number;
              lines?: number;
              duplicates_skipped?: number;
            }[];
            const added = pages.reduce(
              (sum, p) => sum + (p.added_lines ?? p.lines ?? 0),
              0,
            );
            const skipped = pages.reduce(
              (sum, p) => sum + (p.duplicates_skipped || 0),
              0,
            );
            setMessage(
              pages.some((p) => p.preserved)
                ? "已有 OCR 引文已保留，没有覆盖。"
                : `本页识别结束：新增 ${added} 行，跳过 ${skipped} 行重复文字。请核对原图；语义索引会继续在后台更新。`,
            );
          } else
            setMessage(
              current.error ||
                "任务已停止或中断，已识别内容保留，可到任务与成果查看或重试。",
            );
          void onRefresh().catch(() => {
            if (mounted.current) setError("文献列表刷新失败，请稍后重试。");
          });
        } else {
          setMessage(`本页识别中：${current.message || "等待执行"}`);
          timer = setTimeout(poll, 1500);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setJob(null);
          setMessage(
            (e as Error).message + " 可到任务与成果查看，勿重复提交。",
          );
        }
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [job?.id]);
  useEffect(() => {
    const controller = new AbortController();
    setReport(null);
    setError("");
    if (identifier) {
      void fetch(`/api/documents/${identifier}/text-quality`, {
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok)
            throw new Error("读取文字覆盖情况失败，请刷新重试。");
          return response.json() as Promise<Quality>;
        })
        .then((value) => {
          if (!controller.signal.aborted) setReport(value);
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError((e as Error).message);
        });
    }
    return () => controller.abort();
  }, [identifier, revision]);
  if (!identifier) return null;
  return (
    <section className="document-quality" aria-label="逐页文字覆盖检查">
      <div className="work-row">
        <h3>逐页文字覆盖检查</h3>
        <button onClick={() => setRevision((n) => n + 1)}>刷新文字检查</button>
        {report && (
          <button
            onClick={() =>
              downloadText(
                "document-text-quality.json",
                JSON.stringify(report, null, 2),
                "application/json",
              )
            }
          >
            导出文字检查
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {submitting && <p role="status">正在提交本页识别…</p>}
      {!report && !error && <p role="status">正在读取页面文字情况…</p>}
      {report && (
        <>
          <p>
            有文字 {report.text_pages} / {report.pages.length} 页 · 需核对{" "}
            {report.attention_pages.length} 页
          </p>
          <p className="muted">{report.notice}</p>
          <p>
            如果页面只有标题或图注能被选中，而正文是图片，请显示全部页面，再对该页补充识别。已有原生文字和引文会保留。
          </p>
          {report.retry_pages.length > 0 && (
            <p>
              点击下方“识别扫描文字”处理缺字页，任务结束后刷新检查。已经保存的
              OCR 引文会保留，不会被重跑覆盖。
            </p>
          )}
          <label>
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => setShowAll(e.target.checked)}
            />
            显示全部页面
          </label>
          <div className="quality-pages">
            {report.pages
              .filter((p) => showAll || report.attention_pages.includes(p.page))
              .map((p) => (
                <div className="quality-page" key={p.page}>
                  <span>
                    第 {p.page} 页 · {labels[p.state]} ·{" "}
                    {p.native_chars + p.ocr_chars} 字符
                  </span>
                  {p.confidence !== null && (
                    <small>
                      OCR 平均置信度 {p.confidence.toFixed(2)}（非正确率）
                    </small>
                  )}
                  {p.ocr_warning && <small>{p.ocr_warning}</small>}
                  {!!p.duplicates_skipped && (
                    <small>已跳过 {p.duplicates_skipped} 行重复文字</small>
                  )}
                  {p.ocr_chars === 0 ? (
                    <button
                      disabled={submitting || !!job}
                      aria-label={`补充识别第 ${p.page} 页`}
                      onClick={() => void recognize(p.page)}
                    >
                      补充识别本页
                    </button>
                  ) : (
                    <small>已有 OCR 引文，保留原结果</small>
                  )}
                  <button
                    aria-label={`查看第 ${p.page} 页原图`}
                    onClick={() =>
                      onLocate({
                        document_id: identifier,
                        page: p.page,
                        bbox: [0, 0, 0, 0],
                        width: p.width,
                        height: p.height,
                      })
                    }
                  >
                    查看原图
                  </button>
                </div>
              ))}
          </div>
          {!report.attention_pages.length && !showAll && (
            <p>未发现缺字或低置信度提示；公式、表格和阅读顺序仍需核对原文。</p>
          )}
          <details className="extended-help">
            <summary>如何使用文字检查</summary>
            <p>
              先查看需核对的页，再打开原图区分空白页、图表页和扫描正文。缺字页可运行
              OCR；对于已有标题、图注但正文未提取的页面，勾选“显示全部页面”后点击“补充识别本页”。面板显示任务进度，结束后自动刷新。离开页面后任务继续，可在任务与成果查看。重复文字仅在文本和位置均匹配时跳过；低置信度页仍需原图核对。已有
              OCR 引文不会重写。
            </p>
          </details>
        </>
      )}
    </section>
  );
}
