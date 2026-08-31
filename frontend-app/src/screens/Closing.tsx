import { useEffect, useRef, useState } from "react";
import { AppHeader } from "../components/AppHeader";

const CLOSING_TEXT =
  "Thank you for using this system. I hope the information was helpful. The researcher will now ask you a few questions. Goodbye!";

const RESET_DELAY_MS = 4000;

interface Props {
  onSave: () => Promise<void>;
  onDone: () => void;
}

/** Shows a clear "saving" state while the session-end API call is in flight, then confirms and
 * auto-resets to the researcher setup screen for the next participant after a short delay -
 * kiosk-style, no manual reset step needed between sessions. */
export function Closing({ onSave, onDone }: Props) {
  const [saving, setSaving] = useState(true);
  const [saveFailed, setSaveFailed] = useState(false);
  const firedRef = useRef(false);

  useEffect(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    (async () => {
      try {
        await onSave();
      } catch {
        setSaveFailed(true);
      } finally {
        setSaving(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (saving) return;
    const timer = window.setTimeout(onDone, RESET_DELAY_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saving]);

  return (
    <div className="screen closing-screen">
      <AppHeader light />
      <div className="closing-content">
        <h1>Thank you</h1>
        <p className="lede">{CLOSING_TEXT}</p>
        {saving ? (
          <p className="muted" aria-live="polite">
            Saving your session...
          </p>
        ) : (
          <p className="muted" aria-live="polite">
            {saveFailed ? "This session has ended." : "Session saved."}
          </p>
        )}
      </div>
    </div>
  );
}
