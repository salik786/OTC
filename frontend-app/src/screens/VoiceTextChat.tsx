import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Waveform } from "../components/Waveform";
import { useConversation } from "../hooks/useConversation";
import type { SessionStartResponse } from "../lib/api";

interface Props {
  session: SessionStartResponse;
  onEndSession: () => void;
}

/** Voice + text chat: one persistent screen where the transcript is always visible while the
 * participant talks or types - no separate full-screen "listening" takeover. */
export function VoiceTextChat({ session, onEndSession }: Props) {
  const conv = useConversation(session);
  const [typedText, setTypedText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [conv.history.length, conv.sttStatus]);

  function handleTypedSubmit() {
    if (!typedText.trim() || conv.submitting) return;
    conv.submitText(typedText.trim(), "typed");
    setTypedText("");
  }

  async function handleMicTap() {
    if (conv.sttStatus === "recording") {
      await conv.stopVoiceAndSubmit();
    } else if (conv.sttStatus === "idle") {
      conv.startVoice();
    }
  }

  return (
    <div className="screen chat-screen">
      <div className="chat-layout">
        <div className="chat-history" ref={listRef} aria-live="polite">
          {conv.history.length === 0 && conv.sttStatus === "idle" && (
            <p className="muted qa-empty">Ask anything about this medicine - by voice or by typing below.</p>
          )}
          {conv.history.map((turn) => (
            <div key={turn.turnNumber} className="qa-turn">
              <div className="qa-bubble qa-bubble-participant">{turn.queryText}</div>
              <div className={`qa-bubble qa-bubble-system ${turn.inScope ? "" : "qa-bubble-deflected"}`}>
                {!turn.inScope && <span className="deflect-tag">Outside what I can help with</span>}
                {turn.answerText}
              </div>
            </div>
          ))}
          {conv.sttStatus === "recording" && (
            <div className="chat-live-transcript">
              <Waveform active={true} />
              <p className="muted">Listening... tap the microphone when you're done.</p>
            </div>
          )}
          {conv.submitting && (
            <div className="qa-turn">
              <div className="qa-bubble qa-bubble-system qa-bubble-loading">Thinking...</div>
            </div>
          )}
          {conv.sttError && <p className="error-text">{conv.sttError}</p>}
        </div>

        <div className="chat-input-bar">
          <input
            type="text"
            value={typedText}
            placeholder="Type your question"
            onChange={(e) => setTypedText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleTypedSubmit()}
            aria-label="Type your question"
          />
          <button
            className={`mic-button-small ${conv.sttStatus === "recording" ? "mic-recording" : ""}`}
            onClick={handleMicTap}
            disabled={conv.sttStatus === "transcribing"}
            aria-label={conv.sttStatus === "recording" ? "Stop and send" : "Ask by voice"}
          >
            🎙
          </button>
          <Button variant="primary" onClick={handleTypedSubmit} disabled={!typedText.trim() || conv.submitting}>
            Ask
          </Button>
        </div>

        <Button variant="ghost" onClick={onEndSession} className="end-session-btn">
          I'm done - end session
        </Button>
      </div>
    </div>
  );
}
