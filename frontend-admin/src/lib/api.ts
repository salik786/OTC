const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function authHeader(credentials: string): Record<string, string> {
  return { Authorization: `Basic ${credentials}` };
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json();
}

export async function verifyCredentials(credentials: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/admin/products`, { headers: authHeader(credentials) });
  return res.ok;
}

export interface Product {
  id: string;
  slug: string;
  display_name: string;
}

export interface DocumentOut {
  id: string;
  product_id: string;
  product_slug: string;
  filename: string;
  uploaded_at: string;
  chunk_count: number;
  active: boolean;
}

export interface DocumentChunk {
  chunk_id: string;
  chunk_index: number;
  section_label: string | null;
  text: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  text: string;
  section_label: string | null;
  score: number;
}

export interface SessionSummary {
  session_id: string;
  participant_id: string;
  platform: string;
  condition: string;
  product_slug: string;
  start_time: string;
  end_time: string | null;
  total_turns: number;
  voice_turns: number;
  typed_turns: number;
  errors_logged: number;
}

export interface RetrievedChunkLog {
  rank: number;
  chunk_id: string;
  section_label: string | null;
  score: number;
  text: string;
  document_id: string | null;
  document_filename: string | null;
}

export interface Turn {
  turn_number: number;
  input_method: string;
  query_text: string;
  retrieved_chunk_ids: string[];
  retrieved_chunks: RetrievedChunkLog[];
  config_version: number | null;
  response_text: string;
  in_scope: boolean;
  latency_ms: number;
  timestamp: string;
}

export type RagConfig = {
  top_k: number;
  core_info_top_k: number;
  history_turns: number;
  generation_model: string;
  temperature: number;
  max_tokens: number;
  core_info_max_tokens: number;
  fallback_text: string;
  system_prompt: string;
  chunking_strategy: string;
  chunk_size_chars: number;
  chunk_overlap_chars: number;
  embedding_model: string;
};

export interface RagFieldMeta {
  type: "int" | "float" | "choice" | "text" | "prompt";
  group: string;
  help: string;
  min?: number;
  max?: number;
  choices?: string[];
  max_len?: number;
  reindex?: boolean;
}

export interface RagVersion {
  version: number;
  note: string;
  created_by: string;
  created_at: string;
  is_active: boolean;
  config: RagConfig;
}

export interface RagSettingsOverview {
  active: RagVersion;
  defaults: RagConfig;
  fields: Record<keyof RagConfig, RagFieldMeta>;
  chunking_strategies: Record<string, string>;
  embedding_dims: Record<string, number>;
  index: {
    embedding_model: string;
    chunking_strategy: string;
    chunk_size_chars: number;
    chunk_overlap_chars: number;
    built_at: string | null;
    chunk_count: number;
    documents: { filename: string; chunk_count: number; source_reconstructed: boolean }[];
  };
  pending_reindex: string[];
}

export interface RagTestResult {
  answer_text: string;
  in_scope: boolean;
  latency_ms: number;
  note?: string;
  retrieved_chunks: { section_label: string | null; score: number; text: string; document_filename: string | null }[];
}

export interface RagRegressionResult {
  passed: number;
  total: number;
  results: { query: string; expected_in_scope: boolean; in_scope: boolean; passed: boolean; answer_text: string }[];
}

export const api = {
  listProducts: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/products`, { headers: authHeader(credentials) }).then((r) => handle<Product[]>(r)),

  listDocuments: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/documents`, { headers: authHeader(credentials) }).then((r) => handle<DocumentOut[]>(r)),

  uploadDocument: (credentials: string, productSlug: string, file: File, productDisplayName?: string) => {
    const form = new FormData();
    form.append("product_slug", productSlug);
    if (productDisplayName) form.append("product_display_name", productDisplayName);
    form.append("file", file);
    return fetch(`${API_BASE}/api/admin/documents`, {
      method: "POST",
      headers: authHeader(credentials),
      body: form,
    }).then((r) => handle<DocumentOut>(r));
  },

  getDocumentChunks: (credentials: string, documentId: string) =>
    fetch(`${API_BASE}/api/admin/documents/${documentId}/chunks`, { headers: authHeader(credentials) }).then((r) =>
      handle<DocumentChunk[]>(r)
    ),

  deleteDocument: (credentials: string, documentId: string) =>
    fetch(`${API_BASE}/api/admin/documents/${documentId}`, {
      method: "DELETE",
      headers: authHeader(credentials),
    }).then((r) => handle<{ deleted: string }>(r)),

  testRetrieval: (credentials: string, query: string, productSlug: string, topK = 5) =>
    fetch(`${API_BASE}/api/admin/test-retrieval`, {
      method: "POST",
      headers: { ...authHeader(credentials), "Content-Type": "application/json" },
      body: JSON.stringify({ query, product_slug: productSlug, top_k: topK }),
    }).then((r) => handle<{ retrieved_chunks: RetrievedChunk[]; latency_ms: number }>(r)),


  getRagSettings: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/settings`, { headers: authHeader(credentials) }).then((r) => handle<RagSettingsOverview>(r)),

  saveRagSettings: (credentials: string, config: Partial<RagConfig>, note: string) =>
    fetch(`${API_BASE}/api/admin/settings`, {
      method: "PUT",
      headers: { ...authHeader(credentials), "Content-Type": "application/json" },
      body: JSON.stringify({ config, note }),
    }).then((r) => handle<{ version: RagVersion; needs_reindex: string[] }>(r)),

  listRagVersions: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/settings/versions`, { headers: authHeader(credentials) }).then((r) => handle<RagVersion[]>(r)),

  restoreRagVersion: (credentials: string, version: number) =>
    fetch(`${API_BASE}/api/admin/settings/versions/${version}/activate`, {
      method: "POST",
      headers: authHeader(credentials),
    }).then((r) => handle<{ version: RagVersion; needs_reindex: string[] }>(r)),

  reindexRag: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/settings/reindex`, { method: "POST", headers: authHeader(credentials) }).then((r) =>
      handle<{ documents: number; chunks: number; seconds: number; config_version: number }>(r)
    ),

  testRagQuestion: (credentials: string, productSlug: string, queryText: string, config: Partial<RagConfig>) =>
    fetch(`${API_BASE}/api/admin/settings/test`, {
      method: "POST",
      headers: { ...authHeader(credentials), "Content-Type": "application/json" },
      body: JSON.stringify({ product_slug: productSlug, query_text: queryText, config }),
    }).then((r) => handle<RagTestResult>(r)),

  runRagRegression: (credentials: string, productSlug: string, config: Partial<RagConfig>) =>
    fetch(`${API_BASE}/api/admin/settings/regression`, {
      method: "POST",
      headers: { ...authHeader(credentials), "Content-Type": "application/json" },
      body: JSON.stringify({ product_slug: productSlug, config }),
    }).then((r) => handle<RagRegressionResult>(r)),

  listSessions: (credentials: string, opts: { limit?: number; platform?: string; productSlug?: string } = {}) => {
    const params = new URLSearchParams();
    params.set("limit", String(opts.limit ?? 100));
    if (opts.platform) params.set("platform", opts.platform);
    if (opts.productSlug) params.set("product_slug", opts.productSlug);
    return fetch(`${API_BASE}/api/admin/sessions?${params.toString()}`, { headers: authHeader(credentials) }).then((r) =>
      handle<SessionSummary[]>(r)
    );
  },

  getSessionTurns: (credentials: string, sessionId: string) =>
    fetch(`${API_BASE}/api/admin/sessions/${sessionId}/turns`, { headers: authHeader(credentials) }).then((r) =>
      handle<Turn[]>(r)
    ),

  deleteSession: (credentials: string, sessionId: string) =>
    fetch(`${API_BASE}/api/admin/sessions/${sessionId}`, {
      method: "DELETE",
      headers: authHeader(credentials),
    }).then((r) => handle<{ deleted: string }>(r)),

  exportSessionUrl: (sessionId: string) => `${API_BASE}/api/sessions/${sessionId}/export`,

  exportAllSessionsUrl: (format: "csv" | "json", opts: { platform?: string; productSlug?: string } = {}) => {
    const params = new URLSearchParams();
    params.set("format", format);
    if (opts.platform) params.set("platform", opts.platform);
    if (opts.productSlug) params.set("product_slug", opts.productSlug);
    return `${API_BASE}/api/admin/sessions/export?${params.toString()}`;
  },
};

export { API_BASE };
