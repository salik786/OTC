import { useEffect, useRef, useState } from "react";
import { useAuth } from "../AuthContext";
import { api, ApiError, type DocumentOut, type Product } from "../lib/api";

export function Documents() {
  const { credentials } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    if (!credentials) return;
    const [prods, docs] = await Promise.all([api.listProducts(credentials), api.listDocuments(credentials)]);
    setProducts(prods);
    setDocuments(docs);
    if (!selectedProduct && prods.length > 0) setSelectedProduct(prods[0].slug);
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credentials]);

  async function handleUpload() {
    if (!credentials || !fileInputRef.current?.files?.[0] || !selectedProduct) return;
    setUploading(true);
    setError(null);
    setMessage(null);
    try {
      const doc = await api.uploadDocument(credentials, selectedProduct, fileInputRef.current.files[0]);
      setMessage(`Ingested "${doc.filename}" - ${doc.chunk_count} chunks. This replaced any previous active document for ${selectedProduct}.`);
      fileInputRef.current.value = "";
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(doc: DocumentOut) {
    if (!credentials) return;
    if (!confirm(`Delete "${doc.filename}" (${doc.product_slug})? This removes its chunks from the vector index immediately.`)) return;
    try {
      await api.deleteDocument(credentials, doc.id);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    }
  }

  return (
    <section>
      <h2>Corpus Documents</h2>
      <div className="panel">
        <h3>Upload leaflet</h3>
        <p className="muted">
          Uploading replaces the current active document for the selected product - it does not append. The
          vector index is rebuilt automatically.
        </p>
        <div className="form-row">
          <select value={selectedProduct} onChange={(e) => setSelectedProduct(e.target.value)}>
            {products.map((p) => (
              <option key={p.id} value={p.slug}>
                {p.display_name} ({p.slug})
              </option>
            ))}
          </select>
          <input ref={fileInputRef} type="file" accept=".pdf,.txt,.md" />
          <button onClick={handleUpload} disabled={uploading}>
            {uploading ? "Ingesting..." : "Upload & Ingest"}
          </button>
        </div>
        {message && <p className="success">{message}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="panel">
        <h3>Ingested documents</h3>
        <table>
          <thead>
            <tr>
              <th>Filename</th>
              <th>Product</th>
              <th>Uploaded</th>
              <th>Chunks</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id}>
                <td>{d.filename}</td>
                <td>{d.product_slug}</td>
                <td>{new Date(d.uploaded_at).toLocaleString()}</td>
                <td>{d.chunk_count}</td>
                <td>{d.active ? "yes" : "no"}</td>
                <td>
                  <button className="danger" onClick={() => handleDelete(d)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  No documents ingested yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
