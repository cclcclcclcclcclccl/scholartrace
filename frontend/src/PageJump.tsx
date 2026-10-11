import { useEffect, useId, useState } from "react";

/** Keep an editable draft separate from the page that is actually rendered. */
export function PageJump({
  page,
  total,
  documentId,
  onJump,
}: {
  page: number;
  total: number;
  documentId: string;
  onJump: (page: number) => void;
}) {
  const [draft, setDraft] = useState(String(page));
  const [error, setError] = useState("");
  const errorId = useId();
  useEffect(() => {
    setDraft(String(page));
    setError("");
  }, [page, documentId]);
  function commit() {
    if (draft === String(page)) return;
    const trimmed = draft.trim();
    if (!trimmed) {
      setDraft(String(page));
      setError("");
      return;
    }
    const next = Number(trimmed);
    if (
      !/^\d+$/.test(trimmed) ||
      !Number.isSafeInteger(next) ||
      next < 1 ||
      next > total
    ) {
      setError(`请输入 1–${total} 之间的整数页码`);
      setDraft(String(page));
      return;
    }
    setDraft(String(next));
    setError("");
    onJump(next);
  }
  return (
    <div className="page-jump">
      <label>
        <input
          aria-label="当前页码"
          type="text"
          inputMode="numeric"
          role="spinbutton"
          aria-valuemin={1}
          aria-valuemax={total}
          aria-valuenow={page}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : undefined}
          title="输入页码后按回车、点击跳转或移开焦点"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setError("");
          }}
          onFocus={(event) => event.currentTarget.select()}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return;
            if (event.key === "Enter") {
              event.preventDefault();
              commit();
            }
            if (event.key === "Escape") {
              event.preventDefault();
              setDraft(String(page));
              setError("");
            }
            if (event.key === "ArrowUp" || event.key === "ArrowDown") {
              event.preventDefault();
              const next = Math.max(
                1,
                Math.min(total, page + (event.key === "ArrowUp" ? 1 : -1)),
              );
              setDraft(String(next));
              setError("");
              onJump(next);
            }
          }}
        />
        <span>/ {total}</span>
      </label>
      <button
        className="page-jump-button"
        onMouseDown={(event) => event.preventDefault()}
        onClick={commit}
      >
        跳转
      </button>
      {error && (
        <span id={errorId} className="page-jump-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
