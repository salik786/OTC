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
