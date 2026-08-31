import { AppHeader } from "./AppHeader";
import { BackButton } from "./BackButton";

interface Props {
  onBack: () => void;
}

/** Back button and brand header laid out as a true flex row (not independently positioned
 * elements) so the centered "MedCheck" wordmark gets exactly the space left over after the back
 * button, and can never visually collide with it - centering within the full screen width looks
 * right in isolation but mathematically overlaps a corner button once the wordmark is wide enough
 * relative to the screen, which a flex row avoids by construction. */
export function TopNav({ onBack }: Props) {
  return (
    <div className="top-nav">
      <BackButton onClick={onBack} />
      <AppHeader compact />
    </div>
  );
}
