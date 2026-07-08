import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ResearcherSetup } from "./screens/ResearcherSetup";
import { Welcome } from "./screens/Welcome";
import { Listening } from "./screens/Listening";
import { CoreInfo } from "./screens/CoreInfo";
import { QandA } from "./screens/QandA";
import { Closing } from "./screens/Closing";
import { useSession } from "./hooks/useSession";
import { useTTS, stopAllSpeech } from "./hooks/useTTS";
import { api, type InputMethod, type SessionStartResponse } from "./lib/api";
import type { QATurn } from "./types";

/** Stops any in-flight TTS and resets scroll on every route change - without this, audio started
 * on one screen kept playing after navigating away (confirmed bug). */
function NavigationEffects() {
  const location = useLocation();
  useEffect(() => {
    stopAllSpeech();
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return null;
}

/** Traps the browser back button on the Closing screen - kiosk sessions must be a dead end,
 * not re-enterable once closed. */
function useBackNavigationTrap(active: boolean) {
  useEffect(() => {
    if (!active) return;
    window.history.pushState(null, "", window.location.href);
    const handler = () => window.history.pushState(null, "", window.location.href);
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, [active]);
}

function RequireSession({ session, children }: { session: SessionStartResponse | null; children: React.ReactNode }) {
  if (!session) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function AppRoot() {
  return (
    <BrowserRouter>
      <NavigationEffects />
      <App />
    </BrowserRouter>
  );
}

function App() {
  const navigate = useNavigate();
  const { session, error: sessionError, startSession, endSession } = useSession();
  const answerTts = useTTS();

  const [starting, setStarting] = useState(false);
  const [qaHistory, setQaHistory] = useState<QATurn[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [listeningReturnTo, setListeningReturnTo] = useState<"/welcome" | "/qa">("/welcome");
  const [ended, setEnded] = useState(false);

  useBackNavigationTrap(ended);

  async function handleStart(productSlug: string) {
    setStarting(true);
    const started = await startSession(productSlug);
    setStarting(false);
    if (started) navigate("/welcome");
  }

  async function submitQuery(text: string, method: InputMethod) {
    if (!session || ended) return;
    setSubmitting(true);
    navigate("/qa");
    try {
      const res = await api.query(session.session_id, text, method);
      setQaHistory((h) => [
        ...h,
        { turnNumber: res.turn_number, queryText: text, answerText: res.answer_text, inScope: res.in_scope },
      ]);
      answerTts.speak(res.answer_text);
    } catch {
      setQaHistory((h) => [
        ...h,
        {
          turnNumber: h.length + 1,
          queryText: text,
          answerText: "Sorry, something went wrong reaching the system. Please try again.",
          inScope: false,
        },
      ]);
    } finally {
      setSubmitting(false);
    }
  }

  function openListening(returnTo: "/welcome" | "/qa") {
    setListeningReturnTo(returnTo);
    navigate("/listening");
  }

  async function handleEndSession() {
    if (ended) return; // kiosk dead-end guard: never re-enter the session once closed
    setEnded(true);
    await endSession();
  }

  return (
    <Routes>
      <Route path="/" element={<ResearcherSetup onStart={handleStart} starting={starting} error={sessionError} />} />

      <Route
        path="/welcome"
        element={
          <RequireSession session={session}>
            <Welcome onTellMe={() => navigate("/core-info")} onAskQuestion={() => openListening("/welcome")} />
          </RequireSession>
        }
      />

      <Route
        path="/listening"
        element={
          <RequireSession session={session}>
            <Listening
              onSubmit={(text, method) => submitQuery(text, method)}
              onCancel={() => navigate(listeningReturnTo)}
            />
          </RequireSession>
        }
      />

      <Route
        path="/core-info"
        element={
          <RequireSession session={session}>
            {session && (
              <CoreInfo
                sessionId={session.session_id}
                productDisplayName={session.product_display_name}
                onAskQuestion={() => navigate("/qa")}
              />
            )}
          </RequireSession>
        }
      />

      <Route
        path="/qa"
        element={
          <RequireSession session={session}>
            <QandA
              history={qaHistory}
              submitting={submitting}
              onSubmitTyped={(text) => submitQuery(text, "typed")}
              onOpenListening={() => openListening("/qa")}
              onEndSession={() => navigate("/closing")}
            />
          </RequireSession>
        }
      />

      <Route
        path="/closing"
        element={
          <RequireSession session={session}>
            <Closing onSessionEnd={handleEndSession} />
          </RequireSession>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
