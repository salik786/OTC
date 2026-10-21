import io
import logging
import re
import uuid
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk, Document, Product
from app.rag.config_store import ActiveConfig, get_active_config
from app.rag.vectorstore import get_vectorstore

logger = logging.getLogger("otc.ingest")

# Where the built-in leaflets live (also used by main.py to seed a fresh database).
SEED_CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "seed_corpus"

settings = get_settings()

# Common OTC leaflet section headers. Matched case-insensitively at line start, optionally
# followed by a colon. Leaflets that don't use recognizable headers fall back to sliding-window
# chunking - we can't assume every leaflet is structured the same way.
SECTION_HEADERS = [
    "uses", "used for", "what is this medicine used for", "purpose", "description",
    "dosage", "dose", "directions", "how to take", "how to use", "supplement facts", "drug facts",
    "warnings", "precautions", "do not use if", "when to ask a pharmacist", "ask a doctor",
    "storage", "expiry", "how long to use once opened", "other information",
    "missed dose", "if you miss a dose", "other medicines", "pregnancy", "overdose",
    "side effects", "ingredients", "active ingredient", "active ingredients", "inactive ingredients",
    "other ingredients", "questions", "questions or comments",
]
_HEADER_PATTERN = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_text(filename: str, file_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return file_bytes.decode("utf-8", errors="replace")


def _structural_chunks(text: str) -> list[dict] | None:
    matches = list(_HEADER_PATTERN.finditer(text))
    if len(matches) < 2:
        return None  # not enough structure to trust header-based splitting

    chunks = []
    # Anything before the first recognized header (product name/description, ingredient tables,
    # intro text) would otherwise be silently discarded - capture it as its own chunk instead of
    # losing it, since it's often the most important content (what the product actually is).
    preamble = text[: matches[0].start()].strip()
    if preamble:
        chunks.append({"section_label": "Overview", "text": f"Overview: {preamble}"})

    for i, m in enumerate(matches):
        label = m.group(1).strip().title()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            chunks.append({"section_label": label, "text": f"{label}: {body}"})
    return chunks or None


def _cfg(cfg) -> dict:
    """Accept an ActiveConfig, a plain config dict, or None (= the active config)."""
    if cfg is None:
        return get_active_config().config
    return cfg.config if isinstance(cfg, ActiveConfig) else cfg


def _windows(text: str, size: int, overlap: int, label: str | None) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        body = text[start:end].strip()
        if body:
            chunks.append({"section_label": label, "text": body})
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _sliding_window_chunks(text: str, size: int, overlap: int) -> list[dict]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    return _windows(text, size, overlap, None)


def _split_oversized(chunks: list[dict], size: int, overlap: int) -> list[dict]:
    """Keep each section's label but cut any section longer than `size` into overlapping windows."""
    out: list[dict] = []
    for c in chunks:
        if len(c["text"]) <= size:
            out.append(c)
        else:
            out.extend(_windows(c["text"], size, overlap, c["section_label"]))
    return out


def chunk_text(text: str, cfg=None) -> list[dict]:
    """Split a leaflet into chunks according to the chunking settings in `cfg` (default: the active
    config). 'by_section' is the original behaviour, so existing leaflets chunk identically."""
    c = _cfg(cfg)
    size, overlap, strategy = c["chunk_size_chars"], c["chunk_overlap_chars"], c["chunking_strategy"]
    if strategy == "sliding_window":
        return _sliding_window_chunks(text, size, overlap)
    structural = _structural_chunks(text)
    if structural is None:
        return _sliding_window_chunks(text, size, overlap)  # no usable headers: same fallback as before
    if strategy == "by_section_max_size":
        return _split_oversized(structural, size, overlap)
    return structural


def get_or_create_product(db: Session, slug: str, display_name: str | None = None) -> Product:
    product = db.query(Product).filter(Product.slug == slug).first()
    if product is None:
        product = Product(slug=slug, display_name=display_name or slug.replace("_", " ").title())
        db.add(product)
        db.commit()
        db.refresh(product)
    return product


def _insert_chunks(db: Session, document: Document, product_id: str, raw_chunks: list[dict]) -> None:
    for i, c in enumerate(raw_chunks):
        db.add(Chunk(
            document_id=document.id,
            product_id=product_id,
            chunk_index=i,
            section_label=c["section_label"],
            text=c["text"],
        ))


def sync_index(db: Session, cfg=None) -> None:
    """Make the search index match the database. Normally that's a plain rebuild; if the index was
    built with different chunking/embedding settings than the active config, a full re-index (which
    re-chunks every leaflet from its source text) keeps all leaflets chunked consistently."""
    c = _cfg(cfg)
    vs = get_vectorstore()
    if vs.matches_config(c):
        vs.rebuild(db, c)
    else:
        reindex_all(db, c)


def ingest_document(db: Session, product_slug: str, filename: str, file_bytes: bytes, cfg=None) -> Document:
    """Ingests a leaflet for a product. Replaces (not appends to) any existing active document
    for that product, per the study's re-ingest/replace requirement."""
    c = _cfg(cfg)
    product = get_or_create_product(db, product_slug)

    # Replace semantics: deactivate + delete the old active document and its chunks.
    old_docs = db.query(Document).filter(Document.product_id == product.id, Document.active == True).all()  # noqa: E712
    for old in old_docs:
        db.delete(old)
    db.commit()

    text = extract_text(filename, file_bytes)
    raw_chunks = chunk_text(text, c)

    document = Document(product_id=product.id, filename=filename, chunk_count=len(raw_chunks), active=True,
                        source_text=text, source_reconstructed=False)
    db.add(document)
    db.commit()
    db.refresh(document)

    _insert_chunks(db, document, product.id, raw_chunks)
    db.commit()

    sync_index(db, c)
    return document


def delete_document(db: Session, document_id: str) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise ValueError("document not found")
    db.delete(doc)
    db.commit()
    sync_index(db)


def reindex_all(db: Session, cfg=None) -> dict:
    """Re-chunk every leaflet from its stored source text with `cfg`'s chunking settings, re-embed
    with its embedding model, and swap the index. All-or-nothing: the failure-prone steps (reading
    sources, calling the embeddings API) run BEFORE anything is modified, so an error - e.g. an
    unavailable embedding model - leaves the existing chunks and index serving untouched."""
    c = _cfg(cfg)
    docs = db.query(Document).all()
    missing = [d.filename for d in docs if not d.source_text]
    if missing:
        raise ValueError(f"No source text stored for: {', '.join(missing)}. Re-upload these leaflets first.")

    planned: list[tuple[Document, list[dict]]] = [(d, chunk_text(d.source_text, c)) for d in docs]
    new_chunk_rows: list[tuple[str, Document, int, dict]] = []
    for d, chunks in planned:
        for i, ch in enumerate(chunks):
            new_chunk_rows.append((uuid.uuid4().hex, d, i, ch))

    vs = get_vectorstore()
    index, chunk_ids, product_ids = vs.build_arrays(
        [(cid, d.product_id, ch["text"]) for cid, d, _, ch in new_chunk_rows], c["embedding_model"])

    try:
        db.query(Chunk).delete()
        for cid, d, i, ch in new_chunk_rows:
            db.add(Chunk(id=cid, document_id=d.id, product_id=d.product_id, chunk_index=i,
                         section_label=ch["section_label"], text=ch["text"]))
        for d, chunks in planned:
            d.chunk_count = len(chunks)
        db.commit()
    except Exception:
        db.rollback()
        raise
    vs.install(index, chunk_ids, product_ids, c)
    logger.info("re-indexed %d documents into %d chunks (model=%s, strategy=%s)",
                len(docs), len(new_chunk_rows), c["embedding_model"], c["chunking_strategy"])
    return {"documents": len(docs), "chunks": len(new_chunk_rows)}


def _reconstruct_source(chunks: list[Chunk]) -> str:
    """Rebuild a leaflet's text from its chunks (for documents ingested before source_text was
    stored): each 'Label: body' chunk becomes a 'Label' header line plus its body, so re-chunking by
    section reproduces the same sections. Approximate for sliding-window chunks (overlaps repeat)."""
    parts = []
    for c in sorted(chunks, key=lambda c: c.chunk_index):
        label = c.section_label
        if label and c.text.startswith(f"{label}: "):
            body = c.text[len(label) + 2:]
            parts.append(body if label == "Overview" else f"{label}\n{body}")
        else:
            parts.append(c.text)
    return "\n\n".join(parts)


def backfill_source_text(db: Session) -> None:
    """For documents with no stored source: use the original seed file when one with the same
    filename ships in seed_corpus (exact), else reconstruct from chunks (flagged approximate)."""
    for doc in db.query(Document).filter(Document.source_text == None).all():  # noqa: E711
        seed = SEED_CORPUS_DIR / doc.filename
        if seed.is_file():
            doc.source_text = seed.read_text(encoding="utf-8")
            doc.source_reconstructed = False
        else:
            chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).all()
            doc.source_text = _reconstruct_source(chunks)
            doc.source_reconstructed = True
        logger.info("backfilled source_text for %s (reconstructed=%s)", doc.filename, doc.source_reconstructed)
    db.commit()
