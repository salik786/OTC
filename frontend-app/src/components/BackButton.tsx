interface Props {
  onClick: () => void;
  label?: string;
}

export function BackButton({ onClick, label = "Back" }: Props) {
  return (
    <button className="back-button" onClick={onClick} aria-label={label}>
      <span aria-hidden="true">←</span> {label}
    </button>
  );
}
