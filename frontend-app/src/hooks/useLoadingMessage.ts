import { useEffect, useState } from "react";

/** A single "Thinking..." label sitting still for several seconds reads as stalled, especially
 * once the thinking orb/status text is the only feedback the participant has. Cycling through a
 * short sequence of concrete-sounding phrases (matching what's actually happening - retrieval,
 * then generation) gives a continuous sense of progress instead. */
const MESSAGES = ["Thinking...", "Checking the leaflet...", "Finding the best answer...", "Almost there..."];

export function useLoadingMessage(active: boolean): string {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setIndex((i) => (i + 1) % MESSAGES.length);
    }, 1500);
    return () => clearInterval(interval);
  }, [active]);

  return MESSAGES[index];
}
