import { useEffect, useRef, useState } from "react";
import { TopNav } from "../components/TopNav";
import { Button } from "../components/Button";
import { Waveform } from "../components/Waveform";
import { useConversation } from "../hooks/useConversation";
import { useLoadingMessage } from "../hooks/useLoadingMessage";
import type { SessionStartResponse } from "../lib/api";

interface Props {
  session: SessionStartResponse;
  onBack: () => void;
  onEndSession: () => void;
}

/** Voice + text chat: one persistent screen where the transcript is always visible while the
 * participant talks or types - no separate full-screen "listening" takeover. Once voice is
 * started, it's hands-free (like GPT voice mode): each answer auto-resumes listening until the
 * participant types instead, taps Stop, or ends the session. */
export function VoiceTextChat({ session, onBack, onEndSession }: Props) {
  const conv = useConversation(session);
  const loadingMessage = useLoadingMessage(conv.submitting);
  const [typedText, setTypedText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const voiceModeActiveRef = useRef(false);
  const wasSpeakingRef = useRef(false);

  // Answers now stream in - the same turn's answerText grows in place rather than history
  // gaining a new entry per word, so scrolling only on history.length changing meant the view
  // stayed pinned wherever it was while the answer kept extending past the visible area. Total
  // answer character count across history changes on every streamed chunk, which keeps this
  // effect (and the scroll it does) firing as the text grows, not just once per turn.
  const totalAnswerChars = conv.history.reduce((sum, t) => sum + t.answerText.length, 0);
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [conv.history.length, totalAnswerChars, conv.sttStatus]);

  useEffect(() => {
    const justStoppedSpeaking = wasSpeakingRef.current && !conv.isSpeaking;
    wasSpeakingRef.current = conv.isSpeaking;
    if (justStoppedSpeaking && voiceModeActiveRef.current && conv.sttStatus === "idle") {
      conv.startVoice();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv.isSpeaking]);

  useEffect(() => {
    return () => {
      voiceModeActiveRef.current = false;
    };
  }, []);

  function handleTypedSubmit() {
    if (!typedText.trim() || conv.submitting) return;
    voiceModeActiveRef.current = false; // typing opts back out of the hands-free voice loop
    conv.submitText(typedText.trim(), "typed");
    setTypedText("");
  }

  async function handleMicTap() {
    if (conv.sttStatus === "recording") {
      await conv.stopVoiceAndSubmit();
    } else if (conv.sttStatus === "idle") {
      voiceModeActiveRef.current = true;
      conv.startVoice();
    }
  }

  function handleStop() {
    voiceModeActiveRef.current = false;
    conv.stopSpeaking();
  }

  return (
    <div className="screen chat-screen">
      <TopNav onBack={onBack} />
      <div className="chat-layout">
        <div className="chat-history" ref={listRef} aria-live="polite">
          {conv.history.length === 0 && conv.sttStatus === "idle" && (
            <p className="muted qa-empty">Ask anything about this medicine - by voice or by typing below.</p>
          )}
          {conv.history.map((turn, i) => (
            <div key={i} className="qa-turn">
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
              <div className="qa-bubble qa-bubble-system qa-bubble-loading">{loadingMessage}</div>
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
          {conv.isSpeaking ? (
            <button className="mic-button-small mic-stop" onClick={handleStop} aria-label="Stop speaking">
              <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <rect x="4" y="4" width="12" height="12" rx="2" />
              </svg>
            </button>
          ) : (
            <button
              className={`mic-button-small ${conv.sttStatus === "recording" ? "mic-recording" : ""}`}
              onClick={handleMicTap}
              disabled={conv.sttStatus === "transcribing"}
              aria-label={conv.sttStatus === "recording" ? "Stop and send" : "Ask by voice"}
            >
              <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
                <rect x="7" y="2.5" width="6" height="10" rx="3" />
                <path d="M4.5 9.5a5.5 5.5 0 0011 0M10 15v2.5M7 17.5h6" strokeLinecap="round" />
              </svg>
            </button>
          )}
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
