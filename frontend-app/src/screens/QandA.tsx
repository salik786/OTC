import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import type { QATurn } from "../types";

interface Props {
  history: QATurn[];
  submitting: boolean;
  onSubmitTyped: (text: string) => void;
  onOpenListening: () => void;
  onEndSession: () => void;
}

export function QandA({ history, submitting, onSubmitTyped, onOpenListening, onEndSession }: Props) {
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [history.length]);

  function handleSubmit() {
    if (!text.trim() || submitting) return;
    onSubmitTyped(text.trim());
    setText("");
  }

  return (
    <div className="screen qa-screen">
      <div className="qa-history" ref={listRef} aria-live="polite">
        {history.length === 0 && (
          <p className="muted qa-empty">Ask anything about this medicine - by voice or by typing below.</p>
        )}
        {history.map((turn) => (
          <div key={turn.turnNumber} className="qa-turn">
            <div className="qa-bubble qa-bubble-participant">{turn.queryText}</div>
            <div className={`qa-bubble qa-bubble-system ${turn.inScope ? "" : "qa-bubble-deflected"}`}>
              {!turn.inScope && <span className="deflect-tag">Outside what I can help with</span>}
              {turn.answerText}
            </div>
          </div>
        ))}
        {submitting && (
          <div className="qa-turn">
            <div className="qa-bubble qa-bubble-system qa-bubble-loading">Thinking...</div>
          </div>
        )}
      </div>

      <div className="qa-input-bar">
        <input
          type="text"
          value={text}
          placeholder="Type your question"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          aria-label="Type your question"
        />
        <button className="mic-button-small" onClick={onOpenListening} aria-label="Ask by voice">
          🎙
        </button>
        <Button variant="primary" onClick={handleSubmit} disabled={!text.trim() || submitting}>
          Ask
        </Button>
      </div>

      <Button variant="ghost" onClick={onEndSession} className="end-session-btn">
        I'm done - end session
      </Button>
    </div>
  );
}
