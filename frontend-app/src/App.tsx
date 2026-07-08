import { useEffect, useState } from "react";
import { ResearcherSetup } from "./screens/ResearcherSetup";
import { Welcome } from "./screens/Welcome";
import { Listening } from "./screens/Listening";
import { CoreInfo } from "./screens/CoreInfo";
import { QandA } from "./screens/QandA";
import { Closing } from "./screens/Closing";
import { useSession } from "./hooks/useSession";
import { useTTS } from "./hooks/useTTS";
import { api, type InputMethod } from "./lib/api";
import type { QATurn, Screen } from "./types";

export default function App() {
  const { session, error: sessionError, startSession, endSession } = useSession();
  const answerTts = useTTS();

  const [screen, setScreen] = useState<Screen>("setup");
  const [starting, setStarting] = useState(false);
  const [qaHistory, setQaHistory] = useState<QATurn[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [listeningReturnTo, setListeningReturnTo] = useState<"welcome" | "qa">("welcome");
  const [ended, setEnded] = useState(false);

  // Each screen is a fresh full-height view - without this, scroll position from a taller
  // previous screen (e.g. Core Info) leaks into the next one, hiding its top content.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [screen]);

  async function handleStart(productSlug: string) {
    setStarting(true);
    const started = await startSession(productSlug);
    setStarting(false);
    if (started) setScreen("welcome");
  }

  async function submitQuery(text: string, method: InputMethod) {
    if (!session || ended) return;
    setSubmitting(true);
    setScreen("qa");
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

  function openListening(returnTo: "welcome" | "qa") {
    setListeningReturnTo(returnTo);
    setScreen("listening");
  }

  async function handleEndSession() {
    if (ended) return; // kiosk dead-end guard: never re-enter the session once closed
    setEnded(true);
    await endSession();
  }

  return (
    <>
      {screen === "setup" && <ResearcherSetup onStart={handleStart} starting={starting} error={sessionError} />}

      {screen === "welcome" && session && (
        <Welcome onTellMe={() => setScreen("core-info")} onAskQuestion={() => openListening("welcome")} />
      )}

      {screen === "listening" && (
        <Listening
          onSubmit={(text, method) => submitQuery(text, method)}
          onCancel={() => setScreen(listeningReturnTo)}
        />
      )}

      {screen === "core-info" && session && (
        <CoreInfo
          sessionId={session.session_id}
          productDisplayName={session.product_display_name}
          onAskQuestion={() => setScreen("qa")}
        />
      )}

      {screen === "qa" && (
        <QandA
          history={qaHistory}
          submitting={submitting}
          onSubmitTyped={(text) => submitQuery(text, "typed")}
          onOpenListening={() => openListening("qa")}
          onEndSession={() => setScreen("closing")}
        />
      )}

      {screen === "closing" && <Closing onSessionEnd={handleEndSession} />}
    </>
  );
}
