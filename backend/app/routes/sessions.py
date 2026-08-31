import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.auth import require_admin
from app.db.models import Document, Product, SessionRecord, Turn
from app.db.session import get_db
from app.schemas import ProductOut, SessionEndRequest, SessionEndResponse, SessionStartRequest, SessionStartResponse

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/products", response_model=list[ProductOut])
def list_available_products(db: DBSession = Depends(get_db)) -> list[ProductOut]:
    """Public (no-auth) product list for the participant app's medicine picker - only products
    with an active ingested document, so a product an admin has created but not yet uploaded a
    leaflet for never shows up as a selectable option mid-study."""
    products = (
        db.query(Product)
        .join(Document, Document.product_id == Product.id)
        .filter(Document.active == True)  # noqa: E712
        .distinct()
        .all()
    )
    return [ProductOut(id=p.id, slug=p.slug, display_name=p.display_name) for p in products]


@router.post("/session/start", response_model=SessionStartResponse)
def start_session(req: SessionStartRequest, db: DBSession = Depends(get_db)) -> SessionStartResponse:
    product = db.query(Product).filter(Product.slug == req.product_slug).first()
    if product is None:
        raise HTTPException(status_code=404, detail=f"unknown product_slug '{req.product_slug}'")

    # Study condition follows directly from platform: Pepper is the embodied condition, every
    # other platform value is the tablet/non-embodied condition. This was previously hardcoded to
    # "tablet_ai" for every session including Pepper's, which would have silently mislabeled every
    # robot-condition session as the tablet condition in any analysis grouped by `condition`.
    condition = "pepper" if req.platform == "pepper" else "tablet_ai"

    participant_id = req.participant_id or f"P-{uuid.uuid4().hex[:8]}"
    session = SessionRecord(
        participant_id=participant_id,
        platform=req.platform,
        condition=condition,
        product_id=product.id,
        device_info=req.device_info.model_dump(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionStartResponse(
        session_id=session.session_id,
        participant_id=session.participant_id,
        platform=session.platform,
        condition=session.condition,
        product_slug=product.slug,
        product_display_name=product.display_name,
        start_time=session.start_time,
    )


@router.post("/session/{session_id}/end", response_model=SessionEndResponse)
def end_session(session_id: str, req: SessionEndRequest, db: DBSession = Depends(get_db)) -> SessionEndResponse:
    session = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.end_time is not None:
        raise HTTPException(status_code=409, detail="session already ended")

    session.end_time = datetime.now(timezone.utc)
    session.errors_logged = req.errors_logged
    db.commit()

    return SessionEndResponse(session_id=session.session_id, end_time=session.end_time, total_turns=session.total_turns)


@router.get("/sessions/{session_id}/export", dependencies=[Depends(require_admin)])
def export_session(session_id: str, db: DBSession = Depends(get_db)) -> StreamingResponse:
    session = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    turns = db.query(Turn).filter(Turn.session_id == session_id).order_by(Turn.turn_number).all()

    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["-- session --"])
    writer.writerow(["session_id", "participant_id", "platform", "condition", "start_time", "end_time", "total_turns", "errors_logged"])
    writer.writerow([
        session.session_id, session.participant_id, session.platform, session.condition,
        session.start_time.isoformat(), session.end_time.isoformat() if session.end_time else "",
        session.total_turns, session.errors_logged,
    ])
    writer.writerow([])

    writer.writerow(["-- turns --"])
    writer.writerow([
        "session_id", "participant_id", "platform", "turn_number", "input_method", "query_text",
        "retrieved_chunk_ids", "response_text", "in_scope", "latency_ms", "timestamp",
    ])
    for t in turns:
        writer.writerow([
            session.session_id, session.participant_id, session.platform, t.turn_number, t.input_method,
            t.query_text, "|".join(t.retrieved_chunk_ids), t.response_text, t.in_scope, t.latency_ms,
            t.timestamp.isoformat(),
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"},
    )
