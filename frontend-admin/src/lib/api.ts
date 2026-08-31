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

export interface Turn {
  turn_number: number;
  input_method: string;
  query_text: string;
  retrieved_chunk_ids: string[];
  response_text: string;
  in_scope: boolean;
  latency_ms: number;
  timestamp: string;
}

export const api = {
  listProducts: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/products`, { headers: authHeader(credentials) }).then((r) => handle<Product[]>(r)),

  listDocuments: (credentials: string) =>
    fetch(`${API_BASE}/api/admin/documents`, { headers: authHeader(credentials) }).then((r) => handle<DocumentOut[]>(r)),

  uploadDocument: (credentials: string, productSlug: string, file: File) => {
    const form = new FormData();
    form.append("product_slug", productSlug);
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

  exportSessionUrl: (sessionId: string) => `${API_BASE}/api/sessions/${sessionId}/export`,
};

export { API_BASE };
