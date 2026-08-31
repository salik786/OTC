import { TopNav } from "../components/TopNav";

interface Props {
  onBack: () => void;
  onChooseChat: () => void;
  onChooseAvatar: () => void;
}

function ChatBubbleIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 5h16v11H9l-4 4V5Z" />
      <line x1="8" y1="9" x2="16" y2="9" />
      <line x1="8" y1="12.5" x2="13" y2="12.5" />
    </svg>
  );
}

function AssistantIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="8" y="3" width="8" height="12" rx="4" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
      <line x1="12" y1="17.5" x2="12" y2="21" />
      <line x1="8.5" y1="21" x2="15.5" y2="21" />
    </svg>
  );
}

export function ModeSelect({ onBack, onChooseChat, onChooseAvatar }: Props) {
  return (
    <div className="screen mode-select-screen">
      <TopNav onBack={onBack} />
      <div className="mode-select-content">
        <h1>How would you like to ask?</h1>
        <p className="lede">Choose whichever feels more comfortable - you can talk or type either way.</p>
        <div className="mode-cards">
          <button className="mode-card" onClick={onChooseChat}>
            <span className="mode-card-icon" aria-hidden="true">
              <ChatBubbleIcon />
            </span>
            <span className="mode-card-title">Voice &amp; Text Chat</span>
            <span className="mode-card-desc">See your conversation as you go, type or talk anytime.</span>
          </button>
          <button className="mode-card" onClick={onChooseAvatar}>
            <span className="mode-card-icon" aria-hidden="true">
              <AssistantIcon />
            </span>
            <span className="mode-card-title">Talk to the Assistant</span>
            <span className="mode-card-desc">A friendly assistant you can speak with directly.</span>
          </button>
        </div>
      </div>
    </div>
  );
}
