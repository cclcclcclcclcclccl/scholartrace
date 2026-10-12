export type Paper = {
  id: string;
  title: string;
  name: string;
  pages: number;
  status: string;
  version: number | null;
  arxiv_id?: string | null;
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
): Promise<T> {
  const response = await fetch(
    url,
    body === undefined
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
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
