import { useEffect, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { Button } from "../components/Button";
import { api, type Product } from "../lib/api";

interface Props {
  onTellMe: (productSlug: string) => void;
  onAskQuestion: (productSlug: string) => void;
  starting: boolean;
  error: string | null;
}

export function ResearcherSetup({ onTellMe, onAskQuestion, starting, error }: Props) {
  const [products, setProducts] = useState<Product[]>([]);
  const [productSlug, setProductSlug] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProducts()
      .then((prods) => {
        setProducts(prods);
        if (prods.length > 0) setProductSlug(prods[0].slug);
      })
      .catch(() => setLoadError("Could not load the medicine list. Check the connection and reload."));
  }, []);

  return (
    <div className="screen researcher-screen">
      <AppHeader />
      <div className="researcher-card">
        <h1>Hello!</h1>
        <p className="lede">
          I'm here to help you understand this medicine - what it's used for, how to take it, and any important
          warnings from the packaging.
        </p>

        <label className="product-select-label" htmlFor="product-select">
          <span className="field-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8">
              <rect x="4" y="9" width="14" height="6" rx="3" transform="rotate(-45 11 12)" />
              <line x1="10" y1="8" x2="12" y2="16" transform="rotate(-45 11 12)" />
            </svg>
          </span>
          Medicine on the counter
        </label>
        <select
          id="product-select"
          className="product-select"
          value={productSlug}
          onChange={(e) => setProductSlug(e.target.value)}
          disabled={products.length === 0}
        >
          {products.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.display_name}
            </option>
          ))}
        </select>

        {loadError && <p className="error-text">{loadError}</p>}
        {!loadError && products.length === 0 && (
          <p className="error-text">No medicines are set up yet. Ask a researcher to upload one in the admin panel.</p>
        )}
        {error && <p className="error-text">{error}</p>}

        <div className="welcome-actions">
          <Button variant="primary" onClick={() => onTellMe(productSlug)} disabled={starting || !productSlug}>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M10 2l1.6 4.7L16.5 8l-4.9 1.3L10 14l-1.6-4.7L3.5 8l4.9-1.3L10 2z" />
            </svg>
            {starting ? "Starting..." : "Tell me about this medicine"}
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M7.5 4.5l6 5.5-6 5.5" />
            </svg>
          </Button>
          <Button
            variant="secondary"
            onClick={() => onAskQuestion(productSlug)}
            disabled={starting || !productSlug}
            aria-label="Ask a question by voice or typing"
          >
            <span className="mic-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="10" cy="10" r="8" />
                <path d="M7.6 7.8a2.4 2.4 0 114.15 1.65c-.68.6-1.35 1.05-1.35 2.05" strokeLinecap="round" />
                <circle cx="10" cy="14" r="0.9" fill="currentColor" stroke="none" />
              </svg>
            </span>
            Ask a question
          </Button>
        </div>

        <p className="muted disclaimer-small">
          <span className="field-icon" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v.01a1 1 0 002 0V7zm0 4a1 1 0 10-2 0v4a1 1 0 102 0v-4z"
                clipRule="evenodd"
              />
            </svg>
          </span>
          I'm not a pharmacist and can't give personal health advice.
        </p>
      </div>
    </div>
  );
}
