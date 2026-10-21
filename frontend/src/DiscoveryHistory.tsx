import { useEffect, useState } from "react";
import { request, downloadText } from "./workspaceApi";
export type DiscoveryRecord = {
  id: number;
  kind: "search" | "related" | "recommendations";
  label: string;
  spec: Record<string, unknown>;
  created_at: string;
  result: unknown;
  view: unknown;
};
type Entry = Omit<DiscoveryRecord, "result" | "view">;
type HistoryPage = { items: Entry[]; next_before: number | null };
const labels = {
  search: "论文检索",
  related: "关联探索",
  recommendations: "偏好推荐",
};
export function discoveryTime(value: string) {
  return new Date(value.replace(" ", "T") + "Z").toLocaleString();
}
export function DiscoveryHistory({
  refreshKey,
  disabled,
  onRestore,
}: {
  refreshKey: number;
  disabled: boolean;
  onRestore: (record: DiscoveryRecord) => void;
}) {
  const [items, setItems] = useState<Entry[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    request<HistoryPage>("/api/discover/history")
      .then((r) => {
        if (active) {
          setItems(r.items);
          setCursor(r.next_before);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [refreshKey]);
  async function act(work: () => Promise<void>) {
    setLoading(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <details className="work-card discovery-history">
      <summary>
        最近发现记录 · {items.length}
        {cursor ? "+" : ""}
      </summary>
      <p>
        检索和关联探索成功返回后自动保存。恢复仅查看当时结果，不请求外部数据源；需要最新结果时再重新检索。记录保存在当前账户。
      </p>
      {error && <p role="alert">{error}</p>}
      {!items.length && !error && (
        <p>还没有保存的发现记录。从上方搜索或关联探索开始。</p>
      )}
      {items.map((item) => (
        <article key={item.id} className="discovery-history-row">
          <div>
            <strong>{item.label}</strong>
            <small>
              {labels[item.kind]} · {discoveryTime(item.created_at)}
              {item.kind === "related" && !item.spec.online
                ? " · 仅本地"
                : item.spec.mode === "identifier"
                  ? " · 编号自动识别"
                  : item.spec.source
                    ? ` · ${item.spec.source}`
                    : ""}
            </small>
          </div>
          <div className="work-row">
            <button
              disabled={disabled || loading}
              onClick={() =>
                void act(async () => {
                  onRestore(
                    await request<DiscoveryRecord>(
                      `/api/discover/history/${item.id}`,
                    ),
                  );
                })
              }
            >
              恢复这次发现
            </button>
            <button
              disabled={disabled || loading}
              onClick={() =>
                void act(async () => {
                  const { view, ...record } = await request<DiscoveryRecord>(
                    `/api/discover/history/${item.id}`,
                  );
                  void view;
                  downloadText(
                    `discovery-${item.id}.json`,
                    JSON.stringify(record, null, 2),
                    "application/json",
                  );
                })
              }
            >
              导出记录 JSON
            </button>
          </div>
        </article>
      ))}
      {cursor !== null && (
        <button
          disabled={disabled || loading}
          onClick={() =>
            void act(async () => {
              const r = await request<HistoryPage>(
                `/api/discover/history?before=${cursor}`,
              );
              setItems((prev) => [
                ...prev,
                ...r.items.filter((x) => !prev.some((y) => y.id === x.id)),
              ]);
              setCursor(r.next_before);
            })
          }
        >
          加载更早记录
        </button>
      )}
    </details>
  );
}
