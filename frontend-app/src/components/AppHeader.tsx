interface Props {
  /** Chat/avatar screens need the header compact so it doesn't eat into conversation space. */
  compact?: boolean;
  /** Closing/listening screens use a solid dark-teal background - the default teal-on-light
   * logo/wordmark would be invisible on it, so this swaps to a white-on-dark treatment. */
  light?: boolean;
}

/** Shared brand header (logo mark, wordmark, tagline, decorative heartbeat divider) rendered at
 * the top of every screen so the "MedCheck" identity is consistent app-wide, not redrawn ad hoc
 * per screen. Not a heading itself - each screen keeps its own <h1> for its actual content, so
 * this stays out of the page's heading hierarchy. */
export function AppHeader({ compact = false, light = false }: Props) {
  const strokeColor = light ? "white" : "var(--color-primary)";
  return (
    <div className={`brand-header ${compact ? "brand-header-compact" : ""} ${light ? "brand-header-light" : ""}`.trim()}>
      <div className="brand-header-row">
        <svg className="brand-logo" width={compact ? 28 : 40} height={compact ? 28 : 40} viewBox="0 0 40 40" aria-hidden="true">
          <path
            d="M20 33 C10 26 4 20 4 13.5 C4 8.5 8 5 12.5 5 C15.7 5 18.3 6.7 20 9.3 C21.7 6.7 24.3 5 27.5 5 C32 5 36 8.5 36 13.5 C36 20 30 26 20 33 Z"
            fill="none"
            stroke={strokeColor}
            strokeWidth="2.6"
            strokeLinejoin="round"
          />
          <path d="M20 13v14M13 20h14" stroke={strokeColor} strokeWidth="2.6" strokeLinecap="round" />
        </svg>
        <div className="brand-wordmark-block">
          <span className="brand-wordmark">MedCheck</span>
          {!compact && <span className="brand-tagline">Smarter Medicine Decisions</span>}
        </div>
      </div>
      {!compact && (
        <svg className="brand-heartbeat" viewBox="0 0 400 24" preserveAspectRatio="none" aria-hidden="true">
          <path
            d="M0 12 H150 L165 2 L180 22 L195 6 L207 12 H400"
            fill="none"
            stroke={light ? "rgba(255,255,255,0.6)" : "var(--color-primary-light)"}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </div>
  );
}
