import { useEffect, useState } from "react";
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
            {starting ? "Starting..." : "Tell me about this medicine"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => onAskQuestion(productSlug)}
            disabled={starting || !productSlug}
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
