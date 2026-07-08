import io
import re

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk, Document, Product
from app.rag.vectorstore import get_vectorstore

settings = get_settings()

# Common OTC leaflet section headers. Matched case-insensitively at line start, optionally
# followed by a colon. Leaflets that don't use recognizable headers fall back to sliding-window
# chunking - we can't assume every leaflet is structured the same way.
SECTION_HEADERS = [
    "uses", "used for", "what is this medicine used for",
    "dosage", "dose", "directions", "how to take", "how to use",
    "warnings", "precautions", "do not use if", "when to ask a pharmacist",
    "storage", "expiry", "how long to use once opened",
    "missed dose", "if you miss a dose",
    "side effects", "ingredients",
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
    for i, m in enumerate(matches):
        label = m.group(1).strip().title()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            chunks.append({"section_label": label, "text": f"{label}: {body}"})
    return chunks or None


def _sliding_window_chunks(text: str) -> list[dict]:
    size = settings.chunk_size_chars
    overlap = settings.chunk_overlap_chars
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        body = text[start:end].strip()
        if body:
            chunks.append({"section_label": None, "text": body})
        if end == len(text):
            break
        start = end - overlap
    return chunks


def chunk_text(text: str) -> list[dict]:
    return _structural_chunks(text) or _sliding_window_chunks(text)


def get_or_create_product(db: Session, slug: str, display_name: str | None = None) -> Product:
    product = db.query(Product).filter(Product.slug == slug).first()
    if product is None:
        product = Product(slug=slug, display_name=display_name or slug.replace("_", " ").title())
        db.add(product)
        db.commit()
        db.refresh(product)
    return product


def ingest_document(db: Session, product_slug: str, filename: str, file_bytes: bytes) -> Document:
    """Ingests a leaflet for a product. Replaces (not appends to) any existing active document
    for that product, per the study's re-ingest/replace requirement."""
    product = get_or_create_product(db, product_slug)

    # Replace semantics: deactivate + delete the old active document and its chunks.
    old_docs = db.query(Document).filter(Document.product_id == product.id, Document.active == True).all()  # noqa: E712
    for old in old_docs:
        db.delete(old)
    db.commit()

    text = extract_text(filename, file_bytes)
    raw_chunks = chunk_text(text)

    document = Document(product_id=product.id, filename=filename, chunk_count=len(raw_chunks), active=True)
    db.add(document)
    db.commit()
    db.refresh(document)

    for i, c in enumerate(raw_chunks):
        db.add(Chunk(
            document_id=document.id,
            product_id=product.id,
            chunk_index=i,
            section_label=c["section_label"],
            text=c["text"],
        ))
    db.commit()

    get_vectorstore().rebuild(db)
    return document


def delete_document(db: Session, document_id: str) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise ValueError("document not found")
    db.delete(doc)
    db.commit()
    get_vectorstore().rebuild(db)
