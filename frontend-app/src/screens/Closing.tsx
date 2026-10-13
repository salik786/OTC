import { useEffect, useRef, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { Button } from "../components/Button";

const CLOSING_TEXT =
  "Thank you for using this system. I hope the information was helpful. The researcher will now ask you a few questions. Goodbye!";

// Long enough for the participant to scan the survey QR code below before the screen resets for
// the next person; the "Finish" button resets immediately if the researcher is ready sooner.
const RESET_DELAY_MS = 120000;

// Survey QR code for the tablet condition - drop the image at public/qr-tablet.png. Until it exists
// the QR block simply doesn't render (onError below), so a missing file never shows a broken image.
const QR_SRC = `${import.meta.env.BASE_URL}qr-tablet.png`;

interface Props {
  onSave: () => Promise<void>;
  onDone: () => void;
}

/** Shows a clear "saving" state while the session-end API call is in flight, then confirms and
 * resets to the researcher setup screen for the next participant (automatically after a delay, or
 * immediately via the Finish button) - kiosk-style. Shows the post-session survey QR code. */
export function Closing({ onSave, onDone }: Props) {
  const [saving, setSaving] = useState(true);
  const [saveFailed, setSaveFailed] = useState(false);
  const [qrAvailable, setQrAvailable] = useState(true);
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
        {qrAvailable && (
          <div className="closing-qr">
            <img
              src={QR_SRC}
              alt="QR code linking to the study survey"
              onError={() => setQrAvailable(false)}
            />
            <p>Scan this QR code to complete a short survey.</p>
          </div>
        )}
        {!saving && (
          <Button variant="ghost" onClick={onDone} className="closing-finish">
            Finish
          </Button>
        )}
      </div>
    </div>
  );
}
