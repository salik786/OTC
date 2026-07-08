type AvatarState = "idle" | "listening" | "speaking" | "thinking";

/** Abstract animated orb (no face) - a professional, non-representational voice indicator like
 * ChatGPT/Siri voice mode use, rather than a cartoon character. A literal robot face read as
 * alien-like regardless of styling and doesn't fit a healthcare tool serving patients of all ages. */
export function AssistantAvatar({ state }: { state: AvatarState }) {
  return (
    <div className={`orb orb-${state}`} aria-hidden="true">
      <div className="orb-ring orb-ring-outer" />
      <div className="orb-ring orb-ring-inner" />
      <div className="orb-core">
        <span className="orb-bar orb-bar-1" />
        <span className="orb-bar orb-bar-2" />
        <span className="orb-bar orb-bar-3" />
        <span className="orb-bar orb-bar-4" />
        <span className="orb-bar orb-bar-5" />
      </div>
    </div>
  );
}
