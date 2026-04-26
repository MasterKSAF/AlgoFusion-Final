import type { ArtifactTree, DocumentCard, DocumentDetail, EventItem, ExportQueue, Stats } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function apiUrl(path: string): string {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE.replace(/\/$/, "")}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  stats: () => fetchJson<Stats>("/api/stats"),
  documents: () => fetchJson<{ documents: DocumentCard[] }>("/api/documents?limit=1000"),
  document: (id: string) => fetchJson<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}`),
  artifacts: (id: string) => fetchJson<ArtifactTree>(`/api/documents/${encodeURIComponent(id)}/artifacts`),
  events: () => fetchJson<{ events: EventItem[] }>("/api/events?limit=80"),
  exportQueue: () => fetchJson<ExportQueue>("/api/export/queue"),
  saveReview: (id: string, fields: Record<string, unknown>) =>
    fetchJson<{ saved: boolean; path: string; field_count: number }>(`/api/documents/${encodeURIComponent(id)}/review`, {
      method: "POST",
      body: JSON.stringify({ fields })
    }),
  artifactText: (id: string, path: string) =>
    fetchJson<{ path: string; text: string; truncated: boolean; error?: string }>(
      `/api/documents/${encodeURIComponent(id)}/artifact-text?path=${encodeURIComponent(path)}`
    ),
  artifactUrl: (id: string, path: string) =>
    apiUrl(`/api/documents/${encodeURIComponent(id)}/artifact?path=${encodeURIComponent(path)}`)
};

