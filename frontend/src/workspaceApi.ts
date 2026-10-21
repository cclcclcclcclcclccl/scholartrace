export type Paper = {
  id: string;
  title: string;
  name: string;
  pages: number;
  status: string;
  version: number | null;
  arxiv_id?: string | null;
  aliases?: string[];
};
export type Anchor = {
  id?: string;
  block_id?: string;
  document_id: string;
  page: number;
  bbox: number[];
  width: number;
  height: number;
  text?: string;
};
export type Job = {
  history_cursor?: number;
  id: string;
  kind: string;
  state: string;
  progress: number;
  message: string;
  error?: string;
  result?: Record<string, unknown>;
  payload: Record<string, unknown>;
  created_at: string;
};
export async function request<T>(
  url: string,
  body?: unknown,
  method = "POST",
  timeoutMs = 300000,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(
      url,
      body === undefined
        ? { signal: AbortSignal.timeout(timeoutMs) }
        : {
            signal: AbortSignal.timeout(timeoutMs),
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
    );
  } catch (e) {
    if ((e as Error).name === "TimeoutError")
      throw new Error(
        "请求等待超时。后台任务可能仍在执行，请到任务中心查看状态后再决定是否重试。",
      );
    if (e instanceof TypeError)
      throw new Error("连接服务失败，请检查本地服务和网络。已有记录仍保留。");
    throw e;
  }
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : Array.isArray(value.detail)
          ? value.detail
              .map(
                (item: { msg?: string; loc?: string[] }) =>
                  `${item.loc?.slice(1).join(" · ") || "参数"}：${(item.msg || "无效取值").replace("Value error, ", "")}`,
              )
              .join("；")
          : `请求失败 (${response.status})`,
    );
  }
  return response.json();
}
export function downloadText(name: string, value: string, type = "text/plain") {
  const url = URL.createObjectURL(
    new Blob([value], { type: `${type};charset=utf-8` }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
