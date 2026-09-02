const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type Platform = "tablet_web" | "mobile_web" | "desktop_web";
export type InputMethod = "voice" | "typed";

export interface DeviceInfo {
  user_agent: string;
  screen_width: number;
  screen_height: number;
}

export interface SessionStartResponse {
  session_id: string;
  participant_id: string;
  platform: Platform;
  condition: string;
  product_slug: string;
  product_display_name: string;
  start_time: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  text: string;
  section_label: string | null;
  score: number;
}

export interface QueryResponse {
  answer_text: string;
  in_scope: boolean;
  retrieved_chunks: RetrievedChunk[];
  latency_ms: number;
  turn_number: number;
}

export interface QueryStreamDone {
  turn_number: number;
  in_scope: boolean;
  latency_ms: number;
  answer_text: string;
}

export interface Product {
  id: string;
  slug: string;
  display_name: string;
}

export interface CoreInfoResponse {
  product_name: string;
  used_for: string | null;
  dose: string | null;
  frequency: string | null;
  max_dose_24h: string | null;
  warnings: string[];
  full_text: string;
  latency_ms: number;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export const api = {
  listProducts: () => fetch(`${API_BASE}/api/products`).then((r) => handle<Product[]>(r)),

  startSession: (platform: Platform, productSlug: string, deviceInfo: DeviceInfo) =>
    fetch(`${API_BASE}/api/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, product_slug: productSlug, device_info: deviceInfo }),
    }).then((r) => handle<SessionStartResponse>(r)),

  endSession: (sessionId: string, errorsLogged = 0) =>
    fetch(`${API_BASE}/api/session/${sessionId}/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ errors_logged: errorsLogged }),
    }).then((r) => handle(r)),

  coreInfo: (sessionId: string) =>
    fetch(`${API_BASE}/api/core-info?session_id=${encodeURIComponent(sessionId)}`, {
      method: "POST",
    }).then((r) => handle<CoreInfoResponse>(r)),

  query: (sessionId: string, queryText: string, inputMethod: InputMethod) =>
    fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, query_text: queryText, input_method: inputMethod }),
    }).then((r) => handle<QueryResponse>(r)),

  /** Reads /api/query/stream as newline-delimited JSON, calling onDelta for each text chunk as
   * the model generates it and onDone once with the final metadata (turn number, in_scope,
   * latency, full answer text) - lets the caller start speaking the first sentence before the
   * model has finished writing the rest of the answer. */
  queryStream: async (
    sessionId: string,
    queryText: string,
    inputMethod: InputMethod,
    onDelta: (text: string) => void,
    onDone: (meta: QueryStreamDone) => void
  ): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, query_text: queryText, input_method: inputMethod }),
    });
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      throw new Error(text || res.statusText);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let done: QueryStreamDone | null = null;
    while (true) {
      const { value, done: readerDone } = await reader.read();
      if (readerDone) break;
      buffer += decoder.decode(value, { stream: true });
      let newlineIndex: number;
      while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        if (!line) continue;
        const event = JSON.parse(line) as { delta?: string } & Partial<QueryStreamDone> & { done?: true };
        if (event.delta) onDelta(event.delta);
        else if (event.done) done = event as unknown as QueryStreamDone;
      }
    }
    if (!done) throw new Error("Stream ended without a final result");
    onDone(done);
  },

  stt: async (audioBlob: Blob): Promise<string> => {
    const form = new FormData();
    form.append("audio", audioBlob, "recording.webm");
    const res = await fetch(`${API_BASE}/api/stt`, { method: "POST", body: form });
    const data = await handle<{ transcript: string }>(res);
    return data.transcript;
  },

  ttsUrl: () => `${API_BASE}/api/tts`,

  speak: async (text: string): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error("TTS request failed");
    return res.blob();
  },
};

export { API_BASE };
