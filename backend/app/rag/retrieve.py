from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk
from app.rag.vectorstore import get_vectorstore

settings = get_settings()


def retrieve(db: Session, query_text: str, product_id: str, top_k: int | None = None) -> list[dict]:
    """Returns retrieved chunks as dicts: {chunk_id, text, section_label, score}, best first."""
    top_k = top_k or settings.retrieval_top_k
    hits = get_vectorstore().search(query_text, product_id, top_k)
    if not hits:
        return []

    chunk_ids = [h[0] for h in hits]
    rows = {c.id: c for c in db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()}

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
        })
    return results
