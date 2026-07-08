import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session as DBSession

from app.auth import require_admin
from app.db.models import Document, Product, SessionRecord
from app.db.session import get_db
from app.rag.ingest import delete_document, ingest_document
from app.rag.retrieve import retrieve
from app.schemas import DocumentOut, ProductOut, RetrievedChunk, SessionSummaryOut, TestRetrievalRequest, TestRetrievalResponse

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
limiter = Limiter(key_func=get_remote_address)


@router.get("/products", response_model=list[ProductOut])
def list_products(db: DBSession = Depends(get_db)) -> list[ProductOut]:
    products = db.query(Product).all()
    return [ProductOut(id=p.id, slug=p.slug, display_name=p.display_name) for p in products]


@router.post("/documents", response_model=DocumentOut)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    product_slug: str = Form(...),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
) -> DocumentOut:
    file_bytes = await file.read()
    document = ingest_document(db, product_slug, file.filename or "leaflet", file_bytes)
    product = db.query(Product).filter(Product.id == document.product_id).first()
    return DocumentOut(
        id=document.id, product_id=document.product_id, product_slug=product.slug,
        filename=document.filename, uploaded_at=document.uploaded_at,
        chunk_count=document.chunk_count, active=document.active,
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: DBSession = Depends(get_db)) -> list[DocumentOut]:
    docs = db.query(Document).all()
    out = []
    for d in docs:
        product = db.query(Product).filter(Product.id == d.product_id).first()
        out.append(DocumentOut(
            id=d.id, product_id=d.product_id, product_slug=product.slug if product else "",
            filename=d.filename, uploaded_at=d.uploaded_at, chunk_count=d.chunk_count, active=d.active,
        ))
    return out


@router.delete("/documents/{document_id}")
def remove_document(document_id: str, db: DBSession = Depends(get_db)) -> dict:
    try:
        delete_document(db, document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="document not found")
    return {"deleted": document_id}


@router.post("/test-retrieval", response_model=TestRetrievalResponse)
def test_retrieval(req: TestRetrievalRequest, db: DBSession = Depends(get_db)) -> TestRetrievalResponse:
    product = db.query(Product).filter(Product.slug == req.product_slug).first()
    if product is None:
        raise HTTPException(status_code=404, detail=f"unknown product_slug '{req.product_slug}'")

    start = time.perf_counter()
    chunks = retrieve(db, req.query, product_id=product.id, top_k=req.top_k)
    latency_ms = (time.perf_counter() - start) * 1000

    return TestRetrievalResponse(
        retrieved_chunks=[RetrievedChunk(chunk_id=c["chunk_id"], text=c["text"], section_label=c["section_label"], score=c["score"]) for c in chunks],
        latency_ms=latency_ms,
    )


@router.get("/sessions", response_model=list[SessionSummaryOut])
def list_sessions(db: DBSession = Depends(get_db), limit: int = 50) -> list[SessionSummaryOut]:
    sessions = db.query(SessionRecord).order_by(SessionRecord.start_time.desc()).limit(limit).all()
    out = []
    for s in sessions:
        product = db.query(Product).filter(Product.id == s.product_id).first()
        out.append(SessionSummaryOut(
            session_id=s.session_id, participant_id=s.participant_id, platform=s.platform,
            condition=s.condition, product_slug=product.slug if product else "",
            start_time=s.start_time, end_time=s.end_time, total_turns=s.total_turns,
            errors_logged=s.errors_logged,
        ))
    return out
