type AvatarState = "idle" | "listening" | "speaking" | "thinking";

/** A Pepper-inspired robot: glossy white/grey shell (gradients + highlights for a plastic look),
 * a dark visor with lens-style eyes, and a chest light strip that animates to indicate state -
 * light-based feedback (like real voice assistants use) rather than a cartoon flapping mouth. */
export function AssistantAvatar({ state }: { state: AvatarState }) {
  return (
    <div className={`avatar avatar-${state}`} aria-hidden="true">
      <div className="avatar-pulse-ring" />
      <svg viewBox="0 0 240 280" className="avatar-svg">
        <defs>
          <linearGradient id="shellGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="55%" stopColor="#eef0f1" />
            <stop offset="100%" stopColor="#d3d7da" />
          </linearGradient>
          <linearGradient id="shellGradientSoft" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f7f8f9" />
            <stop offset="100%" stopColor="#dcdfe2" />
          </linearGradient>
          <radialGradient id="visorGradient" cx="35%" cy="30%" r="80%">
            <stop offset="0%" stopColor="#3a4348" />
            <stop offset="70%" stopColor="#1c2226" />
            <stop offset="100%" stopColor="#101315" />
          </radialGradient>
          <radialGradient id="eyeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffd9a0" />
            <stop offset="60%" stopColor="var(--color-accent)" />
            <stop offset="100%" stopColor="#93692b" />
          </radialGradient>
          <filter id="softShadow" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#1a2422" floodOpacity="0.22" />
          </filter>
        </defs>

        <ellipse cx="120" cy="266" rx="62" ry="10" className="avatar-ground-shadow" />

        <g filter="url(#softShadow)">
          {/* body / shoulders */}
          <path
            d="M 52 260 Q 50 180 80 165 L 160 165 Q 190 180 188 260 Z"
            fill="url(#shellGradient)"
            className="avatar-body"
          />
          <path d="M 62 258 Q 62 195 84 175" className="avatar-body-highlight" />

          {/* shoulder joints */}
          <circle cx="56" cy="190" r="10" fill="url(#shellGradientSoft)" className="avatar-joint" />
          <circle cx="184" cy="190" r="10" fill="url(#shellGradientSoft)" className="avatar-joint" />

          {/* chest panel */}
          <rect x="98" y="192" width="44" height="30" rx="6" fill="#14181a" />
          <rect x="104" y="200" width={10} height={5} rx="1.5" className="avatar-chest-bar avatar-chest-bar-1" />
          <rect x="117" y="200" width={10} height={5} rx="1.5" className="avatar-chest-bar avatar-chest-bar-2" />
          <rect x="130" y="200" width={4} height={5} rx="1.5" className="avatar-chest-bar avatar-chest-bar-3" />
          <rect x="104" y="209" width={4} height={5} rx="1.5" className="avatar-chest-bar avatar-chest-bar-2" />
          <rect x="111" y="209" width={16} height={5} rx="1.5" className="avatar-chest-bar avatar-chest-bar-1" />
          <rect x="130" y="209" width={4} height={5} rx="1.5" className="avatar-chest-bar avatar-chest-bar-3" />

          {/* neck */}
          <rect x="104" y="140" width="32" height="28" fill="url(#shellGradientSoft)" />

          {/* head shell */}
          <rect x="46" y="18" width="148" height="132" rx="46" fill="url(#shellGradient)" className="avatar-head-shell" />
          <ellipse cx="90" cy="46" rx="34" ry="16" className="avatar-head-highlight" />

          {/* side ear discs */}
          <circle cx="46" cy="78" r="13" fill="url(#shellGradientSoft)" className="avatar-ear" />
          <circle cx="194" cy="78" r="13" fill="url(#shellGradientSoft)" className="avatar-ear" />

          {/* visor */}
          <rect x="70" y="52" width="100" height="58" rx="20" fill="url(#visorGradient)" />
          <path d="M 80 60 Q 120 50 160 60" className="avatar-visor-highlight" />

          {/* eyes */}
          <circle cx="98" cy="82" r="8" fill="url(#eyeGlow)" className="avatar-eye" />
          <circle cx="142" cy="82" r="8" fill="url(#eyeGlow)" className="avatar-eye" />
          <circle cx="95" cy="79" r="2.2" className="avatar-eye-spark" />
          <circle cx="139" cy="79" r="2.2" className="avatar-eye-spark" />
        </g>
      </svg>
    </div>
  );
}
