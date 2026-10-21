import type { ReactNode } from "react";
export type SemanticReview = {
  status: string;
  decision?: "same_claim" | "claim_changed" | "unclear";
  method?: string;
  reason: string;
  old_quote?: string;
  new_quote?: string;
  raw_model_decision?: string;
  consistency_warnings?: {
    kind: string;
    reason: string;
    old?: string[];
    new?: string[];
  }[];
};
export function ReviewEvidence({ review }: { review?: SemanticReview }) {
  if (!review)
    return (
      <p className="review-unavailable">
        尚无含义复核结果；原文对齐不代表笔记结论未变。
      </p>
    );
  let content: ReactNode;
  if (review.status !== "model_assessment")
    content = <p className="review-unavailable">{review.reason}</p>;
  else
    content = (
      <>
        {review.consistency_warnings?.map((w, i) => (
          <div className="review-warning" key={i}>
            <strong>
              {{
                numeric_difference: "数值差异待核对",
                observation_mismatch: "笔记关注点待核对",
                missing_observation_evidence: "缺少对应指标的证据",
                condition_not_comparable: "适用条件不一致",
                dataset_not_comparable: "数据集或基准不一致",
                reporting_absence: "未报告不等于未发生",
                negation_difference: "否定差异待核对",
              }[w.kind] || "证据范围待核对"}
            </strong>
            <p>{w.reason}</p>
            {w.old && (
              <p>
                旧引文数值：{w.old.join("、")} → 新引文数值：{w.new?.join("、")}
              </p>
            )}
          </div>
        ))}
        {review.old_quote && review.new_quote && (
          <details
            className="review-evidence"
            open={review.decision === "unclear"}
          >
            <summary>查看本次实际比较的引文</summary>
            <div className="comparison">
              <div>
                <small>旧版比较引文</small>
                <blockquote>{review.old_quote}</blockquote>
              </div>
              <div>
                <small>目标版比较引文</small>
                <blockquote>{review.new_quote}</blockquote>
              </div>
            </div>
            <p>
              这些句子来自两侧原文；引文存在不代表它们足以支持判断。请结合下方完整段落、版本与页码核对。
            </p>
          </details>
        )}
      </>
    );
  return <div className="review-evidence-panel">{content}</div>;
}
