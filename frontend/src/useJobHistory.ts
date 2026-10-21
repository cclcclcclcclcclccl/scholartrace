import { useCallback, useEffect, useRef, useState } from "react";
import { request, type Job } from "./workspaceApi";
type Page = { items: Job[]; next_before: number | null };
export function useJobHistory(kind?: string, enabled = true) {
  const [items, setItems] = useState<Job[]>([]),
    [cursor, setCursor] = useState<number | null>(null),
    [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const older = useRef(false);
  const alive = useRef(true);
  const generation = useRef(0);
  const url =
    "/api/jobs-page" + (kind ? "?kind=" + encodeURIComponent(kind) : "");
  const merge = (rows: Job[]) =>
    setItems((prev) => {
      const all = new Map(prev.map((j) => [j.id, j]));
      rows.forEach((j) => all.set(j.id, j));
      return [...all.values()].sort(
        (a, b) => (b.history_cursor || 0) - (a.history_cursor || 0),
      );
    });
  const refresh = useCallback(async () => {
    const version = generation.current;
    const page = await request<Page>(url, undefined, "GET", 15000);
    if (!alive.current || version !== generation.current) return;
    merge(page.items);
    if (!older.current) setCursor(page.next_before);
    setError("");
  }, [url]);
  useEffect(() => {
    alive.current = true;
    setLoading(false);
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    async function tick() {
      try {
        await refresh();
      } catch (e) {
        if (!stopped)
          setError("任务刷新失败，已保留已有记录：" + (e as Error).message);
      } finally {
        if (!stopped) timer = setTimeout(() => void tick(), 2500);
      }
    }
    if (enabled) void tick();
    return () => {
      stopped = true;
      alive.current = false;
      generation.current++;
      clearTimeout(timer);
    };
  }, [refresh, enabled]);
  async function loadOlder() {
    if (cursor === null || loading) return;
    setLoading(true);
    const version = generation.current;
    try {
      const page = await request<Page>(
        url + (kind ? "&" : "?") + "before=" + cursor,
        undefined,
        "GET",
        15000,
      );
      if (alive.current && version === generation.current) {
        older.current = true;
        merge(page.items);
        setCursor(page.next_before);
        setError("");
      }
    } catch (e) {
      if (alive.current && version === generation.current)
        setError((e as Error).message);
    } finally {
      if (alive.current && version === generation.current) setLoading(false);
    }
  }
  return { items, cursor, error, loading, refresh, loadOlder };
}
