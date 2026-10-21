export type Subquestion = {
  id: string;
  question: string;
  context_question?: string;
  status: "reviewed_answer" | "unresolved";
  claim_count: number;
  omitted_candidate_count?: number;
  reason?: string;
  evidence_ids?: string[];
  selected_evidence_ids?: string[];
  generation_evidence_ids?: string[];
};

export function AnswerCoverage({
  items,
  sources = [],
  onLocateEvidence,
  onPrepareQuestion,
}: {
  items?: Subquestion[];
  sources?: { id?: string; page: number }[];
  onLocateEvidence?: (id: string) => void;
  onPrepareQuestion?: (part: Subquestion) => void;
}) {
  if (!items?.length) return null;
  return (
    <details className="answer-coverage" open>
      <summary>
        逐项回答情况 ·{" "}
        {items.filter((p) => p.status === "reviewed_answer").length}/
        {items.length} 项有回答
      </summary>
      <p className="result-note">
        按问题中的原句逐项列出，请核对是否覆盖你的要求。“有回答”表示有论断通过初筛，不代表完整或正确。
      </p>
      <ol>
        {items.map((p) => (
          <li key={p.id}>
            <strong>{p.question}</strong>
            <p>
              {p.reason ||
                (p.status === "reviewed_answer"
                  ? `${p.claim_count} 条回答通过初筛，仍需核对原文。`
                  : "本轮未形成通过核验的回答；不表示论文没有答案。")}
            </p>
            {(p.status === "unresolved" ||
              (p.omitted_candidate_count || 0) > 0) &&
              onPrepareQuestion && (
                <button
                  className="text-button"
                  onClick={() => onPrepareQuestion(p)}
                >
                  单独追问此项
                </button>
              )}
            {(p.status === "unresolved" ||
              (p.omitted_candidate_count || 0) > 0) &&
              onLocateEvidence && (
                <div className="unresolved-sources">
                  {(p.generation_evidence_ids?.length
                    ? p.generation_evidence_ids
                    : p.selected_evidence_ids?.length
                      ? p.selected_evidence_ids
                      : p.evidence_ids || []
                  )
                    .filter((id) => sources.some((source) => source.id === id))
                    .slice(0, 3)
                    .map((id, index) => (
                      <button
                        key={id}
                        className="text-button"
                        onClick={() => onLocateEvidence(id)}
                      >
                        查看候选原文 {index + 1} · 第
                        {sources.find((source) => source.id === id)?.page} 页
                      </button>
                    ))}
                  {!!p.evidence_ids?.length && (
                    <small>候选原文未经支持性确认，请结合上下文判断。</small>
                  )}
                </div>
              )}
          </li>
        ))}
      </ol>
    </details>
  );
}
