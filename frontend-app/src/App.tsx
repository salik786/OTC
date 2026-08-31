import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ResearcherSetup } from "./screens/ResearcherSetup";
import { ModeSelect } from "./screens/ModeSelect";
import { VoiceTextChat } from "./screens/VoiceTextChat";
import { AvatarChat } from "./screens/AvatarChat";
import { CoreInfo } from "./screens/CoreInfo";
import { Closing } from "./screens/Closing";
import { useSession } from "./hooks/useSession";
import { stopAllSpeech } from "./hooks/useTTS";
import type { SessionStartResponse } from "./lib/api";

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
  const [starting, setStarting] = useState(false);
  const [ended, setEnded] = useState(false);

  useBackNavigationTrap(ended);

  async function handleTellMe(productSlug: string) {
    setEnded(false); // fresh session - re-arm the end-of-session guard for this participant
    setStarting(true);
    const started = await startSession(productSlug);
    setStarting(false);
    if (started) navigate("/core-info");
  }

  async function handleAskQuestion(productSlug: string) {
    setEnded(false);
    setStarting(true);
    const started = await startSession(productSlug);
    setStarting(false);
    if (started) navigate("/mode-select");
  }

  function handleEndSession() {
    if (ended) return; // guard: don't re-trigger while already closing
    setEnded(true);
    navigate("/closing"); // navigate immediately - Closing shows its own "saving" state
  }

  function handleResetToStart() {
    setEnded(false);
    navigate("/");
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <ResearcherSetup onTellMe={handleTellMe} onAskQuestion={handleAskQuestion} starting={starting} error={sessionError} />
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
                onBack={() => navigate("/")}
                onAskQuestion={() => navigate("/mode-select")}
              />
            )}
          </RequireSession>
        }
      />

      <Route
        path="/mode-select"
        element={
          <RequireSession session={session}>
            <ModeSelect
              onBack={() => navigate("/")}
              onChooseChat={() => navigate("/chat")}
              onChooseAvatar={() => navigate("/avatar")}
            />
          </RequireSession>
        }
      />

      <Route
        path="/chat"
        element={
          <RequireSession session={session}>
            {session && (
              <VoiceTextChat
                session={session}
                onBack={() => navigate("/mode-select")}
                onEndSession={handleEndSession}
              />
            )}
          </RequireSession>
        }
      />

      <Route
        path="/avatar"
        element={
          <RequireSession session={session}>
            {session && (
              <AvatarChat
                session={session}
                onBack={() => navigate("/mode-select")}
                onEndSession={handleEndSession}
              />
            )}
          </RequireSession>
        }
      />

      <Route
        path="/closing"
        element={
          <RequireSession session={session}>
            <Closing onSave={endSession} onDone={handleResetToStart} />
          </RequireSession>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
