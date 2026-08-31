import { Button } from "../components/Button";

interface Props {
  onTellMe: () => void;
  onAskQuestion: () => void;
}

export function Welcome({ onTellMe, onAskQuestion }: Props) {
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
