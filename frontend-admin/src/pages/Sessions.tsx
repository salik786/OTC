import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { api, authHeader, type Product, type SessionSummary, type Turn } from "../lib/api";

function formatDuration(start: string, end: string | null): string {
  if (!end) return "-";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function Sessions() {
  const { credentials } = useAuth();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [platformFilter, setPlatformFilter] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const [viewingSession, setViewingSession] = useState<SessionSummary | null>(null);
  const [viewingTurns, setViewingTurns] = useState<Turn[] | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState<string | null>(null);

  async function refresh() {
    if (!credentials) return;
    setLoading(true);
    try {
      const [sess, prods] = await Promise.all([
        api.listSessions(credentials, { platform: platformFilter || undefined, productSlug: productFilter || undefined }),
        products.length ? Promise.resolve(products) : api.listProducts(credentials),
      ]);
      setSessions(sess);
      if (!products.length) setProducts(prods);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credentials, platformFilter, productFilter]);

  async function handleExport(sessionId: string) {
    if (!credentials) return;
    setDownloadError(null);
    try {
      const res = await fetch(api.exportSessionUrl(sessionId), { headers: authHeader(credentials) });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `session_${sessionId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError(`Failed to export session ${sessionId}.`);
    }
  }

  async function handleView(session: SessionSummary) {
    if (!credentials) return;
    setViewingSession(session);
    setViewingTurns(null);
    setViewError(null);
    setViewLoading(true);
    try {
      const turns = await api.getSessionTurns(credentials, session.session_id);
      setViewingTurns(turns);
    } catch {
      setViewError("Could not load this session's transcript.");
    } finally {
      setViewLoading(false);
    }
  }

  function closeView() {
    setViewingSession(null);
    setViewingTurns(null);
    setViewError(null);
  }

  const platforms = Array.from(new Set(sessions.map((s) => s.platform)));

  return (
    <section>
      <h2>Recent Sessions</h2>

      <div className="panel form-row">
        <select value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
          <option value="">All platforms</option>
          {["tablet_web", "mobile_web", "desktop_web", "android_native", "pepper", ...platforms]
            .filter((v, i, arr) => arr.indexOf(v) === i)
            .map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
        </select>
        <select value={productFilter} onChange={(e) => setProductFilter(e.target.value)}>
          <option value="">All products</option>
          {products.map((p) => (
            <option key={p.id} value={p.slug}>
              {p.display_name}
            </option>
          ))}
        </select>
        <button onClick={refresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
        <span className="muted">{sessions.length} session{sessions.length === 1 ? "" : "s"}</span>
      </div>

      {downloadError && <p className="error">{downloadError}</p>}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>Participant</th>
              <th>Platform</th>
              <th>Product</th>
              <th>Start</th>
              <th>Duration</th>
              <th>Status</th>
              <th>Turns</th>
              <th title="Turns asked by voice vs typed">Voice / Typed</th>
              <th>Errors</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.session_id} className={s.errors_logged > 0 ? "row-error" : ""}>
                <td className="mono" title={s.session_id}>
                  {s.session_id.slice(0, 8)}
                </td>
                <td className="mono">{s.participant_id}</td>
                <td>{s.platform}</td>
                <td>{s.product_slug}</td>
                <td>{new Date(s.start_time).toLocaleString()}</td>
                <td>{formatDuration(s.start_time, s.end_time)}</td>
                <td>
                  <span className={`status-badge ${s.end_time ? "status-complete" : "status-open"}`}>
                    {s.end_time ? "Completed" : "In progress"}
                  </span>
                </td>
                <td>{s.total_turns}</td>
                <td>
                  <span className="input-tag input-tag-voice">🎙 {s.voice_turns}</span>{" "}
                  <span className="input-tag input-tag-typed">⌨ {s.typed_turns}</span>
                </td>
                <td>{s.errors_logged > 0 ? <strong>{s.errors_logged}</strong> : s.errors_logged}</td>
                <td>
                  <button onClick={() => handleView(s)}>View</button>{" "}
                  <button onClick={() => handleExport(s.session_id)}>Export CSV</button>
                </td>
              </tr>
            ))}
            {sessions.length === 0 && !loading && (
              <tr>
                <td colSpan={11} className="muted">
                  No sessions recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {viewingSession && (
        <div className="modal-backdrop" onClick={closeView}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                Session <span className="mono">{viewingSession.session_id.slice(0, 8)}</span>{" "}
                <span className="muted">
                  ({viewingSession.platform}, {viewingSession.product_slug})
                </span>
              </h3>
              <button className="link-button" onClick={closeView}>
                Close
              </button>
            </div>
            <p className="muted">
              Participant {viewingSession.participant_id} - started {new Date(viewingSession.start_time).toLocaleString()}
            </p>
            {viewLoading && <p className="muted">Loading...</p>}
            {viewError && <p className="error">{viewError}</p>}
            {viewingTurns && viewingTurns.length === 0 && <p className="muted">No turns recorded for this session.</p>}
            {viewingTurns &&
              viewingTurns.map((t) => (
                <div key={t.turn_number} className={`chunk-card ${!t.in_scope ? "turn-deflected" : ""}`}>
                  <div className="chunk-header">
                    <strong>
                      #{t.turn_number}{" "}
                      <span
                        className={`input-tag ${
                          t.input_method === "voice"
                            ? "input-tag-voice"
                            : t.input_method === "typed"
                              ? "input-tag-typed"
                              : "input-tag-system"
                        }`}
                      >
                        {t.input_method === "voice" ? "🎙 voice" : t.input_method === "typed" ? "⌨ typed" : "⚙ system"}
                      </span>
                    </strong>
                    <span className="muted">
                      {t.latency_ms.toFixed(0)}ms · {new Date(t.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p>
                    <strong>Q:</strong> {t.query_text}
                  </p>
                  <p>
                    <strong>A{!t.in_scope ? " (deflected)" : ""}:</strong> {t.response_text}
                  </p>
                  {t.retrieved_chunk_ids.length > 0 && (
                    <p className="muted mono" style={{ fontSize: "0.75rem" }}>
                      chunks: {t.retrieved_chunk_ids.map((id) => id.slice(0, 8)).join(", ")}
                    </p>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}
    </section>
  );
}
