import { useState } from "react";

const PRODUCTS = [
  { slug: "paracetamol", label: "Paracetamol" },
  { slug: "multivitamin", label: "Multivitamin" },
];

interface Props {
  onStart: (productSlug: string) => void;
  starting: boolean;
  error: string | null;
}

export function ResearcherSetup({ onStart, starting, error }: Props) {
  const [productSlug, setProductSlug] = useState(PRODUCTS[0].slug);

  return (
    <div className="screen researcher-screen">
      <div className="researcher-card">
        <span className="badge">Researcher setup - not participant facing</span>
        <h2>Start a session</h2>
        <p className="muted">
          Place the matching medicine box on the counter before starting. The participant will only see
          information about the product selected here.
        </p>
        <fieldset>
          <legend>Medicine on the counter</legend>
          {PRODUCTS.map((p) => (
            <label key={p.slug} className="radio-row">
              <input
                type="radio"
                name="product"
                value={p.slug}
                checked={productSlug === p.slug}
                onChange={() => setProductSlug(p.slug)}
              />
              {p.label}
            </label>
          ))}
        </fieldset>
        {error && <p className="error-text">{error}</p>}
        <button className="btn btn-primary" onClick={() => onStart(productSlug)} disabled={starting}>
          {starting ? "Starting..." : "Start Session"}
        </button>
      </div>
    </div>
  );
}
