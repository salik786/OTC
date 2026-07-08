import { BackButton } from "../components/BackButton";

interface Props {
  onBack: () => void;
  onChooseChat: () => void;
  onChooseAvatar: () => void;
}

export function ModeSelect({ onBack, onChooseChat, onChooseAvatar }: Props) {
  return (
    <div className="screen mode-select-screen">
      <BackButton onClick={onBack} />
      <div className="mode-select-content">
        <h1>How would you like to ask?</h1>
        <p className="lede">Choose whichever feels more comfortable - you can talk or type either way.</p>
        <div className="mode-cards">
          <button className="mode-card" onClick={onChooseChat}>
            <span className="mode-card-icon" aria-hidden="true">💬</span>
            <span className="mode-card-title">Voice &amp; Text Chat</span>
            <span className="mode-card-desc">See your conversation as you go, type or talk anytime.</span>
          </button>
          <button className="mode-card" onClick={onChooseAvatar}>
            <span className="mode-card-icon" aria-hidden="true">🎙️</span>
            <span className="mode-card-title">Talk to the Assistant</span>
            <span className="mode-card-desc">A friendly assistant you can speak with directly.</span>
          </button>
        </div>
      </div>
    </div>
  );
}
