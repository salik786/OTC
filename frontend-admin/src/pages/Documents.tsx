import { useEffect, useRef, useState } from "react";
import { useAuth } from "../AuthContext";
import { api, ApiError, type DocumentChunk, type DocumentOut, type Product } from "../lib/api";

export function Documents() {
  const { credentials } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [addingNew, setAddingNew] = useState(false);
  const [newSlug, setNewSlug] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [viewingDoc, setViewingDoc] = useState<DocumentOut | null>(null);
  const [viewingChunks, setViewingChunks] = useState<DocumentChunk[] | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState<string | null>(null);

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
    const targetSlug = addingNew ? newSlug.trim() : selectedProduct;
    if (!credentials || !fileInputRef.current?.files?.[0] || !targetSlug) return;
    if (addingNew && !newDisplayName.trim()) return;
    setUploading(true);
    setError(null);
    setMessage(null);
    try {
      const doc = await api.uploadDocument(
        credentials,
        targetSlug,
        fileInputRef.current.files[0],
        addingNew ? newDisplayName.trim() : undefined
      );
      setMessage(`Ingested "${doc.filename}" - ${doc.chunk_count} chunks. This replaced any previous active document for ${targetSlug}.`);
      fileInputRef.current.value = "";
      setAddingNew(false);
      setNewSlug("");
      setNewDisplayName("");
      setSelectedProduct(targetSlug);
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

  async function handleView(doc: DocumentOut) {
    if (!credentials) return;
    setViewingDoc(doc);
    setViewingChunks(null);
    setViewError(null);
    setViewLoading(true);
    try {
      const chunks = await api.getDocumentChunks(credentials, doc.id);
      setViewingChunks(chunks);
    } catch (e) {
      setViewError(e instanceof ApiError ? e.message : "Could not load document content.");
    } finally {
      setViewLoading(false);
    }
  }

  function closeView() {
    setViewingDoc(null);
    setViewingChunks(null);
    setViewError(null);
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
          <select
            value={addingNew ? "__new__" : selectedProduct}
            onChange={(e) => {
              if (e.target.value === "__new__") {
                setAddingNew(true);
              } else {
                setAddingNew(false);
                setSelectedProduct(e.target.value);
              }
            }}
          >
            {products.map((p) => (
              <option key={p.id} value={p.slug}>
                {p.display_name} ({p.slug})
              </option>
            ))}
            <option value="__new__">+ Add new medicine...</option>
          </select>
          {addingNew && (
            <>
              <input
                type="text"
                placeholder="Display name (e.g. Ibuprofen 200mg)"
                value={newDisplayName}
                onChange={(e) => {
                  setNewDisplayName(e.target.value);
                  setNewSlug(e.target.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, ""));
                }}
              />
              <input type="text" placeholder="slug" value={newSlug} onChange={(e) => setNewSlug(e.target.value)} />
            </>
          )}
          <input ref={fileInputRef} type="file" accept=".pdf,.txt,.md" />
          <button onClick={handleUpload} disabled={uploading || (addingNew && (!newSlug || !newDisplayName))}>
            {uploading ? "Ingesting..." : "Upload & Ingest"}
          </button>
        </div>
        {message && <p className="success">{message}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="panel table-scroll">
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
                  <button onClick={() => handleView(d)}>View</button>{" "}
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

      {viewingDoc && (
        <div className="modal-backdrop" onClick={closeView}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {viewingDoc.filename} <span className="muted">({viewingDoc.product_slug})</span>
              </h3>
              <button className="link-button" onClick={closeView}>
                Close
              </button>
            </div>
            <p className="muted">
              This is exactly what was extracted and chunked from this file - what the RAG pipeline actually
              retrieves from, not the raw upload.
            </p>
            {viewLoading && <p className="muted">Loading...</p>}
            {viewError && <p className="error">{viewError}</p>}
            {viewingChunks &&
              viewingChunks.map((c) => (
                <div key={c.chunk_id} className="chunk-card">
                  <div className="chunk-header">
                    <strong>
                      #{c.chunk_index} {c.section_label ?? "Unlabeled chunk"}
                    </strong>
                  </div>
                  <p>{c.text}</p>
                </div>
              ))}
            {viewingChunks && viewingChunks.length === 0 && <p className="muted">No chunks stored for this document.</p>}
          </div>
        </div>
      )}
    </section>
  );
}
