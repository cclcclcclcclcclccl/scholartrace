import type { Anchor, Paper } from "./workspaceApi";

export type ProjectContext = {
  id: string;
  title: string;
  goal: string;
  document_ids: string[];
};
export type ProjectSummary = {
  id: string;
  title: string;
  goal: string;
  revision: number;
  archived: number;
  created_at: string;
  updated_at: string;
  document_count: number;
  artifact_count: number;
};
export type ProjectDetail = ProjectContext & {
  revision: number;
  archived: number;
  updated_at: string;
  documents: (Paper & { archived: number })[];
  notes: (Omit<Anchor, "id"> & {
    id: number;
    block_id: string;
    note: string;
    quote: string;
    title: string;
    version: number | null;
  })[];
  artifacts: { id: string; title: string; kind: string; created_at: string }[];
  jobs: {
    id: string;
    kind: string;
    state: string;
    progress: number;
    message: string;
    error?: string;
  }[];
};
export function projectFromHash() {
  return (
    new URLSearchParams(window.location.hash.slice(1)).get("project") || ""
  );
}
export function openProjectLink(id: string) {
  window.location.hash = new URLSearchParams({ project: id }).toString();
}
