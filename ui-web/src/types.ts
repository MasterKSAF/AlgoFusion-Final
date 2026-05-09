export type DocumentStatus = "uploaded" | "processing" | "completed" | "exported" | "failed";
export type FieldState = "ok" | "null" | "review" | "invalid" | "empty";
export type ViewId = "overview" | "documents" | "review" | "artifacts" | "events";

export interface Stats {
  total: number;
  completed: number;
  processing: number;
  failed: number;
  ready_to_export: number;
  requires_attention: number;
  null_fields: number;
  review_fields: number;
  invalid_fields: number;
  success_rate: number;
  by_type: Record<string, number>;
  run_root: string;
}

export interface DocumentCard {
  id: string;
  storage_dir: string;
  filename: string;
  document_type: string;
  status: DocumentStatus;
  progress: number;
  updated_at: string;
  pages: number | null;
  field_count: number;
  null_count: number;
  review_count: number;
  invalid_count: number;
  ready_to_export: boolean;
  draft_field_count: number;
  final_json_path: string | null;
  base_path: string;
}

export interface FieldValue {
  path: string;
  label: string;
  value: unknown;
  raw_value: unknown;
  draft_value: unknown;
  has_draft: boolean;
  effective_value: unknown;
  state: FieldState;
  effective_state: FieldState;
  catalog: string | null;
}

export interface DocumentDetail extends DocumentCard {
  fields: FieldValue[];
  final_json: unknown;
  raw_final_json: unknown;
  wrapper_document_type: string | null;
  review_draft: { saved_at?: string; fields?: Record<string, unknown> } | null;
}

export interface EventItem {
  level?: string;
  status?: string;
  type?: string;
  event?: string;
  message?: string;
  document?: string;
  filename?: string;
  timestamp?: string;
}

export interface ArtifactFile {
  name: string;
  relative_path: string;
  stage: string;
  size_bytes: number;
  modified_at: string;
  preview_type: "image" | "pdf" | "text" | "download";
}

export interface ArtifactTree {
  document_id: string;
  base_path: string;
  files: ArtifactFile[];
}

export interface ExportQueue {
  requires_attention: DocumentCard[];
  ready: DocumentCard[];
  summary: {
    attention_count: number;
    ready_count: number;
    null_fields: number;
    invalid_fields: number;
  };
}
