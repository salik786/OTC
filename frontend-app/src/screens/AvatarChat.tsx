import { useEffect, useRef, useState } from "react";
import { TopNav } from "../components/TopNav";
import { Button } from "../components/Button";
import { AssistantAvatar } from "../components/AssistantAvatar";
import { useConversation } from "../hooks/useConversation";
import type { SessionStartResponse } from "../lib/api";

interface Props {
  session: SessionStartResponse;
  onBack: () => void;
  onEndSession: () => void;
}

/** Live conversation mode: the avatar is the focus (like a voice-assistant app), with a compact
 * running transcript always visible on the side rather than one big "tap to talk" interaction. */
export function AvatarChat({ session, onBack, onEndSession }: Props) {
  const conv = useConversation(session);
  const [showTyped, setShowTyped] = useState(false);
  const [typedText, setTypedText] = useState("");
  const transcriptRef = useRef<HTMLDivElement>(null);

  // Once the participant taps the mic the first time, the conversation goes hands-free: after
  // each answer finishes speaking, listening resumes automatically (like GPT voice mode) instead
  // of requiring another tap. Turned off by switching to typed input, or ending/leaving the screen.
  const voiceModeActiveRef = useRef(false);
  const wasSpeakingRef = useRef(false);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
  }, [conv.history.length]);

  useEffect(() => {
    const justStoppedSpeaking = wasSpeakingRef.current && !conv.isSpeaking;
    wasSpeakingRef.current = conv.isSpeaking;
    if (justStoppedSpeaking && voiceModeActiveRef.current && conv.sttStatus === "idle" && !showTyped) {
      conv.startVoice();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv.isSpeaking]);

  useEffect(() => {
    return () => {
      voiceModeActiveRef.current = false;
    };
  }, []);

  const avatarState =
    conv.sttStatus === "recording" ? "listening" : conv.submitting ? "thinking" : conv.isSpeaking ? "speaking" : "idle";

  async function handleMicTap() {
    if (conv.sttStatus === "recording") {
      await conv.stopVoiceAndSubmit();
    } else if (conv.sttStatus === "idle") {
      voiceModeActiveRef.current = true;
      conv.startVoice();
    }
  }

  function handleTypedSubmit() {
    if (!typedText.trim() || conv.submitting) return;
    conv.submitText(typedText.trim(), "typed");
    setTypedText("");
  }

  let statusText = "Tap the microphone to talk to me.";
  if (conv.sttStatus === "recording") statusText = "Listening...";
  else if (conv.sttStatus === "transcribing") statusText = "Got it - one moment...";
  else if (conv.submitting) statusText = "Thinking...";
  else if (conv.isSpeaking) statusText = "Speaking...";
  else if (conv.sttError) statusText = conv.sttError;

  function handleStop() {
    voiceModeActiveRef.current = false;
    conv.stopSpeaking();
  }

  return (
    <div className="screen avatar-screen">
      <TopNav onBack={onBack} />
      <div className="avatar-layout">
        <div className="avatar-main">
          <AssistantAvatar state={avatarState} />
          <p className="avatar-status" aria-live="polite">{statusText}</p>

          {conv.isSpeaking ? (
            <div className="avatar-dock">
              <button className="mic-button-compact mic-stop" onClick={handleStop} aria-label="Stop speaking">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <rect x="4" y="4" width="12" height="12" rx="2" />
                </svg>
              </button>
              <span className="muted">Stop</span>
            </div>
          ) : !showTyped ? (
            <div className="avatar-dock">
              <button
                className={`mic-button-compact ${conv.sttStatus === "recording" ? "mic-recording" : ""}`}
                onClick={handleMicTap}
                disabled={conv.sttStatus === "transcribing" || conv.submitting}
                aria-label={conv.sttStatus === "recording" ? "Stop and send" : "Start talking"}
              >
                <svg width="24" height="24" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
                  <rect x="7" y="2.5" width="6" height="10" rx="3" />
                  <path d="M4.5 9.5a5.5 5.5 0 0011 0M10 15v2.5M7 17.5h6" strokeLinecap="round" />
                </svg>
              </button>
              <button
                className="link-button"
                onClick={() => {
                  voiceModeActiveRef.current = false;
                  conv.cancelVoice();
                  setShowTyped(true);
                }}
              >
                Type instead
              </button>
            </div>
          ) : (
            <div className="avatar-dock">
              <input
                type="text"
                value={typedText}
                placeholder="Type your question"
                onChange={(e) => setTypedText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleTypedSubmit()}
                autoFocus
                aria-label="Type your question"
              />
              <Button variant="primary" onClick={handleTypedSubmit} disabled={!typedText.trim()}>
                Ask
              </Button>
              <button className="link-button" onClick={() => setShowTyped(false)}>
                Use voice
              </button>
            </div>
          )}

          <Button variant="ghost" onClick={onEndSession} className="avatar-end-session">
            I'm done - end session
          </Button>
        </div>

        <div className="avatar-transcript-panel" ref={transcriptRef} aria-live="polite">
          {conv.history.length === 0 && (
            <p className="muted avatar-transcript-empty">Your conversation will appear here.</p>
          )}
          {conv.history.map((turn) => (
            <div
              key={turn.turnNumber}
              className={`avatar-transcript-turn ${!turn.inScope ? "avatar-transcript-deflected" : ""}`}
            >
              <div className="avatar-transcript-bubble avatar-transcript-question">{turn.queryText}</div>
              <div className="avatar-transcript-bubble avatar-transcript-answer">{turn.answerText}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
