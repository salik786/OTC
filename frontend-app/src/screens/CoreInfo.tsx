import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { useTTS } from "../hooks/useTTS";
import { api, type CoreInfoResponse } from "../lib/api";

interface Props {
  sessionId: string;
  productDisplayName: string;
  onAskQuestion: () => void;
}

export function CoreInfo({ sessionId, productDisplayName, onAskQuestion }: Props) {
  const [data, setData] = useState<CoreInfoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { speak } = useTTS();
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    api
      .coreInfo(sessionId)
      .then((res) => {
        setData(res);
        speak(res.full_text);
      })
      .catch(() => setError("Could not load information about this medicine. Please tell the researcher."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (error) {
    return (
      <div className="screen core-info-screen">
        <p className="error-text">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="screen core-info-screen">
        <p className="muted" aria-live="polite">
          Loading information about {productDisplayName}...
        </p>
      </div>
    );
  }

  return (
    <div className="screen core-info-screen">
      <div className="info-card">
        <h2>{data.product_name}</h2>

        {data.used_for && (
          <div className="info-row">
            <span className="info-label">Used for</span>
            <p>{data.used_for}</p>
          </div>
        )}
        {data.dose && (
          <div className="info-row">
            <span className="info-label">Dose</span>
            <p>{data.dose}</p>
          </div>
        )}
        {data.frequency && (
          <div className="info-row">
            <span className="info-label">Frequency</span>
            <p>{data.frequency}</p>
          </div>
        )}
        {data.max_dose_24h && (
          <div className="info-row">
            <span className="info-label">Max in 24 hours</span>
            <p>{data.max_dose_24h}</p>
          </div>
        )}
        {data.warnings.length > 0 && (
          <div className="warnings-block">
            <span className="info-label">Warnings</span>
            <ul>
              {data.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        <p className="prompt-text">Do you have any questions?</p>
        <Button variant="primary" onClick={onAskQuestion}>
          Ask a question
        </Button>
      </div>
    </div>
  );
}
