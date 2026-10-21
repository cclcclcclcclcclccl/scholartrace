export type Readiness = {
  notice: string;
  missing_cells: number;
  hints: string[];
  questions: string[];
  papers: {
    document_id: string;
    title: string;
    missing: string[];
    units: string[];
    stages: string[];
  }[];
};

export function ComparisonReadiness({
  value,
  fields,
  onFill,
}: {
  value?: Readiness;
  fields: Record<string, string>;
  onFill?: (document: string, field: string) => void;
}) {
  if (!value) return null;
  return (
    <details className="answer-coverage" open>
      <summary>
        比较前检查 ·{" "}
        {value.missing_cells
          ? `${value.missing_cells} 格待补查`
          : "已整理全部格，仍需判断可比性"}
      </summary>
      <p className="result-note">{value.notice}</p>
      {value.hints.map((hint) => (
        <p className="boundaries-notice" key={hint}>
          {hint}
        </p>
      ))}
      {value.papers.map((p) => (
        <div key={p.document_id}>
          <strong>{p.title}</strong>
          <p>
            摘录单位线索：{p.units.join("、") || "未识别"}；阶段线索：
            {p.stages.join("、") || "未识别"}。
          </p>
          {!!p.missing.length && (
            <p>待补：{p.missing.map((k) => fields[k]).join("、")}</p>
          )}
          {onFill &&
            p.missing.map((field) => (
              <button
                className="text-button"
                key={field}
                onClick={() => onFill(p.document_id, field)}
                aria-label={`补齐检查：${fields[field]}：${p.title}`}
              >
                补齐{fields[field]}
              </button>
            ))}
        </div>
      ))}
      <details>
        <summary>填写后仍需核对的四个问题</summary>
        <ol>
          {value.questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ol>
      </details>
    </details>
  );
}
