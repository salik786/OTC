import { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { TopNav } from "../components/TopNav";
import { api, type CoreInfoResponse } from "../lib/api";

interface Props {
  sessionId: string;
  productDisplayName: string;
  onBack: () => void;
  onAskQuestion: () => void;
}

function UsedForIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="10" cy="10" r="7" />
      <circle cx="10" cy="10" r="3.5" />
      <circle cx="10" cy="10" r="0.6" fill="currentColor" />
    </svg>
  );
}

function DoseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="7" cy="7" r="2.6" />
      <path d="M2.5 17c0-3 2-5 4.5-5s4.5 2 4.5 5" />
      <circle cx="15" cy="7" r="2" />
      <path d="M11.8 12.3c2-.4 3.7 1 3.7 4.7" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="10" cy="10" r="7.5" />
      <path d="M10 5.5V10l3 2" strokeLinecap="round" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
      <path d="M10 3.2 17.5 16.5H2.5Z" />
      <path d="M10 8v3.5" strokeLinecap="round" />
      <circle cx="10" cy="13.8" r="0.7" fill="currentColor" stroke="none" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v.01a1 1 0 002 0V7zm0 4a1 1 0 10-2 0v4a1 1 0 102 0v-4z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function CapsuleIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="9" width="18" height="8" rx="4" transform="rotate(-35 12 13)" />
      <line x1="10" y1="7" x2="14" y2="19" transform="rotate(-35 12 13)" />
    </svg>
  );
}

export function CoreInfo({ sessionId, productDisplayName, onBack, onAskQuestion }: Props) {
  const [data, setData] = useState<CoreInfoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    api
      .coreInfo(sessionId)
      .then((res) => setData(res))
      .catch(() => setError("Could not load information about this medicine. Please tell the researcher."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (error) {
    return (
      <div className="screen core-info-screen">
        <TopNav onBack={onBack} />
        <p className="error-text">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="screen core-info-screen">
        <TopNav onBack={onBack} />
        <p className="muted" aria-live="polite">
          Loading information about {productDisplayName}...
        </p>
      </div>
    );
  }

  return (
    <div className="screen core-info-screen">
      <TopNav onBack={onBack} />
      <div className="info-card">
        <div className="info-card-heading">
          <span className="info-card-pill-icon" aria-hidden="true">
            <CapsuleIcon />
          </span>
          <h2>{data.product_name}</h2>
        </div>

        {data.used_for && (
          <div className="info-row">
            <span className="info-row-icon" aria-hidden="true">
              <UsedForIcon />
            </span>
            <div className="info-row-body">
              <span className="info-label">Used for</span>
              <p>{data.used_for}</p>
            </div>
          </div>
        )}

        {(data.dose || data.frequency) && (
          <div className="info-row-cols">
            {data.dose && (
              <div className="info-row">
                <span className="info-row-icon" aria-hidden="true">
                  <DoseIcon />
                </span>
                <div className="info-row-body">
                  <span className="info-label">Dose</span>
                  <p>{data.dose}</p>
                </div>
              </div>
            )}
            {data.frequency && (
              <div className="info-row">
                <span className="info-row-icon" aria-hidden="true">
                  <ClockIcon />
                </span>
                <div className="info-row-body">
                  <span className="info-label">Frequency</span>
                  <p>{data.frequency}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {data.max_dose_24h && (
          <div className="info-row max-dose-block">
            <span className="info-row-icon" aria-hidden="true">
              <WarningIcon />
            </span>
            <div className="info-row-body">
              <span className="info-label">Max in 24 hours</span>
              <p>{data.max_dose_24h}</p>
            </div>
          </div>
        )}

        {data.warnings.length > 0 && (
          <div className="warnings-block">
            <span className="warnings-heading">
              <span aria-hidden="true">
                <WarningIcon />
              </span>
              Warnings
            </span>
            <ul>
              {data.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        <p className="info-footer-note">
          <span className="field-icon" aria-hidden="true">
            <InfoIcon />
          </span>
          Always read the label and follow the instructions on the packaging.
        </p>

        <p className="prompt-text">Do you have any questions?</p>
        <Button variant="primary" onClick={onAskQuestion}>
          Ask a question
        </Button>
      </div>
    </div>
  );
}
