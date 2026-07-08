import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../AuthContext";
import { api, ApiError, type Product, type RetrievedChunk } from "../lib/api";

export function TestRetrieval() {
  const { credentials } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [productSlug, setProductSlug] = useState("");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<RetrievedChunk[] | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!credentials) return;
    api.listProducts(credentials).then((prods) => {
      setProducts(prods);
      if (prods.length > 0) setProductSlug(prods[0].slug);
    });
  }, [credentials]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!credentials || !query.trim() || !productSlug) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.testRetrieval(credentials, query, productSlug, topK);
      setResults(res.retrieved_chunks);
      setLatency(res.latency_ms);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Retrieval failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Test Retrieval</h2>
      <p className="muted">
        Run sample queries against the live corpus before it goes to participants. Doubles as the protocol's
        "test retrieval with sample queries before integration" step.
      </p>
      <form className="panel form-row" onSubmit={handleSubmit}>
        <select value={productSlug} onChange={(e) => setProductSlug(e.target.value)}>
          {products.map((p) => (
            <option key={p.id} value={p.slug}>
              {p.display_name} ({p.slug})
            </option>
          ))}
        </select>
        <input
          className="grow"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What is the maximum dose in 24 hours?"
        />
        <input
          type="number"
          min={1}
          max={20}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          style={{ width: "5rem" }}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {latency !== null && <p className="muted">Retrieval latency: {latency.toFixed(0)} ms</p>}
      {results && (
        <div className="panel">
          {results.length === 0 && <p className="muted">No chunks retrieved for this query.</p>}
          {results.map((c) => (
            <div key={c.chunk_id} className="chunk-card">
              <div className="chunk-header">
                <strong>{c.section_label ?? "Unlabeled chunk"}</strong>
                <span className="muted">score {c.score.toFixed(3)}</span>
              </div>
              <p>{c.text}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
