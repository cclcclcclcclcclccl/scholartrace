export type Checklist = {
  question: string;
  notice: string;
  items: {
    id: string;
    label: string;
    requested_terms: string[];
    related: { text: string; block_id: string; document_id: string }[];
    status: "candidate" | "unlocated";
    followup: string;
  }[];
};

export function AnswerChecklist({
  value,
  onLocate,
  onFollowup,
}: {
  value?: Checklist;
  onLocate: (id: string) => void;
  onFollowup?: (question: string) => void;
}) {
  if (!value?.items.length) return null;
  return (
    <details className="answer-coverage answer-checklist" open>
      <summary>回答核对清单 · {value.items.length} 项明确要求</summary>
      <p className="result-note">{value.notice}</p>
      <ol>
        {value.items.map((item) => (
          <li key={item.id}>
            <strong>{item.label}</strong>
            <p>
              问题原词：{item.requested_terms.join("、")} ·{" "}
              {item.status === "candidate"
                ? "有相关表述，待核对"
                : "未定位到对应表述，建议补查"}
            </p>
            {!!item.related.length && (
              <details>
                <summary>展开相关回答与来源（{item.related.length}）</summary>
                {item.related.map((part, i) => (
                  <div key={i}>
                    <p>{part.text}</p>
                    {!!part.block_id && (
                      <button
                        className="text-button"
                        onClick={() => onLocate(part.block_id)}
                      >
                        核对清单原文 {i + 1}
                      </button>
                    )}
                  </div>
                ))}
              </details>
            )}
            {onFollowup && (
              <button
                className="text-button"
                onClick={() => onFollowup(item.followup)}
              >
                补问：{item.label}
              </button>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}
