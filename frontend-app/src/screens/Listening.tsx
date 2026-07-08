import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Waveform } from "../components/Waveform";
import { useSTT } from "../hooks/useSTT";
import type { InputMethod } from "../lib/api";

interface Props {
  onSubmit: (text: string, method: InputMethod) => void;
  onCancel: () => void;
}

export function Listening({ onSubmit, onCancel }: Props) {
  const stt = useSTT();
  const [mode, setMode] = useState<"voice" | "typed">("voice");
  const [typedText, setTypedText] = useState("");
  const startedRef = useRef(false);

  useEffect(() => {
    if (mode === "voice" && !startedRef.current) {
      startedRef.current = true;
      stt.start();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  async function handleMicTap() {
    if (stt.status === "recording") {
      const transcript = await stt.stop();
      if (transcript && transcript.trim()) {
        onSubmit(transcript.trim(), "voice");
      }
    } else if (stt.status === "idle") {
      startedRef.current = true;
      stt.start();
    }
  }

  function switchToTyped() {
    stt.cancel();
    setMode("typed");
  }

  function handleTypedSubmit() {
    if (typedText.trim()) onSubmit(typedText.trim(), "typed");
  }

  return (
    <div className="screen listening-screen">
      <div className="listening-content">
        {mode === "voice" ? (
          <>
            <Waveform active={stt.status === "recording"} />
            <p className="listening-status" aria-live="polite">
              {stt.status === "recording" && "Listening... tap the microphone when you're done."}
              {stt.status === "transcribing" && "Got it - one moment..."}
              {stt.status === "idle" && "Tap the microphone to start."}
              {stt.status === "error" && (stt.error ?? "Something went wrong.")}
            </p>
            <button
              className="mic-button"
              onClick={handleMicTap}
              disabled={stt.status === "transcribing"}
              aria-label={stt.status === "recording" ? "Stop and send" : "Start listening"}
            >
              🎙
            </button>
            <button className="link-button" onClick={switchToTyped}>
              Type instead
            </button>
          </>
        ) : (
          <div className="typed-fallback">
            <label htmlFor="typed-question">Type your question</label>
            <input
              id="typed-question"
              type="text"
              value={typedText}
              onChange={(e) => setTypedText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTypedSubmit()}
              autoFocus
            />
            <Button variant="primary" onClick={handleTypedSubmit} disabled={!typedText.trim()}>
              Ask
            </Button>
          </div>
        )}
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
