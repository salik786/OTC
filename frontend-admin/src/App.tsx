import { useState } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import { Login } from "./pages/Login";
import { Documents } from "./pages/Documents";
import { TestRetrieval } from "./pages/TestRetrieval";
import { Sessions } from "./pages/Sessions";
import { Settings } from "./pages/Settings";

type Tab = "documents" | "retrieval" | "sessions" | "settings";

function AdminShell() {
  const { logout } = useAuth();
  const [tab, setTab] = useState<Tab>("documents");

  return (
    <div className="app-shell">
      <header>
        <h1>OTC Study Admin</h1>
        <button className="link-button" onClick={logout}>
          Log out
        </button>
      </header>
      <nav>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>
          Corpus
        </button>
        <button className={tab === "retrieval" ? "active" : ""} onClick={() => setTab("retrieval")}>
          Test Retrieval
        </button>
        <button className={tab === "sessions" ? "active" : ""} onClick={() => setTab("sessions")}>
          Sessions
        </button>
        <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>
          RAG Settings
        </button>
      </nav>
      <main>
        {tab === "documents" && <Documents />}
        {tab === "retrieval" && <TestRetrieval />}
        {tab === "sessions" && <Sessions />}
        {tab === "settings" && <Settings />}
      </main>
    </div>
  );
}

function Gate() {
  const { credentials, loading } = useAuth();
  if (loading) return <div className="app-shell">Loading...</div>;
  return credentials ? <AdminShell /> : <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
