import { useEffect, useRef, useState } from "react";
import { BackButton } from "../components/BackButton";
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
      <BackButton onClick={onBack} />
      <div className="avatar-layout">
        <div className="avatar-main">
          <AssistantAvatar state={avatarState} />
          <p className="avatar-status" aria-live="polite">{statusText}</p>

          {conv.isSpeaking ? (
            <div className="avatar-dock">
              <button className="mic-button-compact mic-stop" onClick={handleStop} aria-label="Stop speaking">
                ⏹
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
                🎙
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
