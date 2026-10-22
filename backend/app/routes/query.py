import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.db.models import Product, SessionRecord, Turn
from app.db.session import SessionLocal, get_db
from app.rag.generate import generate_answer, generate_answer_stream, generate_core_info, is_fallback
from app.rag.retrieve import retrieve
from app.rag.config_store import get_active_config
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



def _chunk_snapshot(chunks: list[dict]) -> list[dict]:
    """What gets stored on the Turn row: the exact retrieved text (not just ids), best first."""
    return [
        {
            "rank": i,
            "chunk_id": c["chunk_id"],
            "section_label": c["section_label"],
            "score": float(c["score"]),
            "text": c["text"],
            "document_id": c.get("document_id"),
            "document_filename": c.get("document_filename"),
        }
        for i, c in enumerate(chunks, start=1)
    ]


def _recent_history(db: DBSession, session_id: str, turns_to_include: int) -> list[dict]:
    """Last few turns (oldest first) so the model can resolve conversational follow-ups like
    "what do you mean by that" - without this, every turn was answered with zero memory of what
    was just said, so any reference back to a prior answer looked like an unanswerable non-sequitur
    and fell through to the fixed deflection."""
    turns = (
        db.query(Turn)
        .filter(Turn.session_id == session_id)
        .order_by(Turn.turn_number.desc())
        .limit(turns_to_include)
        .all()
    )
    return [{"query": t.query_text, "answer": t.response_text} for t in reversed(turns)] if turns_to_include > 0 else []


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, db: DBSession = Depends(get_db)) -> QueryResponse:
    session = _get_session_or_404(db, req.session_id)

    product = db.query(Product).filter(Product.id == session.product_id).first()
    product_display_name = product.display_name if product else "this medicine"

    cfg = get_active_config(db)  # one snapshot for the whole request
    start = time.perf_counter()
    history = _recent_history(db, session.session_id, cfg["history_turns"])
    chunks = retrieve(db, req.query_text, product_id=session.product_id, cfg=cfg)
    answer_text = generate_answer(req.query_text, chunks, product_display_name, history, cfg, req.response_language)
    # The logged in_scope flag reflects whether the fixed deflection text was actually shown.
    in_scope = not is_fallback(answer_text, cfg["fallback_text"], req.response_language)
    latency_ms = (time.perf_counter() - start) * 1000

    turn_number = _next_turn_number(db, session.session_id)
    db.add(Turn(
        session_id=session.session_id,
        turn_number=turn_number,
        input_method=req.input_method,
        query_text=req.query_text,
        retrieved_chunk_ids=[c["chunk_id"] for c in chunks],
        retrieved_chunks=_chunk_snapshot(chunks),
        config_version=cfg.version,
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
    cfg = get_active_config(db)  # one snapshot for the whole request, including the streamed generation
    history = _recent_history(db, session.session_id, cfg["history_turns"])
    chunks = retrieve(db, req.query_text, product_id=session.product_id, cfg=cfg)
    session_id = session.session_id
    query_text = req.query_text
    input_method = req.input_method
    language = req.response_language
    chunk_ids = [c["chunk_id"] for c in chunks]
    chunk_snapshot = _chunk_snapshot(chunks)

    def event_stream():
        start = time.perf_counter()
        parts: list[str] = []
        for delta in generate_answer_stream(query_text, chunks, product_display_name, history, cfg, language):
            parts.append(delta)
            yield json.dumps({"delta": delta}) + "\n"

        answer_text = "".join(parts).strip() or cfg["fallback_text"]
        in_scope = not is_fallback(answer_text, cfg["fallback_text"], language)
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
                retrieved_chunks=chunk_snapshot,
                config_version=cfg.version,
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
            # Leaflet sections the answer was grounded in, best first (extra field - existing
            # clients ignore it; the VR client shows it as the answer's source).
            "sources": list(dict.fromkeys(c["section_label"] for c in chunk_snapshot if c["section_label"]))
            if in_scope else [],
        }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/core-info", response_model=CoreInfoResponse)
def core_info(session_id: str, language: str | None = None, db: DBSession = Depends(get_db)) -> CoreInfoResponse:
    """Auto-triggered structured info delivery for screen 3. Logged as a turn with
    input_method='system' since it isn't participant-initiated."""
    session = _get_session_or_404(db, session_id)
    product = db.query(Product).filter(Product.id == session.product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    start = time.perf_counter()
    query_text = f"What is {product.display_name} used for, the dose, frequency, max dose, and warnings?"
    cfg = get_active_config(db)
    chunks = retrieve(db, query_text, product_id=session.product_id, top_k=cfg["core_info_top_k"], cfg=cfg)
    data = generate_core_info(product.display_name, chunks, cfg, language)
    latency_ms = (time.perf_counter() - start) * 1000
    data["latency_ms"] = latency_ms

    turn_number = _next_turn_number(db, session.session_id)
    db.add(Turn(
        session_id=session.session_id,
        turn_number=turn_number,
        input_method="system",
        query_text=query_text,
        retrieved_chunk_ids=[c["chunk_id"] for c in chunks],
        retrieved_chunks=_chunk_snapshot(chunks),
        config_version=cfg.version,
        response_text=data.get("full_text", ""),
        in_scope=True,
        latency_ms=latency_ms,
    ))
    session.total_turns = turn_number
    db.commit()

    return CoreInfoResponse(**data)
