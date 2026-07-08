import { useEffect, useRef } from "react";
import { useTTS } from "../hooks/useTTS";

const CLOSING_TEXT =
  "Thank you for using this system. I hope the information was helpful. The researcher will now ask you a few questions. Goodbye!";

interface Props {
  onSessionEnd: () => void;
}

export function Closing({ onSessionEnd }: Props) {
  const { speak } = useTTS();
  const firedRef = useRef(false);

  useEffect(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    onSessionEnd();
    speak(CLOSING_TEXT);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="screen closing-screen">
      <div className="closing-content">
        <h1>Thank you</h1>
        <p className="lede">{CLOSING_TEXT}</p>
        <p className="muted">This session has ended.</p>
      </div>
    </div>
  );
}
