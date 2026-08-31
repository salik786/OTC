interface Props {
  onClick: () => void;
  label?: string;
}

export function BackButton({ onClick, label = "Back" }: Props) {
  return (
    <button className="back-button" onClick={onClick} aria-label={label}>
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 4L6 10l6 6" />
      </svg>
      {label}
    </button>
  );
}
