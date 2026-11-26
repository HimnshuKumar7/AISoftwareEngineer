export type Mode = "qa" | "explain" | "optimize" | "duplicates";

export interface User {
  id: string;
  email: string;
  name?: string | null;
}

export interface Repo {
  id: string;
  url: string;
  owner: string;
  name: string;
  branch?: string | null;
  commit_sha?: string | null;
  status: "queued" | "cloning" | "parsing" | "embedding" | "indexing" | "ready" | "failed";
  status_message?: string | null;
  progress: number;
  file_count: number;
  chunk_count: number;
  languages: Record<string, number>;
  created_at: string;
  indexed_at?: string | null;
}

export const ACTIVE_STATUSES: Repo["status"][] = ["queued", "cloning", "parsing", "embedding", "indexing"];

export interface Citation {
  path: string;
  start_line: number;
  end_line: number;
  chunk_id: number;
  kind: string;
  name: string;
}

export interface Source {
  chunk_id: number;
  path: string;
  start_line: number;
  end_line: number;
  kind: string;
  name: string;
  language: string;
  score: number;
  code: string;
  cited?: boolean;
  also_at?: string[];
}

export interface QueryResult {
  id: string;
  conversation_id: string;
  mode: Mode | string;
  question: string;
  answer: string;
  sub_queries: string[];
  citations: Citation[];
  sources: Source[];
  llm_provider?: string | null;
  llm_model?: string | null;
  latency_ms: number;
  removed_citations?: number;
  timings_ms?: Record<string, number>;
  dedupe_stats?: Record<string, number>;
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  last_activity: string;
  messages: number;
}

export interface ProviderInfo {
  provider: string;
  default_model: string;
  configured: boolean;
  is_default: boolean;
}

export interface DuplicateLocation {
  chunk_id: number;
  path: string;
  start_line: number;
  end_line: number;
  name: string;
  kind: string;
  language: string;
  code_preview: string;
}

export interface DuplicateGroup {
  size: number;
  exact: boolean;
  min_lexical_similarity: number;
  locations: DuplicateLocation[];
}

export interface DuplicateReport {
  threshold: number;
  scanned_chunks: number;
  scan_truncated: boolean;
  group_count: number;
  groups: DuplicateGroup[];
}
