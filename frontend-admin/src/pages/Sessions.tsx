import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { api, authHeader, type SessionSummary } from "../lib/api";

export function Sessions() {
  const { credentials } = useAuth();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    if (!credentials) return;
    api.listSessions(credentials).then(setSessions);
  }, [credentials]);

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

  return (
    <section>
      <h2>Recent Sessions</h2>
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
              <th>Turns</th>
              <th>Errors</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.session_id}>
                <td className="mono">{s.session_id.slice(0, 8)}</td>
                <td className="mono">{s.participant_id}</td>
                <td>{s.platform}</td>
                <td>{s.product_slug}</td>
                <td>{new Date(s.start_time).toLocaleString()}</td>
                <td>{s.total_turns}</td>
                <td>{s.errors_logged}</td>
                <td>
                  <button onClick={() => handleExport(s.session_id)}>Export CSV</button>
                </td>
              </tr>
            ))}
            {sessions.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  No sessions recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
