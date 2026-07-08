import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.db.models import Product, SessionRecord, Turn
from app.db.session import get_db
from app.rag.generate import generate_answer, generate_core_info
from app.rag.retrieve import retrieve
from app.rag.scope_guard import FALLBACK_TEXT, is_in_scope
from app.schemas import CoreInfoResponse, QueryRequest, QueryResponse, RetrievedChunk

router = APIRouter(prefix="/api", tags=["query"])


def _get_session_or_404(db: DBSession, session_id: str) -> SessionRecord:
    session = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.end_time is not None:
        raise HTTPException(status_code=409, detail="session already ended")
    return session


def _next_turn_number(db: DBSession, session_id: str) -> int:
    count = db.query(Turn).filter(Turn.session_id == session_id).count()
    return count + 1


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, db: DBSession = Depends(get_db)) -> QueryResponse:
    session = _get_session_or_404(db, req.session_id)

    start = time.perf_counter()
    chunks = retrieve(db, req.query_text, product_id=session.product_id)
    in_scope = is_in_scope(req.query_text, chunks)
    answer_text = generate_answer(req.query_text, chunks) if in_scope else FALLBACK_TEXT
    # Invariant: the logged in_scope flag always matches whether the fixed deflection text
    # was actually shown, regardless of what the earlier classifier gates decided.
    in_scope = answer_text.strip() != FALLBACK_TEXT
    latency_ms = (time.perf_counter() - start) * 1000

    turn_number = _next_turn_number(db, session.session_id)
    db.add(Turn(
        session_id=session.session_id,
        turn_number=turn_number,
        input_method=req.input_method,
        query_text=req.query_text,
        retrieved_chunk_ids=[c["chunk_id"] for c in chunks],
        response_text=answer_text,
        in_scope=in_scope,
        latency_ms=latency_ms,
    ))
    session.total_turns = turn_number
    db.commit()

    return QueryResponse(
        answer_text=answer_text,
        in_scope=in_scope,
        retrieved_chunks=[RetrievedChunk(chunk_id=c["chunk_id"], text=c["text"], section_label=c["section_label"], score=c["score"]) for c in chunks],
        latency_ms=latency_ms,
        turn_number=turn_number,
    )


@router.post("/core-info", response_model=CoreInfoResponse)
def core_info(session_id: str, db: DBSession = Depends(get_db)) -> CoreInfoResponse:
    """Auto-triggered structured info delivery for screen 3. Logged as a turn with
    input_method='system' since it isn't participant-initiated."""
    session = _get_session_or_404(db, session_id)
    product = db.query(Product).filter(Product.id == session.product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    start = time.perf_counter()
    query_text = f"What is {product.display_name} used for, the dose, frequency, max dose, and warnings?"
    chunks = retrieve(db, query_text, product_id=session.product_id, top_k=8)
    data = generate_core_info(product.display_name, chunks)
    latency_ms = (time.perf_counter() - start) * 1000
    data["latency_ms"] = latency_ms

    turn_number = _next_turn_number(db, session.session_id)
    db.add(Turn(
        session_id=session.session_id,
        turn_number=turn_number,
        input_method="system",
        query_text=query_text,
        retrieved_chunk_ids=[c["chunk_id"] for c in chunks],
        response_text=data.get("full_text", ""),
        in_scope=True,
        latency_ms=latency_ms,
    ))
    session.total_turns = turn_number
    db.commit()

    return CoreInfoResponse(**data)
