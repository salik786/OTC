import { useState } from "react";
import { Button } from "../components/Button";

const PRODUCTS = [
  { slug: "paracetamol", label: "Paracetamol" },
  { slug: "multivitamin", label: "Multivitamin" },
];

interface Props {
  onTellMe: (productSlug: string) => void;
  onAskQuestion: (productSlug: string) => void;
  starting: boolean;
  error: string | null;
}

export function ResearcherSetup({ onTellMe, onAskQuestion, starting, error }: Props) {
  const [productSlug, setProductSlug] = useState(PRODUCTS[0].slug);

  return (
    <div className="screen researcher-screen">
      <div className="researcher-card">
        <h1>Hello!</h1>
        <p className="lede">
          I'm here to help you understand this medicine - what it's used for, how to take it, and any important
          warnings from the packaging.
        </p>

        <label className="product-select-label" htmlFor="product-select">
          Medicine on the counter
        </label>
        <select
          id="product-select"
          className="product-select"
          value={productSlug}
          onChange={(e) => setProductSlug(e.target.value)}
        >
          {PRODUCTS.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.label}
            </option>
          ))}
        </select>

        {error && <p className="error-text">{error}</p>}

        <div className="welcome-actions">
          <Button variant="primary" onClick={() => onTellMe(productSlug)} disabled={starting}>
            {starting ? "Starting..." : "Tell me about this medicine"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => onAskQuestion(productSlug)}
            disabled={starting}
            aria-label="Ask a question by voice or typing"
          >
            <span className="mic-icon" aria-hidden="true">
              🎙
            </span>
            Ask a question
          </Button>
        </div>

        <p className="muted disclaimer-small">I'm not a pharmacist and can't give personal health advice.</p>
      </div>
    </div>
  );
}
