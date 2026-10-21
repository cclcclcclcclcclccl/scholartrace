import { useState } from "react";
import { request, type Job } from "./workspaceApi";
export function ImpactContinuation({
  reportId,
  targetId,
  remaining,
}: {
  reportId: string;
  targetId: string;
  remaining: number;
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [failed, setFailed] = useState(false);
  async function submit() {
    setBusy(true);
    setFailed(false);
    setMessage("");
    try {
      const job = await request<Job>("/api/jobs", {
        kind: "impact",
        payload: { document_id: targetId, impact_from: reportId },
      });
      setMessage(
        "下一批已提交（" +
          job.id.slice(0, 8) +
          "）。请在任务中心查看进度与新报告；本报告保留作为上一批记录。",
      );
    } catch (e) {
      setFailed(true);
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="inline-help">
      <p>
        此依赖快照还有 {remaining}{" "}
        条未检查。继续时沿用首次收集的依赖，之后新增的成果需重新发起复核。
      </p>
      <button
        disabled={busy || (!!message && !failed)}
        onClick={() => void submit()}
      >
        {busy ? "提交中…" : "继续下一批成果复核"}
      </button>
      {message && <p role={failed ? "alert" : "status"}>{message}</p>}
    </div>
  );
}
