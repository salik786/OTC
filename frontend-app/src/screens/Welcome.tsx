import { useEffect, useRef } from "react";
import { Button } from "../components/Button";
import { useTTS } from "../hooks/useTTS";

const GREETING =
  "Hello! I am an AI assistant here to help you understand this medicine. I can tell you what it is used for, how to take it, and any important warnings from the packaging. I am not a pharmacist and cannot give personal health advice. Tap the microphone button or type your question to get started. Or tap 'Tell me about this medicine' to hear a full explanation.";

interface Props {
  onTellMe: () => void;
  onAskQuestion: () => void;
}

export function Welcome({ onTellMe, onAskQuestion }: Props) {
  const { speak } = useTTS();
  const spokenRef = useRef(false);

  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;
    speak(GREETING);
  }, [speak]);

  return (
    <div className="screen welcome-screen">
      <div className="welcome-content">
        <h1>Hello!</h1>
        <p className="lede">
          I'm here to help you understand this medicine - what it's used for, how to take it, and any important
          warnings from the packaging.
        </p>
        <p className="muted">I'm not a pharmacist and can't give personal health advice.</p>
        <div className="welcome-actions">
          <Button variant="primary" onClick={onTellMe}>
            Tell me about this medicine
          </Button>
          <Button variant="secondary" onClick={onAskQuestion} aria-label="Ask a question by voice or typing">
            <span className="mic-icon" aria-hidden="true">
              🎙
            </span>
            Ask a question
          </Button>
        </div>
      </div>
    </div>
  );
}
