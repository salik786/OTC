import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.db.models import Product, SessionRecord, Turn
from app.db.session import SessionLocal, get_db
from app.rag.generate import generate_answer, generate_answer_stream, generate_core_info
from app.rag.retrieve import retrieve
from app.rag.scope_guard import FALLBACK_TEXT
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


_HISTORY_TURNS = 4


def _recent_history(db: DBSession, session_id: str) -> list[dict]:
    """Last few turns (oldest first) so the model can resolve conversational follow-ups like
    "what do you mean by that" - without this, every turn was answered with zero memory of what
    was just said, so any reference back to a prior answer looked like an unanswerable non-sequitur
    and fell through to the fixed deflection."""
    turns = (
        db.query(Turn)
        .filter(Turn.session_id == session_id)
        .order_by(Turn.turn_number.desc())
        .limit(_HISTORY_TURNS)
        .all()
    )
    return [{"query": t.query_text, "answer": t.response_text} for t in reversed(turns)]


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, db: DBSession = Depends(get_db)) -> QueryResponse:
    session = _get_session_or_404(db, req.session_id)

    product = db.query(Product).filter(Product.id == session.product_id).first()
    product_display_name = product.display_name if product else "this medicine"

    start = time.perf_counter()
    history = _recent_history(db, session.session_id)
    chunks = retrieve(db, req.query_text, product_id=session.product_id)
    answer_text = generate_answer(req.query_text, chunks, product_display_name, history)
    # The logged in_scope flag reflects whether the fixed deflection text was actually shown.
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


@router.post("/query/stream")
def query_stream(req: QueryRequest, db: DBSession = Depends(get_db)) -> StreamingResponse:
    """Same answer as POST /query, but sent as newline-delimited JSON text deltas as the model
    generates them, instead of one JSON body returned only once generation is fully complete.
    Lets the client start speaking the first sentence while the model is still writing the rest.
    Each line is a JSON object: {"delta": "..."} while generating, then one final
    {"done": true, "turn_number", "in_scope", "latency_ms", "answer_text"} line.

    Does the DB write for this turn with its OWN SessionLocal() rather than the injected `db`,
    rather than depend on exactly when FastAPI tears down a yield-dependency relative to a
    StreamingResponse finishing - retrieval/history/product lookups below still use the injected
    session since those all happen before streaming starts."""
    session = _get_session_or_404(db, req.session_id)
    product = db.query(Product).filter(Product.id == session.product_id).first()
    product_display_name = product.display_name if product else "this medicine"
    history = _recent_history(db, session.session_id)
    chunks = retrieve(db, req.query_text, product_id=session.product_id)
    session_id = session.session_id
    query_text = req.query_text
    input_method = req.input_method
    chunk_ids = [c["chunk_id"] for c in chunks]

    def event_stream():
        start = time.perf_counter()
        parts: list[str] = []
        for delta in generate_answer_stream(query_text, chunks, product_display_name, history):
            parts.append(delta)
            yield json.dumps({"delta": delta}) + "\n"

        answer_text = "".join(parts).strip() or FALLBACK_TEXT
        in_scope = answer_text != FALLBACK_TEXT
        latency_ms = (time.perf_counter() - start) * 1000

        write_db = SessionLocal()
        try:
            turn_number = _next_turn_number(write_db, session_id)
            write_db.add(Turn(
                session_id=session_id,
                turn_number=turn_number,
                input_method=input_method,
                query_text=query_text,
                retrieved_chunk_ids=chunk_ids,
                response_text=answer_text,
                in_scope=in_scope,
                latency_ms=latency_ms,
            ))
            write_session = write_db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
            if write_session is not None:
                write_session.total_turns = turn_number
            write_db.commit()
        finally:
            write_db.close()

        yield json.dumps({
            "done": True,
            "turn_number": turn_number,
            "in_scope": in_scope,
            "latency_ms": latency_ms,
            "answer_text": answer_text,
        }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


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
