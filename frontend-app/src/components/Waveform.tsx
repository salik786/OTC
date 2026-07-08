export function Waveform({ active }: { active: boolean }) {
  const bars = Array.from({ length: 5 });
  return (
    <div className={`waveform ${active ? "waveform-active" : ""}`} aria-hidden="true">
      {bars.map((_, i) => (
        <span key={i} className="waveform-bar" style={{ animationDelay: `${i * 0.12}s` }} />
      ))}
    </div>
  );
}
