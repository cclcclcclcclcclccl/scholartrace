export type Subquestion = {
  id: string;
  question: string;
  status: "reviewed_answer" | "unresolved";
  claim_count: number;
  reason?: string;
};

export function AnswerCoverage({ items }: { items?: Subquestion[] }) {
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
              {p.status === "reviewed_answer"
                ? `${p.claim_count} 条回答通过初筛，仍需核对原文。`
                : p.reason || "本轮未形成通过核验的回答；不表示论文没有答案。"}
            </p>
          </li>
        ))}
      </ol>
    </details>
  );
}
