export type ReadingSession = { active: string; pages: Record<string, number> };
const key = "scholartrace.reading.v1";
export function readSession(): ReadingSession {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "{}");
    return {
      active: typeof value.active === "string" ? value.active : "",
      pages: value.pages && typeof value.pages === "object" ? value.pages : {},
    };
  } catch {
    return { active: "", pages: {} };
  }
}
export function savedPage(id: string, max: number) {
  const page = readSession().pages[id];
  return Number.isInteger(page) && page >= 1 && page <= max ? page : 1;
}
export function rememberPage(id: string, page: number) {
  try {
    const previous = readSession();
    localStorage.setItem(
      key,
      JSON.stringify({ active: id, pages: { ...previous.pages, [id]: page } }),
    );
  } catch {
    /* Storage may be unavailable in a private browser. Reading still works. */
  }
}
