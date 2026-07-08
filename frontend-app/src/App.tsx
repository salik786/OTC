import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ResearcherSetup } from "./screens/ResearcherSetup";
import { Welcome } from "./screens/Welcome";
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

  async function handleStart(productSlug: string) {
    setStarting(true);
    const started = await startSession(productSlug);
    setStarting(false);
    if (started) navigate("/welcome");
  }

  async function handleEndSession() {
    if (ended) return; // kiosk dead-end guard: never re-enter the session once closed
    setEnded(true);
    await endSession();
    navigate("/closing");
  }

  return (
    <Routes>
      <Route path="/" element={<ResearcherSetup onStart={handleStart} starting={starting} error={sessionError} />} />

      <Route
        path="/welcome"
        element={
          <RequireSession session={session}>
            <Welcome onTellMe={() => navigate("/core-info")} onAskQuestion={() => navigate("/mode-select")} />
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
              onBack={() => navigate("/welcome")}
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
              <VoiceTextChat session={session} onBack={() => navigate("/mode-select")} onEndSession={handleEndSession} />
            )}
          </RequireSession>
        }
      />

      <Route
        path="/avatar"
        element={
          <RequireSession session={session}>
            {session && (
              <AvatarChat session={session} onBack={() => navigate("/mode-select")} onEndSession={handleEndSession} />
            )}
          </RequireSession>
        }
      />

      <Route
        path="/closing"
        element={
          <RequireSession session={session}>
            <Closing onSessionEnd={() => {}} />
          </RequireSession>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
