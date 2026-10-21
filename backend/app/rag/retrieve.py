from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk, Document
from app.rag.config_store import get_active_config
from app.rag.vectorstore import get_vectorstore

settings = get_settings()


def retrieve(db: Session, query_text: str, product_id: str, top_k: int | None = None, cfg=None) -> list[dict]:
    """Returns retrieved chunks as dicts: {chunk_id, text, section_label, score, document_id,
    document_filename}, best first."""
    if top_k is None:
        top_k = (cfg.config if hasattr(cfg, 'config') else cfg or get_active_config().config)['top_k']
    hits = get_vectorstore().search(query_text, product_id, top_k)
    if not hits:
        return []

    chunk_ids = [h[0] for h in hits]
    rows = {c.id: c for c in db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()}

    doc_ids = {c.document_id for c in rows.values()}
    filenames = {d.id: d.filename for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()} if doc_ids else {}

    results = []
    for chunk_id, score in hits:
        chunk = rows.get(chunk_id)
        if chunk is None:
            continue
        results.append({
            "chunk_id": chunk.id,
            "text": chunk.text,
            "section_label": chunk.section_label,
            "score": score,
            "document_id": chunk.document_id,
            "document_filename": filenames.get(chunk.document_id),
        })
    return results
